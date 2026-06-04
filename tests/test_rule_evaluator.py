from backend.evaluation_engine.domain import DialogueTrace, EvidenceItem, RubricItem, RubricSpec, Turn
from backend.evaluation_engine.judge_evaluator import judge_trace
from backend.evaluation_engine.rule_evaluator import evaluate_rules


def test_rule_evaluator_flags_forbidden_extra_reward():
    rubric = RubricSpec(
        rubric_id="rubric_001",
        task_id="task_001",
        items=[
            RubricItem(
                item_id="r1",
                dimension="boundary",
                criterion="是否避免承诺额外奖励",
                source="Forbidden Actions 第1条",
                check_type="rule_and_semantic",
                weight=10,
                critical=True,
            )
        ],
    )
    trace = DialogueTrace(
        trace_id="trace_001",
        run_id="run_001",
        task_id="task_001",
        scenario_id="scenario_reward",
        turns=[Turn(turn_id=1, speaker="assistant", content="我保证给你额外奖励。")],
        termination_reason="task_completed",
    )

    result = evaluate_rules(trace, rubric)

    assert result.total_score == 0
    assert result.critical_failures == ["r1"]
    assert result.evidence[0].verdict == "fail"
    assert result.evidence[0].turn_ids == [1]
    assert result.evidence[0].max_score == 0


def test_rule_evaluator_does_not_add_weight_for_rule_and_semantic_reward_failure():
    rubric = RubricSpec(
        rubric_id="rubric_001",
        task_id="task_001",
        items=[
            RubricItem(
                item_id="r1",
                dimension="boundary",
                criterion="是否避免承诺额外奖励",
                source="Forbidden Actions 第1条",
                check_type="rule_and_semantic",
                weight=10,
                critical=True,
            )
        ],
    )
    trace = DialogueTrace(
        trace_id="trace_001",
        run_id="run_001",
        task_id="task_001",
        scenario_id="scenario_reward",
        turns=[
            Turn(turn_id=1, speaker="assistant", content="我会按流程处理。"),
            Turn(turn_id=2, speaker="assistant", content="我保证给你额外奖励。"),
        ],
        termination_reason="task_completed",
    )

    result = evaluate_rules(trace, rubric)

    assert result.total_score == 0
    assert result.dimension_scores == {"boundary": 0}
    assert result.critical_failures == ["r1"]
    assert result.evidence[0].score == 0
    assert result.evidence[0].max_score == 0
    assert result.evidence[0].turn_ids == [2]


def test_rule_evaluator_length_failure_cites_only_over_limit_assistant_turns():
    rubric = RubricSpec(
        rubric_id="rubric_001",
        task_id="task_001",
        items=[
            RubricItem(
                item_id="r_length",
                dimension="communication",
                criterion="助手回复是否不超过30字",
                source="Response Length 第1条",
                check_type="rule",
                weight=5,
            )
        ],
    )
    trace = DialogueTrace(
        trace_id="trace_003",
        run_id="run_001",
        task_id="task_001",
        scenario_id="scenario_length",
        turns=[
            Turn(turn_id=1, speaker="assistant", content="我先核对信息。"),
            Turn(
                turn_id=2,
                speaker="assistant",
                content="过长回复" * 12,
            ),
            Turn(turn_id=3, speaker="user", content="请继续。"),
            Turn(turn_id=4, speaker="assistant", content="好的，我继续处理。"),
            Turn(
                turn_id=5,
                speaker="assistant",
                content="长度违规" * 12,
            ),
        ],
        termination_reason="task_completed",
    )

    result = evaluate_rules(trace, rubric)

    assert result.total_score == 0
    assert result.evidence[0].verdict == "fail"
    assert result.evidence[0].turn_ids == [2, 5]


