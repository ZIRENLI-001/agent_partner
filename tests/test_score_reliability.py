from __future__ import annotations

from backend.evaluation_engine import app as web_app
from backend.evaluation_engine.domain import DialogueTrace, EvidenceItem, EvaluationResult, RubricItem, RubricSpec, TaskSpec, Turn
from backend.evaluation_engine.engine import build_rubric_spec
from backend.evaluation_engine.judge_evaluator import judge_trace
from backend.evaluation_engine.rubric_quality import rubric_quality_report


def test_score_summary_exposes_percent_normalization_for_cross_task_comparison() -> None:
    results = [
        EvaluationResult(
            trace_id="trace_001",
            scenario_id="scenario_001",
            total_score=13,
            dimension_scores={"task_completion": 13},
            evidence=[
                EvidenceItem(
                    rubric_item_id="step_01",
                    verdict="partial",
                    source="Call Flow 第1步",
                    turn_ids=[1],
                    reason="部分完成",
                    score=13,
                    max_score=20,
                )
            ],
        )
    ]

    summary = web_app._score_summary(results)
    scenario_summary = web_app._scenario_summary(
        type(
            "ScenarioSetLike",
            (),
            {
                "scenarios": [
                    type(
                        "ScenarioLike",
                        (),
                        {
                            "scenario_id": "scenario_001",
                            "coverage_targets": ["step_01"],
                            "expected_test_focus": "流程完成",
                        },
                    )()
                ]
            },
        )(),
        results,
    )

    assert summary["raw_total_score"] == 13
    assert summary["raw_possible_score"] == 20
    assert summary["normalized_score"] == 65.0
    assert summary["normalized_pass_rate"] == 65.0
    assert summary["scoring_scale"] == 100
    assert scenario_summary[0]["normalized_score"] == 65.0
    assert scenario_summary[0]["scoring_scale"] == 100


def test_score_summary_marks_score_unreliable_when_quality_gate_fails() -> None:
    summary = web_app._score_summary_with_quality(
        {
            "total_score": 240,
            "possible_score": 240,
            "pass_rate": 100.0,
            "normalized_score": 100.0,
        },
        {
            "overall_status": "fail",
            "judge_integrity": {"missing_item_count": 37},
        },
    )

    assert summary["pass_rate"] == 100.0
    assert summary["quality_gate_status"] == "fail"
    assert summary["score_reliable"] is False
    assert "37" in summary["score_reliability_reason"]


def test_build_rubric_spec_repairs_model_weights_and_duplicate_items() -> None:
    task_spec = TaskSpec(
        task_id="task_001",
        task_name="接单确认",
        role="调度助手",
        target_user="骑手",
        task_goal="确认骑手是否接单",
        opening_line="您好",
        required_steps=["确认是否接单"],
    )

    class WeakRubricProvider:
        def build(self, task_spec, raw_instruction):
            return RubricSpec(
                rubric_id="model_rubric",
                task_id=task_spec.task_id,
                items=[
                    RubricItem(
                        item_id="same",
                        dimension="unknown_dimension",
                        criterion="确认骑手是否接单",
                        source="model",
                        check_type="semantic",
                        weight=0,
                    ),
                    RubricItem(
                        item_id="same",
                        dimension="boundary_safety",
                        criterion="不得承诺额外奖励",
                        source="model",
                        check_type="rule_and_semantic",
                        weight=99,
                        critical=False,
                    ),
                ],
            )

    rubric = build_rubric_spec(
        task_spec,
        raw_instruction="确认骑手是否接单，不得承诺额外奖励",
        rubric_provider=WeakRubricProvider(),
    )

    assert [item.item_id for item in rubric.items] == ["same", "same_02"]
    assert rubric.items[0].dimension == "task_completion"
    assert rubric.items[0].weight == 1
    assert rubric.items[1].weight == 20
    assert rubric.items[1].critical is True


def test_build_rubric_spec_falls_back_when_model_rubric_does_not_match_task() -> None:
    task_spec = TaskSpec(
        task_id="task_address_exception",
        task_name="地址异常确认",
        role="履约客服",
        target_user="用户",
        task_goal="确认用户新地址并说明无法直接承诺改派",
        opening_line="您好，这边确认订单地址。",
        required_steps=["核实原地址", "确认新地址", "说明将同步调度"],
        constraints=["不得承诺一定改派成功"],
        forbidden_actions=["承诺一定改派成功"],
    )

    class FixedFlyingRiderRubricProvider:
        def build(self, task_spec, raw_instruction):
            return RubricSpec(
                rubric_id="fixed_template",
                task_id=task_spec.task_id,
                items=[
                    RubricItem(
                        item_id="opening_identity",
                        dimension="conversation_quality",
                        criterion="首轮回复必须包含骑手姓名、站长、飞毛腿报名、午晚高峰上线",
                        source="Opening Line",
                        check_type="semantic",
                        weight=8,
                    )
                ],
            )

    diagnostics = {}
    rubric = build_rubric_spec(
        task_spec,
        raw_instruction="用户地址异常，需要确认新地址，不能承诺一定改派成功。",
        rubric_provider=FixedFlyingRiderRubricProvider(),
        stage_diagnostics=diagnostics,
    )

    assert diagnostics["rubric_generation"]["fallback_used"] is True
    assert diagnostics["rubric_generation"]["fallback_reason"] == (
        "model rubric failed task suitability check"
    )
    assert "opening_identity" not in [item.item_id for item in rubric.items]
    assert any("确认新地址" in item.criterion for item in rubric.items)


