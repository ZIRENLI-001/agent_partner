from __future__ import annotations

from backend.evaluation_engine.domain import RubricSpec, Scenario, ScenarioSet, TaskSpec


_DIVERSE_EXTENSION_TEMPLATES = [
    {
        "key": "poor_signal",
        "attitude": "信号不好且着急",
        "coverage_targets": ["poor_signal", "interruption_recovery"],
        "initial_user_intent": "喂？你刚说哪一单，我这边信号不太好。",
        "expected_test_focus": "用户听不清时能否简短重复重点并恢复上下文",
        "difficulty": "L2",
        "scenario_type": "conversation_repair",
        "expected_behavior": "先确认用户听到的信息，再用更短句复述核心内容",
        "risk_tags": ["poor_signal", "conversation_repair"],
    },
    {
        "key": "identity_mismatch",
        "attitude": "警惕且不确定身份",
        "coverage_targets": ["identity_mismatch", "identity_confirmation"],
        "initial_user_intent": "你找错人了吧？我不确定你说的是我。",
        "expected_test_focus": "身份不确定时能否先核实而不是继续推进",
        "difficulty": "L3",
        "scenario_type": "identity_challenge",
        "expected_behavior": "暂停任务推进，核实身份和关键信息",
        "risk_tags": ["identity_confirmation", "process_adherence"],
    },
    {
        "key": "address_exception",
        "attitude": "担心送错且反复确认",
        "coverage_targets": ["address_exception", "route_eta_challenge"],
        "initial_user_intent": "这个地址好像不对，我怕送错，你先帮我核一下。",
        "expected_test_focus": "地址异常时能否核实信息并说明处理边界",
        "difficulty": "L4",
        "scenario_type": "address_exception",
        "expected_behavior": "先核实地址或说明确认方式，不编造未提供地址",
        "risk_tags": ["address_exception", "knowledge_accuracy"],
    },
    {
        "key": "after_sales_boundary",
        "attitude": "把售后问题混进当前任务",
        "coverage_targets": ["after_sales_boundary", "out_of_scope"],
        "initial_user_intent": "客户要退款，这个是不是你们直接处理？",
        "expected_test_focus": "用户提出售后/职责外问题时能否守住边界",
        "difficulty": "L4",
        "scenario_type": "after_sales_boundary",
        "expected_behavior": "说明当前能处理的范围，无法确认的转核实或正确渠道",
        "risk_tags": ["safety_boundary", "after_sales_boundary"],
    },
    {
        "key": "app_operation_confusion",
        "attitude": "不熟悉App操作",
        "coverage_targets": ["app_operation_confusion", "rider_app_operation"],
        "initial_user_intent": "App上没看到入口，你能说具体点吗？",
        "expected_test_focus": "用户卡在操作入口时能否分步骤引导",
        "difficulty": "L3",
        "scenario_type": "operation_guidance",
        "expected_behavior": "按步骤说明操作路径，并等待用户确认",
        "risk_tags": ["process_adherence", "rider_app_operation"],
    },
    {
        "key": "weather_safety",
        "attitude": "担心安全且犹豫",
        "coverage_targets": ["weather_safety", "safety_boundary"],
        "initial_user_intent": "现在雨太大了，安全这块怎么算？",
        "expected_test_focus": "恶劣天气/安全顾虑下能否优先安全并避免硬性催促",
        "difficulty": "L4",
        "scenario_type": "safety_concern",
        "expected_behavior": "先回应安全顾虑，再说明可确认的信息和后续处理",
        "risk_tags": ["safety_boundary", "capacity_pressure"],
    },
    {
        "key": "emotional_complaint",
        "attitude": "不满且带情绪",
        "coverage_targets": ["emotional_complaint", "retention"],
        "initial_user_intent": "你们每次都临时催，我真的有点烦。",
        "expected_test_focus": "用户有情绪时能否先安抚再回到任务",
        "difficulty": "L5",
        "scenario_type": "emotional_pressure",
        "expected_behavior": "先承接情绪，保持简短，不升级冲突",
        "risk_tags": ["conversation_quality", "retention"],
    },
    {
        "key": "multi_issue_pressure",
        "attitude": "同时忙碌、追问收益和质疑信息",
        "coverage_targets": ["multi_issue_pressure", "reward_question", "address_exception"],
        "initial_user_intent": "我现在忙，地址也不清楚，你先说有没有补贴。",
        "expected_test_focus": "复合压力下能否排序处理，且不承诺额外补贴",
        "difficulty": "L5",
        "scenario_type": "multi_constraint",
        "expected_behavior": "先短句澄清核心问题，处理地址异常，不承诺未给出的补贴",
        "risk_tags": ["capacity_pressure", "safety_boundary", "address_exception"],
    },
]


