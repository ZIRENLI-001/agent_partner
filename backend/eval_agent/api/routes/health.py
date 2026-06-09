from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.eval_agent.services.health_service import (
    health_payload,
    liveness_payload,
    readiness_payload,
)

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("")
def health() -> dict[str, object]:
    return health_payload()


@router.get("/live")
def liveness() -> dict[str, str]:
    return liveness_payload()


@router.get("/ready")
def readiness() -> JSONResponse:
    payload, status_code = readiness_payload()
    return JSONResponse(content=payload, status_code=status_code)
