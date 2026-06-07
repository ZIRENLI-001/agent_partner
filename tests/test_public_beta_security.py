import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient
from pydantic import ValidationError
from types import SimpleNamespace

from backend.eval_agent.api.main import create_app
from backend.eval_agent.api.routes.runs import RunRequest
from backend.eval_agent.core.config import settings_from_env
from backend.eval_agent.core.security import trusted_client_ip
from backend.eval_agent.providers.base import ModelConfig, ModelProviderError
from backend.eval_agent.providers.openai_compatible import (
    OpenAICompatibleProvider,
    UrllibJsonTransport,
    _NoRedirectHandler,
)
from backend.eval_agent.services.job_queue import JobQueueFull, JobQuotaExceeded
from backend.eval_agent.services import health_service, run_service
from backend.evaluation_engine import app as engine_app


def configure_production(monkeypatch, frontend_dist):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_ACCESS_TOKEN", "shared-test-token")
    monkeypatch.setenv("EVAL_FRONTEND_DIST", str(frontend_dist))
    monkeypatch.setenv("TRUSTED_HOSTS", "testserver,163.7.11.194,localhost")


def authorized_client(app):
    return TestClient(
        app,
        headers={"Authorization": "Bearer shared-test-token"},
    )


def test_public_beta_settings_are_loaded(monkeypatch):
    monkeypatch.setenv("MAX_JSON_BODY_BYTES", "2097152")
    monkeypatch.setenv("RUNS_PER_IP_PER_HOUR", "10")
    monkeypatch.setenv("MAX_QUEUED_RUNS", "10")
    monkeypatch.setenv("RUN_JOB_TIMEOUT_SECONDS", "900")
    monkeypatch.setenv("TRUSTED_HOSTS", "163.7.11.194,localhost")

    settings = settings_from_env()

    assert settings.max_json_body_bytes == 2 * 1024 * 1024
    assert settings.runs_per_ip_per_hour == 10
    assert settings.max_queued_runs == 10
    assert settings.run_job_timeout_seconds == 900
    assert settings.trusted_hosts == ("163.7.11.194", "localhost")


@pytest.mark.parametrize(
    "payload",
    [
        {"instruction": "x" * 100_001},
        {"instruction": "ok", "input_data": "x" * 1_000_001},
        {
            "instruction": "ok",
            "selected_scenario_ids": [
                "scenario_%d" % index for index in range(21)
            ],
        },
        {
            "instruction": "ok",
            "model_config": {"model_name": "x" * 257},
        },
        {
            "instruction": "ok",
            "model_config": {"api_base": "x" * 2049},
        },
    ],
)
def test_run_request_rejects_oversized_fields(payload):
    with pytest.raises(ValidationError):
        RunRequest(**payload)


def test_run_detail_rejects_windows_and_posix_path_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(run_service, "RUN_ROOT", tmp_path)
    monkeypatch.setattr(
        run_service,
        "RUN_STATUS_STORE",
        run_service.MemoryRunStatusStore(),
    )
    request = SimpleNamespace(
        instruction="# Role\nAssistant\n# Task\nSay hello",
        input_data="",
        minimum_scenarios=1,
        selected_scenario_ids=[],
        workspace_id="workspace",
        project_id="project",
        created_by="tester",
        eval_model_config=run_service.RuntimeModelConfig(provider="mock"),
    )
    created = run_service.create_run_payload(request)
    nested = tmp_path / "nested"
    nested.mkdir()

    for run_id in (
        "../%s" % created["run_id"],
        "..\\%s" % created["run_id"],
        "%s/extra" % created["run_id"],
    ):
        with pytest.raises(HTTPException) as exc:
            engine_app._run_detail_payload(nested, run_id)
        assert exc.value.status_code == 404


