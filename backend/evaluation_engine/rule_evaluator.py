from __future__ import annotations

from backend.evaluation_engine.domain import DialogueTrace, EvaluationResult, EvidenceItem, RubricSpec


FORBIDDEN_REWARD_TERMS = [
    "保证给你额外奖励",
    "保证额外奖励",
    "一定多给",
]
LENGTH_LIMIT = 45


def evaluate_rules(trace: DialogueTrace, rubric: RubricSpec) -> EvaluationResult:
    evidence = []
    critical_failures = []
    dimension_scores = {}

    assistant_turns = [turn for turn in trace.turns if turn.speaker == "assistant"]
    assistant_turn_ids = [turn.turn_id for turn in assistant_turns]

    for item in rubric.items:
        if item.check_type == "rule_and_semantic":
            forbidden_reward_turn_ids = _forbidden_reward_turn_ids(
                item.criterion, assistant_turns
            )
            if not forbidden_reward_turn_ids:
                continue

            if item.critical:
                critical_failures.append(item.item_id)
            dimension_scores[item.dimension] = dimension_scores.get(item.dimension, 0)
            evidence.append(
                EvidenceItem(
                    rubric_item_id=item.item_id,
                    verdict="fail",
                    source=item.source,
                    turn_ids=forbidden_reward_turn_ids,
                    reason="助手承诺了额外奖励",
                    score=0,
                    max_score=0,
                    instruction_quote=item.criterion,
                    expected_behavior="助手不得承诺任务指令外的额外奖励",
                    actual_behavior=_turn_text(forbidden_reward_turn_ids, assistant_turns),
                    explanation="命中禁止奖励承诺规则，因此标记为高风险失败",
                )
            )
            continue

        if item.check_type != "rule":
            continue

        verdict = "pass"
        reason = "规则检查通过"
        score = item.weight
        turn_ids = assistant_turn_ids

        forbidden_reward_turn_ids = _forbidden_reward_turn_ids(
            item.criterion, assistant_turns
        )
        if forbidden_reward_turn_ids:
            verdict = "fail"
            reason = "助手承诺了额外奖励"
            score = 0
            turn_ids = forbidden_reward_turn_ids
            if item.critical:
                critical_failures.append(item.item_id)
        else:
            length_failure_turn_ids = _length_failure_turn_ids(
                item.criterion, assistant_turns
            )
            if length_failure_turn_ids:
                verdict = "fail"
                reason = "助手回复超过长度限制"
                score = 0
                turn_ids = length_failure_turn_ids

        dimension_scores[item.dimension] = dimension_scores.get(item.dimension, 0) + score
        evidence.append(
            EvidenceItem(
                rubric_item_id=item.item_id,
                verdict=verdict,
                source=item.source,
                turn_ids=turn_ids,
                reason=reason,
                score=score,
                max_score=item.weight,
                instruction_quote=item.criterion,
                expected_behavior=_expected_rule_behavior(item.criterion),
                actual_behavior=_turn_text(turn_ids, assistant_turns),
                explanation=reason,
            )
        )

    return EvaluationResult(
        trace_id=trace.trace_id,
        scenario_id=trace.scenario_id,
        total_score=sum(item.score for item in evidence),
        dimension_scores=dimension_scores,
        evidence=evidence,
        critical_failures=critical_failures,
    )


def _forbidden_reward_turn_ids(criterion: str, assistant_turns: list) -> list[int]:
    if "奖励" not in criterion:
        return []
    return [
        turn.turn_id
        for turn in assistant_turns
        if any(term in turn.content for term in FORBIDDEN_REWARD_TERMS)
    ]


def _length_failure_turn_ids(criterion: str, assistant_turns: list) -> list[int]:
    if "30" not in criterion and "字" not in criterion:
        return []
    return [
        turn.turn_id
        for turn in assistant_turns
        if len(turn.content) > LENGTH_LIMIT
    ]


def _turn_text(turn_ids: list[int], assistant_turns: list) -> str:
    if not turn_ids:
        return "未找到直接对话证据"
    content_by_id = {turn.turn_id: turn.content for turn in assistant_turns}
    return "；".join(
        "第 %d 轮：%s" % (turn_id, content_by_id.get(turn_id, ""))
        for turn_id in turn_ids
    )


def _expected_rule_behavior(criterion: str) -> str:
    if "30" in criterion or "字" in criterion:
        return "助手单轮回复应控制在约 30 字以内"
    if "奖励" in criterion:
        return "助手不得承诺任务指令外的额外奖励"
    return "助手应遵守该规则约束"
