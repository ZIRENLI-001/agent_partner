# Dialogue Eval Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a准生产 MVP Web 工作台 that evaluates dialogue models against complex multi-turn task instructions using generated user scenarios, multi-turn traces, mixed rule/Judge scoring, and evidence-based reports.

**Architecture:** Implement a Python evaluation engine with JSON-first domain objects and file-backed run storage, then expose it through a FastAPI Web/API layer and a lightweight browser wizard. The MVP must run a full `ScenarioSet` in one click, persist `TaskSpec`, `RubricSpec`, `ScenarioSet`, `DialogueTrace[]`, `EvaluationResult[]`, and `Report`, and avoid single-scenario assumptions.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, pytest, uvicorn, vanilla HTML/CSS/JS for the demo UI, file-backed storage under `runs/{run_id}`.

---

## File Structure

Create these files:

```text
pyproject.toml
eval_agent/__init__.py
eval_agent/domain.py
eval_agent/storage.py
eval_agent/instruction_parser.py
eval_agent/rubric_builder.py
eval_agent/scenario_generator.py
eval_agent/providers.py
eval_agent/user_simulator.py
eval_agent/dialogue_runner.py
eval_agent/rule_evaluator.py
eval_agent/judge_evaluator.py
eval_agent/report_writer.py
eval_agent/engine.py
eval_agent/app.py
eval_agent/web/index.html
tests/test_domain.py
tests/test_instruction_parser.py
tests/test_scenario_generator.py
tests/test_dialogue_runner.py
tests/test_rule_evaluator.py
tests/test_engine.py
tests/test_report_writer.py
```

Responsibilities:

- `domain.py`: Pydantic models shared across all modules.
- `storage.py`: file-backed `RunStore` for reproducible run artifacts.
- `instruction_parser.py`: deterministic parser for structured markdown-like task instructions.
- `rubric_builder.py`: converts `TaskSpec` into weighted rubric items.
- `scenario_generator.py`: creates reusable scenario suites from task branches.
- `providers.py`: model provider protocol plus deterministic fake providers for tests/demo.
- `user_simulator.py`: builds simulated user turns from scenarios and history.
- `dialogue_runner.py`: runs a full scenario to `DialogueTrace`.
- `rule_evaluator.py`: deterministic rule checks for hard constraints.
- `judge_evaluator.py`: semantic evaluator abstraction with deterministic heuristic fallback.
- `report_writer.py`: Markdown report generation with evidence chains.
- `engine.py`: orchestrates one-click full `ScenarioSet` evaluation.
- `app.py` and `web/index.html`: lightweight Web wizard over the same engine.

## Task 1: Project Scaffold and Domain Models

**Files:**
- Create: `pyproject.toml`
- Create: `eval_agent/__init__.py`
- Create: `eval_agent/domain.py`
- Test: `tests/test_domain.py`

- [ ] **Step 1: Write failing domain model tests**

Create `tests/test_domain.py`:

```python
from backend.evaluation_engine.domain import (
    DialogueTrace,
    EvaluationResult,
    EvidenceItem,
    RubricItem,
    RubricSpec,
    Scenario,
    ScenarioSet,
    TaskSpec,
    Turn,
)


def test_task_spec_requires_versioned_identity():
    spec = TaskSpec(
        task_id="task_001",
        version="v1",
        task_name="飞毛腿通知",
        role="站长",
        target_user="骑手",
        task_goal="通知合同生效",
        opening_line="你好",
        required_steps=["确认身份", "告知合同生效"],
        constraints=["每次回复约30字以内"],
        faq=[{"intent": "退出", "expected_answer": "前一天取消"}],
        edge_cases=[{"trigger": "不想配送", "expected_behavior": "挽留"}],
        forbidden_actions=["承诺额外奖励"],
    )

    assert spec.task_id == "task_001"
    assert spec.version == "v1"
    assert spec.required_steps[1] == "告知合同生效"


def test_evaluation_evidence_is_traceable():
    rubric = RubricSpec(
        rubric_id="rubric_001",
        task_id="task_001",
        version="v1",
        items=[
            RubricItem(
                item_id="r1",
                dimension="task_completion",
                criterion="是否告知合同生效",
                source="Call Flow 第1步",
                check_type="semantic",
                weight=10,
                critical=False,
            )
        ],
    )
    trace = DialogueTrace(
        trace_id="trace_001",
        run_id="run_001",
        task_id="task_001",
        scenario_id="scenario_001",
        turns=[
            Turn(turn_id=1, speaker="assistant", content="今天合同已经生效。"),
        ],
        termination_reason="task_completed",
    )
    result = EvaluationResult(
        trace_id=trace.trace_id,
        scenario_id="scenario_001",
        total_score=10,
        dimension_scores={"task_completion": 10},
        evidence=[
            EvidenceItem(
                rubric_item_id=rubric.items[0].item_id,
                verdict="pass",
                source="Call Flow 第1步",
                turn_ids=[1],
                reason="模型明确告知合同生效",
                score=10,
                max_score=10,
            )
        ],
        critical_failures=[],
    )

    assert result.evidence[0].source == "Call Flow 第1步"
    assert result.evidence[0].turn_ids == [1]


def test_scenario_set_contains_multiple_scenarios():
    scenario_set = ScenarioSet(
        suite_id="suite_001",
        task_id="task_001",
        version="v1",
        scenarios=[
            Scenario(
                scenario_id="scenario_normal",
                task_id="task_001",
                user_profile={"role": "骑手", "attitude": "配合"},
                coverage_targets=["contract_active"],
                initial_user_intent="正常确认",
                expected_test_focus="基础任务完成",
            ),
            Scenario(
                scenario_id="scenario_reward",
                task_id="task_001",
                user_profile={"role": "骑手", "attitude": "关注收益"},
                coverage_targets=["reward_question", "boundary_no_extra_promise"],
                initial_user_intent="询问奖励",
                expected_test_focus="奖励边界",
            ),
        ],
    )

    assert len(scenario_set.scenarios) == 2
    assert scenario_set.scenarios[1].coverage_targets == ["reward_question", "boundary_no_extra_promise"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/test_domain.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'backend.evaluation_engine.domain'`.

- [ ] **Step 3: Add package config and domain models**

Create `pyproject.toml`:

```toml
[project]
name = "dialogue-eval-platform"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.111.0",
  "pydantic>=2.7.0",
  "uvicorn>=0.30.0",
  "python-multipart>=0.0.9"
]

[project.optional-dependencies]
dev = [
  "pytest>=8.2.0"
]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

Create `eval_agent/__init__.py`:

```python
__all__ = []
```

Create `eval_agent/domain.py`:

```python
from __future__ import annotations

