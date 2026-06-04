# Evaluator Reliability Quality Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add quantitative reliability proof for the evaluation system by producing `quality_summary` for every run and a calibration self-check against sample-library `expected_labels`.

**Architecture:** Add two focused backend modules under `backend/evaluation_engine`: one computes per-run chain quality, the other compares evaluator output against calibration ground truth labels. Integrate the summaries into `FullRunResult`, persisted run artifacts, API payloads, and report text without changing the existing stage execution order.

**Tech Stack:** Python 3.9, Pydantic domain models, FastAPI service payloads, existing pytest suite, existing React frontend API consumption.

---

## File Structure

- Create `backend/evaluation_engine/quality_summary.py`  
  Owns per-run quality gate metrics: scenario coverage/diversity, Rubric suitability, Judge漏项, evidence traceability, report completeness, timing anomalies, and an overall status.

- Create `backend/evaluation_engine/calibration_benchmark.py`  
  Owns evaluator self-check metrics against calibration sample `expected_labels`: verdict accuracy, critical false-negative/false-positive counts, evidence turn hit rate, and mismatch rows.

- Modify `backend/evaluation_engine/engine.py`  
  Adds `quality_summary` and `calibration_self_check` to `FullRunResult`, computes them after report generation, and persists JSON artifacts.

- Modify `backend/evaluation_engine/app.py`  
  Adds summaries to run API response/detail payloads so frontend/report pages can read them.

- Modify `backend/evaluation_engine/report_writer.py`  
  Adds a reliability section to the Markdown report when summaries are present.

- Modify `backend/eval_agent/services/calibration_service.py` and route files if needed  
  Adds a calibration benchmark API payload for evaluator self-check without requiring a full model run.

- Modify frontend response types and report rendering only after backend payload is stable  
  Likely files: `frontend/src/api/runs.ts`, `frontend/src/pages/RunDetailPage.tsx`, `frontend/src/pages/EvaluationWizardPage.tsx`, `frontend/src/pages/QuickEvaluationPage.tsx`, `frontend/src/components/evaluation/RunCharts.tsx`.

---

### Task 1: Add Per-Run Quality Summary Module

**Files:**
- Create: `backend/evaluation_engine/quality_summary.py`
- Test: `tests/test_quality_summary.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_quality_summary.py`:

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
from backend.evaluation_engine.quality_summary import build_quality_summary


def _task():
    return TaskSpec(
        task_id="task_quality",
        task_name="飞毛腿通知",
        role="站长",
        target_user="骑手",
        task_goal="通知合同生效",
        opening_line="你好",
    )


def _rubric():
    return RubricSpec(
        rubric_id="rubric_quality",
        task_id="task_quality",
        items=[
            RubricItem(
                item_id="contract_notice",
                dimension="task_completion",
                criterion="告知合同生效",
                source="Call Flow 第1步",
                check_type="semantic",
                weight=4,
                critical=True,
            ),
            RubricItem(
                item_id="short_reply",
                dimension="conversation_quality",
                criterion="短句回复",
                source="Constraints 第1条",
                check_type="rule",
                weight=2,
            ),
        ],
    )


def _scenarios():
    return ScenarioSet(
        suite_id="suite_quality",
        task_id="task_quality",
        scenarios=[
            Scenario(
                scenario_id="normal",
                task_id="task_quality",
                user_profile={"role": "骑手"},
                coverage_targets=["contract_notice", "short_reply"],
                initial_user_intent="正常确认",
                expected_test_focus="基础流程",
                difficulty="L1",
                scenario_type="normal_confirmation",
                risk_tags=["baseline"],
            ),
            Scenario(
                scenario_id="reward",
                task_id="task_quality",
                user_profile={"role": "骑手"},
                coverage_targets=["reward_question", "boundary_no_extra_promise"],
                initial_user_intent="追问奖励",
                expected_test_focus="边界风险",
                difficulty="L4",
                scenario_type="reward_boundary",
                risk_tags=["safety_boundary"],
            ),
        ],
    )


