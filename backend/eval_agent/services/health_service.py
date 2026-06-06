from __future__ import annotations

import os
from pathlib import Path
import tempfile

from backend.eval_agent.core.config import Settings, settings_from_env
from backend.eval_agent.services.run_status_store import redis_client_from_url
from backend.evaluation_engine.calibration_dataset import DEFAULT_DATASET_PATH


def health_payload() -> dict[str, object]:
    settings = settings_from_env()
    artifact_root = settings.artifact_root
    frontend_dist = settings.frontend_dist

    checks = {
        "api": "ok",
        "evaluation_engine": "ok",
        "calibration_dataset": "ok" if DEFAULT_DATASET_PATH.exists() else "missing",
        "artifact_root": "ok" if artifact_root.exists() or artifact_root.parent.exists() else "missing",
        "frontend": "built" if frontend_dist.exists() else "fallback",
    }
    status = "ok" if all(value in {"ok", "built", "fallback"} for value in checks.values()) else "degraded"

    payload: dict[str, object] = {
        "status": status,
        "checks": checks,
    }
    if settings.environment.lower() != "production":
        payload["paths"] = {
            "artifact_root": str(artifact_root),
            "frontend_dist": str(frontend_dist),
            "calibration_dataset": str(DEFAULT_DATASET_PATH),
        }
    return payload


def liveness_payload() -> dict[str, str]:
    return {"status": "ok"}


def redis_ready(settings: Settings) -> bool:
    try:
        return bool(redis_client_from_url(settings.redis_url).ping())
    except Exception:
        return False


def artifact_root_ready(settings: Settings) -> bool:
    root = Path(settings.artifact_root)
    try:
        root.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix=".ready-", dir=root)
        os.close(descriptor)
        Path(name).unlink()
        return True
    except OSError:
        return False


def frontend_ready(settings: Settings) -> bool:
    if settings.environment.lower() != "production":
        return True
    return (Path(settings.frontend_dist) / "index.html").is_file()


def readiness_payload() -> tuple[dict[str, object], int]:
    settings = settings_from_env()
    production = settings.environment.lower() == "production"
    checks = {
        "configuration": (
            "ok" if not production or bool(settings.access_token) else "unavailable"
        ),
        "redis": "ok" if redis_ready(settings) else "unavailable",
        "artifact_root": "ok" if artifact_root_ready(settings) else "unavailable",
        "frontend": "ok" if frontend_ready(settings) else "unavailable",
    }
    ready = all(value == "ok" for value in checks.values())
    return (
        {
            "status": "ok" if ready else "unavailable",
            "checks": checks,
        },
        200 if ready else 503,
    )
