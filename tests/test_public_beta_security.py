import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from types import SimpleNamespace

from backend.eval_agent.api.main import create_app
from backend.eval_agent.api.routes.runs import RunRequest
from backend.eval_agent.core.config import settings_from_env
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
