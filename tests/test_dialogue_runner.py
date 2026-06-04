from typing import Optional

from backend.evaluation_engine.dialogue_runner import run_dialogue
from backend.evaluation_engine.domain import RunConfig, Scenario, TaskSpec, Turn
from backend.evaluation_engine.providers import FakeAssistantProvider, FakeUserProvider
from backend.evaluation_engine.user_simulator import next_user_turn


def _task() -> TaskSpec:
    return TaskSpec(
        task_id="task_001",
        task_name="飞毛腿通知",
        role="站长",
        target_user="骑手",
        task_goal="通知合同生效",
        opening_line="你好，请问是王师傅吗？我是站长。",
        required_steps=["告知合同生效"],
        constraints=["每次回复约30字以内"],
    )


def _scenario(
    scenario_id: str = "scenario_normal",
    coverage_targets: Optional[list[str]] = None,
    initial_user_intent: str = "正常确认",
) -> Scenario:
    return Scenario(
        scenario_id=scenario_id,
        task_id="task_001",
        user_profile={"role": "骑手", "attitude": "配合"},
        coverage_targets=coverage_targets or ["normal_completion"],
        initial_user_intent=initial_user_intent,
        expected_test_focus="基础任务完成",
    )


def test_run_dialogue_creates_multi_turn_trace():
    task = _task()
    scenario = _scenario()
    config = RunConfig(run_id="run_001", task_id="task_001", max_turns=4)

    trace = run_dialogue(
        task_spec=task,
        scenario=scenario,
        run_config=config,
        assistant_provider=FakeAssistantProvider(),
        user_provider=FakeUserProvider(),
    )

    assert trace.run_id == "run_001"
    assert trace.scenario_id == "scenario_normal"
    assert len(trace.turns) >= 2
    assert trace.turns[0].speaker == "assistant"
    assert trace.termination_reason in {"task_completed", "max_turns"}


def test_run_dialogue_labels_simulated_user_turns_as_user_simulator():
    task = _task()
    scenario = _scenario()
    config = RunConfig(run_id="run_001", task_id="task_001", max_turns=4)

    trace = run_dialogue(
        task_spec=task,
        scenario=scenario,
        run_config=config,
        assistant_provider=FakeAssistantProvider(),
        user_provider=FakeUserProvider(),
    )

    non_assistant_speakers = [
        turn.speaker for turn in trace.turns if turn.speaker != "assistant"
    ]
    assert "user_simulator" in non_assistant_speakers
    assert "user" not in non_assistant_speakers


def test_assistant_provider_does_not_receive_scenario():
    class SpyAssistantProvider:
        def generate(self, task_spec: TaskSpec, history: list[Turn]) -> str:
            if not history:
                return task_spec.opening_line
            return "今天合同已经生效。<DONE>"

    trace = run_dialogue(
        task_spec=_task(),
        scenario=_scenario(),
        run_config=RunConfig(run_id="run_001", task_id="task_001", max_turns=4),
        assistant_provider=SpyAssistantProvider(),
        user_provider=FakeUserProvider(),
    )

    assert trace.termination_reason == "task_completed"


def test_fake_user_first_turn_uses_initial_user_intent_for_custom_scenario():
    task = _task()
    scenario = Scenario(
        scenario_id="scenario_normal",
        task_id="task_001",
        user_profile={"role": "骑手", "attitude": "配合"},
        coverage_targets=["faq_exit"],
        initial_user_intent="这是一个未来补充场景的首轮意图",
        expected_test_focus="基础任务完成",
    )
    config = RunConfig(run_id="run_001", task_id="task_001", max_turns=4)

    trace = run_dialogue(
        task_spec=task,
        scenario=scenario,
        run_config=config,
        assistant_provider=FakeAssistantProvider(),
        user_provider=FakeUserProvider(),
    )

    assert trace.turns[1].content == "这是一个未来补充场景的首轮意图"


def test_next_user_turn_replaces_assistant_echo_with_natural_user_fallback():
    class EchoingUserProvider:
        def generate(self, scenario: Scenario, history: list[Turn]) -> str:
            return history[-1].content

    assistant_content = "今天飞毛腿合同已经生效，午晚高峰需要上线。"
    scenario = _scenario(
        coverage_targets=["busy_or_unavailable"],
        initial_user_intent="我现在在路上，不方便听太久。",
    )
    history = [Turn(turn_id=1, speaker="assistant", content=assistant_content)]

    user_turn = next_user_turn(EchoingUserProvider(), scenario, history)

    assert user_turn != assistant_content
    assert "合同已经生效" not in user_turn
    assert "不方便" in user_turn or "简单" in user_turn


