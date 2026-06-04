from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict, Field

from backend.eval_agent.services.run_service import (
    create_run_payload,
    run_comparison_payload,
    run_detail_payload,
    run_history_payload,
    run_status_payload,
    submit_run_payload,
)

router = APIRouter(prefix="/api/runs", tags=["runs"])


class ModelConfig(BaseModel):
    provider: str = "mock"
    model_name: str = ""
    api_base: str = ""
    api_key: str = ""
    judge_mode: str = "hybrid"
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


class RunRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    instruction: str
    input_data: str = ""
    minimum_scenarios: int = Field(default=5, ge=1, le=20)
    eval_model_config: ModelConfig = Field(
        default_factory=ModelConfig,
        alias="model_config",
    )
    selected_scenario_ids: list[str] = Field(default_factory=list)
    workspace_id: str = "workspace_demo"
    project_id: str = "project_meituan_fulfillment"
    created_by: str = "demo_user"


@router.post("")
def create_run(request: RunRequest) -> dict[str, object]:
    return create_run_payload(request)


@router.post("/async", status_code=status.HTTP_202_ACCEPTED)
def submit_run(request: RunRequest) -> dict[str, object]:
    return submit_run_payload(request)


@router.get("/history")
def run_history() -> dict[str, object]:
    return run_history_payload()


@router.get("/comparison")
def run_comparison() -> dict[str, object]:
    return run_comparison_payload()


@router.get("/{run_id}")
def run_detail(run_id: str) -> dict[str, object]:
    return run_detail_payload(run_id)


@router.get("/{run_id}/status")
def run_status(run_id: str) -> dict[str, object]:
    return run_status_payload(run_id)
