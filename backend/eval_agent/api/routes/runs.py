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
    provider: str = Field(default="mock", max_length=64)
    model_name: str = Field(default="", max_length=256)
    api_base: str = Field(default="", max_length=2048)
    api_key: str = Field(default="", max_length=4096)
    judge_mode: str = Field(default="hybrid", max_length=64)
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


class RunRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    instruction: str = Field(min_length=1, max_length=100_000)
    input_data: str = Field(default="", max_length=1_000_000)
    minimum_scenarios: int = Field(default=5, ge=1, le=20)
    eval_model_config: ModelConfig = Field(
        default_factory=ModelConfig,
        alias="model_config",
    )
    selected_scenario_ids: list[str] = Field(default_factory=list, max_length=20)
    workspace_id: str = Field(default="workspace_demo", max_length=128)
    project_id: str = Field(default="project_meituan_fulfillment", max_length=128)
    created_by: str = Field(default="demo_user", max_length=128)


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
