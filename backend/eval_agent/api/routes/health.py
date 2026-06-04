from __future__ import annotations

from fastapi import APIRouter

from backend.eval_agent.services.health_service import health_payload

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("")
def health() -> dict[str, object]:
    return health_payload()
