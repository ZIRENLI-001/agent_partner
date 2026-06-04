import time
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from backend.eval_agent.api.main import create_app
from backend.eval_agent.services.run_status_store import MemoryRunStatusStore


RAW_TASK = """# Role
你是美团外卖骑手的站长。

# Task
通知骑手飞毛腿合同今日生效，并确认骑手是否可以配送。

# Opening Line
你好，请问是王师傅吗？我是站长。

# Call Flow
1. 告知骑手今天飞毛腿合同已生效。
2. 询问骑手是否可以开始配送。
"""


def _test_client(tmp_path, monkeypatch):
    from backend.eval_agent.services import run_service

    monkeypatch.setattr(run_service, "RUN_ROOT", tmp_path)
    monkeypatch.setattr(run_service, "RUN_STATUS_STORE", MemoryRunStatusStore())
    return TestClient(create_app())


def _wait_for_completed(client, run_id, attempts=40):
    status = client.get("/api/runs/%s/status" % run_id)
    for _ in range(attempts):
        if status.json()["status"] == "completed":
            return status
        time.sleep(0.05)
        status = client.get("/api/runs/%s/status" % run_id)
    return status


def test_smoke_chain_covers_context_import_stages_async_run_and_detail(tmp_path, monkeypatch):
    client = _test_client(tmp_path, monkeypatch)

    health = client.get("/api/health")
    context = client.get("/api/context")
    samples = client.get("/api/import/mock-evaluation-rows")
    parse = client.post("/api/stages/parse", json={"instruction": RAW_TASK})
    rubric = client.post("/api/stages/rubric", json={"instruction": RAW_TASK})
    simulation = client.post(
        "/api/stages/scenarios",
        json={"instruction": RAW_TASK, "minimum_scenarios": 2},
    )
    submitted = client.post(
        "/api/runs/async",
        json={
            "instruction": RAW_TASK,
            "minimum_scenarios": 2,
            "model_config": {"provider": "mock", "model_name": "smoke-model"},
        },
    )

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["checks"]["evaluation_engine"] == "ok"
    assert health.json()["checks"]["calibration_dataset"] == "ok"
    assert health.json()["checks"]["artifact_root"] == "ok"
    assert context.status_code == 200
    assert samples.status_code == 200
    assert parse.status_code == 200
    assert rubric.status_code == 200
    assert simulation.status_code == 200
    assert submitted.status_code == 202
    assert parse.json()["stage"] == "parse"
    assert rubric.json()["stage"] == "rubric"
    assert len(simulation.json()["scenario_set"]["scenarios"]) == 2

    run_id = submitted.json()["run_id"]
    status = _wait_for_completed(client, run_id)
    detail = client.get("/api/runs/%s" % run_id)

    assert status.status_code == 200
    assert status.json()["status"] == "completed"
    assert detail.status_code == 200
    assert detail.json()["trace_count"] == 2


def test_high_concurrency_async_submissions_keep_unique_run_ids_and_complete(tmp_path, monkeypatch):
    client = _test_client(tmp_path, monkeypatch)

    def submit(index):
        response = client.post(
            "/api/runs/async",
            json={
                "instruction": RAW_TASK,
                "minimum_scenarios": 1,
                "model_config": {"provider": "mock", "model_name": "concurrency-%s" % index},
            },
        )
        assert response.status_code == 202
        return response.json()["run_id"]

    with ThreadPoolExecutor(max_workers=8) as executor:
        run_ids = list(executor.map(submit, range(12)))

    assert len(run_ids) == 12
    assert len(set(run_ids)) == 12
    for run_id in run_ids:
        status = _wait_for_completed(client, run_id)
        assert status.json()["status"] == "completed"
        assert client.get("/api/runs/%s" % run_id).json()["run_id"] == run_id


def test_backend_stage_status_labels_use_dialogue_simulation_language():
    from backend.eval_agent.services import run_service

    completed = run_service._all_completed_stages()
    labels_by_key = {item["key"]: item["name"] for item in completed}

    assert labels_by_key["scenario_generation"] == "对话模拟"
    assert "场景生成" not in [item["name"] for item in completed]


def test_frontend_run_stage_submits_stage_payload_and_buttons_show_loading_feedback():
    page = open("frontend/src/pages/EvaluationWizardPage.tsx", encoding="utf-8").read()

    assert "const primaryActionFeedbackLabel" in page
    assert "disabled={loading}" in page
    assert "正在生成当前步骤" in page
    assert "正在执行评测" in page
    assert "input_data: stagePayload.input_data" in page


def test_make_smoke_covers_health_and_core_api_surfaces():
    makefile = open("Makefile", encoding="utf-8").read()

    assert "/api/health" in makefile
    assert "/api/context" in makefile
    assert "/api/calibration/summary" in makefile
    assert "/api/import/mock-evaluation-rows" in makefile
    assert "curl -fsS" in makefile