def test_production_rejects_large_json_before_route(monkeypatch, tmp_path):
    frontend_dist = tmp_path / "frontend"
    frontend_dist.mkdir()
    (frontend_dist / "index.html").write_text("<html></html>", encoding="utf-8")
    configure_production(monkeypatch, frontend_dist)
    client = authorized_client(create_app())

    response = client.post(
        "/api/stages/parse",
        content=b"x" * (2 * 1024 * 1024 + 1),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413


def test_production_disables_sync_run(monkeypatch, tmp_path):
    frontend_dist = tmp_path / "frontend"
    frontend_dist.mkdir()
    (frontend_dist / "index.html").write_text("<html></html>", encoding="utf-8")
    configure_production(monkeypatch, frontend_dist)

    response = authorized_client(create_app()).post(
        "/api/runs",
        json={"instruction": "test"},
    )

    assert response.status_code in {404, 405}


def test_production_requires_frontend_build(monkeypatch, tmp_path):
    configure_production(monkeypatch, tmp_path / "missing")

    with pytest.raises(RuntimeError, match="frontend"):
        create_app()


def test_legacy_app_uses_production_security(monkeypatch):
    monkeypatch.setenv("APP_ACCESS_TOKEN", "shared-test-token")

    response = TestClient(engine_app.app).get("/api/context")

    assert response.status_code == 401


def test_production_rejects_unknown_host(monkeypatch, tmp_path):
    frontend_dist = tmp_path / "frontend"
    frontend_dist.mkdir()
    (frontend_dist / "index.html").write_text("<html></html>", encoding="utf-8")
    configure_production(monkeypatch, frontend_dist)
    client = TestClient(create_app(), base_url="http://evil.example")

    response = client.get("/api/health")

    assert response.status_code == 400


def test_production_adds_security_headers(monkeypatch, tmp_path):
    frontend_dist = tmp_path / "frontend"
    frontend_dist.mkdir()
    (frontend_dist / "index.html").write_text("<html></html>", encoding="utf-8")
    configure_production(monkeypatch, frontend_dist)

    response = authorized_client(create_app()).get("/api/context")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "default-src 'self'" in response.headers["content-security-policy"]


def test_liveness_contains_no_dependency_details():
    response = TestClient(create_app()).get("/api/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_production_readiness_fails_when_redis_is_unavailable(
    monkeypatch,
    tmp_path,
):
    frontend_dist = tmp_path / "frontend"
    frontend_dist.mkdir()
    (frontend_dist / "index.html").write_text("<html></html>", encoding="utf-8")
    configure_production(monkeypatch, frontend_dist)
    monkeypatch.setenv("EVAL_ARTIFACT_ROOT", str(tmp_path / "runs"))
    monkeypatch.setattr(health_service, "redis_ready", lambda settings: False)

    response = TestClient(create_app()).get("/api/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable",
        "checks": {
            "configuration": "ok",
            "redis": "unavailable",
            "artifact_root": "ok",
            "frontend": "ok",
        },
    }


def test_production_readiness_reports_artifact_and_frontend_failures(
    monkeypatch,
    tmp_path,
):
    frontend_dist = tmp_path / "frontend"
    frontend_dist.mkdir()
    (frontend_dist / "index.html").write_text("<html></html>", encoding="utf-8")
    configure_production(monkeypatch, frontend_dist)
    monkeypatch.setattr(health_service, "redis_ready", lambda settings: True)
    monkeypatch.setattr(
        health_service,
        "artifact_root_ready",
        lambda settings: False,
    )
    monkeypatch.setattr(
        health_service,
        "frontend_ready",
        lambda settings: False,
    )

    response = TestClient(create_app()).get("/api/health/ready")

    assert response.status_code == 503
    assert response.json()["checks"]["artifact_root"] == "unavailable"
    assert response.json()["checks"]["frontend"] == "unavailable"
    assert "paths" not in response.json()


def test_local_proxy_forwarded_ip_is_used():
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/runs/async",
            "headers": [(b"x-forwarded-for", b"203.0.113.8")],
            "client": ("127.0.0.1", 12345),
        }
    )

    assert trusted_client_ip(request, ("127.0.0.1",)) == "203.0.113.8"


def test_untrusted_peer_cannot_spoof_forwarded_ip():
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/runs/async",
            "headers": [(b"x-forwarded-for", b"203.0.113.8")],
            "client": ("198.51.100.4", 12345),
        }
    )

    assert trusted_client_ip(request, ("127.0.0.1",)) == "198.51.100.4"


