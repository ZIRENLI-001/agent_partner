from pathlib import Path

from backend.eval_agent.providers.base import ModelResponse


ROOT = Path(__file__).resolve().parents[1]


def test_root_deployment_docs_and_commands_are_present():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    frontend_readme = (ROOT / "frontend" / "README.md").read_text(encoding="utf-8")

    for text in [
        "make install",
        "make build",
        "make test",
        "make dev",
        "make smoke",
        "python3 -m uvicorn backend.eval_agent.api.main:app",
        "npm ci",
    ]:
        assert text in readme

    for key in [
        "APP_ENV=development",
        "HOST=127.0.0.1",
        "PORT=8070",
        "EVAL_ARTIFACT_ROOT=runs",
        "EVAL_FRONTEND_DIST=frontend/dist",
        "DEFAULT_PROVIDER_TYPE=mock",
        "DEFAULT_API_BASE=",
        "DEFAULT_MODEL_NAME=",
        "REQUEST_TIMEOUT_SECONDS=60",
        "REQUEST_RETRY_COUNT=2",
        "REQUEST_RETRY_BACKOFF_SECONDS=0.5",
        "EVAL_SCENARIO_CONCURRENCY=3",
        "EVAL_SCENARIO_BATCH_SIZE=6",
        "EVAL_MODEL_CACHE_TTL_SECONDS=900",
        "EVAL_MODEL_CACHE_MAX_ENTRIES=512",
        "EVAL_REPORT_MAX_EVIDENCE_ITEMS=80",
        "EVAL_RUN_STATUS_TTL_SECONDS=86400",
    ]:
        assert key in env_example

    for target in ["install:", "build:", "test:", "dev:", "smoke:"]:
        assert target in makefile

    assert "React + TypeScript + Vite" in frontend_readme
    assert "legacy fallback" in frontend_readme
    assert "current runnable MVP is still served" not in frontend_readme


def test_settings_resolve_paths_from_project_root_and_environment(monkeypatch, tmp_path):
    from backend.eval_agent.core.config import (
        project_root,
        resolve_project_path,
        settings_from_env,
    )

    artifact_root = tmp_path / "custom-runs"
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("EVAL_ARTIFACT_ROOT", str(artifact_root))
    monkeypatch.setenv("EVAL_FRONTEND_DIST", "frontend/dist")
    monkeypatch.setenv("DEFAULT_PROVIDER_TYPE", "openrouter")
    monkeypatch.setenv("DEFAULT_API_BASE", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("DEFAULT_MODEL_NAME", "openai/gpt-4o-mini")
    monkeypatch.setenv("REQUEST_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("EVAL_SCENARIO_BATCH_SIZE", "4")
    monkeypatch.setenv("EVAL_MODEL_CACHE_TTL_SECONDS", "120")
    monkeypatch.setenv("EVAL_REPORT_MAX_EVIDENCE_ITEMS", "12")

    root = project_root()
    settings = settings_from_env()

    assert root == ROOT
    assert resolve_project_path("frontend/dist") == ROOT / "frontend" / "dist"
    assert settings.environment == "test"
    assert settings.artifact_root == artifact_root
    assert settings.frontend_dist == ROOT / "frontend" / "dist"
    assert settings.default_provider_type == "openrouter"
    assert settings.default_api_base == "https://openrouter.ai/api/v1"
    assert settings.default_model_name == "openai/gpt-4o-mini"
    assert settings.request_timeout_seconds == 45
    assert settings.scenario_batch_size == 4
    assert settings.model_cache_ttl_seconds == 120
    assert settings.report_max_evidence_items == 12


def test_settings_loads_project_dotenv_when_process_env_missing(monkeypatch, tmp_path):
    from backend.eval_agent.core import config as config_module

    monkeypatch.setattr(config_module, "project_root", lambda: tmp_path)
    monkeypatch.delenv("EVAL_CHAIN_PROVIDER", raising=False)
    monkeypatch.delenv("EVAL_CHAIN_API_KEY", raising=False)
    monkeypatch.delenv("REQUEST_TIMEOUT_SECONDS", raising=False)
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "EVAL_CHAIN_PROVIDER=openrouter",
                "EVAL_CHAIN_API_KEY=sk-dotenv-secret",
                "REQUEST_TIMEOUT_SECONDS=33",
            ]
        ),
        encoding="utf-8",
    )

    settings = config_module.settings_from_env()

    assert settings.eval_chain_provider == "openrouter"
    assert settings.eval_chain_api_key == "sk-dotenv-secret"
    assert settings.request_timeout_seconds == 33


