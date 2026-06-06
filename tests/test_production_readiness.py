import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.eval_agent.api.main import create_app
from backend.eval_agent.providers.base import ModelConfig, ModelProviderError
from backend.eval_agent.providers.openai_compatible import OpenAICompatibleProvider
from backend.eval_agent.storage.artifact_store import ArtifactStore


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FailingTransport:
    def post_json(self, url, headers, payload, timeout_seconds):
        raise TimeoutError("network timeout with sk-secret-value")


class FlakyTransport:
    def __init__(self):
        self.calls = 0

    def post_json(self, url, headers, payload, timeout_seconds):
        self.calls += 1
        if self.calls == 1:
            raise TimeoutError("temporary timeout")
        return {"choices": [{"message": {"content": "ok after retry"}}]}


class CountingTransport:
    def __init__(self):
        self.calls = 0

    def post_json(self, url, headers, payload, timeout_seconds):
        self.calls += 1
        return {"choices": [{"message": {"content": "cached response"}}]}


def test_model_provider_normalizes_transport_errors_without_leaking_api_key():
    provider = OpenAICompatibleProvider(transport=FailingTransport())
    config = ModelConfig(
        provider_type="openrouter",
        api_base="https://openrouter.ai/api/v1",
        api_key="sk-secret-value",
        model_name="openai/gpt-4o",
    )

    with pytest.raises(ModelProviderError) as exc_info:
        provider.generate([{"role": "user", "content": "hello"}], config)

    message = str(exc_info.value)
    assert "Model provider request failed" in message
    assert "sk-secret-value" not in message
    assert exc_info.value.provider_type == "openrouter"
    assert exc_info.value.model_name == "openai/gpt-4o"


def test_model_provider_retries_transient_transport_errors():
    transport = FlakyTransport()
    provider = OpenAICompatibleProvider(transport=transport)
    config = ModelConfig(
        provider_type="openrouter",
        api_base="https://openrouter.ai/api/v1",
        api_key="sk-secret-value",
        model_name="openai/gpt-4o",
        retry_count=1,
        retry_backoff_seconds=0,
    )

    response = provider.generate([{"role": "user", "content": "hello"}], config)

    assert response.content == "ok after retry"
    assert transport.calls == 2


def test_model_provider_caches_identical_chain_model_requests():
    transport = CountingTransport()
    provider = OpenAICompatibleProvider(transport=transport)
    provider.clear_cache()
    config = ModelConfig(
        provider_type="openrouter",
        api_base="https://openrouter.ai/api/v1",
        api_key="sk-secret-value",
        model_name="openai/gpt-4o",
        cache_enabled=True,
        cache_ttl_seconds=60,
    )
    messages = [{"role": "user", "content": "same prompt"}]

    first = provider.generate(messages, config)
    second = provider.generate(messages, config)

    assert first.content == "cached response"
    assert second.content == "cached response"
    assert transport.calls == 1


def test_model_provider_rejects_missing_required_configuration():
    provider = OpenAICompatibleProvider()

    with pytest.raises(ValueError, match="api_base is required"):
        provider.generate([], ModelConfig(model_name="openai/gpt-4o"))

    with pytest.raises(ValueError, match="model_name is required"):
        provider.generate([], ModelConfig(api_base="https://openrouter.ai/api/v1"))


def test_artifact_store_rejects_unsafe_run_ids_and_filenames(tmp_path):
    store = ArtifactStore(tmp_path)

    for bad_run_id in ["", ".", "..", "../run_1", "run/1", "run\\1"]:
        with pytest.raises(ValueError, match="Invalid artifact path"):
            store.write_text(bad_run_id, "report.md", "bad")

    for bad_filename in ["", ".", "..", "../report.md", "nested/report.md", "nested\\report.md"]:
        with pytest.raises(ValueError, match="Invalid artifact path"):
            store.write_text("run_safe", bad_filename, "bad")


def test_run_config_persists_model_secret_only_as_configured_flag(tmp_path, monkeypatch):
    from backend.eval_agent.services import run_service

    monkeypatch.setattr(run_service, "RUN_ROOT", tmp_path)
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/api/runs",
        json={
            "instruction": "# Role\n你是站长\n# Task\n通知骑手合同生效",
            "model_config": {
                "provider": "openrouter",
                "model_name": "openai/gpt-4o",
                "api_base": "https://openrouter.ai/api/v1",
                "api_key": "sk-production-secret",
            },
        },
    )

    assert response.status_code == 200
    run_id = response.json()["run_id"]
    config_text = (tmp_path / run_id / "run_config.json").read_text(encoding="utf-8")
    config = json.loads(config_text)

    assert "sk-production-secret" not in config_text
    assert config["model_config_summary"]["api_key_configured"] is True
    assert config["model_config_summary"]["model_name"] == "openai/gpt-4o"


def test_production_api_keeps_unknown_api_paths_out_of_spa_fallback():
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/not-found")

    assert response.status_code == 404


def test_api_access_token_protects_business_routes(monkeypatch):
    monkeypatch.setenv("APP_ACCESS_TOKEN", "shared-test-token")
    app = create_app()
    client = TestClient(app)

    unauthorized = client.get("/api/context")
    authorized = client.get(
        "/api/context",
        headers={"Authorization": "Bearer shared-test-token"},
    )
    health = client.get("/api/health")

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
    assert health.status_code == 200


def test_production_requires_access_token(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("APP_ACCESS_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="APP_ACCESS_TOKEN"):
        create_app()


def test_model_provider_rejects_api_base_outside_allowlist(monkeypatch):
    monkeypatch.setenv(
        "ALLOWED_MODEL_API_BASES",
        "https://openrouter.ai/api/v1",
    )
    provider = OpenAICompatibleProvider(transport=CountingTransport())
    config = ModelConfig(
        provider_type="openai_compatible",
        api_base="http://127.0.0.1:8080/v1",
        model_name="internal-model",
    )

    with pytest.raises(ValueError, match="ALLOWED_MODEL_API_BASES"):
        provider.generate([{"role": "user", "content": "hello"}], config)


def test_production_health_does_not_expose_server_paths(monkeypatch, tmp_path):
    frontend_dist = tmp_path / "frontend"
    frontend_dist.mkdir()
    (frontend_dist / "index.html").write_text("<html></html>", encoding="utf-8")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_ACCESS_TOKEN", "shared-test-token")
    monkeypatch.setenv("EVAL_FRONTEND_DIST", str(frontend_dist))
    monkeypatch.setenv("TRUSTED_HOSTS", "testserver,localhost")
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert "paths" not in response.json()


def test_production_disables_api_documentation(monkeypatch, tmp_path):
    frontend_dist = tmp_path / "frontend"
    frontend_dist.mkdir()
    (frontend_dist / "index.html").write_text("<html></html>", encoding="utf-8")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_ACCESS_TOKEN", "shared-test-token")
    monkeypatch.setenv("EVAL_FRONTEND_DIST", str(frontend_dist))
    monkeypatch.setenv("TRUSTED_HOSTS", "testserver,localhost")
    app = create_app()
    client = TestClient(app)

    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_gitignore_excludes_private_key_files():
    gitignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "*.pem" in gitignore.splitlines()