@pytest.mark.parametrize(
    ("queue_error", "expected_status", "expected_detail"),
    [
        (
            JobQuotaExceeded("internal quota key failed"),
            429,
            "Hourly evaluation quota exceeded",
        ),
        (
            JobQueueFull("internal queue length failed"),
            503,
            "Evaluation queue is unavailable",
        ),
    ],
)
def test_production_queue_errors_map_to_public_status_codes(
    monkeypatch,
    tmp_path,
    queue_error,
    expected_status,
    expected_detail,
):
    class RejectingQueue:
        def submit(self, source_ip, run_id, payload):
            raise queue_error

    frontend_dist = tmp_path / "frontend"
    frontend_dist.mkdir()
    (frontend_dist / "index.html").write_text("<html></html>", encoding="utf-8")
    configure_production(monkeypatch, frontend_dist)
    monkeypatch.setattr(run_service, "job_queue", lambda require_redis=False: RejectingQueue())

    response = authorized_client(create_app()).post(
        "/api/runs/async",
        json={"instruction": "test"},
    )

    assert response.status_code == expected_status
    assert response.json()["detail"] == expected_detail
    assert "internal" not in response.text


def test_production_model_base_requires_https(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv(
        "ALLOWED_MODEL_API_BASES",
        "http://models.example.test/v1",
    )
    provider = OpenAICompatibleProvider(transport=SimpleNamespace())
    config = ModelConfig(
        provider_type="openai_compatible",
        api_base="http://models.example.test/v1",
        model_name="test-model",
    )

    with pytest.raises(ValueError, match="HTTPS"):
        provider.generate([{"role": "user", "content": "hello"}], config)


def test_private_model_base_requires_internal_gateway_provider(monkeypatch):
    monkeypatch.setenv(
        "ALLOWED_MODEL_API_BASES",
        "https://127.0.0.1:8443/v1",
    )
    provider = OpenAICompatibleProvider(transport=SimpleNamespace())

    with pytest.raises(ValueError, match="private"):
        provider.generate(
            [{"role": "user", "content": "hello"}],
            ModelConfig(
                provider_type="openai_compatible",
                api_base="https://127.0.0.1:8443/v1",
                model_name="test-model",
            ),
        )


def test_internal_gateway_may_use_exact_allowlisted_private_base(monkeypatch):
    class StaticTransport:
        def post_json(self, url, headers, payload, timeout_seconds):
            return {"choices": [{"message": {"content": "ok"}}]}

    monkeypatch.setenv(
        "ALLOWED_MODEL_API_BASES",
        "https://127.0.0.1:8443/v1",
    )
    provider = OpenAICompatibleProvider(transport=StaticTransport())

    response = provider.generate(
        [{"role": "user", "content": "hello"}],
        ModelConfig(
            provider_type="internal_gateway",
            api_base="https://127.0.0.1:8443/v1",
            model_name="test-model",
        ),
    )

    assert response.content == "ok"


def test_model_transport_rejects_redirects():
    handler = _NoRedirectHandler()

    assert (
        handler.redirect_request(
            request=SimpleNamespace(),
            fp=None,
            code=302,
            msg="Found",
            headers={},
            newurl="https://evil.example/v1",
        )
        is None
    )


def test_model_transport_passes_timeout_as_keyword(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self, size):
            return b'{"choices":[{"message":{"content":"ok"}}]}'

    calls = []

    def opener(*args, **kwargs):
        calls.append((args, kwargs))
        return Response()

    transport = UrllibJsonTransport(opener=opener)
    monkeypatch.setenv("MODEL_RESPONSE_MAX_BYTES", "1024")

    response = transport.post_json(
        "https://models.example.test/v1/chat/completions",
        {},
        {"model": "test-model", "messages": []},
        37,
    )

    assert response["choices"][0]["message"]["content"] == "ok"
    assert len(calls[0][0]) == 1
    assert calls[0][1] == {"timeout": 37}


def test_model_response_body_is_bounded(monkeypatch):
    class OversizedResponse:
        def __init__(self):
            self.read_size = None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self, size):
            self.read_size = size
            return b"x" * size

    response = OversizedResponse()
    transport = UrllibJsonTransport(
        opener=lambda request, *, timeout: response,
        max_response_bytes=32,
    )
    provider = OpenAICompatibleProvider(transport=transport)
    monkeypatch.setenv(
        "ALLOWED_MODEL_API_BASES",
        "https://models.example.test/v1",
    )

    with pytest.raises(ModelProviderError, match="too large"):
        provider.generate(
            [{"role": "user", "content": "hello"}],
            ModelConfig(
                provider_type="openai_compatible",
                api_base="https://models.example.test/v1",
                model_name="test-model",
            ),
        )

    assert response.read_size == 33