def test_process_env_overrides_project_dotenv(monkeypatch, tmp_path):
    from backend.eval_agent.core import config as config_module

    monkeypatch.setattr(config_module, "project_root", lambda: tmp_path)
    monkeypatch.setenv("EVAL_CHAIN_API_KEY", "sk-process-secret")
    (tmp_path / ".env").write_text(
        "EVAL_CHAIN_API_KEY=sk-dotenv-secret\n",
        encoding="utf-8",
    )

    settings = config_module.settings_from_env()

    assert settings.eval_chain_api_key == "sk-process-secret"


def test_run_service_uses_configured_artifact_root(tmp_path, monkeypatch):
    from backend.eval_agent.api.routes.runs import RunRequest
    from backend.eval_agent.services import run_service

    monkeypatch.setenv("EVAL_ARTIFACT_ROOT", str(tmp_path))

    response = run_service.create_run_payload(
        RunRequest(
            instruction="# Role\n你是站长\n# Task\n通知骑手合同生效",
            minimum_scenarios=1,
        )
    )

    assert (tmp_path / response["run_id"] / "run_config.json").exists()


class RecordingModelProvider:
    def __init__(self):
        self.messages = None
        self.config = None

    def generate(self, messages, config):
        self.messages = messages
        self.config = config
        return ModelResponse(content="模型回复<DONE>", raw={"ok": True})


def test_provider_selection_keeps_mock_for_demo_model_config():
    from backend.eval_agent.api.routes.runs import ModelConfig
    from backend.eval_agent.services.run_service import build_assistant_provider
    from backend.evaluation_engine.providers import FakeAssistantProvider

    provider = build_assistant_provider(ModelConfig(provider="mock"))

    assert isinstance(provider, FakeAssistantProvider)


def test_provider_selection_uses_openai_compatible_adapter_for_real_models():
    from backend.eval_agent.api.routes.runs import ModelConfig
    from backend.eval_agent.services.run_service import build_assistant_provider

    model_provider = RecordingModelProvider()
    assistant = build_assistant_provider(
        ModelConfig(
            provider="openrouter",
            model_name="openai/gpt-4o-mini",
            api_base="https://openrouter.ai/api/v1",
            api_key="sk-test",
        ),
        model_provider=model_provider,
    )

    content = assistant.generate(
        task_spec=type(
            "TaskSpecStub",
            (),
            {
                "role": "站长",
                "task": "通知骑手合同生效",
                "opening_line": "你好，请问是王师傅吗？",
                "constraints": ["每次回复控制在约30字"],
                "faq": [{"question": "如何退出", "answer": "提前一天取消"}],
            },
        )(),
        history=[
            type("TurnStub", (), {"speaker": "assistant", "content": "你好"})(),
            type("TurnStub", (), {"speaker": "user_simulator", "content": "我不想配送"})(),
        ],
    )

    assert content == "模型回复<DONE>"
    assert model_provider.config.provider_type == "openrouter"
    assert model_provider.config.model_name == "openai/gpt-4o-mini"
    assert model_provider.config.api_key == "sk-test"
    assert model_provider.messages[0]["role"] == "system"
    assert "站长" in model_provider.messages[0]["content"]
    assert model_provider.messages[-1] == {"role": "user", "content": "我不想配送"}