from typing import Literal

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
    error: str | None = None


class EvidenceItem(BaseModel):
    rubric_item_id: str
    verdict: Verdict
    source: str
    turn_ids: list[int]
    reason: str
    score: int
    max_score: int


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
    max_turns: int = 8


class Report(BaseModel):
    run_id: str
    task_id: str
    markdown: str
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python3 -m pytest tests/test_domain.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml eval_agent/__init__.py eval_agent/domain.py tests/test_domain.py
git commit -m "feat: add evaluation domain models"
```

Expected: commit succeeds. If the workspace is not a git repository, skip this commit step and record that the plan was executed in a non-git workspace.

## Task 2: Instruction Parser and Rubric Builder

**Files:**
- Create: `eval_agent/instruction_parser.py`
- Create: `eval_agent/rubric_builder.py`
- Test: `tests/test_instruction_parser.py`

- [ ] **Step 1: Write failing parser/rubric tests**

Create `tests/test_instruction_parser.py`:

```python
from backend.evaluation_engine.instruction_parser import parse_instruction
from backend.evaluation_engine.rubric_builder import build_rubric


RAW_TASK = """# Role
你是美团外卖骑手的站长。

# Task
致电"飞毛腿"骑手，通知他们今天合同已成功签署，并提醒他们完成配送任务。

# Opening Line
你好，请问是${rider_name}吗？我是站长。

# Call Flow
1. 告知骑手今天飞毛腿合同已生效，并询问他们是否可以开始配送。
2. 说明单日飞毛腿合同需要连续 Y 天完成配送；否则合同将受到影响。
3. 尽量挽留不想配送的骑手，鼓励能配送的骑手，并提醒他们注意安全。

# Knowledge Points (FAQ)
- 如需退出飞毛腿，必须在前一天 Z 点之前在 App 的"飞毛腿报名"中取消；次日生效。

# Constraints
- 保持语气随意，像打电话一样自然。
- 每次回复控制在约 30 个字以内。
- 如被问及超出职责范围的问题，回复："我向同事确认后再回电给你。我现在能回答的先回答。"
"""


def test_parse_instruction_extracts_core_sections():
    spec = parse_instruction(RAW_TASK, task_id="task_001")

    assert spec.role == "美团外卖骑手的站长"
    assert "合同已成功签署" in spec.task_goal
    assert spec.opening_line.startswith("你好，请问是")
    assert len(spec.required_steps) == 3
    assert any("30" in item for item in spec.constraints)
    assert spec.faq[0]["intent"] == "退出飞毛腿"
    assert spec.edge_cases[0]["trigger"] == "不想配送"


def test_build_rubric_contains_sources_and_mixed_check_types():
    spec = parse_instruction(RAW_TASK, task_id="task_001")
    rubric = build_rubric(spec)

    assert rubric.task_id == "task_001"
    assert len(rubric.items) >= 6
    assert all(item.source for item in rubric.items)
    assert any(item.check_type == "rule" for item in rubric.items)
    assert any(item.check_type == "semantic" for item in rubric.items)
    assert any(item.critical for item in rubric.items)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest tests/test_instruction_parser.py -v
```

Expected: FAIL with `ModuleNotFoundError` for parser or rubric module.

- [ ] **Step 3: Implement deterministic parser**

Create `eval_agent/instruction_parser.py`:

```python
from __future__ import annotations

import re

from backend.evaluation_engine.domain import TaskSpec


SECTION_RE = re.compile(r"^#\s*(.+?)\s*$", re.MULTILINE)


def _section_map(raw: str) -> dict[str, str]:
    matches = list(SECTION_RE.finditer(raw))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        name = match.group(1).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(raw)
        sections[name.lower()] = raw[start:end].strip()
    return sections


def _clean_bullet(line: str) -> str:
    line = line.strip()
    line = re.sub(r"^\d+\.\s*", "", line)
    line = re.sub(r"^[-*]\s*", "", line)
    return line.strip()


def _numbered_or_bullets(text: str) -> list[str]:
    result: list[str] = []
    for line in text.splitlines():
        item = _clean_bullet(line)
        if item:
            result.append(item)
    return result


def _faq_items(text: str) -> list[dict[str, str]]:
    items = []
    for item in _numbered_or_bullets(text):
        if "退出" in item:
            intent = "退出飞毛腿"
        elif "奖励" in item:
            intent = "奖励"
        else:
            intent = item[:20]
        items.append({"intent": intent, "expected_answer": item})
    return items


def _edge_cases(required_steps: list[str], constraints: list[str], faq: list[dict[str, str]]) -> list[dict[str, str]]:
    cases: list[dict[str, str]] = []
    if any("不想配送" in step for step in required_steps):
        cases.append({"trigger": "不想配送", "expected_behavior": "尽量挽留；若坚持无法配送，安慰后结束"})
    if any("超出职责范围" in item for item in constraints):
        cases.append({"trigger": "超出职责范围", "expected_behavior": "说明向同事确认后再回电"})
    if any("退出" in item["intent"] for item in faq):
        cases.append({"trigger": "询问退出方式", "expected_behavior": "按 FAQ 说明 App 取消路径和生效时间"})
    return cases


def parse_instruction(raw: str, task_id: str = "task_001") -> TaskSpec:
    sections = _section_map(raw)
    role = sections.get("role", "").strip("。 \n")
    task_goal = sections.get("task", "")
    opening_line = sections.get("opening line", "")
    required_steps = _numbered_or_bullets(sections.get("call flow", ""))
    constraints = _numbered_or_bullets(sections.get("constraints", ""))
    faq = _faq_items(sections.get("knowledge points (faq)", ""))
    forbidden_actions = []
    if any("超出职责范围" in item for item in constraints):
        forbidden_actions.append("对超出职责范围问题直接下结论")
    if "奖励" in raw or "优惠" in raw:
        forbidden_actions.append("承诺指令外奖励或优惠")

    return TaskSpec(
        task_id=task_id,
        version="v1",
        task_name="复杂外呼任务",
        role=role,
        target_user="骑手" if "骑手" in raw else "用户",
        task_goal=task_goal,
        opening_line=opening_line,
        required_steps=required_steps,
        constraints=constraints,
        faq=faq,
        edge_cases=_edge_cases(required_steps, constraints, faq),
        forbidden_actions=forbidden_actions,
    )
```

- [ ] **Step 4: Implement rubric builder**

Create `eval_agent/rubric_builder.py`:

```python
from __future__ import annotations

from backend.evaluation_engine.domain import RubricItem, RubricSpec, TaskSpec


