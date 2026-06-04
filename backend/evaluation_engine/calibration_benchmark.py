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
            evidence_by_item = {item.rubric_item_id: item for item in result.evidence}

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

            if (
                severity == "critical"
                and expected_verdict in FAILING_VERDICTS
                and actual_verdict == "pass"
            ):
                critical_false_pass_count += 1
            if (
                severity == "critical"
                and expected_verdict == "pass"
                and actual_verdict in (FAILING_VERDICTS | {"missing"})
            ):
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
