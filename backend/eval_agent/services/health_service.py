from __future__ import annotations

from backend.eval_agent.core.config import settings_from_env
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