def build_rubric(task_spec: TaskSpec) -> RubricSpec:
    items: list[RubricItem] = []
    counter = 1

    for index, step in enumerate(task_spec.required_steps, start=1):
        items.append(
            RubricItem(
                item_id=f"r{counter}",
                dimension="task_completion" if index == 1 else "flow_adherence",
                criterion=f"是否完成流程步骤：{step}",
                source=f"Call Flow 第{index}步",
                check_type="semantic",
                weight=8,
            )
        )
        counter += 1

    for index, constraint in enumerate(task_spec.constraints, start=1):
        check_type = "rule" if "30" in constraint or "字" in constraint else "semantic"
        items.append(
            RubricItem(
                item_id=f"r{counter}",
                dimension="constraint_adherence",
                criterion=f"是否遵守约束：{constraint}",
                source=f"Constraints 第{index}条",
                check_type=check_type,
                weight=5,
            )
        )
        counter += 1

    for index, faq in enumerate(task_spec.faq, start=1):
        items.append(
            RubricItem(
                item_id=f"r{counter}",
                dimension="faq_accuracy",
                criterion=f"是否准确回答 FAQ：{faq['intent']}",
                source=f"Knowledge Points 第{index}条",
                check_type="semantic",
                weight=7,
            )
        )
        counter += 1

    for index, edge_case in enumerate(task_spec.edge_cases, start=1):
        items.append(
            RubricItem(
                item_id=f"r{counter}",
                dimension="exception_handling",
                criterion=f"是否正确处理异常分支：{edge_case['trigger']}",
                source=f"Edge Case 第{index}条",
                check_type="semantic",
                weight=8,
            )
        )
        counter += 1

    for index, action in enumerate(task_spec.forbidden_actions, start=1):
        items.append(
            RubricItem(
                item_id=f"r{counter}",
                dimension="boundary",
                criterion=f"是否避免禁止行为：{action}",
                source=f"Forbidden Actions 第{index}条",
                check_type="rule_and_semantic",
                weight=10,
                critical=True,
            )
        )
        counter += 1

    return RubricSpec(
        rubric_id=f"rubric_{task_spec.task_id}",
        task_id=task_spec.task_id,
        version=task_spec.version,
        items=items,
    )
```

- [ ] **Step 5: Run parser/rubric tests**

Run:

```bash
python3 -m pytest tests/test_instruction_parser.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add eval_agent/instruction_parser.py eval_agent/rubric_builder.py tests/test_instruction_parser.py
git commit -m "feat: parse task instructions into rubric"
```

Expected: commit succeeds, or skip in non-git workspace.

## Task 3: Scenario Generation

**Files:**
- Create: `eval_agent/scenario_generator.py`
- Test: `tests/test_scenario_generator.py`

- [ ] **Step 1: Write failing scenario tests**

Create `tests/test_scenario_generator.py`:

```python
from backend.evaluation_engine.domain import TaskSpec
from backend.evaluation_engine.rubric_builder import build_rubric
from backend.evaluation_engine.scenario_generator import generate_scenarios


def _task_spec() -> TaskSpec:
    return TaskSpec(
        task_id="task_001",
        version="v1",
        task_name="飞毛腿通知",
        role="站长",
        target_user="骑手",
        task_goal="通知合同生效",
        opening_line="你好",
        required_steps=["确认身份", "告知合同生效", "说明单量要求"],
        constraints=["每次回复约30字以内"],
        faq=[{"intent": "退出飞毛腿", "expected_answer": "前一天取消"}],
        edge_cases=[
            {"trigger": "不想配送", "expected_behavior": "挽留"},
            {"trigger": "超出职责范围", "expected_behavior": "确认后回电"},
        ],
        forbidden_actions=["承诺额外奖励"],
    )


def test_generate_scenarios_produces_minimum_coverage():
    task = _task_spec()
    rubric = build_rubric(task)
    scenario_set = generate_scenarios(task, rubric, minimum=5)

    assert scenario_set.task_id == task.task_id
    assert len(scenario_set.scenarios) >= 5
    all_targets = {target for scenario in scenario_set.scenarios for target in scenario.coverage_targets}
    assert "normal_completion" in all_targets
    assert "refusal_to_deliver" in all_targets
    assert "faq_exit" in all_targets
    assert "boundary_no_extra_promise" in all_targets
    assert "out_of_scope" in all_targets
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/test_scenario_generator.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'backend.evaluation_engine.scenario_generator'`.

- [ ] **Step 3: Implement scenario generator**

Create `eval_agent/scenario_generator.py`:

```python
from __future__ import annotations

from backend.evaluation_engine.domain import RubricSpec, Scenario, ScenarioSet, TaskSpec


def generate_scenarios(task_spec: TaskSpec, rubric: RubricSpec, minimum: int = 5) -> ScenarioSet:
    scenarios = [
        Scenario(
            scenario_id="scenario_normal_completion",
            task_id=task_spec.task_id,
            user_profile={"role": task_spec.target_user, "attitude": "配合", "background": "愿意听完说明"},
            coverage_targets=["normal_completion", "contract_active", "required_steps"],
            initial_user_intent="正常确认身份并接受说明",
            expected_test_focus="基础任务完成和流程覆盖",
        ),
        Scenario(
            scenario_id="scenario_refusal_to_deliver",
            task_id=task_spec.task_id,
            user_profile={"role": task_spec.target_user, "attitude": "抗拒", "background": "今天不想配送"},
            coverage_targets=["refusal_to_deliver", "exception_handling"],
            initial_user_intent="表示今天不想配送",
            expected_test_focus="挽留、安抚和合理结束",
        ),
        Scenario(
            scenario_id="scenario_faq_exit",
            task_id=task_spec.task_id,
            user_profile={"role": task_spec.target_user, "attitude": "疑惑", "background": "不清楚退出方式"},
            coverage_targets=["faq_exit", "faq_accuracy"],
            initial_user_intent="询问如何退出飞毛腿",
            expected_test_focus="FAQ 准确性",
        ),
        Scenario(
            scenario_id="scenario_reward_question",
            task_id=task_spec.task_id,
            user_profile={"role": task_spec.target_user, "attitude": "关注收益", "background": "想知道是否有额外奖励"},
            coverage_targets=["reward_question", "boundary_no_extra_promise"],
            initial_user_intent="询问是否能保证额外奖励",
            expected_test_focus="奖励边界和禁止承诺",
        ),
        Scenario(
            scenario_id="scenario_out_of_scope",
            task_id=task_spec.task_id,
            user_profile={"role": task_spec.target_user, "attitude": "追问", "background": "质疑站长是否能调整排名"},
            coverage_targets=["out_of_scope", "boundary"],
            initial_user_intent="询问站长能否调整排名或派单",
            expected_test_focus="超出职责范围处理",
        ),
    ]

    if minimum > len(scenarios):
        scenarios.append(
            Scenario(
                scenario_id="scenario_busy_call",
                task_id=task_spec.task_id,
                user_profile={"role": task_spec.target_user, "attitude": "忙碌", "background": "正在配送不方便长聊"},
                coverage_targets=["busy_or_unavailable", "termination"],
                initial_user_intent="表示正在配送不方便长聊",
                expected_test_focus="忙碌状态下简短处理和结束",
            )
        )

    return ScenarioSet(
        suite_id=f"suite_{task_spec.task_id}_v1",
        task_id=task_spec.task_id,
        version=task_spec.version,
        scenarios=scenarios[: max(minimum, 5)],
    )
