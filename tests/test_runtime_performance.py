import json
import threading
import time

from backend.eval_agent.services.run_status_store import RunStatusStore
from backend.evaluation_engine.domain import Scenario, ScenarioSet
from backend.evaluation_engine.engine import _timed_stage, run_full_evaluation
from backend.evaluation_engine.providers import FakeUserProvider


RAW_TASK = """# Role
你是美团外卖骑手的站长。

# Task
通知骑手飞毛腿合同今日生效，并确认骑手是否可以配送。

# Opening Line
你好，请问是王师傅吗？我是站长。

# Call Flow
1. 告知骑手今天飞毛腿合同已生效。
2. 询问骑手是否可以开始配送。

# Constraints
- 每次回复控制在约 30 个字以内。
"""


class TrackingAssistantProvider:
    def __init__(self):
        self.active = 0
        self.max_active = 0
        self.lock = threading.Lock()

    def generate(self, task_spec, history):
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            time.sleep(0.03)
            if not history:
                return task_spec.opening_line
            return "今天合同已生效，可以开始配送。<DONE>"
        finally:
            with self.lock:
                self.active -= 1


class StaticScenarioProvider:
    def generate(self, task_spec, rubric, input_data, minimum):
        return ScenarioSet(
            suite_id="suite_static",
            task_id=task_spec.task_id,
            scenarios=[
                Scenario(
                    scenario_id="scenario_%03d" % index,
                    task_id=task_spec.task_id,
                    user_profile={"role": "骑手"},
                    coverage_targets=["normal"],
                    initial_user_intent="我可以开始配送吗？",
                    expected_test_focus="确认合同生效与配送安排",
                )
                for index in range(1, minimum + 1)
            ],
        )


def test_full_evaluation_runs_scenarios_concurrently_and_keeps_result_order(tmp_path):
    assistant = TrackingAssistantProvider()

    result = run_full_evaluation(
        raw_instruction=RAW_TASK,
        run_root=tmp_path,
        assistant_provider=assistant,
        user_provider=FakeUserProvider(),
        minimum_scenarios=4,
        scenario_provider=StaticScenarioProvider(),
        scenario_concurrency=4,
    )

    assert assistant.max_active > 1
    assert [trace.scenario_id for trace in result.traces] == [
        "scenario_001",
        "scenario_002",
        "scenario_003",
        "scenario_004",
    ]
    assert [item.scenario_id for item in result.results] == [
        "scenario_001",
        "scenario_002",
        "scenario_003",
        "scenario_004",
    ]
    assert result.stage_timings_ms["scenario_execution"] > 0


def test_timed_stage_records_sub_millisecond_work_as_non_zero():
    timings = {}

    result = _timed_stage(
        "instruction_parsing",
        timings,
        progress_callback=None,
        action=lambda: "done",
    )

    assert result == "done"
    assert timings["instruction_parsing"] >= 1


def test_full_evaluation_limits_scenario_batch_size_even_with_higher_concurrency(tmp_path):
    assistant = TrackingAssistantProvider()

    run_full_evaluation(
        raw_instruction=RAW_TASK,
        run_root=tmp_path,
        assistant_provider=assistant,
        user_provider=FakeUserProvider(),
        minimum_scenarios=4,
        scenario_provider=StaticScenarioProvider(),
        scenario_concurrency=4,
        scenario_batch_size=2,
    )

    assert assistant.max_active <= 2


class FakeRedisClient:
    def __init__(self):
        self.values = {}
        self.ttls = {}

    def setex(self, key, ttl, value):
        self.values[key] = value
        self.ttls[key] = ttl

    def get(self, key):
        return self.values.get(key)


def test_run_status_store_persists_json_status_with_ttl():
    redis_client = FakeRedisClient()
    store = RunStatusStore(redis_client=redis_client, key_prefix="test:run", ttl_seconds=90)

    store.set_status(
        "run_123",
        status="running",
        current_stage="场景生成",
        stages=[{"name": "指令解析", "status": "completed"}],
    )

    payload = store.get_status("run_123")
    raw = redis_client.values["test:run:run_123"]
    decoded = json.loads(raw)

    assert payload["run_id"] == "run_123"
    assert payload["status"] == "running"
    assert payload["current_stage"] == "场景生成"
    assert decoded["stages"][0]["name"] == "指令解析"
    assert redis_client.ttls["test:run:run_123"] == 90


def test_run_status_store_falls_back_to_memory_when_redis_unavailable(monkeypatch):
    from backend.eval_agent.services import run_service

    monkeypatch.setattr(run_service, "RUN_STATUS_STORE", None)
    monkeypatch.setattr(
        run_service,
        "redis_client_from_url",
        lambda redis_url: (_ for _ in ()).throw(RuntimeError("redis unavailable")),
    )

    store = run_service.run_status_store()
    store.set_status("run_memory", status="queued", current_stage="queued")

    assert store.get_status("run_memory")["status"] == "queued"
    assert store.get_status("run_memory")["storage"] == "memory"


def test_async_run_endpoint_records_redis_backed_status(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from backend.eval_agent.api.main import create_app
    from backend.eval_agent.services import run_service

    redis_client = FakeRedisClient()
    status_store = RunStatusStore(
        redis_client=redis_client,
        key_prefix="test:run",
        ttl_seconds=90,
    )
    monkeypatch.setattr(run_service, "RUN_ROOT", tmp_path)
    monkeypatch.setattr(run_service, "RUN_STATUS_STORE", status_store)

    app = create_app()
    client = TestClient(app)

    submitted = client.post(
        "/api/runs/async",
        json={
            "instruction": RAW_TASK,
            "minimum_scenarios": 2,
            "model_config": {"provider": "mock", "model_name": "async-test-model"},
        },
    )

    assert submitted.status_code == 202
    run_id = submitted.json()["run_id"]
    status = client.get("/api/runs/%s/status" % run_id)
    for _ in range(20):
        if status.json()["status"] == "completed":
            break
        time.sleep(0.05)
        status = client.get("/api/runs/%s/status" % run_id)
    detail = client.get("/api/runs/%s" % run_id)

    assert status.status_code == 200
    assert status.json()["run_id"] == run_id
    assert status.json()["status"] == "completed"
    assert status.json()["result_url"] == "/api/runs/%s" % run_id
    assert detail.status_code == 200
    assert detail.json()["run_id"] == run_id
    assert detail.json()["trace_count"] == 2
