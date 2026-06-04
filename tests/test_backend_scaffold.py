from backend.eval_agent.core.config import Settings
import pytest

from backend.eval_agent.providers.base import ModelConfig
from backend.eval_agent.api.main import create_app
from backend.eval_agent.providers.openai_compatible import OpenAICompatibleProvider
from backend.eval_agent.storage.artifact_store import ArtifactStore
from fastapi.testclient import TestClient


def test_settings_default_paths_support_development_deploy():
    settings = Settings()

    assert settings.app_name == "Dialogue Eval Platform"
    assert settings.database_url == "sqlite:///./artifacts/app.db"
    assert settings.artifact_root == "artifacts/runs"
    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.default_provider_type == "mock"


def test_settings_accepts_openrouter_model_defaults():
    settings = Settings(
        default_provider_type="openrouter",
        default_api_base="https://openrouter.ai/api/v1",
        default_model_name="openai/gpt-4o",
    )

    assert settings.default_provider_type == "openrouter"
    assert settings.default_api_base == "https://openrouter.ai/api/v1"
    assert settings.default_model_name == "openai/gpt-4o"


def test_artifact_store_writes_run_artifact(tmp_path):
    store = ArtifactStore(tmp_path)

    path = store.write_text("run_abc123", "report.md", "# Report")

    assert path == tmp_path / "run_abc123" / "report.md"
    assert path.read_text(encoding="utf-8") == "# Report"


def test_artifact_store_rejects_path_traversal(tmp_path):
    store = ArtifactStore(tmp_path)

    with pytest.raises(ValueError, match="Invalid artifact path"):
        store.write_text("run_abc123", "../report.md", "bad")


class RecordingTransport:
    def __init__(self):
        self.url = ""
        self.headers = {}
        self.payload = {}

    def post_json(self, url, headers, payload, timeout_seconds):
        self.url = url
        self.headers = headers
        self.payload = payload
        return {
            "choices": [
                {"message": {"content": "模型回复"}}
            ],
            "usage": {"prompt_tokens": 4, "completion_tokens": 2},
        }


def test_openai_compatible_provider_builds_chat_completion_request():
    transport = RecordingTransport()
    provider = OpenAICompatibleProvider(transport=transport)
    config = ModelConfig(
        provider_type="openrouter",
        api_base="https://openrouter.ai/api/v1",
        api_key="sk-or-secret",
        model_name="openai/gpt-4o",
        temperature=0.2,
        max_tokens=128,
    )

    response = provider.generate(
        messages=[{"role": "user", "content": "你好"}],
        config=config,
    )

    assert transport.url == "https://openrouter.ai/api/v1/chat/completions"
    assert transport.headers["Authorization"] == "Bearer sk-or-secret"
    assert transport.payload["model"] == "openai/gpt-4o"
    assert transport.payload["messages"] == [{"role": "user", "content": "你好"}]
    assert transport.payload["temperature"] == 0.2
    assert transport.payload["max_tokens"] == 128
    assert response.content == "模型回复"
    assert response.raw["usage"]["completion_tokens"] == 2


def test_openai_compatible_provider_can_request_json_response_format():
    transport = RecordingTransport()
    provider = OpenAICompatibleProvider(transport=transport)
    config = ModelConfig(
        provider_type="openrouter",
        api_base="https://openrouter.ai/api/v1",
        api_key="sk-or-secret",
        model_name="anthropic/claude-sonnet-4.6",
        response_format={"type": "json_object"},
    )

    provider.generate(
        messages=[{"role": "user", "content": "只输出JSON"}],
        config=config,
    )

    assert transport.payload["response_format"] == {"type": "json_object"}


def test_model_config_summary_does_not_expose_api_key():
    config = ModelConfig(
        provider_type="openrouter",
        api_base="https://openrouter.ai/api/v1",
        api_key="sk-or-secret",
        model_name="openai/gpt-4o",
    )

    assert config.safe_summary() == {
        "provider_type": "openrouter",
        "api_base": "https://openrouter.ai/api/v1",
        "model_name": "openai/gpt-4o",
        "api_key_configured": True,
        "api_key_last4": "cret",
    }


def test_production_app_context_route_matches_mvp_context():
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/context")

    assert response.status_code == 200
    assert response.json()["workspace"]["name"] == "美团履约评测空间"


def test_production_app_exposes_calibration_dataset_routes():
    app = create_app()
    client = TestClient(app)

    summary = client.get("/api/calibration/summary")
    samples = client.get("/api/calibration/samples")

    assert summary.status_code == 200
    assert samples.status_code == 200
    assert summary.json()["sample_count"] >= 10
    assert summary.json()["label_counts"]["fail"] > 0
    assert samples.json()["summary"]["sample_count"] == summary.json()["sample_count"]


def test_calibration_self_check_endpoint_exposes_expected_label_metrics():
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/calibration/self-check")

    assert response.status_code == 200
    payload = response.json()
    assert "sample_count" in payload
    assert "label_count" in payload
    assert "verdict_accuracy" in payload
    assert "evidence_turn_hit_rate" in payload
    assert "critical_false_pass_count" in payload
    assert "critical_false_fail_count" in payload


def test_production_app_stage_routes_generate_parse_rubric_and_scenarios():
    app = create_app()
    client = TestClient(app)
    payload = {
        "instruction": "# Role\n你是站长\n# Task\n通知骑手合同生效",
        "input_data": "{\"city\":\"北京\"}",
        "minimum_scenarios": 5,
    }

    parse_response = client.post("/api/stages/parse", json=payload)
    rubric_response = client.post("/api/stages/rubric", json=payload)
    scenarios_response = client.post("/api/stages/scenarios", json=payload)

    assert parse_response.status_code == 200
    assert parse_response.json()["stage"] == "parse"
    assert parse_response.json()["input_data_summary"]["format"] == "json"
    assert parse_response.json()["evaluation_strategy"]["stages"]
    assert rubric_response.status_code == 200
    assert rubric_response.json()["stage"] == "rubric"
    assert rubric_response.json()["evaluation_strategy"]["stages"]
    assert scenarios_response.status_code == 200
    assert scenarios_response.json()["stage"] == "scenarios"
    assert len(scenarios_response.json()["scenario_set"]["scenarios"]) >= 5
    strategy_stages = {
        stage["stage"]: stage
        for stage in scenarios_response.json()["evaluation_strategy"]["stages"]
    }
    assert "scenario_generation" in strategy_stages
    assert strategy_stages["semantic_judge"]["temperature"] == 0


def test_production_app_run_routes_create_history_and_detail(tmp_path, monkeypatch):
    from backend.eval_agent.services import run_service

    monkeypatch.setattr(run_service, "RUN_ROOT", tmp_path)
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/runs",
        json={
            "instruction": "# Role\n你是站长\n# Task\n通知骑手合同生效",
            "model_config": {"model_name": "openrouter-demo"},
        },
    )

    assert created.status_code == 200
    run_id = created.json()["run_id"]
    assert created.json()["trace_count"] >= 1

    history = client.get("/api/runs/history")
    detail = client.get(f"/api/runs/{run_id}")

    assert history.status_code == 200
    assert history.json()["runs"][0]["run_id"] == run_id
    assert detail.status_code == 200
    assert detail.json()["run_id"] == run_id
    assert detail.json()["model_config_summary"]["model_name"] == "openrouter-demo"