def test_quality_summary_reports_coverage_traceability_and_timing_health():
    traces = [
        DialogueTrace(
            trace_id="trace_1",
            run_id="run_quality",
            task_id="task_quality",
            scenario_id="normal",
            turns=[
                Turn(turn_id=1, speaker="assistant", content="合同已生效。"),
                Turn(turn_id=2, speaker="user_simulator", content="好。"),
            ],
            termination_reason="task_completed",
        )
    ]
    results = [
        EvaluationResult(
            trace_id="trace_1",
            scenario_id="normal",
            total_score=4,
            dimension_scores={"task_completion": 4},
            evidence=[
                EvidenceItem(
                    rubric_item_id="contract_notice",
                    verdict="pass",
                    source="Call Flow 第1步",
                    turn_ids=[1],
                    reason="命中合同生效",
                    score=4,
                    max_score=4,
                ),
                EvidenceItem(
                    rubric_item_id="short_reply",
                    verdict="fail",
                    source="Constraints 第1条",
                    turn_ids=[],
                    reason="Judge 未返回该评测项结果",
                    score=0,
                    max_score=2,
                ),
            ],
            critical_failures=[],
        )
    ]
    summary = build_quality_summary(
        task_spec=_task(),
        rubric=_rubric(),
        scenario_set=_scenarios(),
        traces=traces,
        results=results,
        report_markdown="# 评测报告\n\n## 量化结果\n\n## 证据链\n",
        stage_timings_ms={
            "instruction_parsing": 1,
            "rubric_generation": 1200,
            "scenario_generation": 900,
            "scenario_execution": 1500,
            "report_generation": 600,
        },
        stage_diagnostics={
            "rubric_generation": {"quality_report": {"is_suitable": True}},
        },
    )

    assert summary["overall_status"] == "warn"
    assert summary["scenario_coverage"]["scenario_count"] == 2
    assert summary["scenario_coverage"]["coverage_target_count"] >= 4
    assert summary["scenario_coverage"]["difficulty_count"] == 2
    assert summary["judge_integrity"]["expected_rubric_items"] == 2
    assert summary["judge_integrity"]["missing_item_count"] == 1
    assert summary["evidence_traceability"]["traceable_evidence_rate"] == 50.0
    assert summary["report_integrity"]["has_quantitative_result"] is True
    assert summary["timing_health"]["zero_duration_stages"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/test_quality_summary.py::test_quality_summary_reports_coverage_traceability_and_timing_health -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'backend.evaluation_engine.quality_summary'`.

- [ ] **Step 3: Implement `quality_summary.py`**

Create `backend/evaluation_engine/quality_summary.py`:

```python
from __future__ import annotations

from backend.evaluation_engine.domain import (
    DialogueTrace,
    EvaluationResult,
    RubricSpec,
    ScenarioSet,
    TaskSpec,
)


REQUIRED_REPORT_SECTIONS = {
    "has_quantitative_result": "## 量化结果",
    "has_evidence_chain": "## 证据链",
}


def build_quality_summary(
    task_spec: TaskSpec,
    rubric: RubricSpec,
    scenario_set: ScenarioSet,
    traces: list[DialogueTrace],
    results: list[EvaluationResult],
    report_markdown: str,
    stage_timings_ms: dict[str, int],
    stage_diagnostics: dict[str, dict[str, object]],
) -> dict[str, object]:
    scenario_coverage = _scenario_coverage(scenario_set)
    rubric_health = _rubric_health(stage_diagnostics)
    judge_integrity = _judge_integrity(rubric, results)
    evidence_traceability = _evidence_traceability(traces, results)
    report_integrity = _report_integrity(report_markdown)
    timing_health = _timing_health(stage_timings_ms)
    overall_status = _overall_status(
        rubric_health,
        judge_integrity,
        evidence_traceability,
        report_integrity,
        timing_health,
    )
    return {
        "task_id": task_spec.task_id,
        "overall_status": overall_status,
        "scenario_coverage": scenario_coverage,
        "rubric_health": rubric_health,
        "judge_integrity": judge_integrity,
        "evidence_traceability": evidence_traceability,
        "report_integrity": report_integrity,
        "timing_health": timing_health,
    }


def _scenario_coverage(scenario_set: ScenarioSet) -> dict[str, object]:
    scenarios = scenario_set.scenarios
    coverage_targets = {target for scenario in scenarios for target in scenario.coverage_targets}
    risk_tags = {tag for scenario in scenarios for tag in scenario.risk_tags}
    difficulties = {scenario.difficulty for scenario in scenarios if scenario.difficulty}
    scenario_types = {scenario.scenario_type for scenario in scenarios if scenario.scenario_type}
    diversity_score = min(
        100.0,
        round(
            len(difficulties) * 12
            + len(scenario_types) * 8
            + min(len(coverage_targets), 12) * 3,
            1,
        ),
    )
    return {
        "scenario_count": len(scenarios),
        "coverage_target_count": len(coverage_targets),
        "risk_tag_count": len(risk_tags),
        "difficulty_count": len(difficulties),
        "scenario_type_count": len(scenario_types),
        "diversity_score": diversity_score,
        "coverage_targets": sorted(coverage_targets),
    }


def _rubric_health(stage_diagnostics: dict[str, dict[str, object]]) -> dict[str, object]:
    diagnostic = stage_diagnostics.get("rubric_generation", {})
    quality_report = diagnostic.get("quality_report")
    is_suitable = True
    if isinstance(quality_report, dict) and "is_suitable" in quality_report:
        is_suitable = bool(quality_report["is_suitable"])
    return {
        "is_suitable": is_suitable,
        "fallback_used": bool(diagnostic.get("fallback_used", False)),
        "fallback_reason": str(diagnostic.get("fallback_reason", "")),
    }


def _judge_integrity(rubric: RubricSpec, results: list[EvaluationResult]) -> dict[str, object]:
    expected_items = {item.item_id for item in rubric.items if item.check_type in {"semantic", "rule_and_semantic", "rule"}}
    evidence_items = [item for result in results for item in result.evidence]
    observed_items = {item.rubric_item_id for item in evidence_items}
    missing_by_reason = [
        item.rubric_item_id
        for item in evidence_items
        if "Judge 未返回" in item.reason or "漏评" in item.explanation
    ]
    missing_items = sorted((expected_items - observed_items) | set(missing_by_reason))
    score_overflow_items = [
        item.rubric_item_id for item in evidence_items if item.score > item.max_score
    ]
    return {
        "expected_rubric_items": len(expected_items),
        "observed_rubric_items": len(observed_items),
        "missing_item_count": len(missing_items),
        "missing_items": missing_items,
        "score_overflow_count": len(score_overflow_items),
        "score_overflow_items": score_overflow_items,
    }


def _evidence_traceability(
    traces: list[DialogueTrace],
    results: list[EvaluationResult],
) -> dict[str, object]:
    valid_turn_ids = {
        trace.scenario_id: {turn.turn_id for turn in trace.turns}
        for trace in traces
    }
    evidence_items = [item for result in results for item in result.evidence]
    traceable = 0
    invalid_turn_refs = []
    for result in results:
        valid_ids = valid_turn_ids.get(result.scenario_id, set())
        for item in result.evidence:
            if item.turn_ids and set(item.turn_ids).issubset(valid_ids):
                traceable += 1
            invalid_ids = [turn_id for turn_id in item.turn_ids if turn_id not in valid_ids]
            if invalid_ids:
                invalid_turn_refs.append(
                    {
                        "scenario_id": result.scenario_id,
                        "rubric_item_id": item.rubric_item_id,
                        "invalid_turn_ids": invalid_ids,
                    }
                )
    total = len(evidence_items)
    rate = 0.0 if total == 0 else round(traceable * 100 / total, 1)
    return {
        "evidence_count": total,
        "traceable_evidence_count": traceable,
        "traceable_evidence_rate": rate,
        "invalid_turn_ref_count": len(invalid_turn_refs),
        "invalid_turn_refs": invalid_turn_refs,
    }


def _report_integrity(report_markdown: str) -> dict[str, object]:
    result = {
        key: marker in report_markdown
        for key, marker in REQUIRED_REPORT_SECTIONS.items()
    }
    result["missing_sections"] = [
        marker
        for key, marker in REQUIRED_REPORT_SECTIONS.items()
        if not result[key]
    ]
    return result


def _timing_health(stage_timings_ms: dict[str, int]) -> dict[str, object]:
    zero_stages = [
        name for name, value in stage_timings_ms.items() if int(value) <= 0
    ]
    slow_stages = [
        {"stage": name, "duration_ms": int(value)}
        for name, value in stage_timings_ms.items()
        if int(value) >= 180000
    ]
    return {
        "zero_duration_stages": zero_stages,
        "slow_stages": slow_stages,
        "total_duration_ms": sum(int(value) for value in stage_timings_ms.values()),
    }


def _overall_status(
    rubric_health: dict[str, object],
    judge_integrity: dict[str, object],
    evidence_traceability: dict[str, object],
    report_integrity: dict[str, object],
    timing_health: dict[str, object],
) -> str:
    if (
        not rubric_health["is_suitable"]
        or judge_integrity["score_overflow_count"]
        or evidence_traceability["invalid_turn_ref_count"]
        or report_integrity["missing_sections"]
    ):
        return "fail"
    if (
        judge_integrity["missing_item_count"]
        or evidence_traceability["traceable_evidence_rate"] < 80
        or timing_health["zero_duration_stages"]
        or timing_health["slow_stages"]
    ):
        return "warn"
    return "pass"
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python3 -m pytest tests/test_quality_summary.py -q
```

Expected: PASS.

---

### Task 2: Add Calibration Expected-Label Self-Check

**Files:**
- Create: `backend/evaluation_engine/calibration_benchmark.py`
- Test: `tests/test_calibration_benchmark.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_calibration_benchmark.py`:

```python
from backend.evaluation_engine.calibration_benchmark import (
    compare_evaluator_output_to_expected_labels,
)
from backend.evaluation_engine.domain import EvaluationResult, EvidenceItem


def test_calibration_self_check_computes_accuracy_and_evidence_turn_hit_rate():
    samples = [
        {
            "sample_id": "sample_1",
            "expected_labels": [
                {
                    "rubric_item_id": "contract_notice",
                    "expected_verdict": "pass",
                    "evidence_turn_ids": [3],
                    "severity": "normal",
                },
                {
                    "rubric_item_id": "boundary_no_extra_promise",
                    "expected_verdict": "fail",
                    "evidence_turn_ids": [5],
                    "severity": "critical",
                },
            ],
        }
    ]
    evaluator_results = {
        "sample_1": EvaluationResult(
            trace_id="trace_1",
            scenario_id="sample_1",
            total_score=1,
            dimension_scores={"task_completion": 1},
            evidence=[
                EvidenceItem(
                    rubric_item_id="contract_notice",
                    verdict="pass",
                    source="expected_labels",
                    turn_ids=[3],
                    reason="命中合同生效",
                    score=1,
                    max_score=1,
                ),
                EvidenceItem(
                    rubric_item_id="boundary_no_extra_promise",
                    verdict="pass",
                    source="expected_labels",
                    turn_ids=[4],
                    reason="误判为通过",
                    score=1,
                    max_score=1,
                ),
            ],
        )
    }

    summary = compare_evaluator_output_to_expected_labels(samples, evaluator_results)

    assert summary["sample_count"] == 1
    assert summary["label_count"] == 2
    assert summary["verdict_accuracy"] == 50.0
    assert summary["critical_false_pass_count"] == 1
    assert summary["critical_false_fail_count"] == 0
    assert summary["evidence_turn_hit_rate"] == 50.0
    assert summary["mismatches"][0]["rubric_item_id"] == "boundary_no_extra_promise"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/test_calibration_benchmark.py::test_calibration_self_check_computes_accuracy_and_evidence_turn_hit_rate -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'backend.evaluation_engine.calibration_benchmark'`.

- [ ] **Step 3: Implement `calibration_benchmark.py`**

Create `backend/evaluation_engine/calibration_benchmark.py`:

```python
from __future__ import annotations

from typing import Any

from backend.evaluation_engine.domain import EvaluationResult


PASSING_VERDICTS = {"pass"}
FAILING_VERDICTS = {"fail", "needs_review"}


def compare_evaluator_output_to_expected_labels(
    samples: list[dict[str, Any]],
    evaluator_results: dict[str, EvaluationResult],
) -> dict[str, object]:
    label_count = 0
    verdict_hits = 0
    evidence_turn_hits = 0
    critical_false_pass_count = 0
    critical_false_fail_count = 0
    mismatches = []

    for sample in samples:
        sample_id = str(sample.get("sample_id", ""))
        result = evaluator_results.get(sample_id)
        evidence_by_item = {}
        if result is not None:
            evidence_by_item = {
                item.rubric_item_id: item for item in result.evidence
            }

        for label in sample.get("expected_labels", []):
            label_count += 1
            rubric_item_id = str(label.get("rubric_item_id", ""))
            expected_verdict = str(label.get("expected_verdict", ""))
            expected_turn_ids = set(label.get("evidence_turn_ids") or [])
            severity = str(label.get("severity", "normal"))
            evidence = evidence_by_item.get(rubric_item_id)
            actual_verdict = evidence.verdict if evidence is not None else "missing"
            actual_turn_ids = set(evidence.turn_ids if evidence is not None else [])

            verdict_match = _verdict_matches(expected_verdict, actual_verdict)
            turn_match = bool(expected_turn_ids and actual_turn_ids & expected_turn_ids)
            if verdict_match:
                verdict_hits += 1
            if turn_match:
                evidence_turn_hits += 1

            if severity == "critical" and expected_verdict in FAILING_VERDICTS and actual_verdict == "pass":
                critical_false_pass_count += 1
            if severity == "critical" and expected_verdict == "pass" and actual_verdict in FAILING_VERDICTS | {"missing"}:
                critical_false_fail_count += 1

            if not verdict_match or not turn_match:
                mismatches.append(
                    {
                        "sample_id": sample_id,
                        "rubric_item_id": rubric_item_id,
                        "expected_verdict": expected_verdict,
                        "actual_verdict": actual_verdict,
                        "expected_turn_ids": sorted(expected_turn_ids),
                        "actual_turn_ids": sorted(actual_turn_ids),
                        "verdict_match": verdict_match,
                        "evidence_turn_match": turn_match,
                        "severity": severity,
                    }
                )

    return {
        "sample_count": len(samples),
        "label_count": label_count,
        "verdict_accuracy": _percent(verdict_hits, label_count),
        "evidence_turn_hit_rate": _percent(evidence_turn_hits, label_count),
        "critical_false_pass_count": critical_false_pass_count,
        "critical_false_fail_count": critical_false_fail_count,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches[:50],
    }


def _verdict_matches(expected: str, actual: str) -> bool:
    if expected == actual:
        return True
    if expected in FAILING_VERDICTS and actual in FAILING_VERDICTS:
        return True
    return False


def _percent(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator * 100 / denominator, 1)
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python3 -m pytest tests/test_calibration_benchmark.py -q
```

Expected: PASS.

---

### Task 3: Integrate `quality_summary` Into Full Run Artifacts and API Payloads

**Files:**
- Modify: `backend/evaluation_engine/engine.py`
- Modify: `backend/evaluation_engine/app.py`
- Test: `tests/test_engine.py` or `tests/test_app.py`

- [ ] **Step 1: Write failing integration test**

Append to `tests/test_app.py`:

```python
def test_create_run_returns_quality_summary_and_persists_artifact(tmp_path, monkeypatch):
    from backend.eval_agent.services import run_service
    from fastapi.testclient import TestClient
    from backend.eval_agent.api.main import create_app

    monkeypatch.setattr(run_service, "RUN_ROOT", tmp_path)
    client = TestClient(create_app())

    response = client.post(
        "/api/runs",
        json={
            "instruction": "# Role\n你是站长。\n# Task\n通知合同生效。\n# Opening Line\n你好",
            "minimum_scenarios": 2,
            "model_config": {"provider": "mock", "model_name": "mock"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["quality_summary"]["overall_status"] in {"pass", "warn", "fail"}
    assert "scenario_coverage" in payload["quality_summary"]
    assert "evidence_traceability" in payload["quality_summary"]
    assert (tmp_path / payload["run_id"] / "quality_summary.json").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/test_app.py::test_create_run_returns_quality_summary_and_persists_artifact -q
```

Expected: FAIL because response does not include `quality_summary`.

- [ ] **Step 3: Modify `engine.py`**

Implementation instructions:

1. Import `build_quality_summary`.
2. Add `quality_summary: dict[str, object] = field(default_factory=dict)` to `FullRunResult`.
3. After `report = _timed_stage(...)`, compute:

```python
quality_summary = build_quality_summary(
    task_spec=task_spec,
    rubric=rubric,
    scenario_set=scenario_set,
    traces=traces,
    results=results,
    report_markdown=report.markdown,
    stage_timings_ms=stage_timings_ms,
    stage_diagnostics=stage_diagnostics,
)
```

4. Persist:

```python
store.write_json(run_id, "quality_summary.json", quality_summary)
```

5. Return it in `FullRunResult`.

- [ ] **Step 4: Modify `app.py` response/detail helpers**

Find the run response payload builder and run detail loader. Add:

```python
"quality_summary": result.quality_summary,
```

For persisted detail, read `quality_summary.json` if present:

```python
quality_summary = store.read_json(run_id, "quality_summary.json", default={})
```

Use the existing storage helper style in `backend/evaluation_engine/app.py`.

- [ ] **Step 5: Run integration test**

Run:

```bash
python3 -m pytest tests/test_app.py::test_create_run_returns_quality_summary_and_persists_artifact -q
```

Expected: PASS.

---

### Task 4: Add Calibration Self-Check API Payload

**Files:**
- Modify: `backend/eval_agent/services/calibration_service.py`
- Modify: calibration route file under `backend/eval_agent/api/routes/`
- Test: `tests/test_backend_scaffold.py` or `tests/test_app.py`

- [ ] **Step 1: Write failing API test**

Append to `tests/test_backend_scaffold.py`:

```python
def test_calibration_self_check_endpoint_exposes_expected_label_metrics():
    from fastapi.testclient import TestClient
    from backend.eval_agent.api.main import create_app

    client = TestClient(create_app())
    response = client.get("/api/calibration/self-check")

    assert response.status_code == 200
    payload = response.json()
    assert "sample_count" in payload
    assert "label_count" in payload
    assert "verdict_accuracy" in payload
    assert "evidence_turn_hit_rate" in payload
    assert "critical_false_pass_count" in payload
    assert "critical_false_fail_count" in payload
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/test_backend_scaffold.py::test_calibration_self_check_endpoint_exposes_expected_label_metrics -q
```

Expected: FAIL with HTTP 404.

- [ ] **Step 3: Implement payload service**

In `backend/eval_agent/services/calibration_service.py`, add:

```python
from backend.evaluation_engine.calibration_benchmark import (
    compare_evaluator_output_to_expected_labels,
)


def calibration_self_check_payload() -> dict[str, object]:
    dataset = load_calibration_dataset()
    # First implementation publishes ground-truth readiness without running model calls.
    # It uses empty evaluator results so missing evaluator outputs are visible.
    return compare_evaluator_output_to_expected_labels(dataset, {})
```

This first endpoint proves the dataset has machine-readable expected labels and exposes the metric contract. A later task can feed real benchmark `EvaluationResult` objects into the same function.

- [ ] **Step 4: Add API route**

In the calibration route file, import and expose:

```python
@router.get("/self-check")
def calibration_self_check() -> dict[str, object]:
    return calibration_self_check_payload()
```

- [ ] **Step 5: Run endpoint test**

Run:

```bash
python3 -m pytest tests/test_backend_scaffold.py::test_calibration_self_check_endpoint_exposes_expected_label_metrics -q
```

Expected: PASS.

---

### Task 5: Add Reliability Section to Markdown Report

**Files:**
- Modify: `backend/evaluation_engine/report_writer.py`
- Test: `tests/test_report_writer.py`

- [ ] **Step 1: Write failing report test**

Append to `tests/test_report_writer.py`:

```python
def test_report_renders_quality_summary_when_provided():
    task = TaskSpec(
        task_id="task_001",
        task_name="飞毛腿通知",
        role="站长",
        target_user="骑手",
        task_goal="通知合同生效",
        opening_line="你好",
    )
    scenarios = ScenarioSet(suite_id="suite_001", task_id="task_001", scenarios=[])
    report = write_markdown_report(
        "run_001",
        task,
        scenarios,
        [],
        quality_summary={
            "overall_status": "warn",
            "scenario_coverage": {"scenario_count": 5, "diversity_score": 86.0},
            "judge_integrity": {"missing_item_count": 1, "score_overflow_count": 0},
            "evidence_traceability": {"traceable_evidence_rate": 92.5},
            "timing_health": {"total_duration_ms": 12000, "slow_stages": []},
        },
    )

    assert "## 评测系统可靠性" in report.markdown
    assert "链路状态：warn" in report.markdown
    assert "场景数：5" in report.markdown
    assert "证据轮次命中率：92.5%" in report.markdown
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/test_report_writer.py::test_report_renders_quality_summary_when_provided -q
```

Expected: FAIL because `write_markdown_report` does not accept `quality_summary`.

- [ ] **Step 3: Modify report writer signature and content**

Change signature:

```python
def write_markdown_report(
    run_id: str,
    task_spec: TaskSpec,
    scenario_set: ScenarioSet,
    results: list[EvaluationResult],
    input_data_summary: Optional[dict[str, object]] = None,
    quality_summary: Optional[dict[str, object]] = None,
) -> Report:
```

Before `## 改进建议`, add:

```python
if quality_summary:
    lines.extend(["", "## 评测系统可靠性"])
    lines.extend(_quality_summary_lines(quality_summary))
```

Add helper:

```python
def _quality_summary_lines(summary: dict[str, object]) -> list[str]:
    scenario = summary.get("scenario_coverage", {})
    judge = summary.get("judge_integrity", {})
    evidence = summary.get("evidence_traceability", {})
    timing = summary.get("timing_health", {})
    return [
        "- 链路状态：%s" % summary.get("overall_status", "unknown"),
        "- 场景数：%s，场景多样性：%s"
        % (scenario.get("scenario_count", 0), scenario.get("diversity_score", 0)),
        "- Judge 漏项：%s，分数溢出：%s"
        % (judge.get("missing_item_count", 0), judge.get("score_overflow_count", 0)),
        "- 证据轮次命中率：%s%%" % evidence.get("traceable_evidence_rate", 0.0),
        "- 总耗时：%sms，慢阶段数：%s"
        % (timing.get("total_duration_ms", 0), len(timing.get("slow_stages", []))),
    ]
```

- [ ] **Step 4: Pass quality summary from `engine.write_report`**

In `backend/evaluation_engine/engine.py`, pass `quality_summary` to the template report after computing it. If this creates a timing cycle because report is needed before quality summary, keep persisted/API `quality_summary` in Task 3 and render the reliability section in API-side report only in a follow-up. Do not block Task 3 on report text.

- [ ] **Step 5: Run report test**

Run:

```bash
python3 -m pytest tests/test_report_writer.py::test_report_renders_quality_summary_when_provided -q
```

Expected: PASS.

---

### Task 6: Add Frontend Visibility for Reliability Metrics

**Files:**
- Modify: `frontend/src/api/runs.ts`
- Modify: report pages/components that render `score_summary`
- Test: `tests/test_frontend_scaffold.py`

- [ ] **Step 1: Write failing frontend scaffold test**

Append to `tests/test_frontend_scaffold.py`:

```python
def test_frontend_report_surfaces_quality_summary_metrics():
    runs_api = (FRONTEND / "src" / "api" / "runs.ts").read_text(encoding="utf-8")
    wizard_page = (
        FRONTEND / "src" / "pages" / "EvaluationWizardPage.tsx"
    ).read_text(encoding="utf-8")

    assert "quality_summary" in runs_api
    assert "链路健康度" in wizard_page
    assert "quality_summary?.overall_status" in wizard_page
    assert "traceable_evidence_rate" in wizard_page
    assert "missing_item_count" in wizard_page
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/test_frontend_scaffold.py::test_frontend_report_surfaces_quality_summary_metrics -q
```

Expected: FAIL.

- [ ] **Step 3: Update TypeScript run response type**

In `frontend/src/api/runs.ts`, add:

```ts
export interface QualitySummary {
  overall_status: "pass" | "warn" | "fail" | string;
  scenario_coverage?: {
    scenario_count?: number;
    diversity_score?: number;
  };
  judge_integrity?: {
    missing_item_count?: number;
    score_overflow_count?: number;
  };
  evidence_traceability?: {
    traceable_evidence_rate?: number;
  };
  timing_health?: {
    total_duration_ms?: number;
    slow_stages?: unknown[];
  };
}
```

Add `quality_summary?: QualitySummary;` to `RunResponse`.

- [ ] **Step 4: Render concise reliability cards**

In the report rendering component/page, add four compact metrics:

```tsx
const quality = result.quality_summary;
```

Render labels:

```tsx
<section className="report-section">
  <h2>链路健康度</h2>
  <div className="metric-row">
    <Metric label="链路状态" value={quality?.overall_status || "unknown"} />
    <Metric
      label="证据命中"
      value={`${quality?.evidence_traceability?.traceable_evidence_rate ?? 0}%`}
    />
    <Metric
      label="Judge 漏项"
      value={quality?.judge_integrity?.missing_item_count ?? 0}
    />
    <Metric
      label="场景多样性"
      value={quality?.scenario_coverage?.diversity_score ?? 0}
    />
  </div>
</section>
```

Reuse the existing `Metric` component pattern if present in that page.

- [ ] **Step 5: Run frontend scaffold and build**

Run:

```bash
python3 -m pytest tests/test_frontend_scaffold.py::test_frontend_report_surfaces_quality_summary_metrics -q
npm run build
```

Expected: both PASS.

---

## Final Verification

- [ ] Run backend targeted tests:

```bash
python3 -m pytest tests/test_quality_summary.py tests/test_calibration_benchmark.py -q
```

Expected: PASS.

- [ ] Run API and report tests:

```bash
python3 -m pytest tests/test_app.py tests/test_backend_scaffold.py tests/test_report_writer.py -q
```

Expected: PASS.

- [ ] Run full backend test suite:

```bash
python3 -m pytest -q
```

Expected: all tests pass.

- [ ] Run frontend build:

```bash
cd frontend
npm run build
```

Expected: TypeScript and Vite build pass.

- [ ] Restart services:

```bash
python3 -m uvicorn backend.eval_agent.api.main:app --host 127.0.0.1 --port 8070
cd frontend && npm run dev
```

Expected:
- Backend health endpoint returns `{"status":"ok"}`.
- Frontend is accessible at `http://127.0.0.1:5173/`.

---

## Self-Review

- Spec coverage: The plan covers per-run `quality_summary`, expected-label self-check metrics, API/report/frontend visibility, and test verification.
- Placeholder scan: No `TBD`, `TODO`, or unbounded “add tests” instructions remain.
- Type consistency: The plan uses existing domain names: `EvaluationResult`, `EvidenceItem`, `ScenarioSet`, `RubricSpec`, `FullRunResult`, and `RunResponse`.
- Scope control: This plan avoids changing prompt generation, model routing, and scenario simulation logic. It only adds reliability proof and quality-gate outputs.