def test_next_user_turn_rejects_earlier_assistant_script_and_role_leak_for_merchant_scene():
    class ScriptRepeatingUserProvider:
        def generate(self, scenario: Scenario, history: list[Turn]) -> str:
            return "您好，请问是店长或负责人吗？这边是美团履约运营，想和您确认一笔出餐延迟的订单。"

    scenario = Scenario(
        scenario_id="merchant_delay_notice",
        task_id="task_merchant",
        user_profile={"role": "商家店长", "attitude": "忙碌"},
        coverage_targets=["merchant_delay_notice", "short_reply", "handoff_boundary"],
        risk_tags=["merchant_delay", "dispatch_collaboration"],
        initial_user_intent="还要五分钟，后厨正在做。",
        expected_test_focus="确认商家出餐延迟",
    )
    history = [
        Turn(
            turn_id=1,
            speaker="assistant",
            content="您好，请问是店长或负责人吗？这边是美团履约运营，想和您确认一笔出餐延迟的订单。",
        ),
        Turn(turn_id=2, speaker="user_simulator", content="是，我这边有点忙。"),
        Turn(turn_id=3, speaker="assistant", content="您有一笔订单出餐延迟，请问还需要几分钟能出餐？"),
    ]

    user_turn = next_user_turn(ScriptRepeatingUserProvider(), scenario, history)

    assert "美团履约运营" not in user_turn
    assert "请问是店长或负责人" not in user_turn
    assert "几分钟能出餐" not in user_turn
    assert "五分钟" in user_turn or "后厨" in user_turn


def test_next_user_turn_rejects_cross_domain_and_platform_side_user_content():
    class CrossDomainUserProvider:
        def generate(self, scenario: Scenario, history: list[Turn]) -> str:
            return "另外，我们最近上线了低延迟直播的功能，可以帮助您更及时地了解订单状态，您感兴趣了解一下吗？"

    scenario = Scenario(
        scenario_id="merchant_delay_notice",
        task_id="task_merchant",
        user_profile={"role": "商家店长", "attitude": "解释原因"},
        coverage_targets=["merchant_delay_notice", "short_reply", "handoff_boundary"],
        risk_tags=["merchant_delay", "dispatch_collaboration"],
        initial_user_intent="后厨有点压单，还需要五分钟。",
        expected_test_focus="确认商家出餐延迟",
    )
    history = [
        Turn(
            turn_id=1,
            speaker="assistant",
            content="您这边有一笔订单目前显示出餐延迟，请问是什么原因导致的呢？",
        )
    ]

    user_turn = next_user_turn(CrossDomainUserProvider(), scenario, history)

    assert "低延迟直播" not in user_turn
    assert "上线" not in user_turn
    assert "您感兴趣" not in user_turn
    assert "五分钟" in user_turn or "后厨" in user_turn


def test_next_user_turn_rejects_rider_platform_side_prompts():
    class PlatformPromptingUserProvider:
        def generate(self, scenario: Scenario, history: list[Turn]) -> str:
            return "今天有活动，奖励比较多，能抽点时间上线吗？"

    scenario = Scenario(
        scenario_id="rider_capacity_pressure",
        task_id="task_rider",
        user_profile={"role": "骑手", "attitude": "忙碌"},
        coverage_targets=["busy_or_unavailable", "reward_question"],
        risk_tags=["capacity_pressure", "benefit_boundary"],
        initial_user_intent="我今天家里有事，不一定能上线。",
        expected_test_focus="处理骑手忙碌和奖励追问",
    )
    history = [
        Turn(
            turn_id=1,
            speaker="assistant",
            content="王师傅您好，我是站长，飞毛腿合同今天生效，午晚高峰要上线。",
        )
    ]

    user_turn = next_user_turn(PlatformPromptingUserProvider(), scenario, history)

    assert "预计能完成多少单" not in user_turn
    assert "奖励比较多" not in user_turn
    assert "抽点时间上线" not in user_turn
    assert "不一定能上线" in user_turn or "不太方便" in user_turn or "额外补贴" in user_turn


def test_next_user_turn_rejects_rider_service_script_about_exit_flow():
    class ServiceScriptUserProvider:
        def generate(self, scenario: Scenario, history: list[Turn]) -> str:
            return "如果你想退出飞毛腿合同，可以告诉我吗？我帮你了解下具体流程。"

    scenario = Scenario(
        scenario_id="rider_faq_exit",
        task_id="task_rider",
        user_profile={"role": "骑手", "attitude": "询问规则"},
        coverage_targets=["faq_exit", "rider_app_operation"],
        risk_tags=["knowledge_accuracy"],
        initial_user_intent="那我今天还能退出飞毛腿吗？",
        expected_test_focus="准确回答退出飞毛腿 FAQ",
    )
    history = [
        Turn(
            turn_id=1,
            speaker="assistant",
            content="飞毛腿合同今天生效，午晚高峰需要上线。",
        )
    ]

    user_turn = next_user_turn(ServiceScriptUserProvider(), scenario, history)

    assert "可以告诉我吗" not in user_turn
    assert "帮你了解" not in user_turn
    assert "具体流程" not in user_turn
    assert "退出" in user_turn or "规则" in user_turn or "没太听清" in user_turn


