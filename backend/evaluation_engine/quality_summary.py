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
    judge_integrity = _judge_integrity(rubric, scenario_set, results)
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
    remediation_actions = _remediation_actions(
        scenario_coverage,
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
        "remediation_actions": remediation_actions,
    }


def _scenario_coverage(scenario_set: ScenarioSet) -> dict[str, object]:
    scenarios = scenario_set.scenarios
    coverage_targets = {
        target for scenario in scenarios for target in scenario.coverage_targets
    }
    risk_tags = {tag for scenario in scenarios for tag in scenario.risk_tags}
    difficulties = {scenario.difficulty for scenario in scenarios if scenario.difficulty}
    scenario_types = {
        scenario.scenario_type for scenario in scenarios if scenario.scenario_type
    }
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


def _judge_integrity(
    rubric: RubricSpec,
    scenario_set: ScenarioSet,
    results: list[EvaluationResult],
) -> dict[str, object]:
    scenario_by_id = {
        scenario.scenario_id: scenario for scenario in scenario_set.scenarios
    }
    expected_items = set()
    for result in results:
        scenario = scenario_by_id.get(result.scenario_id)
        if scenario is None:
            expected_items.update(
                item.item_id
                for item in rubric.items
                if item.check_type in {"semantic", "rule_and_semantic", "rule"}
            )
            continue
        expected_items.update(_expected_item_ids_for_scenario(rubric, scenario))
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


def _expected_item_ids_for_scenario(rubric: RubricSpec, scenario) -> set[str]:
    coverage_targets = set(getattr(scenario, "coverage_targets", []) or [])
    risk_tags = set(getattr(scenario, "risk_tags", []) or [])
    if not coverage_targets and not risk_tags:
        return {
            item.item_id
            for item in rubric.items
            if item.check_type in {"semantic", "rule_and_semantic", "rule"}
        }
    return {
        item.item_id
        for item in rubric.items
        if item.check_type in {"semantic", "rule_and_semantic", "rule"}
        and _rubric_item_matches_scenario(item, coverage_targets, risk_tags)
    }


def _rubric_item_matches_scenario(
    item,
    coverage_targets: set[str],
    risk_tags: set[str],
) -> bool:
    if item.item_id in coverage_targets or item.item_id in risk_tags:
        return True
    if item.dimension in coverage_targets or item.dimension in risk_tags:
        return True
    item_text = " ".join([item.item_id, item.dimension, item.source, item.criterion])
    targets = coverage_targets | risk_tags
    if any(term in item_text for term in ["Opening Line", "开场", "首轮", "自我介绍"]):
        return "opening_identity" in coverage_targets
    if item.critical and any(
        term in target
        for target in targets
        for term in ["boundary", "forbidden", "no_extra", "safety", "hallucination"]
    ):
        return True
    return any(target and target in item_text for target in targets)


def _evidence_traceability(
    traces: list[DialogueTrace],
    results: list[EvaluationResult],
) -> dict[str, object]:
    valid_turn_ids = {
        trace.scenario_id: {turn.turn_id for turn in trace.turns} for trace in traces
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
        key: marker in report_markdown for key, marker in REQUIRED_REPORT_SECTIONS.items()
    }
    result["missing_sections"] = [
        marker for key, marker in REQUIRED_REPORT_SECTIONS.items() if not result[key]
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


def _remediation_actions(
    scenario_coverage: dict[str, object],
    rubric_health: dict[str, object],
    judge_integrity: dict[str, object],
    evidence_traceability: dict[str, object],
    report_integrity: dict[str, object],
    timing_health: dict[str, object],
) -> list[dict[str, object]]:
    actions: list[dict[str, object]] = []
    if not rubric_health.get("is_suitable", True):
        actions.append(
            {
                "stage": "rubric",
                "action": "修改 Rubric 后重新生成",
                "reason": "Rubric 与当前任务不匹配，继续执行会放大误判。",
            }
        )
    if int(judge_integrity.get("missing_item_count", 0) or 0):
        actions.append(
            {
                "stage": "run",
                "action": "重新执行评测",
                "reason": "存在应评未评项，需要基于当前场景和 Rubric 重新跑 Judge。",
                "affected_count": judge_integrity.get("missing_item_count", 0),
            }
        )
    if int(evidence_traceability.get("invalid_turn_ref_count", 0) or 0):
        actions.append(
            {
                "stage": "run",
                "action": "重新执行评测",
                "reason": "证据轮次引用无效，需要重跑执行评测生成可追溯证据。",
                "affected_count": evidence_traceability.get("invalid_turn_ref_count", 0),
            }
        )
    if report_integrity.get("missing_sections"):
        actions.append(
            {
                "stage": "report",
                "action": "重新生成报告",
                "reason": "报告缺少量化结果或证据链章节，需要重新生成报告分析。",
                "affected_count": len(report_integrity.get("missing_sections", [])),
            }
        )
    if int(scenario_coverage.get("scenario_count", 0) or 0) < 2:
        actions.append(
            {
                "stage": "scenarios",
                "action": "增加对话模拟后重新生成",
                "reason": "当前场景数过少，建议补充用户反应分支后再执行评测。",
                "affected_count": scenario_coverage.get("scenario_count", 0),
            }
        )
    if timing_health.get("zero_duration_stages") or timing_health.get("slow_stages"):
        actions.append(
            {
                "stage": "run",
                "action": "检查模型配置后重新执行",
                "reason": "链路耗时异常，可能存在模型调用或阶段统计问题。",
            }
        )
    return _dedupe_actions(actions)


def _dedupe_actions(actions: list[dict[str, object]]) -> list[dict[str, object]]:
    deduped = []
    seen = set()
    for action in actions:
        key = (action.get("stage"), action.get("action"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(action)
    return deduped
