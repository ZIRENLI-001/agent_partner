import json
from pathlib import Path

from backend.eval_agent.providers.base import ModelResponse


class RecordingModelProvider:
    def __init__(self, content: str = "模型输出<DONE>"):
        self.content = content
        self.calls = []

    def generate(self, messages, config):
        self.calls.append({"messages": messages, "config": config})
        return ModelResponse(content=self.content, raw={"ok": True})


class SequencedModelProvider:
    def __init__(self, contents: list[str]):
        self.contents = list(contents)
        self.calls = []

    def generate(self, messages, config):
        self.calls.append({"messages": messages, "config": config})
        if not self.contents:
            raise AssertionError("no model response left")
        return ModelResponse(content=self.contents.pop(0), raw={"ok": True})


def test_backend_chain_model_config_summary_is_persisted_without_api_keys(tmp_path, monkeypatch):
    from backend.eval_agent.api.routes.runs import ModelConfig, RunRequest
    from backend.eval_agent.services import run_service

    monkeypatch.setattr(run_service, "RUN_ROOT", tmp_path)
    monkeypatch.setenv("EVAL_CHAIN_PROVIDER", "openrouter")
    monkeypatch.setenv("EVAL_CHAIN_API_BASE", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("EVAL_CHAIN_API_KEY", "sk-chain-secret")
    monkeypatch.setenv("EVAL_USER_SIMULATOR_MODEL", "openai/gpt-4.1-mini")
    monkeypatch.setenv("EVAL_SEMANTIC_JUDGE_MODEL", "anthropic/claude-sonnet-4.6")
    monkeypatch.setenv("EVAL_RUBRIC_GENERATOR_MODEL", "anthropic/claude-sonnet-4.6")
    monkeypatch.setenv("EVAL_SCENARIO_GENERATOR_MODEL", "google/gemini-2.5-flash")
    monkeypatch.setenv("EVAL_REPORT_GENERATOR_MODEL", "openai/gpt-4.1-mini")
    monkeypatch.setenv("EVAL_INSTRUCTION_PARSER_MODEL", "anthropic/claude-sonnet-4.6")
    response = run_service.create_run_payload(
        RunRequest(
            instruction="# Role\n你是站长\n# Task\n通知骑手合同生效",
            minimum_scenarios=1,
            model_config=ModelConfig(
                provider="mock",
                model_name="target-demo",
                api_key="sk-target-secret",
            ),
        )
    )

    run_config_path = tmp_path / response["run_id"] / "run_config.json"
    run_config = json.loads(run_config_path.read_text(encoding="utf-8"))
    serialized_response = json.dumps(response, ensure_ascii=False)
    serialized_config = json.dumps(run_config, ensure_ascii=False)

    assert response["stage_model_config_summary"]["target_model"]["model_name"] == "target-demo"
    assert response["stage_model_config_summary"]["user_simulator"]["model_name"] == "openai/gpt-4.1-mini"
    assert response["stage_model_config_summary"]["semantic_judge"]["model_name"] == "anthropic/claude-sonnet-4.6"
    assert response["stage_model_config_summary"]["rubric_generator"]["model_name"] == "anthropic/claude-sonnet-4.6"
    assert response["stage_model_config_summary"]["scenario_generator"]["model_name"] == "google/gemini-2.5-flash"
    assert response["stage_model_config_summary"]["report_generator"]["model_name"] == "openai/gpt-4.1-mini"
    assert response["stage_model_config_summary"]["instruction_parser"]["model_name"] == "anthropic/claude-sonnet-4.6"
    assert response["stage_model_config_summary"]["target_model"]["api_key_configured"] is True
    assert run_config["stage_model_config_summary"]["semantic_judge"]["api_key_configured"] is True
    assert "sk-target-secret" not in serialized_response
    assert "sk-chain-secret" not in serialized_response
    assert "sk-target-secret" not in serialized_config
    assert "sk-chain-secret" not in serialized_config


def test_legacy_model_config_still_maps_to_target_model_summary(tmp_path, monkeypatch):
    from backend.eval_agent.api.routes.runs import ModelConfig, RunRequest
    from backend.eval_agent.services import run_service

    monkeypatch.setattr(run_service, "RUN_ROOT", tmp_path)
    response = run_service.create_run_payload(
        RunRequest(
            instruction="# Role\n你是站长\n# Task\n通知骑手合同生效",
            minimum_scenarios=1,
            model_config=ModelConfig(
                provider="mock",
                model_name="legacy-target",
                api_key="sk-legacy-secret",
            ),
        )
    )

    assert response["model_config_summary"]["model_name"] == "legacy-target"
    assert response["stage_model_config_summary"]["target_model"]["model_name"] == "legacy-target"
    assert "sk-legacy-secret" not in json.dumps(response, ensure_ascii=False)


def test_backend_chain_models_fallback_to_mock_without_chain_api_key(monkeypatch):
    from backend.eval_agent.services import run_service

    monkeypatch.setenv("EVAL_CHAIN_API_KEY", "")
    monkeypatch.setenv("EVAL_CHAIN_PROVIDER", "openrouter")
    monkeypatch.setenv("EVAL_USER_SIMULATOR_MODEL", "openai/gpt-4.1-mini")

    configs = run_service.backend_stage_model_config()

    assert configs["user_simulator"].provider == "mock"
    assert configs["semantic_judge"].provider == "mock"


def test_openrouter_target_model_uses_backend_chain_key_when_frontend_key_empty(monkeypatch):
    from backend.eval_agent.api.routes.runs import ModelConfig, RunRequest
    from backend.eval_agent.services import run_service

    monkeypatch.setenv("EVAL_CHAIN_PROVIDER", "openrouter")
    monkeypatch.setenv("EVAL_CHAIN_API_BASE", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("EVAL_CHAIN_API_KEY", "sk-backend-openrouter")

    configs = run_service.effective_stage_model_config(
        RunRequest(
            instruction="# Role\n你是站长\n# Task\n通知骑手合同生效",
            model_config=ModelConfig(
                provider="openrouter",
                model_name="openai/gpt-4.1-mini",
                api_base="https://openrouter.ai/api/v1",
                api_key="",
            ),
        )
    )

    assert configs["target_model"].provider == "openrouter"
    assert configs["target_model"].model_name == "openai/gpt-4.1-mini"
    assert configs["target_model"].api_base == "https://openrouter.ai/api/v1"
    assert configs["target_model"].api_key == "sk-backend-openrouter"
    summary = run_service.stage_model_config_summary(configs)
    assert summary["target_model"]["api_key_configured"] is True
    assert "sk-backend-openrouter" not in json.dumps(summary, ensure_ascii=False)


def test_user_simulator_model_adapter_uses_its_own_model_config():
    from backend.eval_agent.api.routes.runs import ModelConfig
    from backend.eval_agent.services.run_service import build_user_provider
    from backend.evaluation_engine.domain import Scenario

    model_provider = RecordingModelProvider(content="我现在不想配送。")
    user_provider = build_user_provider(
        ModelConfig(
            provider="openrouter",
            model_name="openrouter/user-sim",
            api_base="https://openrouter.ai/api/v1",
            api_key="sk-user",
        ),
        model_provider=model_provider,
    )

    content = user_provider.generate(
        Scenario(
            scenario_id="scenario_refusal",
            task_id="task_001",
            user_profile={"role": "骑手", "attitude": "不想配送"},
            coverage_targets=["refusal_to_deliver"],
            initial_user_intent="我不想配送",
            expected_test_focus="拒配挽留",
        ),
        history=[],
    )

    assert content == "我现在不想配送。"
    assert model_provider.calls[0]["config"].model_name == "openrouter/user-sim"
    assert "refusal_to_deliver" in model_provider.calls[0]["messages"][0]["content"]


def test_user_simulator_history_is_transcript_not_chat_assistant_memory():
    from backend.eval_agent.api.routes.runs import ModelConfig
    from backend.eval_agent.services.run_service import build_user_provider
    from backend.evaluation_engine.domain import Scenario, Turn

    model_provider = RecordingModelProvider(content="我今天身体有点累，不太想跑。")
    user_provider = build_user_provider(
        ModelConfig(
            provider="openrouter",
            model_name="openrouter/user-sim",
            api_base="https://openrouter.ai/api/v1",
            api_key="sk-user",
        ),
        model_provider=model_provider,
    )

    user_provider.generate(
        Scenario(
            scenario_id="rider_refusal",
            task_id="task_001",
            user_profile={"role": "骑手", "attitude": "疲惫"},
            coverage_targets=["refusal_to_deliver"],
            initial_user_intent="我今天身体有点累。",
            expected_test_focus="拒配挽留",
        ),
        history=[
            Turn(
                turn_id=1,
                speaker="assistant",
                content="飞毛腿合同今天生效，午晚高峰需要上线。",
            ),
            Turn(turn_id=2, speaker="user_simulator", content="我今天身体有点累。"),
        ],
    )

    messages = model_provider.calls[0]["messages"]
    assert [message["role"] for message in messages] == ["system", "user"]
    assert "第 1 轮assistant：飞毛腿合同今天生效" in messages[1]["content"]
    assert "第 2 轮user_simulator：我今天身体有点累" in messages[1]["content"]


def test_semantic_judge_model_adapter_returns_evidence_from_json():
    from backend.eval_agent.api.routes.runs import ModelConfig
    from backend.eval_agent.services.run_service import build_semantic_judge_provider
    from backend.evaluation_engine.domain import DialogueTrace, RubricItem, Turn

    model_provider = RecordingModelProvider(
        content=json.dumps(
            {
                "verdict": "partial",
                "score": 4,
                "turn_ids": [2],
                "reason": "覆盖了合同生效，但缺少是否配送确认",
                "explanation": "第2轮只覆盖部分流程",
            },
            ensure_ascii=False,
        )
    )
    judge_provider = build_semantic_judge_provider(
        ModelConfig(
            provider="openrouter",
            model_name="openrouter/judge",
            api_base="https://openrouter.ai/api/v1",
            api_key="sk-judge",
        ),
        model_provider=model_provider,
    )
    evidence = judge_provider.judge(
        DialogueTrace(
            trace_id="trace_001",
            run_id="run_001",
            task_id="task_001",
            scenario_id="scenario_001",
            turns=[Turn(turn_id=2, speaker="assistant", content="合同已经生效。")],
            termination_reason="task_completed",
        ),
        RubricItem(
            item_id="step_01",
            dimension="task_completion",
            criterion="询问骑手是否可以开始配送",
            source="Call Flow 第1步",
            check_type="semantic",
            weight=10,
        ),
    )

    assert evidence.verdict == "partial"
    assert evidence.score == 4
    assert evidence.max_score == 10
    assert evidence.turn_ids == [2]
    assert evidence.rubric_item_id == "step_01"
    assert model_provider.calls[0]["config"].model_name == "openrouter/judge"


def test_semantic_judge_model_adapter_batches_rubric_items_in_one_model_call():
    from backend.eval_agent.api.routes.runs import ModelConfig
    from backend.eval_agent.services.run_service import build_semantic_judge_provider
    from backend.evaluation_engine.domain import DialogueTrace, RubricItem, Turn

    model_provider = RecordingModelProvider(
        content=json.dumps(
            {
                "items": [
                    {
                        "rubric_item_id": "step_01",
                        "verdict": "pass",
                        "score": 10,
                        "turn_ids": [2],
                        "reason": "已通知合同生效",
                        "explanation": "第2轮完成合同生效通知",
                    },
                    {
                        "rubric_item_id": "step_02",
                        "verdict": "fail",
                        "score": 0,
                        "turn_ids": [],
                        "reason": "未询问能否开始配送",
                        "explanation": "轨迹中没有配送确认问题",
                    },
                ]
            },
            ensure_ascii=False,
        )
    )
    judge_provider = build_semantic_judge_provider(
        ModelConfig(
            provider="openrouter",
            model_name="openrouter/judge",
            api_base="https://openrouter.ai/api/v1",
            api_key="sk-judge",
        ),
        model_provider=model_provider,
    )

    evidence = judge_provider.judge_many(
        DialogueTrace(
            trace_id="trace_001",
            run_id="run_001",
            task_id="task_001",
            scenario_id="scenario_001",
            turns=[Turn(turn_id=2, speaker="assistant", content="合同已经生效。")],
            termination_reason="task_completed",
        ),
        [
            RubricItem(
                item_id="step_01",
                dimension="task_completion",
                criterion="通知骑手合同生效",
                source="Call Flow 第1步",
                check_type="semantic",
                weight=10,
            ),
            RubricItem(
                item_id="step_02",
                dimension="process_adherence",
                criterion="询问骑手是否可以开始配送",
                source="Call Flow 第1步",
                check_type="semantic",
                weight=8,
            ),
        ],
    )

    assert len(model_provider.calls) == 1
    assert [item.rubric_item_id for item in evidence] == ["step_01", "step_02"]
    assert [item.score for item in evidence] == [10, 0]
    assert model_provider.calls[0]["config"].max_tokens == 3000
    assert "rubric_items" in model_provider.calls[0]["messages"][1]["content"]


def test_semantic_judge_batch_missing_item_is_retried_with_single_item_judge():
    from backend.eval_agent.api.routes.runs import ModelConfig
    from backend.eval_agent.services.run_service import build_semantic_judge_provider
    from backend.evaluation_engine.domain import DialogueTrace, RubricItem, Turn

    model_provider = SequencedModelProvider(
        [
            json.dumps(
                {
                    "items": [
                        {
                            "rubric_item_id": "step_01",
                            "verdict": "pass",
                            "score": 10,
                            "turn_ids": [1],
                            "reason": "已完成开场确认",
                            "explanation": "第1轮完成",
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            json.dumps(
                {
                    "verdict": "pass",
                    "score": 6,
                    "turn_ids": [3],
                    "reason": "已询问是否可以开始配送",
                    "explanation": "第3轮完成配送确认",
                },
                ensure_ascii=False,
            ),
        ]
    )
    judge_provider = build_semantic_judge_provider(
        ModelConfig(
            provider="openrouter",
            model_name="openrouter/judge",
            api_base="https://openrouter.ai/api/v1",
            api_key="sk-judge",
        ),
        model_provider=model_provider,
    )

    evidence = judge_provider.judge_many(
        DialogueTrace(
            trace_id="trace_001",
            run_id="run_001",
            task_id="task_001",
            scenario_id="scenario_001",
            turns=[
                Turn(turn_id=1, speaker="assistant", content="您好，请问是王师傅吗？"),
                Turn(turn_id=2, speaker="user_simulator", content="是我。"),
                Turn(turn_id=3, speaker="assistant", content="合同已生效，可以开始配送吗？"),
            ],
            termination_reason="task_completed",
        ),
        [
            RubricItem(
                item_id="step_01",
                dimension="task_completion",
                criterion="确认身份",
                source="Call Flow 第1步",
                check_type="semantic",
                weight=10,
            ),
            RubricItem(
                item_id="step_02",
                dimension="process_adherence",
                criterion="询问是否可以开始配送",
                source="Call Flow 第1步",
                check_type="semantic",
                weight=6,
            ),
        ],
    )

    missing_item_evidence = evidence[1]
    assert missing_item_evidence.rubric_item_id == "step_02"
    assert missing_item_evidence.verdict == "pass"
    assert missing_item_evidence.score == 6
    assert missing_item_evidence.turn_ids == [3]
    assert "已询问是否可以开始配送" in missing_item_evidence.reason
    assert len(model_provider.calls) == 2
    assert "rubric_items" in model_provider.calls[0]["messages"][1]["content"]
    assert "rubric_item" in model_provider.calls[1]["messages"][1]["content"]


def test_scenario_generator_model_adapter_returns_model_scenarios():
    from backend.eval_agent.api.routes.runs import ModelConfig
    from backend.eval_agent.services.run_service import build_scenario_generator_provider
    from backend.evaluation_engine.instruction_parser import parse_instruction
    from backend.evaluation_engine.rubric_builder import build_rubric

    model_provider = RecordingModelProvider(
        content=json.dumps(
            {
                "scenarios": [
                    {
                        "scenario_id": "model_generated_reward_probe",
                        "user_profile": {"role": "骑手", "attitude": "关注收益"},
                        "coverage_targets": ["reward_question", "boundary_no_extra_promise"],
                        "initial_user_intent": "今天跑飞毛腿有没有额外奖励？",
                        "expected_test_focus": "测试被测模型是否会越权承诺奖励",
                        "difficulty": "L4",
                        "scenario_type": "model_generated",
                        "expected_behavior": "只能解释指令内奖励规则，不承诺额外奖励",
                        "risk_tags": ["safety_boundary", "model_generated"],
                    }
                ]
            },
            ensure_ascii=False,
        )
    )
    scenario_provider = build_scenario_generator_provider(
        ModelConfig(
            provider="openrouter",
            model_name="openrouter/scenario-generator",
            api_base="https://openrouter.ai/api/v1",
            api_key="sk-scenario",
        ),
        model_provider=model_provider,
    )
    task_spec = parse_instruction(
        "# Role\n你是美团外卖骑手的站长。\n# Task\n通知骑手飞毛腿合同生效。",
        task_id="task_001",
    )
    rubric = build_rubric(task_spec)

    scenario_set = scenario_provider.generate(
        task_spec,
        rubric,
        '{"rider_name":"王师傅"}',
        minimum=1,
    )

    assert scenario_set.scenarios[0].scenario_id == "model_generated_reward_probe"
    assert scenario_set.scenarios[0].task_id == "task_001"
    assert "model_generated" in scenario_set.scenarios[0].risk_tags
    assert model_provider.calls[0]["config"].model_name == "openrouter/scenario-generator"
    prompt = model_provider.calls[0]["messages"][1]["content"]
    assert "TaskSpec" in prompt
    assert "Rubric" in prompt
    assert "input_data" in prompt
    assert "minimum_scenarios" in prompt
    assert "L1-L5" in prompt
    assert "只输出JSON" in model_provider.calls[0]["messages"][0]["content"]


def test_scenario_generator_sanitizes_invalid_initial_user_intent():
    from backend.eval_agent.api.routes.runs import ModelConfig
    from backend.eval_agent.services.run_service import build_scenario_generator_provider
    from backend.evaluation_engine.instruction_parser import parse_instruction
    from backend.evaluation_engine.rubric_builder import build_rubric

    model_provider = RecordingModelProvider(
        content=json.dumps(
            {
                "scenarios": [
                    {
                        "scenario_id": "bad_rider_prompt",
                        "user_profile": {"role": "骑手", "attitude": "疲惫"},
                        "coverage_targets": ["refusal_to_deliver", "faq_exit"],
                        "initial_user_intent": "请问你现在方便说几句吗？只需要确认一下合同信息，很快的。",
                        "expected_test_focus": "处理骑手拒配和退出追问",
                        "difficulty": "L3",
                        "scenario_type": "model_generated",
                        "expected_behavior": "用户应表达真实阻力",
                        "risk_tags": ["capacity_pressure"],
                    }
                ]
            },
            ensure_ascii=False,
        )
    )
    scenario_provider = build_scenario_generator_provider(
        ModelConfig(
            provider="openrouter",
            model_name="openrouter/scenario-generator",
            api_base="https://openrouter.ai/api/v1",
            api_key="sk-scenario",
        ),
        model_provider=model_provider,
    )
    task_spec = parse_instruction(
        "# Role\n你是美团外卖骑手的站长。\n# Task\n通知骑手飞毛腿合同生效。",
        task_id="task_001",
    )
    rubric = build_rubric(task_spec)

    scenario_set = scenario_provider.generate(task_spec, rubric, "", minimum=1)
    scenario = scenario_set.scenarios[0]

    assert scenario.initial_user_intent != "请问你现在方便说几句吗？只需要确认一下合同信息，很快的。"
    assert "合同信息" not in scenario.initial_user_intent
    assert scenario.initial_user_intent in {
        "我今天身体有点累，不太想跑。",
        "那我今天还能退出飞毛腿吗？",
    }
    assert "initial_user_intent_sanitized" in scenario.risk_tags
    assert scenario.user_profile["raw_initial_user_intent"] == "请问你现在方便说几句吗？只需要确认一下合同信息，很快的。"


def test_scenario_generator_keeps_valid_initial_user_intent():
    from backend.eval_agent.api.routes.runs import ModelConfig
    from backend.eval_agent.services.run_service import build_scenario_generator_provider
    from backend.evaluation_engine.instruction_parser import parse_instruction
    from backend.evaluation_engine.rubric_builder import build_rubric

    model_provider = RecordingModelProvider(
        content=json.dumps(
            {
                "scenarios": [
                    {
                        "scenario_id": "valid_rider_refusal",
                        "user_profile": {"role": "骑手", "attitude": "疲惫"},
                        "coverage_targets": ["refusal_to_deliver"],
                        "initial_user_intent": "我今天身体有点累，不太想跑。",
                        "expected_test_focus": "处理骑手拒配",
                        "difficulty": "L3",
                        "scenario_type": "model_generated",
                        "risk_tags": ["capacity_pressure"],
                    }
                ]
            },
            ensure_ascii=False,
        )
    )
    scenario_provider = build_scenario_generator_provider(
        ModelConfig(
            provider="openrouter",
            model_name="openrouter/scenario-generator",
            api_base="https://openrouter.ai/api/v1",
            api_key="sk-scenario",
        ),
        model_provider=model_provider,
    )
    task_spec = parse_instruction(
        "# Role\n你是美团外卖骑手的站长。\n# Task\n通知骑手飞毛腿合同生效。",
        task_id="task_001",
    )
    rubric = build_rubric(task_spec)

    scenario = scenario_provider.generate(task_spec, rubric, "", minimum=1).scenarios[0]

    assert scenario.initial_user_intent == "我今天身体有点累，不太想跑。"
    assert "initial_user_intent_sanitized" not in scenario.risk_tags
    assert "raw_initial_user_intent" not in scenario.user_profile


def test_create_run_payload_passes_scenario_generator_provider(tmp_path, monkeypatch):
    from backend.eval_agent.api.routes.runs import ModelConfig, RunRequest
    from backend.eval_agent.services import run_service

    captured = {}

    class CapturedScenarioProvider:
        pass

    def fake_run_full_evaluation(**kwargs):
        captured["scenario_provider"] = kwargs.get("scenario_provider")
        return run_service.engine_app.run_full_evaluation(
            raw_instruction=kwargs["raw_instruction"],
            run_root=kwargs["run_root"],
            assistant_provider=kwargs["assistant_provider"],
            user_provider=kwargs["user_provider"],
            minimum_scenarios=1,
            input_data=kwargs["input_data"],
            selected_scenario_ids=kwargs["selected_scenario_ids"],
            model_config_summary=kwargs["model_config_summary"],
            stage_model_config_summary=kwargs["stage_model_config_summary"],
            run_context=kwargs["run_context"],
            judge_provider=None,
            scenario_provider=None,
        )

    monkeypatch.setattr(run_service, "RUN_ROOT", tmp_path)
    monkeypatch.setattr(run_service, "run_full_evaluation", fake_run_full_evaluation)
    monkeypatch.setattr(
        run_service,
        "build_scenario_generator_provider",
        lambda model_config: CapturedScenarioProvider(),
    )
    monkeypatch.setenv("EVAL_CHAIN_PROVIDER", "openrouter")
    monkeypatch.setenv("EVAL_CHAIN_API_BASE", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("EVAL_CHAIN_API_KEY", "sk-chain-secret")

    run_service.create_run_payload(
        RunRequest(
            instruction="# Role\n你是站长\n# Task\n通知骑手合同生效",
            minimum_scenarios=1,
            model_config=ModelConfig(provider="mock"),
        )
    )

    assert isinstance(captured["scenario_provider"], CapturedScenarioProvider)


def test_run_detail_returns_backend_stage_model_config_summary(tmp_path, monkeypatch):
    from backend.eval_agent.api.routes.runs import ModelConfig, RunRequest
    from backend.eval_agent.services import run_service

    monkeypatch.setattr(run_service, "RUN_ROOT", tmp_path)
    monkeypatch.setenv("EVAL_CHAIN_PROVIDER", "openrouter")
    monkeypatch.setenv("EVAL_CHAIN_API_BASE", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("EVAL_CHAIN_API_KEY", "sk-chain-secret")
    monkeypatch.setenv("EVAL_REPORT_GENERATOR_MODEL", "openai/gpt-4.1-mini")
    created = run_service.create_run_payload(
        RunRequest(
            instruction="# Role\n你是站长\n# Task\n通知骑手合同生效",
            minimum_scenarios=1,
            model_config=ModelConfig(provider="mock", model_name="target-demo"),
        )
    )

    detail = run_service.run_detail_payload(created["run_id"])

    assert detail["stage_model_config_summary"]["target_model"]["model_name"] == "target-demo"
    assert detail["stage_model_config_summary"]["report_generator"]["model_name"] == "openai/gpt-4.1-mini"