def test_next_user_turn_rejects_rider_role_reversal_variants_from_real_runs():
    bad_outputs = [
        "你今天有空吗，能上线完成单量任务吗？",
        "请问你现在方便说几句吗？只需要确认一下合同信息，很快的。",
        "你说身体累我能理解，可是你签了飞毛腿合同，我们这边有指标要完成，你要是今天不配送，可能会影响后续接单机会的。能不能帮忙出一单？",
        "你可以通过骑手APP里的“飞毛腿”页面找到退出选项，然后按照提示操作退出。如果找不到，我可以帮你详细说明退出步骤。",
    ]

    scenario = Scenario(
        scenario_id="rider_contract_followup",
        task_id="task_rider",
        user_profile={"role": "骑手", "attitude": "抗拒"},
        coverage_targets=["refusal_to_deliver", "faq_exit", "contract_impact"],
        risk_tags=["capacity_pressure", "rider_app_operation"],
        initial_user_intent="我今天身体有点累，不太想跑。",
        expected_test_focus="处理骑手拒配和退出追问",
    )
    history = [
        Turn(
            turn_id=1,
            speaker="assistant",
            content="飞毛腿合同今天生效，午晚高峰需要上线。",
        )
    ]

    for bad_output in bad_outputs:
        class RoleReversalUserProvider:
            def generate(self, scenario: Scenario, history: list[Turn]) -> str:
                return bad_output

        user_turn = next_user_turn(RoleReversalUserProvider(), scenario, history)

        assert user_turn != bad_output
        assert "我们这边有指标" not in user_turn
        assert "只需要确认一下合同信息" not in user_turn
        assert "按照提示操作退出" not in user_turn
        assert "能上线完成单量任务" not in user_turn


def test_next_user_turn_rejects_meta_placeholder_user_content():
    class PlaceholderUserProvider:
        def generate(self, scenario: Scenario, history: list[Turn]) -> str:
            return "确认自己是机构负责人"

    scenario = Scenario(
        scenario_id="course_identity_confirm",
        task_id="task_course",
        user_profile={"role": "机构负责人", "attitude": "配合"},
        coverage_targets=["identity_confirmation", "product_upgrade_notice"],
        risk_tags=["task_completion"],
        initial_user_intent="确认自己是机构负责人",
        expected_test_focus="确认身份后说明低延迟直播选项",
    )
    history = [
        Turn(turn_id=1, speaker="assistant", content="您好，请问您是校区负责人吗？")
    ]

    user_turn = next_user_turn(PlaceholderUserProvider(), scenario, history)

    assert user_turn != "确认自己是机构负责人"
    assert "确认自己" not in user_turn
    assert "负责人" in user_turn or "什么事" in user_turn or "没太听清" in user_turn


def test_next_user_turn_rejects_invalid_initial_intent_fallback():
    class EmptyUserProvider:
        def generate(self, scenario: Scenario, history: list[Turn]) -> str:
            return ""

    scenario = Scenario(
        scenario_id="merchant_delay_notice",
        task_id="task_merchant",
        user_profile={"role": "商家店长", "attitude": "忙碌"},
        coverage_targets=["merchant_delay_notice"],
        risk_tags=["merchant_delay"],
        initial_user_intent="您好，这边是美团履约运营，想确认一笔出餐延迟订单。",
        expected_test_focus="确认商家出餐延迟",
    )
    history = [
        Turn(
            turn_id=1,
            speaker="assistant",
            content="您好，请问是负责人吗？我想确认一笔出餐延迟订单。",
        )
    ]

    user_turn = next_user_turn(EmptyUserProvider(), scenario, history)

    assert "美团履约运营" not in user_turn
    assert "确认一笔出餐延迟订单" not in user_turn
    assert "五分钟" in user_turn or "后厨" in user_turn


def test_next_user_turn_keeps_user_identity_consistent_across_turns():
    class ContradictingUserProvider:
        def generate(self, scenario: Scenario, history: list[Turn]) -> str:
            return "是的，我是负责人，我店里这边一般备餐很稳定。"

    scenario = Scenario(
        scenario_id="merchant_delay_notice",
        task_id="task_merchant",
        user_profile={"role": "店员", "attitude": "转接老板"},
        coverage_targets=["merchant_delay_notice"],
        risk_tags=["merchant_delay"],
        initial_user_intent="啊？我不是负责人，我就是打工的。",
        expected_test_focus="确认商家出餐延迟",
    )
    history = [
        Turn(turn_id=1, speaker="assistant", content="请问是负责人吗？"),
        Turn(turn_id=2, speaker="user_simulator", content="啊？我不是负责人，我就是打工的。"),
        Turn(turn_id=3, speaker="assistant", content="那麻烦帮我找一下负责人。"),
    ]

    user_turn = next_user_turn(ContradictingUserProvider(), scenario, history)

    assert "我是负责人" not in user_turn
    assert "我店里" not in user_turn
    assert "喊一下老板" in user_turn or "不是负责人" in user_turn