```

- [ ] **Step 4: Run scenario tests**

Run:

```bash
python3 -m pytest tests/test_scenario_generator.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add eval_agent/scenario_generator.py tests/test_scenario_generator.py
git commit -m "feat: generate user simulation scenarios"
```

Expected: commit succeeds, or skip in non-git workspace.

## Task 4: Providers, User Simulator, and Dialogue Runner

**Files:**
- Create: `eval_agent/providers.py`
- Create: `eval_agent/user_simulator.py`
- Create: `eval_agent/dialogue_runner.py`
- Test: `tests/test_dialogue_runner.py`

- [ ] **Step 1: Write failing dialogue runner tests**

Create `tests/test_dialogue_runner.py`:

```python
from backend.evaluation_engine.dialogue_runner import run_dialogue
from backend.evaluation_engine.domain import RunConfig, Scenario, TaskSpec
from backend.evaluation_engine.providers import FakeAssistantProvider, FakeUserProvider


def test_run_dialogue_creates_multi_turn_trace():
    task = TaskSpec(
        task_id="task_001",
        task_name="飞毛腿通知",
        role="站长",
        target_user="骑手",
        task_goal="通知合同生效",
        opening_line="你好，请问是王师傅吗？我是站长。",
        required_steps=["告知合同生效"],
        constraints=["每次回复约30字以内"],
    )
    scenario = Scenario(
        scenario_id="scenario_normal",
        task_id="task_001",
        user_profile={"role": "骑手", "attitude": "配合"},
        coverage_targets=["normal_completion"],
        initial_user_intent="正常确认",
        expected_test_focus="基础任务完成",
    )
    config = RunConfig(run_id="run_001", task_id="task_001", max_turns=4)

    trace = run_dialogue(
        task_spec=task,
        scenario=scenario,
        run_config=config,
        assistant_provider=FakeAssistantProvider(),
        user_provider=FakeUserProvider(),
    )

    assert trace.run_id == "run_001"
    assert trace.scenario_id == "scenario_normal"
    assert len(trace.turns) >= 2
    assert trace.turns[0].speaker == "assistant"
    assert trace.termination_reason in {"task_completed", "max_turns"}
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/test_dialogue_runner.py -v
```

Expected: FAIL with missing provider/dialogue modules.

- [ ] **Step 3: Implement providers**

Create `eval_agent/providers.py`:

```python
from __future__ import annotations

from typing import Protocol

from backend.evaluation_engine.domain import Scenario, TaskSpec, Turn


class AssistantProvider(Protocol):
    def generate(self, task_spec: TaskSpec, history: list[Turn]) -> str:
        ...


class UserProvider(Protocol):
    def generate(self, scenario: Scenario, history: list[Turn]) -> str:
        ...


class FakeAssistantProvider:
    def generate(self, task_spec: TaskSpec, history: list[Turn]) -> str:
        user_text = " ".join(turn.content for turn in history if turn.speaker in {"user", "user_simulator"})
        if not history:
            return task_spec.opening_line
        if "退出" in user_text:
            return "前一天在 App 取消，次日生效。"
        if "奖励" in user_text or "额外" in user_text:
            return "按页面规则为准，我不额外承诺。"
        if "不想" in user_text or "跑不了" in user_text:
            return "理解，你确认跑不了我就先记录。"
        if "排名" in user_text or "派单" in user_text:
            return "这个我确认后再回电给你。"
        return "今天飞毛腿已生效，记得高峰上线。"


class FakeUserProvider:
    def generate(self, scenario: Scenario, history: list[Turn]) -> str:
        if not any(turn.speaker in {"user", "user_simulator"} for turn in history):
            return scenario.initial_user_intent
        if "正常" in scenario.scenario_id:
            return "好的，我知道了。"
        if "reward" in scenario.scenario_id:
            return "那具体奖励按哪里看？"
        if "refusal" in scenario.scenario_id:
            return "今天确实跑不了。"
        if "out_of_scope" in scenario.scenario_id:
            return "那排名到底能不能帮我调？"
        return "明白了。"
```

- [ ] **Step 4: Implement user simulator wrapper**

Create `eval_agent/user_simulator.py`:

```python
from __future__ import annotations

from backend.evaluation_engine.domain import Scenario, Turn
from backend.evaluation_engine.providers import UserProvider


def next_user_turn(provider: UserProvider, scenario: Scenario, history: list[Turn]) -> str:
    content = provider.generate(scenario, history).strip()
    if not content:
        return "我听不太清，你再说一遍。"
    return content
```

- [ ] **Step 5: Implement dialogue runner**

Create `eval_agent/dialogue_runner.py`:

```python
from __future__ import annotations

from backend.evaluation_engine.domain import DialogueTrace, RunConfig, Scenario, TaskSpec, Turn
from backend.evaluation_engine.providers import AssistantProvider, UserProvider
from backend.evaluation_engine.user_simulator import next_user_turn


def _is_done(text: str) -> bool:
    return any(marker in text for marker in ["知道了", "明白了", "先记录"])


def run_dialogue(
    task_spec: TaskSpec,
    scenario: Scenario,
    run_config: RunConfig,
    assistant_provider: AssistantProvider,
    user_provider: UserProvider,
) -> DialogueTrace:
    turns: list[Turn] = []
    turn_id = 1

    assistant_text = assistant_provider.generate(task_spec, turns)
    turns.append(Turn(turn_id=turn_id, speaker="assistant", content=assistant_text))
    turn_id += 1

    termination_reason = "max_turns"
    while turn_id <= run_config.max_turns:
        user_text = next_user_turn(user_provider, scenario, turns)
        turns.append(Turn(turn_id=turn_id, speaker="user_simulator", content=user_text))
        turn_id += 1
        if turn_id > run_config.max_turns:
            break

        assistant_text = assistant_provider.generate(task_spec, turns)
        turns.append(Turn(turn_id=turn_id, speaker="assistant", content=assistant_text))
        turn_id += 1

        if _is_done(user_text) or _is_done(assistant_text):
            termination_reason = "task_completed"
            break

    return DialogueTrace(
        trace_id=f"trace_{run_config.run_id}_{scenario.scenario_id}",
        run_id=run_config.run_id,
        task_id=task_spec.task_id,
        scenario_id=scenario.scenario_id,
        turns=turns,
        termination_reason=termination_reason,
    )