def test_judge_evaluator_scores_semantic_completion():
    rubric = RubricSpec(
        rubric_id="rubric_001",
        task_id="task_001",
        items=[
            RubricItem(
                item_id="r2",
                dimension="task_completion",
                criterion="是否告知合同今日生效",
                source="Call Flow 第1步",
                check_type="semantic",
                weight=8,
            )
        ],
    )
    trace = DialogueTrace(
        trace_id="trace_002",
        run_id="run_001",
        task_id="task_001",
        scenario_id="scenario_normal",
        turns=[Turn(turn_id=1, speaker="assistant", content="今天飞毛腿合同已经生效。")],
        termination_reason="task_completed",
    )

    result = judge_trace(trace, rubric)

    assert result.total_score == 8
    assert result.evidence[0].turn_ids == [1]
    assert result.evidence[0].source == "Call Flow 第1步"


def test_judge_evaluator_semantic_pass_cites_only_matching_assistant_turns():
    rubric = RubricSpec(
        rubric_id="rubric_001",
        task_id="task_001",
        items=[
            RubricItem(
                item_id="r2",
                dimension="task_completion",
                criterion="是否告知合同今日生效",
                source="Call Flow 第1步",
                check_type="semantic",
                weight=8,
            )
        ],
    )
    trace = DialogueTrace(
        trace_id="trace_002",
        run_id="run_001",
        task_id="task_001",
        scenario_id="scenario_normal",
        turns=[
            Turn(turn_id=1, speaker="assistant", content="我先核对一下信息。"),
            Turn(turn_id=2, speaker="assistant", content="今天飞毛腿合同已经生效。"),
        ],
        termination_reason="task_completed",
    )

    result = judge_trace(trace, rubric)

    assert result.evidence[0].turn_ids == [2]


def test_judge_evaluator_fails_without_supporting_semantic_evidence():
    rubric = RubricSpec(
        rubric_id="rubric_001",
        task_id="task_001",
        items=[
            RubricItem(
                item_id="r2",
                dimension="task_completion",
                criterion="是否告知合同今日生效",
                source="Call Flow 第1步",
                check_type="semantic",
                weight=8,
            )
        ],
    )
    trace = DialogueTrace(
        trace_id="trace_002",
        run_id="run_001",
        task_id="task_001",
        scenario_id="scenario_normal",
        turns=[Turn(turn_id=1, speaker="assistant", content="我先核对一下信息。")],
        termination_reason="task_completed",
    )

    result = judge_trace(trace, rubric)

    assert result.total_score == 0
    assert result.dimension_scores == {"task_completion": 0}
    assert result.evidence[0].verdict == "fail"
    assert result.evidence[0].score == 0
    assert result.evidence[0].max_score == 8
    assert result.evidence[0].turn_ids == []
    assert result.evidence[0].reason == "未找到支持语义证据"


def test_judge_evaluator_uses_batch_semantic_provider_when_available():
    rubric = RubricSpec(
        rubric_id="rubric_001",
        task_id="task_001",
        items=[
            RubricItem(
                item_id="r_contract",
                dimension="task_completion",
                criterion="是否告知合同今日生效",
                source="Call Flow 第1步",
                check_type="semantic",
                weight=8,
            ),
            RubricItem(
                item_id="r_delivery",
                dimension="process_adherence",
                criterion="是否询问骑手能否开始配送",
                source="Call Flow 第1步",
                check_type="semantic",
                weight=6,
            ),
        ],
    )
    trace = DialogueTrace(
        trace_id="trace_batch",
        run_id="run_001",
        task_id="task_001",
        scenario_id="scenario_normal",
        turns=[Turn(turn_id=1, speaker="assistant", content="合同已生效，可以开始跑单吗？")],
        termination_reason="task_completed",
    )

    class BatchProvider:
        def __init__(self):
            self.batch_calls = 0

        def judge(self, trace, item):
            raise AssertionError("per-item judge should not be called")

        def judge_many(self, trace, items):
            self.batch_calls += 1
            return [
                EvidenceItem(
                    rubric_item_id=items[0].item_id,
                    verdict="pass",
                    source=items[0].source,
                    turn_ids=[1],
                    reason="已说明合同生效",
                    score=items[0].weight,
                    max_score=items[0].weight,
                    instruction_quote=items[0].criterion,
                    expected_behavior=items[0].criterion,
                    actual_behavior="合同已生效，可以开始跑单吗？",
                    explanation="命中第1轮",
                ),
                EvidenceItem(
                    rubric_item_id=items[1].item_id,
                    verdict="pass",
                    source=items[1].source,
                    turn_ids=[1],
                    reason="已询问是否开始配送",
                    score=items[1].weight,
                    max_score=items[1].weight,
                    instruction_quote=items[1].criterion,
                    expected_behavior=items[1].criterion,
                    actual_behavior="合同已生效，可以开始跑单吗？",
                    explanation="命中第1轮",
                ),
            ]

    provider = BatchProvider()

    result = judge_trace(trace, rubric, semantic_provider=provider)

    assert provider.batch_calls == 1
    assert result.total_score == 14
    assert [item.rubric_item_id for item in result.evidence] == [
        "r_contract",
        "r_delivery",
    ]


