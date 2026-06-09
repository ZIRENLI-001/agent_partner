from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


Verdict = Literal["pass", "partial", "fail", "needs_review"]
Speaker = Literal["assistant", "user", "user_simulator", "system"]
CheckType = Literal["rule", "semantic", "rule_and_semantic"]


class TaskSpec(BaseModel):
    task_id: str
    version: str = "v1"
    task_name: str
    role: str
    target_user: str
    task_goal: str
    opening_line: str
    required_steps: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    faq: list[dict[str, str]] = Field(default_factory=list)
    edge_cases: list[dict[str, str]] = Field(default_factory=list)
    forbidden_actions: list[str] = Field(default_factory=list)


class RubricItem(BaseModel):
    item_id: str
    dimension: str
    criterion: str
    source: str
    check_type: CheckType
    weight: int
    critical: bool = False


class RubricSpec(BaseModel):
    rubric_id: str
    task_id: str
    version: str = "v1"
    items: list[RubricItem]


class Scenario(BaseModel):
    scenario_id: str
    task_id: str
    user_profile: dict[str, str]
    coverage_targets: list[str]
    initial_user_intent: str
    expected_test_focus: str
    difficulty: str = "L1"
    scenario_type: str = "baseline"
    expected_behavior: str = ""
    risk_tags: list[str] = Field(default_factory=list)


class ScenarioSet(BaseModel):
    suite_id: str
    task_id: str
    version: str = "v1"
    scenarios: list[Scenario]


class Turn(BaseModel):
    turn_id: int
    speaker: Speaker
    content: str


class DialogueTrace(BaseModel):
    trace_id: str
    run_id: str
    task_id: str
    scenario_id: str
    turns: list[Turn]
    termination_reason: str
    error: Optional[str] = None


class EvidenceItem(BaseModel):
    rubric_item_id: str
    verdict: Verdict
    source: str
    turn_ids: list[int]
    reason: str
    score: int
    max_score: int
    instruction_quote: str = ""
    expected_behavior: str = ""
    actual_behavior: str = ""
    explanation: str = ""


class EvaluationResult(BaseModel):
    trace_id: str
    scenario_id: str
    total_score: int
    dimension_scores: dict[str, int]
    evidence: list[EvidenceItem]
    critical_failures: list[str] = Field(default_factory=list)


class RunConfig(BaseModel):
    run_id: str
    task_id: str
    target_model: str = "fake-target"
    user_model: str = "fake-user"
    judge_model: str = "heuristic-judge"
    max_turns: int = 17


class Report(BaseModel):
    run_id: str
    task_id: str
    markdown: str
