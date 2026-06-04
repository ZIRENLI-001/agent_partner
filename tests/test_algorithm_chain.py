from backend.evaluation_engine.instruction_parser import parse_instruction
from backend.evaluation_engine.rubric_builder import build_rubric
from backend.evaluation_engine.sample_tasks import FULFILLMENT_BACKGROUND, load_sample_tasks
from backend.evaluation_engine.scenario_generator import generate_scenarios


def _task_by_name(keyword: str):
    for task in load_sample_tasks():
        if keyword in task["name"] or keyword in task["instruction"]:
            return task
    raise AssertionError("sample task not found: %s" % keyword)


def test_sample_tasks_include_fulfillment_background_for_scenario_expansion():
    tasks = load_sample_tasks()

    assert len(tasks) >= 2
    assert any("飞毛腿" in task["instruction"] for task in tasks)
    assert any("低延迟直播" in task["instruction"] for task in tasks)

    background_text = " ".join(FULFILLMENT_BACKGROUND["capabilities"])
    for term in ["订单调度", "骑手 App", "ETA", "运力", "路由优化", "智能调度"]:
        assert term in background_text


def test_fulfillment_scenarios_cover_l1_to_l5_difficulty_and_meituan_risks():
    task = _task_by_name("飞毛腿")
    spec = parse_instruction(task["instruction"], task_id="fulfillment_task")
    rubric = build_rubric(spec)

    scenario_set = generate_scenarios(spec, rubric, minimum=8)
    scenarios = scenario_set.scenarios

    assert len(scenarios) >= 8
    assert {scenario.difficulty for scenario in scenarios}.issuperset(
        {"L1", "L2", "L3", "L4", "L5"}
    )
    assert all(scenario.scenario_type for scenario in scenarios)
    assert all(scenario.expected_behavior for scenario in scenarios)
    assert all(scenario.risk_tags for scenario in scenarios)
    assert any("capacity_pressure" in scenario.risk_tags for scenario in scenarios)
    assert any("route_eta_challenge" in scenario.risk_tags for scenario in scenarios)
    assert any(
        {"busy_or_unavailable", "refusal_to_deliver", "reward_question"}.issubset(
            set(scenario.coverage_targets)
        )
        for scenario in scenarios
    )


def test_course_scenarios_cover_interruption_price_and_third_party_configuration():
    task = _task_by_name("课程")
    spec = parse_instruction(task["instruction"], task_id="course_task")
    rubric = build_rubric(spec)

    scenario_set = generate_scenarios(spec, rubric, minimum=8)
    targets = [set(scenario.coverage_targets) for scenario in scenario_set.scenarios]

    assert any("interruption_recovery" in target for target in targets)
    assert any("price_question" in target for target in targets)
    assert any("third_party_configuration" in target for target in targets)
    assert any("driving_hangup" in target for target in targets)
    assert {scenario.difficulty for scenario in scenario_set.scenarios}.issuperset(
        {"L1", "L2", "L3", "L4", "L5"}
    )


def test_rubric_contains_production_dimensions_and_critical_risk_items():
    task = _task_by_name("飞毛腿")
    spec = parse_instruction(task["instruction"], task_id="fulfillment_task")

    rubric = build_rubric(spec)
    dimensions = {item.dimension for item in rubric.items}
    critical_criteria = " ".join(item.criterion for item in rubric.items if item.critical)

    assert {
        "task_completion",
        "process_adherence",
        "knowledge_accuracy",
        "constraint_following",
        "boundary_safety",
        "conversation_quality",
    }.issubset(dimensions)
    assert "承诺额外奖励" in critical_criteria
    assert "超出职责范围" in critical_criteria


def test_stage_model_strategy_declares_model_choices_and_standards():
    from backend.evaluation_engine.evaluation_strategy import build_evaluation_strategy

    task = _task_by_name("飞毛腿")
    spec = parse_instruction(task["instruction"], task_id="fulfillment_task")
    strategy = build_evaluation_strategy(spec)

    stages = {stage.stage: stage for stage in strategy.stages}

    for stage in [
        "instruction_parsing",
        "rubric_generation",
        "scenario_generation",
        "user_simulation",
        "target_model",
        "semantic_judge",
        "rule_judge",
        "report_generation",
    ]:
        assert stage in stages
        assert stages[stage].model_choice
        assert stages[stage].evaluation_standard

    assert stages["semantic_judge"].temperature == 0
    assert "证据" in stages["semantic_judge"].evaluation_standard
    assert "确定性规则" in stages["rule_judge"].model_choice