```

- [ ] **Step 6: Run dialogue tests**

Run:

```bash
python3 -m pytest tests/test_dialogue_runner.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add eval_agent/providers.py eval_agent/user_simulator.py eval_agent/dialogue_runner.py tests/test_dialogue_runner.py
git commit -m "feat: run simulated multi-turn dialogues"
```

Expected: commit succeeds, or skip in non-git workspace.

## Task 5: Rule and Judge Evaluation

**Files:**
- Create: `eval_agent/rule_evaluator.py`
- Create: `eval_agent/judge_evaluator.py`
- Test: `tests/test_rule_evaluator.py`

- [ ] **Step 1: Write failing evaluator tests**

Create `tests/test_rule_evaluator.py`:

```python
from backend.evaluation_engine.domain import DialogueTrace, RubricItem, RubricSpec, Turn
from backend.evaluation_engine.judge_evaluator import judge_trace
from backend.evaluation_engine.rule_evaluator import evaluate_rules


def test_rule_evaluator_flags_forbidden_extra_reward():
    rubric = RubricSpec(
        rubric_id="rubric_001",
        task_id="task_001",
        items=[
            RubricItem(
                item_id="r1",
                dimension="boundary",
                criterion="是否避免承诺额外奖励",
                source="Forbidden Actions 第1条",
                check_type="rule_and_semantic",
                weight=10,
                critical=True,
            )
        ],
    )
    trace = DialogueTrace(
        trace_id="trace_001",
        run_id="run_001",
        task_id="task_001",
        scenario_id="scenario_reward",
        turns=[Turn(turn_id=1, speaker="assistant", content="我保证给你额外奖励。")],
        termination_reason="task_completed",
    )

    result = evaluate_rules(trace, rubric)

    assert result.total_score == 0
    assert result.critical_failures == ["r1"]
    assert result.evidence[0].verdict == "fail"


def test_judge_evaluator_scores_semantic_completion():
    rubric = RubricSpec(
        rubric_id="rubric_001",
        task_id="task_001",
        items=[
            RubricItem(
                item_id="r2",
                dimension="task_completion",
                criterion="是否告知合同今日生效",
                source="Call Flow 第1步",
                check_type="semantic",
                weight=8,
            )
        ],
    )
    trace = DialogueTrace(
        trace_id="trace_002",
        run_id="run_001",
        task_id="task_001",
        scenario_id="scenario_normal",
        turns=[Turn(turn_id=1, speaker="assistant", content="今天飞毛腿合同已经生效。")],
        termination_reason="task_completed",
    )

    result = judge_trace(trace, rubric)

    assert result.total_score == 8
    assert result.evidence[0].turn_ids == [1]
    assert result.evidence[0].source == "Call Flow 第1步"
```

- [ ] **Step 2: Run evaluator tests to verify failure**

Run:

```bash
python3 -m pytest tests/test_rule_evaluator.py -v
```

Expected: FAIL with missing evaluator modules.

- [ ] **Step 3: Implement rule evaluator**

Create `eval_agent/rule_evaluator.py`:

```python
from __future__ import annotations

from backend.evaluation_engine.domain import DialogueTrace, EvaluationResult, EvidenceItem, RubricSpec


FORBIDDEN_REWARD_TERMS = ["保证给你额外奖励", "保证额外奖励", "一定多给"]


def _assistant_text(trace: DialogueTrace) -> str:
    return "\n".join(turn.content for turn in trace.turns if turn.speaker == "assistant")


def evaluate_rules(trace: DialogueTrace, rubric: RubricSpec) -> EvaluationResult:
    text = _assistant_text(trace)
    evidence: list[EvidenceItem] = []
    critical_failures: list[str] = []
    total = 0
    dimension_scores: dict[str, int] = {}

    for item in rubric.items:
        if item.check_type not in {"rule", "rule_and_semantic"}:
            continue

        verdict = "pass"
        score = item.weight
        reason = "规则检查通过"
        turn_ids = [turn.turn_id for turn in trace.turns if turn.speaker == "assistant"]

        if "30" in item.criterion or "字" in item.criterion:
            too_long = any(len(turn.content) > 45 for turn in trace.turns if turn.speaker == "assistant")
            if too_long:
                verdict = "fail"
                score = 0
                reason = "存在单轮回复明显超过约30字"

        if "额外奖励" in item.criterion:
            violated = any(term in text for term in FORBIDDEN_REWARD_TERMS)
            if violated:
                verdict = "fail"
                score = 0
                reason = "模型承诺了指令外额外奖励"
                if item.critical:
                    critical_failures.append(item.item_id)

        total += score
        dimension_scores[item.dimension] = dimension_scores.get(item.dimension, 0) + score
        evidence.append(
            EvidenceItem(
                rubric_item_id=item.item_id,
                verdict=verdict,
                source=item.source,
                turn_ids=turn_ids[:1] if turn_ids else [],
                reason=reason,
                score=score,
                max_score=item.weight,
            )
        )

    return EvaluationResult(
        trace_id=trace.trace_id,
        scenario_id=trace.scenario_id,
        total_score=total,
        dimension_scores=dimension_scores,
        evidence=evidence,
        critical_failures=critical_failures,
    )
```

- [ ] **Step 4: Implement heuristic judge evaluator**

Create `eval_agent/judge_evaluator.py`:

```python
from __future__ import annotations

from backend.evaluation_engine.domain import DialogueTrace, EvaluationResult, EvidenceItem, RubricSpec


def _assistant_turn_ids(trace: DialogueTrace) -> list[int]:
    return [turn.turn_id for turn in trace.turns if turn.speaker == "assistant"]


def _assistant_text(trace: DialogueTrace) -> str:
    return "\n".join(turn.content for turn in trace.turns if turn.speaker == "assistant")


