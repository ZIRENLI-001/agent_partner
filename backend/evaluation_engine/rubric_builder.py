from __future__ import annotations

from backend.evaluation_engine.domain import RubricItem, RubricSpec, TaskSpec


def build_rubric(spec: TaskSpec) -> RubricSpec:
    items = []

    for index, step in enumerate(spec.required_steps, start=1):
        items.append(
            RubricItem(
                item_id="step_%02d" % index,
                dimension="task_completion",
                criterion="完成通话流程要求：%s" % step,
                source="Call Flow 第%d步" % index,
                check_type="semantic",
                weight=10,
            )
        )
        items.append(
            RubricItem(
                item_id="process_%02d" % index,
                dimension="process_adherence",
                criterion="按任务流程顺序推进并覆盖关键动作：%s" % step,
                source="Call Flow 第%d步" % index,
                check_type="semantic",
                weight=6,
            )
        )

    for index, constraint in enumerate(spec.constraints, start=1):
        dimension = _constraint_dimension(constraint)
        items.append(
            RubricItem(
                item_id="constraint_%02d" % index,
                dimension=dimension,
                criterion=_constraint_criterion(constraint),
                source="Constraints 第%d条" % index,
                check_type=_constraint_check_type(constraint),
                weight=5,
                critical="超出职责范围" in constraint,
            )
        )

    for index, faq in enumerate(spec.faq, start=1):
        intent = faq.get("intent", "FAQ")
        expected_answer = faq.get("expected_answer", "")
        items.append(
            RubricItem(
                item_id="faq_%02d" % index,
                dimension="knowledge_accuracy",
                criterion="当用户询问%s时，回答：%s" % (intent, expected_answer),
                source="Knowledge Points (FAQ) 第%d条" % index,
                check_type="semantic",
                weight=8,
            )
        )

    for index, edge_case in enumerate(spec.edge_cases, start=1):
        items.append(
            RubricItem(
                item_id="edge_%02d" % index,
                dimension="edge_case_handling",
                criterion="遇到%s时，%s"
                % (
                    edge_case.get("trigger", "边界场景"),
                    edge_case.get("expected_behavior", "按任务要求处理"),
                ),
                source="Inferred Edge Case 第%d条" % index,
                check_type="semantic",
                weight=8,
            )
        )

    for index, forbidden_action in enumerate(spec.forbidden_actions, start=1):
        items.append(
            RubricItem(
                item_id="forbidden_%02d" % index,
                dimension="boundary_safety",
                criterion="不得%s" % forbidden_action,
                source="Forbidden Actions 第%d条" % index,
                check_type="rule_and_semantic",
                weight=20,
                critical=True,
            )
        )

    return RubricSpec(
        rubric_id="%s_rubric" % spec.task_id,
        task_id=spec.task_id,
        version=spec.version,
        items=items,
    )


def _constraint_criterion(constraint: str) -> str:
    if "30" in constraint:
        return "每次回复应控制在约 30 个字以内"
    return "遵守约束：%s" % constraint


def _constraint_dimension(constraint: str) -> str:
    if "语气" in constraint or "自然" in constraint or "回复控制" in constraint or "30" in constraint:
        return "conversation_quality"
    if "超出职责范围" in constraint:
        return "constraint_following"
    return "constraint_following"


def _constraint_check_type(constraint: str) -> str:
    if "30" in constraint:
        return "rule"
    if "超出职责范围" in constraint:
        return "rule_and_semantic"
    return "semantic"
