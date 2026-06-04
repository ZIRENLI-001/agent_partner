from __future__ import annotations

from typing import Any

from backend.evaluation_engine.domain import RubricItem, RubricSpec, TaskSpec


ALLOWED_DIMENSIONS = {
    "task_completion",
    "process_adherence",
    "knowledge_accuracy",
    "boundary_safety",
    "conversation_quality",
    "edge_case_handling",
    "constraint_following",
}

MIN_ITEM_WEIGHT = 1
MAX_ITEM_WEIGHT = 20
MIN_SUITABLE_COVERAGE_RATIO = 0.6


def standardize_rubric(rubric: RubricSpec) -> RubricSpec:
    seen_item_ids: dict[str, int] = {}
    items = []
    for item in rubric.items:
        item_id = _unique_item_id(item.item_id, seen_item_ids)
        dimension = item.dimension
        if dimension not in ALLOWED_DIMENSIONS:
            dimension = _infer_dimension(item)
        weight = max(MIN_ITEM_WEIGHT, min(MAX_ITEM_WEIGHT, int(item.weight)))
        critical = item.critical or _is_high_risk_boundary(item)
        items.append(
            RubricItem(
                item_id=item_id,
                dimension=dimension,
                criterion=item.criterion,
                source=item.source,
                check_type=item.check_type,
                weight=weight,
                critical=critical,
            )
        )
    return RubricSpec(
        rubric_id=rubric.rubric_id,
        task_id=rubric.task_id,
        version=rubric.version,
        items=items,
    )


def rubric_quality_report(task_spec: TaskSpec, rubric: RubricSpec) -> dict[str, Any]:
    expected_groups = _expected_coverage_groups(task_spec)
    covered_groups = {
        group
        for group, probes in expected_groups.items()
        if _rubric_covers_any(rubric, probes)
    }
    missing_coverage = [
        group for group in expected_groups if group not in covered_groups
    ]
    fixed_template_risk = _fixed_template_risk(task_spec, rubric)
    coverage_ratio = (
        round(len(covered_groups) / len(expected_groups), 3)
        if expected_groups
        else 1.0
    )
    is_suitable = (
        coverage_ratio >= MIN_SUITABLE_COVERAGE_RATIO
        and not fixed_template_risk
        and "required_steps" not in missing_coverage
    )
    return {
        "is_suitable": is_suitable,
        "coverage_ratio": coverage_ratio,
        "covered_groups": sorted(covered_groups),
        "missing_coverage": missing_coverage,
        "fixed_template_risk": fixed_template_risk,
    }


def _expected_coverage_groups(task_spec: TaskSpec) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    if task_spec.required_steps:
        groups["required_steps"] = task_spec.required_steps + ["流程", "步骤", task_spec.task_goal]
    if task_spec.constraints:
        groups["constraints"] = task_spec.constraints + ["约束", "不得", "不能"]
    if task_spec.faq:
        groups["faq"] = [
            text
            for item in task_spec.faq
            for text in [item.get("intent", ""), item.get("expected_answer", "")]
            if text
        ] + ["FAQ", "回答", "知识"]
    if task_spec.edge_cases:
        groups["edge_cases"] = [
            text
            for item in task_spec.edge_cases
            for text in [item.get("trigger", ""), item.get("expected_behavior", "")]
            if text
        ] + ["异常", "边界"]
    if task_spec.forbidden_actions:
        groups["forbidden_actions"] = task_spec.forbidden_actions + ["禁止", "不得"]
    if not groups:
        groups["task_goal"] = [task_spec.task_goal, task_spec.task_name]
    return groups


def _rubric_covers_any(rubric: RubricSpec, probes: list[str]) -> bool:
    rubric_text = _rubric_text(rubric)
    return any(_meaningful_overlap(probe, rubric_text) for probe in probes if probe)


def _meaningful_overlap(probe: str, rubric_text: str) -> bool:
    normalized_probe = _normalize_text(probe)
    if not normalized_probe:
        return False
    if normalized_probe in rubric_text:
        return True
    tokens = _tokens(normalized_probe)
    if not tokens:
        return False
    matched = sum(1 for token in tokens if token in rubric_text)
    return matched >= max(1, min(2, len(tokens)))


def _fixed_template_risk(task_spec: TaskSpec, rubric: RubricSpec) -> bool:
    task_text = _normalize_text(
        " ".join(
            [
                task_spec.task_name,
                task_spec.role,
                task_spec.target_user,
                task_spec.task_goal,
                task_spec.opening_line,
                " ".join(task_spec.required_steps),
            ]
        )
    )
    rubric_text = _rubric_text(rubric)
    template_markers = [
        "飞毛腿",
        "骑手",
        "站长",
        "午餐",
        "晚餐",
        "单日合同",
        "多日合同",
    ]
    marker_hits = [marker for marker in template_markers if marker in rubric_text]
    off_task_hits = [marker for marker in marker_hits if marker not in task_text]
    return len(off_task_hits) >= 2


def _rubric_text(rubric: RubricSpec) -> str:
    return _normalize_text(
        " ".join(
            " ".join(
                [
                    item.item_id,
                    item.dimension,
                    item.criterion,
                    item.source,
                    item.check_type,
                ]
            )
            for item in rubric.items
        )
    )


def _normalize_text(text: str) -> str:
    return "".join(str(text).lower().split())


def _tokens(text: str) -> list[str]:
    separators = "，。；、：:,. ;/|()（）[]【】\"'`"
    current = text
    for separator in separators:
        current = current.replace(separator, " ")
    return [token.strip().lower() for token in current.split() if len(token.strip()) >= 2]


def _unique_item_id(item_id: str, seen_item_ids: dict[str, int]) -> str:
    clean_id = item_id.strip() or "item"
    count = seen_item_ids.get(clean_id, 0) + 1
    seen_item_ids[clean_id] = count
    if count == 1:
        return clean_id
    return "%s_%02d" % (clean_id, count)


def _infer_dimension(item: RubricItem) -> str:
    text = " ".join([item.item_id, item.criterion, item.source])
    if any(term in text for term in ["不得", "禁止", "不能", "额外奖励", "边界"]):
        return "boundary_safety"
    if any(term in text for term in ["FAQ", "知识", "回答", "告知"]):
        return "knowledge_accuracy"
    if any(term in text for term in ["异常", "地址", "忙", "拒绝", "挽留"]):
        return "edge_case_handling"
    if any(term in text for term in ["语气", "简洁", "字", "话术"]):
        return "conversation_quality"
    if any(term in text for term in ["顺序", "流程", "步骤"]):
        return "process_adherence"
    return "task_completion"


def _is_high_risk_boundary(item: RubricItem) -> bool:
    text = " ".join([item.dimension, item.criterion, item.source])
    return any(term in text for term in ["不得", "禁止", "不能", "额外奖励", "超出职责"])
