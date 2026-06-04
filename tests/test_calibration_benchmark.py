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