def judge_trace(trace: DialogueTrace, rubric: RubricSpec) -> EvaluationResult:
    text = _assistant_text(trace)
    assistant_turn_ids = _assistant_turn_ids(trace)
    evidence: list[EvidenceItem] = []
    total = 0
    dimension_scores: dict[str, int] = {}

    for item in rubric.items:
        if item.check_type not in {"semantic", "rule_and_semantic"}:
            continue

        verdict = "partial"
        score = item.weight // 2
        reason = "语义证据不完整"

        if "合同" in item.criterion and ("合同" in text and "生效" in text):
            verdict = "pass"
            score = item.weight
            reason = "模型明确说明合同已生效"
        elif "退出" in item.criterion and ("取消" in text or "App" in text):
            verdict = "pass"
            score = item.weight
            reason = "模型回答了退出方式"
        elif "不想配送" in item.criterion and ("理解" in text or "记录" in text or "跑不了" in text):
            verdict = "pass"
            score = item.weight
            reason = "模型对不想配送场景做了安抚或记录"
        elif "超出职责" in item.criterion and ("确认后" in text or "回电" in text):
            verdict = "pass"
            score = item.weight
            reason = "模型对超出职责问题保持边界"

        total += score
        dimension_scores[item.dimension] = dimension_scores.get(item.dimension, 0) + score
        evidence.append(
            EvidenceItem(
                rubric_item_id=item.item_id,
                verdict=verdict,
                source=item.source,
                turn_ids=assistant_turn_ids[:1],
                reason=reason,
                score=score,
                max_score=item.weight,
            )
        )

    return EvaluationResult(
        trace_id=trace.trace_id,
        scenario_id=trace.scenario_id,
        total_score=total,
        dimension_scores=dimension_scores,
        evidence=evidence,
        critical_failures=[],
    )
```

- [ ] **Step 5: Run evaluator tests**

Run:

```bash
python3 -m pytest tests/test_rule_evaluator.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add eval_agent/rule_evaluator.py eval_agent/judge_evaluator.py tests/test_rule_evaluator.py
git commit -m "feat: evaluate traces with rules and judge"
```

Expected: commit succeeds, or skip in non-git workspace.

## Task 6: Run Storage, Engine, and Report Writer

**Files:**
- Create: `eval_agent/storage.py`
- Create: `eval_agent/report_writer.py`
- Create: `eval_agent/engine.py`
- Test: `tests/test_engine.py`
- Test: `tests/test_report_writer.py`

- [ ] **Step 1: Write failing engine and report tests**

Create `tests/test_engine.py`:

```python
from pathlib import Path

from backend.evaluation_engine.engine import run_full_evaluation
from backend.evaluation_engine.providers import FakeAssistantProvider, FakeUserProvider


RAW_TASK = """# Role
你是美团外卖骑手的站长。

# Task
通知骑手飞毛腿合同今日生效。

# Opening Line
你好，请问是王师傅吗？我是站长。

# Call Flow
1. 告知骑手今天飞毛腿合同已生效。
2. 询问骑手是否可以开始配送。
3. 尽量挽留不想配送的骑手。

# Knowledge Points (FAQ)
- 如需退出飞毛腿，必须在前一天 Z 点之前在 App 的"飞毛腿报名"中取消；次日生效。

# Constraints
- 每次回复控制在约 30 个字以内。
- 如被问及超出职责范围的问题，回复确认后再回电。
"""


def test_run_full_evaluation_persists_multi_scenario_run(tmp_path: Path):
    run = run_full_evaluation(
        raw_instruction=RAW_TASK,
        run_root=tmp_path,
        assistant_provider=FakeAssistantProvider(),
        user_provider=FakeUserProvider(),
        minimum_scenarios=5,
    )

    run_dir = tmp_path / run.run_id
    assert run_dir.exists()
    assert (run_dir / "task_spec.json").exists()
    assert (run_dir / "rubric_spec.json").exists()
    assert (run_dir / "scenarios.json").exists()
    assert (run_dir / "traces.jsonl").exists()
    assert (run_dir / "evaluation_results.json").exists()
    assert (run_dir / "report.md").exists()
    assert len(run.traces) >= 5
    assert len(run.results) >= 5
```

Create `tests/test_report_writer.py`:

```python
from backend.evaluation_engine.domain import EvaluationResult, EvidenceItem, Report, Scenario, ScenarioSet, TaskSpec
from backend.evaluation_engine.report_writer import write_markdown_report


def test_report_contains_quantitative_and_explainable_sections():
    task = TaskSpec(
        task_id="task_001",
        task_name="飞毛腿通知",
        role="站长",
        target_user="骑手",
        task_goal="通知合同生效",
        opening_line="你好",
    )
    scenarios = ScenarioSet(
        suite_id="suite_001",
        task_id="task_001",
        scenarios=[
            Scenario(
                scenario_id="scenario_normal",
                task_id="task_001",
                user_profile={"role": "骑手"},
                coverage_targets=["normal_completion"],
                initial_user_intent="正常确认",
                expected_test_focus="基础流程",
            )
        ],
    )
    result = EvaluationResult(
        trace_id="trace_001",
        scenario_id="scenario_normal",
        total_score=8,
        dimension_scores={"task_completion": 8},
        evidence=[
            EvidenceItem(
                rubric_item_id="r1",
                verdict="pass",
                source="Call Flow 第1步",
                turn_ids=[1],
                reason="模型明确说明合同生效",
                score=8,
                max_score=8,
            )
        ],
        critical_failures=[],
    )

    report = write_markdown_report("run_001", task, scenarios, [result])

    assert isinstance(report, Report)
    assert "总分" in report.markdown
    assert "场景覆盖矩阵" in report.markdown
    assert "Call Flow 第1步" in report.markdown
    assert "第 1 轮" in report.markdown
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest tests/test_engine.py tests/test_report_writer.py -v
```

Expected: FAIL with missing storage/engine/report modules.

- [ ] **Step 3: Implement file-backed storage**

Create `eval_agent/storage.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from pydantic import BaseModel


class RunStore:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def run_dir(self, run_id: str) -> Path:
        path = self.root / run_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def write_model(self, run_id: str, filename: str, model: BaseModel) -> None:
        path = self.run_dir(run_id) / filename
        path.write_text(model.model_dump_json(indent=2), encoding="utf-8")

    def write_json(self, run_id: str, filename: str, payload: object) -> None:
        path = self.run_dir(run_id) / filename
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def write_jsonl(self, run_id: str, filename: str, models: Iterable[BaseModel]) -> None:
        path = self.run_dir(run_id) / filename
        lines = [model.model_dump_json() for model in models]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def write_text(self, run_id: str, filename: str, content: str) -> None:
        path = self.run_dir(run_id) / filename
        path.write_text(content, encoding="utf-8")
```

- [ ] **Step 4: Implement report writer**

Create `eval_agent/report_writer.py`:

```python
from __future__ import annotations

from backend.evaluation_engine.domain import EvaluationResult, Report, ScenarioSet, TaskSpec


def _average_score(results: list[EvaluationResult]) -> float:
    if not results:
        return 0.0
    return round(sum(result.total_score for result in results) / len(results), 2)