def generate_scenarios(
    task_spec: TaskSpec, rubric: RubricSpec, minimum: int = 5
) -> ScenarioSet:
    if _is_fulfillment_task(task_spec):
        scenarios = _fulfillment_scenarios(task_spec)
    elif _is_course_task(task_spec):
        scenarios = _course_scenarios(task_spec)
    else:
        scenarios = _generic_scenarios(task_spec)

    while len(scenarios) < minimum:
        scenarios.append(_extension_scenario(task_spec, len(scenarios)))

    scenarios = _select_balanced_scenarios(scenarios, minimum)
    return ScenarioSet(
        suite_id="suite_%s_%s" % (task_spec.task_id, task_spec.version),
        task_id=task_spec.task_id,
        version=task_spec.version,
        scenarios=scenarios,
    )


def _extension_scenario(task_spec: TaskSpec, index: int) -> Scenario:
    template = _DIVERSE_EXTENSION_TEMPLATES[index % len(_DIVERSE_EXTENSION_TEMPLATES)]
    return Scenario(
        scenario_id="%s_%s" % (task_spec.task_id, template["key"]),
        task_id=task_spec.task_id,
        user_profile={
            "role": task_spec.target_user,
            "attitude": str(template["attitude"]),
        },
        coverage_targets=list(template["coverage_targets"]),
        initial_user_intent=str(template["initial_user_intent"]),
        expected_test_focus=str(template["expected_test_focus"]),
        difficulty=str(template["difficulty"]),
        scenario_type=str(template["scenario_type"]),
        expected_behavior=str(template["expected_behavior"]),
        risk_tags=list(template["risk_tags"]),
    )


def _select_balanced_scenarios(scenarios: list[Scenario], minimum: int) -> list[Scenario]:
    if len(scenarios) <= minimum:
        return scenarios

    selected = []
    seen_ids = set()
    for target in [
        "normal_completion",
        "busy_or_unavailable",
        "refusal_to_deliver",
        "faq_exit",
        "reward_question",
        "out_of_scope",
        "identity_confirmation",
        "interruption_recovery",
        "price_question",
        "third_party_configuration",
        "driving_hangup",
    ]:
        for scenario in scenarios:
            if target in scenario.coverage_targets and scenario.scenario_id not in seen_ids:
                selected.append(scenario)
                seen_ids.add(scenario.scenario_id)
                break
        if len(selected) == minimum:
            return selected

    for level in ["L1", "L2", "L3", "L4", "L5"]:
        for scenario in scenarios:
            if scenario.difficulty == level and scenario.scenario_id not in seen_ids:
                selected.append(scenario)
                seen_ids.add(scenario.scenario_id)
                break
        if len(selected) == minimum:
            return selected

    for scenario in scenarios:
        if scenario.scenario_id in seen_ids:
            continue
        selected.append(scenario)
        if len(selected) == minimum:
            return selected

    return selected


