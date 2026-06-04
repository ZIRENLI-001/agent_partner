from backend.eval_agent.services.stage_service import scenarios_stage_payload
from backend.evaluation_engine.domain import Scenario, ScenarioSet


class StaticScenarioProvider:
    def generate(self, task_spec, rubric, input_data, minimum):
        return ScenarioSet(
            suite_id="suite_stage_model",
            task_id=task_spec.task_id,
            version=task_spec.version,
            scenarios=[
                Scenario(
                    scenario_id="stage_model_refusal",
                    task_id=task_spec.task_id,
                    user_profile={"role": "骑手", "attitude": "拒绝配送"},
                    coverage_targets=["refusal_to_deliver", "retention"],
                    initial_user_intent="我今天不想跑。",
                    expected_test_focus="测试拒配挽留",
                    difficulty="L3",
                    scenario_type="model_generated",
                    expected_behavior="挽留并说明合同影响",
                    risk_tags=["model_generated", "capacity_pressure"],
                )
            ],
        )


def test_scenarios_stage_payload_can_use_model_scenario_provider():
    payload = scenarios_stage_payload(
        "# Role\n你是站长\n# Task\n通知骑手飞毛腿合同生效",
        minimum_scenarios=1,
        input_data='{"rider_name":"王师傅"}',
        scenario_provider=StaticScenarioProvider(),
    )

    scenario = payload["scenario_set"]["scenarios"][0]

    assert scenario["scenario_id"] == "stage_model_refusal"
    assert "model_generated" in scenario["risk_tags"]
