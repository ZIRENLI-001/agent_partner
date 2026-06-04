from __future__ import annotations

from typing import Protocol

from backend.evaluation_engine.domain import (
    DialogueTrace,
    EvaluationResult,
    EvidenceItem,
    RubricItem,
    RubricSpec,
)


class SemanticJudgeProvider(Protocol):
    def judge(self, trace: DialogueTrace, item: RubricItem) -> EvidenceItem:
        ...

    def judge_many(self, trace: DialogueTrace, items: list[RubricItem]) -> list[EvidenceItem]:
        ...


SEMANTIC_PATTERNS = [
    ("合同", "生效"),
    ("退出", "取消"),
    ("不想配送", "挽留"),
    ("不配送", "挽留"),
    ("不想配送", "鼓励"),
    ("不配送", "鼓励"),
    ("超出职责", "确认后再回电"),
    ("范围", "确认后再回电"),
]


def judge_trace(
    trace: DialogueTrace,
    rubric: RubricSpec,
    semantic_provider: SemanticJudgeProvider | None = None,
) -> EvaluationResult:
    if semantic_provider is not None:
        return _judge_trace_with_provider(trace, rubric, semantic_provider)

    evidence = []
    dimension_scores = {}

    assistant_turns = [turn for turn in trace.turns if turn.speaker == "assistant"]

    for item in rubric.items:
        if item.check_type not in ("semantic", "rule_and_semantic"):
            continue

        matched_turn_ids = _semantic_match_turn_ids(item.criterion, assistant_turns)
        if matched_turn_ids:
            verdict = "pass"
            reason = "语义检查通过"
            score = item.weight
        else:
            matched_turn_ids = _partial_match_turn_ids(item.criterion, assistant_turns)
            if matched_turn_ids:
                verdict = "partial"
                reason = "找到相关但不完整的语义证据"
                score = max(1, round(item.weight * 0.5))
            else:
                verdict = "fail"
                reason = "未找到支持语义证据"
                score = 0

        dimension_scores[item.dimension] = dimension_scores.get(item.dimension, 0) + score
        evidence.append(
                EvidenceItem(
                    rubric_item_id=item.item_id,
                    verdict=verdict,
                    source=item.source,
                    turn_ids=matched_turn_ids,
                    reason=reason,
                    score=score,
                    max_score=item.weight,
                    instruction_quote=item.criterion,
                    expected_behavior="助手应满足该语义评测项：%s" % item.criterion,
                    actual_behavior=_turn_text(matched_turn_ids, assistant_turns),
                    explanation=reason,
                )
            )

    return EvaluationResult(
        trace_id=trace.trace_id,
        scenario_id=trace.scenario_id,
        total_score=sum(item.score for item in evidence),
        dimension_scores=dimension_scores,
        evidence=evidence,
        critical_failures=[],
    )


def _judge_trace_with_provider(
    trace: DialogueTrace,
    rubric: RubricSpec,
    semantic_provider: SemanticJudgeProvider,
) -> EvaluationResult:
    evidence = []
    dimension_scores = {}
    critical_failures = []
    semantic_items = [
        item
        for item in rubric.items
        if item.check_type in ("semantic", "rule_and_semantic")
    ]

    if hasattr(semantic_provider, "judge_many"):
        try:
            judged_items = semantic_provider.judge_many(trace, semantic_items)
        except Exception:
            judged_items = [
                semantic_provider.judge(trace, item) for item in semantic_items
            ]
    else:
        judged_items = [semantic_provider.judge(trace, item) for item in semantic_items]

    item_by_id = {item.item_id: item for item in semantic_items}
    for judged in judged_items:
        item = item_by_id.get(judged.rubric_item_id)
        if item is None:
            continue
        judged = _normalize_provider_evidence(judged, item, trace)
        dimension_scores[item.dimension] = (
            dimension_scores.get(item.dimension, 0) + judged.score
        )
        if item.critical and judged.verdict in ("fail", "needs_review"):
            critical_failures.append(item.item_id)
        evidence.append(judged)

    judged_item_ids = {item.rubric_item_id for item in evidence}
    for item in semantic_items:
        if item.item_id in judged_item_ids:
            continue
        missing = _missing_provider_evidence(item)
        dimension_scores[item.dimension] = dimension_scores.get(item.dimension, 0)
        if item.critical:
            critical_failures.append(item.item_id)
        evidence.append(missing)

    return EvaluationResult(
        trace_id=trace.trace_id,
        scenario_id=trace.scenario_id,
        total_score=sum(item.score for item in evidence),
        dimension_scores=dimension_scores,
        evidence=evidence,
        critical_failures=critical_failures,
    )