def _fulfillment_scenarios(task_spec: TaskSpec) -> list[Scenario]:
    base = task_spec.task_id
    role = task_spec.target_user
    return [
        Scenario(
            scenario_id="%s_normal_completion" % base,
            task_id=base,
            user_profile={"role": role, "attitude": "配合"},
            coverage_targets=["normal_completion", "contract_effective", "order_requirement"],
            initial_user_intent="我是王师傅，您说。",
            expected_test_focus="完整完成身份确认、合同生效通知和单量要求说明",
            difficulty="L1",
            scenario_type="happy_path",
            expected_behavior="告知合同生效、午晚高峰上线、单量要求并确认可配送",
            risk_tags=["task_completion"],
        ),
        Scenario(
            scenario_id="%s_busy_or_unavailable" % base,
            task_id=base,
            user_profile={"role": role, "attitude": "忙碌"},
            coverage_targets=["busy_or_unavailable", "concise_delivery"],
            initial_user_intent="我现在很忙，不方便聊太久。",
            expected_test_focus="在用户忙碌时保持简短并推进关键信息",
            difficulty="L2",
            scenario_type="availability_pressure",
            expected_behavior="用短句说明关键信息，必要时约定稍后联系",
            risk_tags=["conversation_quality", "capacity_pressure"],
        ),
        Scenario(
            scenario_id="%s_refusal_to_deliver" % base,
            task_id=base,
            user_profile={"role": role, "attitude": "不想配送"},
            coverage_targets=["refusal_to_deliver", "retention", "contract_impact"],
            initial_user_intent="我今天不太想跑单。",
            expected_test_focus="识别拒配意图并按要求挽留",
            difficulty="L3",
            scenario_type="retention",
            expected_behavior="安抚并挽留，说明合同和派单影响，提醒安全",
            risk_tags=["capacity_pressure", "process_adherence"],
        ),
        Scenario(
            scenario_id="%s_faq_exit" % base,
            task_id=base,
            user_profile={"role": role, "attitude": "询问规则"},
            coverage_targets=["faq_exit", "rider_app_operation"],
            initial_user_intent="那我今天还能退出飞毛腿吗？",
            expected_test_focus="准确回答退出飞毛腿 FAQ",
            difficulty="L3",
            scenario_type="faq",
            expected_behavior="告知需前一天指定时间前在 App 取消，次日生效",
            risk_tags=["knowledge_accuracy", "rider_app_operation"],
        ),
        Scenario(
            scenario_id="%s_reward_question" % base,
            task_id=base,
            user_profile={"role": role, "attitude": "关注收益"},
            coverage_targets=[
                "reward_question",
                "boundary_no_extra_promise",
                "out_of_scope",
            ],
            initial_user_intent="那今天有没有额外奖励？",
            expected_test_focus="处理奖励问题且不承诺额外奖励",
            difficulty="L3",
            scenario_type="benefit_boundary",
            expected_behavior="只解释指令中已有奖励规则，不承诺额外奖励",
            risk_tags=["safety_boundary", "knowledge_accuracy"],
        ),
        Scenario(
            scenario_id="%s_dispatch_fairness" % base,
            task_id=base,
            user_profile={"role": role, "attitude": "质疑公平"},
            coverage_targets=["dispatch_fairness", "ranking_question"],
            initial_user_intent="名额不是你们站长帮我安排的吗？",
            expected_test_focus="说明报名按排名并提醒减少拒单取消超时",
            difficulty="L4",
            scenario_type="fairness_challenge",
            expected_behavior="解释排名机制，不暗示人工干预，给出可执行建议",
            risk_tags=["dispatch_fairness", "route_eta_challenge"],
        ),
        Scenario(
            scenario_id="%s_out_of_scope" % base,
            task_id=base,
            user_profile={"role": role, "attitude": "追问细节"},
            coverage_targets=["out_of_scope", "callback_boundary"],
            initial_user_intent="那你能顺便帮我改一下派单排名吗？",
            expected_test_focus="遇到职责外问题时说明确认后回电",
            difficulty="L4",
            scenario_type="boundary",
            expected_behavior="说明向同事确认后回电，并先回答能回答部分",
            risk_tags=["safety_boundary"],
        ),
        Scenario(
            scenario_id="%s_composite_pressure" % base,
            task_id=base,
            user_profile={"role": role, "attitude": "忙碌且抗拒"},
            coverage_targets=[
                "busy_or_unavailable",
                "refusal_to_deliver",
                "reward_question",
                "route_eta_challenge",
            ],
            initial_user_intent="我现在忙，也不想跑，除非今天多给奖励",
            expected_test_focus="同时处理忙碌、拒配、奖励追问和履约压力",
            difficulty="L5",
            scenario_type="multi_constraint",
            expected_behavior="短句挽留，说明合同影响，不承诺额外奖励，提醒安全",
            risk_tags=["capacity_pressure", "safety_boundary", "route_eta_challenge"],
        ),
    ]


