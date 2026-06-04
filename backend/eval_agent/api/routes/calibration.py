from __future__ import annotations

from fastapi import APIRouter

from backend.eval_agent.services.calibration_service import (
    calibration_samples_payload,
    calibration_self_check_payload,
    calibration_summary_payload,
)

router = APIRouter(prefix="/api/calibration", tags=["calibration"])


@router.get("/summary")
def calibration_summary() -> dict[str, object]:
    return calibration_summary_payload()


@router.get("/samples")
def calibration_samples() -> dict[str, object]:
    return calibration_samples_payload()


@router.get("/self-check")
def calibration_self_check() -> dict[str, object]:
    return calibration_self_check_payload()