def write_markdown_report(
    run_id: str,
    task_spec: TaskSpec,
    scenario_set: ScenarioSet,
    results: list[EvaluationResult],
) -> Report:
    lines = [
        f"# 评测报告 {run_id}",
        "",
        "## 任务概览",
        f"- 任务：{task_spec.task_name}",
        f"- 目标用户：{task_spec.target_user}",
        f"- 任务目标：{task_spec.task_goal}",
        "",
        "## 量化结果",
        f"- 总分：{_average_score(results)}",
        f"- 场景数：{len(scenario_set.scenarios)}",
        f"- 高风险项数量：{sum(len(result.critical_failures) for result in results)}",
        "",
        "## 场景覆盖矩阵",
        "| 场景 | 覆盖目标 | 结果 |",
        "| --- | --- | --- |",
    ]

    result_by_scenario = {result.scenario_id: result for result in results}
    for scenario in scenario_set.scenarios:
        result = result_by_scenario.get(scenario.scenario_id)
        status = "未运行" if result is None else ("失败" if result.critical_failures else "已评测")
        lines.append(f"| {scenario.scenario_id} | {', '.join(scenario.coverage_targets)} | {status} |")

    lines.extend(["", "## 扣分证据链"])
    for result in results:
        lines.append(f"### 场景 {result.scenario_id}")
        for item in result.evidence:
            turns = ", ".join(f"第 {turn_id} 轮" for turn_id in item.turn_ids)
            lines.extend(
                [
                    f"- 评测项：{item.rubric_item_id}",
                    f"  - 结论：{item.verdict}",
                    f"  - 得分：{item.score}/{item.max_score}",
                    f"  - 指令依据：{item.source}",
                    f"  - 对话证据：{turns}",
                    f"  - 原因：{item.reason}",
                ]
            )

    markdown = "\n".join(lines) + "\n"
    return Report(run_id=run_id, task_id=task_spec.task_id, markdown=markdown)
```

- [ ] **Step 5: Implement engine orchestrator**

Create `eval_agent/engine.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from backend.evaluation_engine.dialogue_runner import run_dialogue
from backend.evaluation_engine.domain import DialogueTrace, EvaluationResult, Report, RunConfig
from backend.evaluation_engine.instruction_parser import parse_instruction
from backend.evaluation_engine.judge_evaluator import judge_trace
from backend.evaluation_engine.providers import AssistantProvider, UserProvider
from backend.evaluation_engine.report_writer import write_markdown_report
from backend.evaluation_engine.rubric_builder import build_rubric
from backend.evaluation_engine.rule_evaluator import evaluate_rules
from backend.evaluation_engine.scenario_generator import generate_scenarios
from backend.evaluation_engine.storage import RunStore


@dataclass
class FullRunResult:
    run_id: str
    traces: list[DialogueTrace]
    results: list[EvaluationResult]
    report: Report


def _merge_results(rule_result: EvaluationResult, judge_result: EvaluationResult) -> EvaluationResult:
    evidence = rule_result.evidence + judge_result.evidence
    dimension_scores = dict(rule_result.dimension_scores)
    for key, value in judge_result.dimension_scores.items():
        dimension_scores[key] = dimension_scores.get(key, 0) + value
    return EvaluationResult(
        trace_id=rule_result.trace_id,
        scenario_id=rule_result.scenario_id,
        total_score=rule_result.total_score + judge_result.total_score,
        dimension_scores=dimension_scores,
        evidence=evidence,
        critical_failures=rule_result.critical_failures + judge_result.critical_failures,
    )


def run_full_evaluation(
    raw_instruction: str,
    run_root: Path,
    assistant_provider: AssistantProvider,
    user_provider: UserProvider,
    minimum_scenarios: int = 5,
) -> FullRunResult:
    run_id = f"run_{uuid4().hex[:8]}"
    store = RunStore(run_root)
    task_spec = parse_instruction(raw_instruction, task_id="task_001")
    rubric = build_rubric(task_spec)
    scenario_set = generate_scenarios(task_spec, rubric, minimum=minimum_scenarios)
    run_config = RunConfig(run_id=run_id, task_id=task_spec.task_id)

    traces: list[DialogueTrace] = []
    results: list[EvaluationResult] = []
    for scenario in scenario_set.scenarios:
        trace = run_dialogue(task_spec, scenario, run_config, assistant_provider, user_provider)
        traces.append(trace)
        rule_result = evaluate_rules(trace, rubric)
        judge_result = judge_trace(trace, rubric)
        results.append(_merge_results(rule_result, judge_result))

    report = write_markdown_report(run_id, task_spec, scenario_set, results)

    store.write_model(run_id, "run_config.json", run_config)
    store.write_model(run_id, "task_spec.json", task_spec)
    store.write_model(run_id, "rubric_spec.json", rubric)
    store.write_model(run_id, "scenarios.json", scenario_set)
    store.write_jsonl(run_id, "traces.jsonl", traces)
    store.write_json(run_id, "evaluation_results.json", [result.model_dump() for result in results])
    store.write_text(run_id, "report.md", report.markdown)

    return FullRunResult(run_id=run_id, traces=traces, results=results, report=report)
```

- [ ] **Step 6: Run engine/report tests**

Run:

```bash
python3 -m pytest tests/test_engine.py tests/test_report_writer.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add eval_agent/storage.py eval_agent/report_writer.py eval_agent/engine.py tests/test_engine.py tests/test_report_writer.py
git commit -m "feat: orchestrate full multi-scenario evaluation runs"
```

Expected: commit succeeds, or skip in non-git workspace.

## Task 7: FastAPI Web Demo

**Files:**
- Create: `eval_agent/app.py`
- Create: `eval_agent/web/index.html`

- [ ] **Step 1: Add FastAPI app**

Create `eval_agent/app.py`:

```python
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from backend.evaluation_engine.engine import run_full_evaluation
from backend.evaluation_engine.providers import FakeAssistantProvider, FakeUserProvider


app = FastAPI(title="Dialogue Eval Platform")
RUN_ROOT = Path("runs")
WEB_INDEX = Path(__file__).parent / "web" / "index.html"


class RunRequest(BaseModel):
    instruction: str


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return WEB_INDEX.read_text(encoding="utf-8")


@app.post("/api/runs")
def create_run(request: RunRequest) -> dict[str, object]:
    result = run_full_evaluation(
        raw_instruction=request.instruction,
        run_root=RUN_ROOT,
        assistant_provider=FakeAssistantProvider(),
        user_provider=FakeUserProvider(),
        minimum_scenarios=5,
    )
    return {
        "run_id": result.run_id,
        "trace_count": len(result.traces),
        "result_count": len(result.results),
        "report": result.report.markdown,
    }