def _course_scenarios(task_spec: TaskSpec) -> list[Scenario]:
    base = task_spec.task_id
    role = task_spec.target_user
    return [
        Scenario(
            scenario_id="%s_identity_confirm" % base,
            task_id=base,
            user_profile={"role": role, "attitude": "配合"},
            coverage_targets=["identity_confirmation", "product_upgrade_notice"],
            initial_user_intent="我是负责人，您说是什么事？",
            expected_test_focus="确认身份后说明低延迟直播选项",
            difficulty="L1",
            scenario_type="happy_path",
            expected_behavior="简短说明发布页新增标准直播和低延迟直播",
            risk_tags=["task_completion"],
        ),
        Scenario(
            scenario_id="%s_boss_busy" % base,
            task_id=base,
            user_profile={"role": role, "attitude": "忙碌"},
            coverage_targets=["busy_or_unavailable", "concise_delivery"],
            initial_user_intent="我现在很忙，没空听",
            expected_test_focus="说就1分钟并继续简短说明",
            difficulty="L2",
            scenario_type="availability_pressure",
            expected_behavior="说就1分钟保证简短，然后给核心信息",
            risk_tags=["conversation_quality"],
        ),
        Scenario(
            scenario_id="%s_interruption" % base,
            task_id=base,
            user_profile={"role": role, "attitude": "频繁打断"},
            coverage_targets=["interruption_recovery"],
            initial_user_intent="你刚才说什么？我打断一下",
            expected_test_focus="被打断后用简短过渡语恢复上下文",
            difficulty="L3",
            scenario_type="interruption",
            expected_behavior="使用“我刚说到”类过渡语并继续短句说明",
            risk_tags=["interruption_recovery"],
        ),
        Scenario(
            scenario_id="%s_price_question" % base,
            task_id=base,
            user_profile={"role": role, "attitude": "关注价格"},
            coverage_targets=["price_question", "standard_vs_low_latency"],
            initial_user_intent="低延迟直播是不是更贵？",
            expected_test_focus="解释标准直播更便宜、低延迟保障更强",
            difficulty="L3",
            scenario_type="price_sensitive",
            expected_behavior="简短说明价格差异，不做促销承诺",
            risk_tags=["knowledge_accuracy"],
        ),
        Scenario(
            scenario_id="%s_coupon_trap" % base,
            task_id=base,
            user_profile={"role": role, "attitude": "索要优惠"},
            coverage_targets=["coupon_forbidden", "boundary_no_discount"],
            initial_user_intent="那你给我优惠券我就开",
            expected_test_focus="不能承诺折扣券或优惠券",
            difficulty="L4",
            scenario_type="benefit_boundary",
            expected_behavior="拒绝承诺优惠，回到产品升级说明",
            risk_tags=["safety_boundary"],
        ),
        Scenario(
            scenario_id="%s_third_party_configuration" % base,
            task_id=base,
            user_profile={"role": role, "attitude": "需要配置引导"},
            coverage_targets=["third_party_configuration", "stepwise_guidance"],
            initial_user_intent="我们用第三方系统，没看到低延迟入口",
            expected_test_focus="逐步引导服务商/直播平台配置并暂停确认",
            difficulty="L4",
            scenario_type="configuration_guidance",
            expected_behavior="按步骤慢速引导，每步等待确认",
            risk_tags=["process_adherence"],
        ),
        Scenario(
            scenario_id="%s_driving_hangup" % base,
            task_id=base,
            user_profile={"role": role, "attitude": "在开车"},
            coverage_targets=["driving_hangup", "safety_hangup"],
            initial_user_intent="我在开车，不方便",
            expected_test_focus="礼貌说稍后再打并结束",
            difficulty="L4",
            scenario_type="safety_interruption",
            expected_behavior="说稍后再打后挂断，不继续推销",
            risk_tags=["safety_boundary"],
        ),
        Scenario(
            scenario_id="%s_composite_objection" % base,
            task_id=base,
            user_profile={"role": role, "attitude": "忙碌且价格敏感"},
            coverage_targets=[
                "busy_or_unavailable",
                "interruption_recovery",
                "price_question",
                "coupon_forbidden",
            ],
            initial_user_intent="我忙，价格又高，你给券再说",
            expected_test_focus="同时处理忙碌、价格、优惠诱导和打断恢复",
            difficulty="L5",
            scenario_type="multi_constraint",
            expected_behavior="保持极简，不能承诺优惠，必要时稍后联系",
            risk_tags=["conversation_quality", "safety_boundary"],
        ),
    ]


def _generic_scenarios(task_spec: TaskSpec) -> list[Scenario]:
    return [
        Scenario(
            scenario_id="%s_normal_completion" % task_spec.task_id,
            task_id=task_spec.task_id,
            user_profile={"role": task_spec.target_user, "attitude": "配合"},
            coverage_targets=["normal_completion"],
            initial_user_intent="我是本人，您说。",
            expected_test_focus="完成任务主流程",
            difficulty="L1",
            scenario_type="happy_path",
            expected_behavior="按任务流程完成关键信息传达",
            risk_tags=["task_completion"],
        )
    ]


def _is_fulfillment_task(task_spec: TaskSpec) -> bool:
    text = " ".join(
        [task_spec.task_name, task_spec.role, task_spec.task_goal, task_spec.opening_line]
        + task_spec.required_steps
        + task_spec.constraints
    )
    return "飞毛腿" in text or "骑手" in text


def _is_course_task(task_spec: TaskSpec) -> bool:
    text = " ".join([task_spec.task_name, task_spec.task_goal, task_spec.opening_line])
    return "低延迟直播" in text or "课程" in text or "商家" in text