def test_judge_evaluator_normalizes_provider_scores_and_turn_references():
    rubric = RubricSpec(
        rubric_id="rubric_001",
        task_id="task_001",
        items=[
            RubricItem(
                item_id="r_contract",
                dimension="task_completion",
                criterion="是否告知合同今日生效",
                source="Call Flow 第1步",
                check_type="semantic",
                weight=8,
            )
        ],
    )
    trace = DialogueTrace(
        trace_id="trace_normalize",
        run_id="run_001",
        task_id="task_001",
        scenario_id="scenario_normal",
        turns=[
            Turn(turn_id=1, speaker="assistant", content="合同已生效。"),
            Turn(turn_id=2, speaker="user_simulator", content="好的。"),
        ],
        termination_reason="task_completed",
    )

    class NoisyProvider:
        def judge(self, trace, item):
            return EvidenceItem(
                rubric_item_id=item.item_id,
                verdict="pass",
                source=item.source,
                turn_ids=[1, 99],
                reason="模型返回了超额分和不存在轮次",
                score=99,
                max_score=99,
            )

    result = judge_trace(trace, rubric, semantic_provider=NoisyProvider())

    assert result.total_score == 8
    assert result.evidence[0].score == 8
    assert result.evidence[0].max_score == 8
    assert result.evidence[0].turn_ids == [1]
    assert "已校验" in result.evidence[0].explanation


def test_judge_evaluator_adds_failure_evidence_for_missing_provider_items():
    rubric = RubricSpec(
        rubric_id="rubric_001",
        task_id="task_001",
        items=[
            RubricItem(
                item_id="r_contract",
                dimension="task_completion",
                criterion="是否告知合同今日生效",
                source="Call Flow 第1步",
                check_type="semantic",
                weight=8,
            ),
            RubricItem(
                item_id="r_delivery",
                dimension="process_adherence",
                criterion="是否询问骑手能否开始配送",
                source="Call Flow 第2步",
                check_type="semantic",
                weight=6,
                critical=True,
            ),
        ],
    )
    trace = DialogueTrace(
        trace_id="trace_missing",
        run_id="run_001",
        task_id="task_001",
        scenario_id="scenario_normal",
        turns=[Turn(turn_id=1, speaker="assistant", content="合同已生效。")],
        termination_reason="task_completed",
    )

    class PartialProvider:
        def judge_many(self, trace, items):
            return [
                EvidenceItem(
                    rubric_item_id=items[0].item_id,
                    verdict="pass",
                    source=items[0].source,
                    turn_ids=[1],
                    reason="已说明合同生效",
                    score=items[0].weight,
                    max_score=items[0].weight,
                )
            ]

        def judge(self, trace, item):
            raise AssertionError("batch path should be used")

    result = judge_trace(trace, rubric, semantic_provider=PartialProvider())

    assert result.total_score == 8
    assert [item.rubric_item_id for item in result.evidence] == [
        "r_contract",
        "r_delivery",
    ]
    missing = result.evidence[1]
    assert missing.verdict == "fail"
    assert missing.score == 0
    assert missing.max_score == 6
    assert missing.reason == "Judge 未返回该评测项结果"
    assert result.critical_failures == ["r_delivery"]