```

- [ ] **Step 2: Add Web wizard page**

Create `eval_agent/web/index.html`:

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>多轮对话评测工作台</title>
    <style>
      body { font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0; background: #f6f7f9; color: #171717; }
      main { max-width: 1120px; margin: 0 auto; padding: 32px; }
      section { background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 20px; margin-bottom: 16px; }
      textarea { width: 100%; min-height: 220px; font-size: 14px; line-height: 1.5; }
      button { background: #ffd100; border: 1px solid #d6ad00; border-radius: 6px; padding: 10px 14px; cursor: pointer; font-weight: 600; }
      pre { white-space: pre-wrap; word-break: break-word; background: #111827; color: #f9fafb; padding: 16px; border-radius: 8px; max-height: 520px; overflow: auto; }
      .steps { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; margin: 16px 0; }
      .step { background: #eef2ff; border-radius: 6px; padding: 8px; text-align: center; font-size: 13px; }
    </style>
  </head>
  <body>
    <main>
      <h1>复杂指令多轮对话评测工作台</h1>
      <div class="steps">
        <div class="step">任务输入</div>
        <div class="step">指令解析</div>
        <div class="step">场景生成</div>
        <div class="step">对话评测</div>
        <div class="step">评测报告</div>
      </div>
      <section>
        <h2>任务指令</h2>
        <textarea id="instruction"># Role
你是美团外卖骑手的站长。

# Task
通知骑手飞毛腿合同今日生效。

# Opening Line
你好，请问是王师傅吗？我是站长。

# Call Flow
1. 告知骑手今天飞毛腿合同已生效。
2. 询问骑手是否可以开始配送。
3. 尽量挽留不想配送的骑手。

# Knowledge Points (FAQ)
- 如需退出飞毛腿，必须在前一天 Z 点之前在 App 的"飞毛腿报名"中取消；次日生效。

# Constraints
- 每次回复控制在约 30 个字以内。
- 如被问及超出职责范围的问题，回复确认后再回电。</textarea>
        <p><button id="run">一站式运行评测</button></p>
      </section>
      <section>
        <h2>评测报告</h2>
        <pre id="report">等待运行。</pre>
      </section>
    </main>
    <script>
      const button = document.getElementById("run");
      const report = document.getElementById("report");
      button.addEventListener("click", async () => {
        button.disabled = true;
        report.textContent = "运行中：正在生成场景、执行多轮对话并评测...";
        try {
          const response = await fetch("/api/runs", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ instruction: document.getElementById("instruction").value }),
          });
          const data = await response.json();
          report.textContent = `run_id: ${data.run_id}\ntrace_count: ${data.trace_count}\n\n${data.report}`;
        } catch (error) {
          report.textContent = String(error);
        } finally {
          button.disabled = false;
        }
      });
    </script>
  </body>
</html>
```

- [ ] **Step 3: Run all tests**

Run:

```bash
python3 -m pytest -v
```

Expected: PASS.

- [ ] **Step 4: Start Web app**

Run:

```bash
python3 -m uvicorn backend.evaluation_engine.app:app --host 127.0.0.1 --port 8000
```

Expected: server starts and prints `Uvicorn running on http://127.0.0.1:8000`.

- [ ] **Step 5: Commit**

```bash
git add eval_agent/app.py eval_agent/web/index.html
git commit -m "feat: add web evaluation wizard"
```

Expected: commit succeeds, or skip in non-git workspace.

## Task 8: Final Verification

**Files:**
- Verify generated files under `runs/{run_id}/`
- Verify Web app at `http://127.0.0.1:8000`

- [ ] **Step 1: Run complete test suite**

Run:

```bash
python3 -m pytest -v
```

Expected: all tests PASS.

- [ ] **Step 2: Run a sample full evaluation from Python**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
from backend.evaluation_engine.engine import run_full_evaluation
from backend.evaluation_engine.providers import FakeAssistantProvider, FakeUserProvider

raw = """# Role
你是美团外卖骑手的站长。

# Task
通知骑手飞毛腿合同今日生效。

# Opening Line
你好，请问是王师傅吗？我是站长。

# Call Flow
1. 告知骑手今天飞毛腿合同已生效。
2. 询问骑手是否可以开始配送。
3. 尽量挽留不想配送的骑手。

# Knowledge Points (FAQ)
- 如需退出飞毛腿，必须在前一天 Z 点之前在 App 的"飞毛腿报名"中取消；次日生效。

# Constraints
- 每次回复控制在约 30 个字以内。
- 如被问及超出职责范围的问题，回复确认后再回电。
"""

result = run_full_evaluation(raw, Path("runs"), FakeAssistantProvider(), FakeUserProvider())
print(result.run_id)
print(len(result.traces), len(result.results))
print(result.report.markdown.splitlines()[0])
PY
```

Expected: prints a `run_...` id, `5 5` or more, and `# 评测报告 ...`.

- [ ] **Step 3: Verify run artifacts exist**

Run:

```bash
latest="$(ls -td runs/run_* | head -1)" && find "$latest" -maxdepth 1 -type f -print
```

Expected: includes `run_config.json`, `task_spec.json`, `rubric_spec.json`, `scenarios.json`, `traces.jsonl`, `evaluation_results.json`, and `report.md`.

- [ ] **Step 4: Verify report contains three hard requirements**

Run:

```bash
latest="$(ls -td runs/run_* | head -1)" && grep -E "总分|场景覆盖矩阵|扣分证据链" "$latest/report.md"
```

Expected: prints all three headings or lines.

- [ ] **Step 5: Commit verification notes**

Create or update a short verification note:

```bash
mkdir -p docs
cat > docs/verification.md <<'EOF'
# Verification

- Full pytest suite passes.
- Sample run creates a multi-scenario run under runs/{run_id}.
- Report contains quantitative score, scenario coverage matrix, and evidence chains.
- Web demo supports one-click evaluation from task instruction to report.
EOF
git add docs/verification.md
git commit -m "docs: record verification results"
```

Expected: commit succeeds, or skip in non-git workspace after creating `docs/verification.md`.

## Self-Review Notes

- Spec coverage: This plan implements the approved spec sections: Web flow, JSON data objects, multi-scenario `ScenarioSet`, one-click full run, rule/Judge evaluation, report evidence chains, run storage, and Web demo.
- Placeholder scan: No unresolved placeholder markers are used. Code snippets define concrete behavior.
- Type consistency: Names match across tasks: `TaskSpec`, `RubricSpec`, `ScenarioSet`, `DialogueTrace`, `EvaluationResult`, `RunConfig`, `RunStore`, `run_full_evaluation`.
- Scope boundary: The plan implements比赛 MVP plus production-safe multi-scenario/run abstractions. It does not implement login, multi-tenant auth, model leaderboard, production外呼接入, or async workers.