def test_rubric_quality_report_rejects_fixed_template_unrelated_to_task() -> None:
    task_spec = TaskSpec(
        task_id="task_address_exception",
        task_name="地址异常确认",
        role="履约客服",
        target_user="用户",
        task_goal="确认用户新地址并说明无法直接承诺改派",
        opening_line="您好，这边确认订单地址。",
        required_steps=["核实原地址", "确认新地址", "说明将同步调度"],
        constraints=["不得承诺一定改派成功"],
        faq=[{"intent": "能否改地址", "expected_answer": "记录后同步调度确认"}],
        edge_cases=[{"trigger": "用户催促", "expected_behavior": "安抚并说明处理边界"}],
        forbidden_actions=["承诺一定改派成功"],
    )
    rubric = RubricSpec(
        rubric_id="fixed_flying_rider_template",
        task_id=task_spec.task_id,
        items=[
            RubricItem(
                item_id="opening_identity",
                dimension="conversation_quality",
                criterion="首轮回复必须包含称呼骑手姓名、自我介绍为站长、飞毛腿报名和午晚高峰上线",
                source="Opening Line",
                check_type="semantic",
                weight=8,
            )
        ],
    )

    report = rubric_quality_report(task_spec, rubric)

    assert report["is_suitable"] is False
    assert "required_steps" in report["missing_coverage"]
    assert "forbidden_actions" in report["missing_coverage"]
    assert report["coverage_ratio"] < 0.5


def test_rubric_quality_report_accepts_task_specific_unseen_address_rubric() -> None:
    task_spec = TaskSpec(
        task_id="task_address_exception",
        task_name="地址异常确认",
        role="履约客服",
        target_user="用户",
        task_goal="确认用户新地址并说明无法直接承诺改派",
        opening_line="您好，这边确认订单地址。",
        required_steps=["核实原地址", "确认新地址", "说明将同步调度"],
        constraints=["不得承诺一定改派成功"],
        faq=[{"intent": "能否改地址", "expected_answer": "记录后同步调度确认"}],
        edge_cases=[{"trigger": "用户催促", "expected_behavior": "安抚并说明处理边界"}],
        forbidden_actions=["承诺一定改派成功"],
    )
    rubric = RubricSpec(
        rubric_id="address_exception_rubric",
        task_id=task_spec.task_id,
        items=[
            RubricItem(
                item_id="verify_original_address",
                dimension="task_completion",
                criterion="核实原地址并确认用户当前地址异常",
                source="required_steps",
                check_type="semantic",
                weight=6,
            ),
            RubricItem(
                item_id="confirm_new_address",
                dimension="task_completion",
                criterion="确认新地址并复述关键信息",
                source="required_steps",
                check_type="semantic",
                weight=8,
            ),
            RubricItem(
                item_id="dispatch_handoff_boundary",
                dimension="boundary_safety",
                criterion="说明将同步调度确认，不得承诺一定改派成功",
                source="constraints",
                check_type="rule_and_semantic",
                weight=10,
                critical=True,
            ),
            RubricItem(
                item_id="address_faq",
                dimension="knowledge_accuracy",
                criterion="用户询问能否改地址时，回答记录后同步调度确认",
                source="faq",
                check_type="semantic",
                weight=6,
            ),
            RubricItem(
                item_id="rush_edge_case",
                dimension="edge_case_handling",
                criterion="用户催促时先安抚，再说明处理边界",
                source="edge_cases",
                check_type="semantic",
                weight=6,
            ),
        ],
    )

    report = rubric_quality_report(task_spec, rubric)

    assert report["is_suitable"] is True
    assert report["missing_coverage"] == []
    assert report["coverage_ratio"] == 1.0


def test_fallback_semantic_judge_gives_partial_credit_for_related_reply() -> None:
    rubric = RubricSpec(
        rubric_id="rubric_001",
        task_id="task_001",
        items=[
            RubricItem(
                item_id="accept_grab_order",
                dimension="task_completion",
                criterion="确认骑手是否愿意接单",
                source="Call Flow 第1步",
                check_type="semantic",
                weight=8,
            )
        ],
    )
    trace = DialogueTrace(
        trace_id="trace_001",
        run_id="run_001",
        task_id="task_001",
        scenario_id="scenario_busy",
        turns=[
            Turn(
                turn_id=1,
                speaker="assistant",
                content="师傅，这单您现在可以接吗？我可以先帮您核对地址。",
            )
        ],
        termination_reason="max_turns",
    )

    result = judge_trace(trace, rubric)

    assert result.evidence[0].verdict == "partial"
    assert result.evidence[0].score == 4
    assert result.evidence[0].max_score == 8
    assert result.evidence[0].turn_ids == [1]
