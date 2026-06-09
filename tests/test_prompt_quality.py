from __future__ import annotations

import json

from backend.eval_agent.services import run_service
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


def _task_spec() -> TaskSpec:
    return TaskSpec(
        task_id="task_prompt_quality",
        task_name="订单履约外呼",
        role="骑手调度助手",
        target_user="骑手",
        task_goal="确认骑手是否可以接单并完成取餐",
        opening_line="您好，这里有一个新订单需要确认。",
        required_steps=["确认身份", "说明订单", "确认是否接单"],
        constraints=["不得承诺额外补贴", "遇到地址异常要核实"],
        faq=[{"question": "距离远怎么办", "answer": "按平台规则说明"}],
        edge_cases=[{"trigger": "骑手很忙", "expected_behavior": "先安抚再确认"}],
        forbidden_actions=["编造奖励"],
    )


def _rubric() -> RubricSpec:
    return RubricSpec(
        rubric_id="rubric_prompt_quality",
        task_id="task_prompt_quality",
        items=[
            RubricItem(
                item_id="accept_grab_order",
                dimension="task_completion",
                criterion="确认骑手是否愿意接单",
                source="required_steps",
                check_type="semantic",
                weight=2,
                critical=True,
            ),
            RubricItem(
                item_id="address_exception",
                dimension="edge_case_handling",
                criterion="地址异常时应核实地址信息",
                source="edge_cases",
                check_type="rule_and_semantic",
                weight=2,
                critical=True,
            ),
        ],
    )


def _scenario() -> Scenario:
    return Scenario(
        scenario_id="boss_busy_retention",
        task_id="task_prompt_quality",
        user_profile={"role": "骑手", "attitude": "忙碌且不耐烦"},
        coverage_targets=["boss_busy_retention", "address_exception"],
        initial_user_intent="我现在很忙，地址也看不清。",
        expected_test_focus="忙碌拒绝和地址异常处理",
        difficulty="L4",
        scenario_type="pressure",
        expected_behavior="测试助手是否先安抚再核实",
        risk_tags=["retention", "address"],
    )


def _trace() -> DialogueTrace:
    return DialogueTrace(
        trace_id="trace_prompt_quality",
        run_id="run_prompt_quality",
        task_id="task_prompt_quality",
        scenario_id="boss_busy_retention",
        turns=[
            Turn(turn_id=1, speaker="assistant", content="您好，可以接这个订单吗？"),
            Turn(turn_id=2, speaker="user", content="我很忙，地址也不清楚。"),
            Turn(turn_id=3, speaker="assistant", content="理解，我先帮您核实地址。"),
        ],
        termination_reason="max_turns",
    )


def test_instruction_parser_prompt_preserves_source_order_and_assumptions() -> None:
    system = run_service._instruction_parser_system_message()["content"]
    user = json.loads(
        run_service._instruction_parser_user_message(
            "先确认身份，再说明订单。",
            "task_prompt_quality",
            input_data='{"coverage_targets":["address_exception"]}',
        )
    )

    combined = system + json.dumps(user, ensure_ascii=False)

    assert "原文顺序" in combined
    assert "显式指令" in combined
    assert "推断假设" in combined
    assert "不得编造" in combined
    assert "source" in combined
    assert "input_data_context" in combined
    assert "不改变关键要素" in combined


def test_rubric_prompt_requires_atomic_observable_and_non_overlapping_items() -> None:
    system = run_service._rubric_generator_system_message()["content"]
    user = json.loads(
        run_service._rubric_generator_user_message(_task_spec(), "按顺序确认接单并处理异常")
    )

    combined = system + json.dumps(user, ensure_ascii=False)

    assert "原子化" in combined
    assert "可观察" in combined
    assert "可判定" in combined
    assert "不得重叠" in combined
    assert "正向义务" in combined
    assert "负向禁止" in combined
    assert "不得复用固定模板" in combined
    assert "不适用于当前任务" in combined
    assert "适配性自检" in combined


def test_dialogue_simulation_prompts_focus_on_user_reactions_and_coverage_mapping() -> None:
    system = run_service._scenario_generator_system_message()["content"]
    user = json.loads(
        run_service._scenario_generator_user_message(
            _task_spec(),
            _rubric(),
            "覆盖目标: accept_grab_order, address_exception",
            minimum=3,
        )
    )
    simulator = run_service._user_simulator_system_message(_scenario())["content"]

    combined = system + json.dumps(user, ensure_ascii=False) + simulator

    assert "用户反应" in combined
    assert "不同用户" in combined
    assert "覆盖目标必须映射" in combined
    assert "rubric item" in combined
    assert "只输出用户下一句话" in combined
    assert "不要替助手完成任务" in combined
    assert "不要复述" in combined
    assert "不要总结助手" in combined
    assert "真实电话用户" in combined
    assert "口语化" in combined
    assert "不要冒充平台" in combined
    assert "不要引入当前任务外的新业务线" in combined
    assert "商家出餐场景不能提课程" in combined
    assert "前后身份和立场必须一致" in combined
    assert "不得跨业务线串场" in combined
    assert "initial_user_intent只能是用户本人自然开口" in combined
    assert "<END_CONVERSATION>" in simulator
    assert "真实结束状态" in simulator
    assert "逐步回应" in simulator
    assert "第一句用户回复" in simulator


def test_execution_prompt_sets_task_boundaries_without_revealing_evaluation_strategy() -> None:
    content = run_service._system_message(_task_spec())["content"]

    assert "不得透露评测策略" in content
    assert "按required_steps顺序推进" in content
    assert "先确认再推进" in content
    assert "不得编造" in content
    assert "<DONE>" in content
    assert "<END_CONVERSATION>" in content
    assert "用户明确结束" in content
    assert "不得提前输出 <DONE>" in content


def test_judge_prompts_require_actual_evidence_and_no_unstated_inference() -> None:
    system = run_service._semantic_judge_system_message(batch=True)["content"]
    user = json.loads(
        run_service._semantic_judge_batch_user_message(_trace(), _rubric().items)
    )

    combined = system + json.dumps(user, ensure_ascii=False)

    assert "实际turn_ids" in combined
    assert "证据原文" in combined
    assert "不得推断未说出的合规" in combined
    assert "score不得超过" in combined
    assert "不得遗漏rubric_item" in combined
    assert "turn_ids必须来自输入turns" in combined
    assert "verdict与score必须一致" in combined


def test_report_prompt_preserves_locked_metrics_and_requires_actionable_evidence_chain() -> None:
    scenario_set = ScenarioSet(
        suite_id="suite_prompt_quality",
        task_id="task_prompt_quality",
        scenarios=[_scenario()],
    )
    results = [
        EvaluationResult(
            trace_id="trace_prompt_quality",
            scenario_id="boss_busy_retention",
            total_score=1,
            dimension_scores={"task_completion": 1},
            evidence=[
                EvidenceItem(
                    rubric_item_id="accept_grab_order",
                    verdict="partial",
                    source="semantic",
                    turn_ids=[1, 2],
                    reason="未完成接单确认",
                    score=1,
                    max_score=2,
                )
            ],
        )
    ]
    system = run_service._report_generator_system_message()["content"]
    user = json.loads(
        run_service._report_generator_user_message(
            "run_prompt_quality",
            _task_spec(),
            scenario_set,
            results,
            {"rows": 1},
        )
    )

    combined = system + json.dumps(user, ensure_ascii=False)

    assert "不得改写" in combined
    assert "locked_metrics" in combined
    assert "阶段概览" in combined
    assert "证据链" in combined
    assert "风险分层" in combined
    assert "遗漏证据" in combined
