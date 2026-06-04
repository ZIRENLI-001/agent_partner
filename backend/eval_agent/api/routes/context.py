from __future__ import annotations

from fastapi import APIRouter

from backend.eval_agent.services.context_service import get_current_context

router = APIRouter(prefix="/api/context", tags=["context"])


@router.get("")
def current_context() -> dict[str, object]:
    return get_current_context()
