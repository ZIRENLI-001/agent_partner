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


def test_task_spec_requires_versioned_identity():
    spec = TaskSpec(
        task_id="task_001",
        version="v1",
        task_name="飞毛腿通知",
        role="站长",
        target_user="骑手",
        task_goal="通知合同生效",
        opening_line="你好",
        required_steps=["确认身份", "告知合同生效"],
        constraints=["每次回复约30字以内"],
        faq=[{"intent": "退出", "expected_answer": "前一天取消"}],
        edge_cases=[{"trigger": "不想配送", "expected_behavior": "挽留"}],
        forbidden_actions=["承诺额外奖励"],
    )

    assert spec.task_id == "task_001"
    assert spec.version == "v1"
    assert spec.required_steps[1] == "告知合同生效"


def test_evaluation_evidence_is_traceable():
    rubric = RubricSpec(
        rubric_id="rubric_001",
        task_id="task_001",
        version="v1",
        items=[
            RubricItem(
                item_id="r1",
                dimension="task_completion",
                criterion="是否告知合同生效",
                source="Call Flow 第1步",
                check_type="semantic",
                weight=10,
                critical=False,
            )
        ],
    )
    trace = DialogueTrace(
        trace_id="trace_001",
        run_id="run_001",
        task_id="task_001",
        scenario_id="scenario_001",
        turns=[
            Turn(turn_id=1, speaker="assistant", content="今天合同已经生效。"),
        ],
        termination_reason="task_completed",
    )
    result = EvaluationResult(
        trace_id=trace.trace_id,
        scenario_id="scenario_001",
        total_score=10,
        dimension_scores={"task_completion": 10},
        evidence=[
            EvidenceItem(
                rubric_item_id=rubric.items[0].item_id,
                verdict="pass",
                source="Call Flow 第1步",
                turn_ids=[1],
                reason="模型明确告知合同生效",
                score=10,
                max_score=10,
            )
        ],
        critical_failures=[],
    )

    assert result.evidence[0].source == "Call Flow 第1步"
    assert result.evidence[0].turn_ids == [1]


def test_scenario_set_contains_multiple_scenarios():
    scenario_set = ScenarioSet(
        suite_id="suite_001",
        task_id="task_001",
        version="v1",
        scenarios=[
            Scenario(
                scenario_id="scenario_normal",
                task_id="task_001",
                user_profile={"role": "骑手", "attitude": "配合"},
                coverage_targets=["contract_active"],
                initial_user_intent="正常确认",
                expected_test_focus="基础任务完成",
            ),
            Scenario(
                scenario_id="scenario_reward",
                task_id="task_001",
                user_profile={"role": "骑手", "attitude": "关注收益"},
                coverage_targets=["reward_question", "boundary_no_extra_promise"],
                initial_user_intent="询问奖励",
                expected_test_focus="奖励边界",
            ),
        ],
    )

    assert len(scenario_set.scenarios) == 2
    assert scenario_set.scenarios[1].coverage_targets == ["reward_question", "boundary_no_extra_promise"]
