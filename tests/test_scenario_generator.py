from backend.evaluation_engine.domain import TaskSpec
from backend.evaluation_engine.rubric_builder import build_rubric
from backend.evaluation_engine.scenario_generator import generate_scenarios


def _task_spec() -> TaskSpec:
    return TaskSpec(
        task_id="task_001",
        version="v1",
        task_name="飞毛腿通知",
        role="站长",
        target_user="骑手",
        task_goal="通知合同生效",
        opening_line="你好",
        required_steps=["确认身份", "告知合同生效", "说明单量要求"],
        constraints=["每次回复约30字以内"],
        faq=[{"intent": "退出飞毛腿", "expected_answer": "前一天取消"}],
        edge_cases=[
            {"trigger": "不想配送", "expected_behavior": "挽留"},
            {"trigger": "超出职责范围", "expected_behavior": "确认后回电"},
        ],
        forbidden_actions=["承诺额外奖励"],
    )


def test_generate_scenarios_produces_minimum_coverage():
    task = _task_spec()
    rubric = build_rubric(task)
    scenario_set = generate_scenarios(task, rubric, minimum=5)

    assert scenario_set.task_id == task.task_id
    assert len(scenario_set.scenarios) >= 5
    all_targets = {target for scenario in scenario_set.scenarios for target in scenario.coverage_targets}
    assert "normal_completion" in all_targets
    assert "refusal_to_deliver" in all_targets
    assert "faq_exit" in all_targets
    assert "boundary_no_extra_promise" in all_targets
    assert "out_of_scope" in all_targets


def test_generate_scenarios_meets_minimum_above_six_with_unique_ids():
    task = _task_spec()
    rubric = build_rubric(task)
    scenario_set = generate_scenarios(task, rubric, minimum=9)

    scenario_ids = [scenario.scenario_id for scenario in scenario_set.scenarios]
    assert len(scenario_set.scenarios) >= 9
    assert len(scenario_ids) == len(set(scenario_ids))


def test_generate_scenarios_extends_minimum_with_rich_user_reactions():
    task = _task_spec()
    rubric = build_rubric(task)
    scenario_set = generate_scenarios(task, rubric, minimum=12)

    all_targets = {target for scenario in scenario_set.scenarios for target in scenario.coverage_targets}
    scenario_types = {scenario.scenario_type for scenario in scenario_set.scenarios}
    initial_intents = [scenario.initial_user_intent for scenario in scenario_set.scenarios]

    assert "deterministic_filler" not in all_targets
    assert "coverage_padding" not in {
        tag for scenario in scenario_set.scenarios for tag in scenario.risk_tags
    }
    assert {
        "poor_signal",
        "identity_mismatch",
        "address_exception",
        "after_sales_boundary",
    }.issubset(all_targets)
    assert len(scenario_types) >= 8
    assert not any("按常规节奏回应" in intent for intent in initial_intents)


def test_generate_scenarios_uses_task_version_in_suite_metadata():
    task = _task_spec()
    task.version = "v2"
    rubric = build_rubric(task)
    scenario_set = generate_scenarios(task, rubric, minimum=5)

    assert scenario_set.suite_id == "suite_task_001_v2"
    assert scenario_set.suite_id.endswith("_v2")
    assert scenario_set.version == "v2"
