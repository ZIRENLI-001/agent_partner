import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from types import SimpleNamespace

from backend.eval_agent.api.routes.runs import RunRequest
from backend.eval_agent.core.config import settings_from_env
from backend.eval_agent.services import run_service
from backend.evaluation_engine import app as engine_app


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
