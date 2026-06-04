from __future__ import annotations

from backend.evaluation_engine.domain import EvaluationResult


SCORING_SCALE = 100


def normalized_percent(score: float, possible_score: float) -> float:
    if possible_score <= 0:
        return 0.0
    return round(score * SCORING_SCALE / possible_score, 1)


def result_possible_score(result: EvaluationResult) -> int:
    return sum(evidence.max_score for evidence in result.evidence)


def result_payload_with_normalized_score(result: EvaluationResult) -> dict[str, object]:
    payload = result.model_dump(mode="json")
    possible_score = result_possible_score(result)
    normalized_score = normalized_percent(result.total_score, possible_score)
    payload.update(
        {
            "raw_total_score": result.total_score,
            "raw_possible_score": possible_score,
            "normalized_score": normalized_score,
            "normalized_pass_rate": normalized_score,
            "scoring_scale": SCORING_SCALE,
        }
    )
    return payload


def result_dict_with_normalized_score(result: dict[str, object]) -> dict[str, object]:
    evidence_items = [
        evidence
        for evidence in result.get("evidence", [])
        if isinstance(evidence, dict)
    ]
    total_score = _number(result.get("total_score", 0))
    possible_score = sum(_number(evidence.get("max_score", 0)) for evidence in evidence_items)
    normalized_score = normalized_percent(total_score, possible_score)
    payload = dict(result)
    payload.update(
        {
            "raw_total_score": total_score,
            "raw_possible_score": possible_score,
            "normalized_score": normalized_score,
            "normalized_pass_rate": normalized_score,
            "scoring_scale": SCORING_SCALE,
        }
    )
    return payload


def _number(value: object) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0
