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
            RubricItem(
                item_id="unrelated_faq",
                dimension="knowledge_accuracy",
                criterion="回答未被当前场景覆盖的 FAQ",
                source="Knowledge Points (FAQ) 第1条",
                check_type="semantic",
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
    assert "unrelated_faq" not in summary["judge_integrity"]["missing_items"]
    assert summary["remediation_actions"][0]["stage"] == "run"
    assert "重新执行评测" in summary["remediation_actions"][0]["action"]
    assert summary["evidence_traceability"]["traceable_evidence_rate"] == 50.0
    assert summary["report_integrity"]["has_quantitative_result"] is True
    assert summary["timing_health"]["zero_duration_stages"] == []