def _normalize_provider_evidence(
    evidence: EvidenceItem,
    item: RubricItem,
    trace: DialogueTrace,
) -> EvidenceItem:
    valid_turn_ids = {turn.turn_id for turn in trace.turns}
    turn_ids = [turn_id for turn_id in evidence.turn_ids if turn_id in valid_turn_ids]
    max_score = item.weight
    score = max(0, min(evidence.score, max_score))
    verdict = _verdict_for_score(evidence.verdict, score, max_score)
    explanation = evidence.explanation or evidence.reason
    if _evidence_was_normalized(evidence, score, max_score, turn_ids, verdict):
        explanation = "%s；已校验分数范围、证据轮次和结论一致性" % explanation
    return evidence.model_copy(
        update={
            "verdict": verdict,
            "source": evidence.source or item.source,
            "turn_ids": turn_ids,
            "score": score,
            "max_score": max_score,
            "instruction_quote": evidence.instruction_quote or item.criterion,
            "expected_behavior": evidence.expected_behavior
            or "助手应满足该语义评测项：%s" % item.criterion,
            "actual_behavior": evidence.actual_behavior
            or _turn_text(turn_ids, trace.turns),
            "explanation": explanation,
        }
    )


def _verdict_for_score(verdict: str, score: int, max_score: int) -> str:
    if score <= 0:
        return "needs_review" if verdict == "needs_review" else "fail"
    if max_score > 0 and score >= max_score:
        return "pass" if verdict != "needs_review" else "needs_review"
    if verdict in ("fail", "needs_review"):
        return verdict
    return "partial"


def _evidence_was_normalized(
    evidence: EvidenceItem,
    score: int,
    max_score: int,
    turn_ids: list[int],
    verdict: str,
) -> bool:
    return (
        evidence.score != score
        or evidence.max_score != max_score
        or evidence.turn_ids != turn_ids
        or evidence.verdict != verdict
    )


def _missing_provider_evidence(item: RubricItem) -> EvidenceItem:
    return EvidenceItem(
        rubric_item_id=item.item_id,
        verdict="fail",
        source=item.source,
        turn_ids=[],
        reason="Judge 未返回该评测项结果",
        score=0,
        max_score=item.weight,
        instruction_quote=item.criterion,
        expected_behavior="助手应满足该语义评测项：%s" % item.criterion,
        actual_behavior="Judge 未返回证据，无法确认该项达成",
        explanation="执行评测阶段发现模型漏评该rubric item，按失败计入以避免分数虚高",
    )


def _semantic_match_turn_ids(criterion: str, assistant_turns: list) -> list[int]:
    matched_turn_ids = []
    for turn in assistant_turns:
        if any(
            criterion_term in criterion and assistant_term in turn.content
            for criterion_term, assistant_term in SEMANTIC_PATTERNS
        ):
                matched_turn_ids.append(turn.turn_id)
    return matched_turn_ids


PARTIAL_SEMANTIC_PATTERNS = [
    ("接单", ("接", "这单", "订单", "跑单")),
    ("愿意接单", ("接", "这单", "订单", "跑单")),
    ("地址", ("地址", "定位", "位置")),
    ("配送", ("配送", "跑单", "送")),
    ("忙", ("忙", "稍后", "不方便")),
    ("挽留", ("挽留", "理解", "可以", "再确认")),
    ("确认", ("确认", "核对", "可以吗", "能否")),
]


def _partial_match_turn_ids(criterion: str, assistant_turns: list) -> list[int]:
    matched_turn_ids = []
    for turn in assistant_turns:
        if any(
            criterion_term in criterion
            and any(assistant_term in turn.content for assistant_term in assistant_terms)
            for criterion_term, assistant_terms in PARTIAL_SEMANTIC_PATTERNS
        ):
            matched_turn_ids.append(turn.turn_id)
    return matched_turn_ids


def _turn_text(turn_ids: list[int], assistant_turns: list) -> str:
    if not turn_ids:
        return "未找到支持该评测项的助手回复"
    content_by_id = {turn.turn_id: turn.content for turn in assistant_turns}
    return "；".join(
        "第 %d 轮：%s" % (turn_id, content_by_id.get(turn_id, ""))
        for turn_id in turn_ids
    )
