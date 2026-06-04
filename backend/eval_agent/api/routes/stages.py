from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.eval_agent.services.stage_service import (
    parse_stage_payload,
    rubric_stage_payload,
    scenarios_stage_payload,
)

router = APIRouter(prefix="/api/stages", tags=["stages"])


class StageRequest(BaseModel):
    instruction: str
    input_data: str = ""
    minimum_scenarios: int = Field(default=5, ge=1, le=20)


@router.post("/parse")
def parse_stage(request: StageRequest) -> dict[str, object]:
    return parse_stage_payload(request.instruction, request.input_data)


@router.post("/rubric")
def rubric_stage(request: StageRequest) -> dict[str, object]:
    return rubric_stage_payload(request.instruction, input_data=request.input_data)


@router.post("/scenarios")
def scenarios_stage(request: StageRequest) -> dict[str, object]:
    return scenarios_stage_payload(
        request.instruction,
        request.minimum_scenarios,
        input_data=request.input_data,
    )
