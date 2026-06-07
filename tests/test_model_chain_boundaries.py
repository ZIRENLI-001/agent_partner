import json

from backend.eval_agent.providers.base import ModelResponse


class RecordingModelProvider:
    def __init__(self, content: str = "模型输出<DONE>"):
        self.content = content
        self.calls = []

    def generate(self, messages, config):
        self.calls.append({"messages": messages, "config": config})
        return ModelResponse(content=self.content, raw={"ok": True})


def test_stage_model_summary_declares_which_roles_really_call_models(monkeypatch):
    from backend.eval_agent.services import run_service

    monkeypatch.setenv("EVAL_CHAIN_PROVIDER", "openrouter")
    monkeypatch.setenv("EVAL_CHAIN_API_BASE", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("EVAL_CHAIN_API_KEY", "sk-chain-secret")

    summary = run_service.stage_model_config_summary(
        run_service.backend_stage_model_config()
    )

    assert summary["target_model"]["execution_mode"] == "target_dialogue_model"
    assert summary["user_simulator"]["execution_mode"] == "model_call"
    assert summary["semantic_judge"]["execution_mode"] == "model_call_with_rule_fallback"
    assert summary["scenario_generator"]["execution_mode"] == "model_call_with_rule_fallback"
    assert summary["instruction_parser"]["execution_mode"] == "model_call_with_rule_fallback"
    assert summary["rubric_generator"]["execution_mode"] == "model_call_with_rule_fallback"
    assert summary["report_generator"]["execution_mode"] == "model_call_with_template_fallback"
    assert "sk-chain-secret" not in json.dumps(summary, ensure_ascii=False)


def test_end_to_end_run_routes_model_backed_roles_to_engine(tmp_path, monkeypatch):
    from backend.eval_agent.api.routes.runs import ModelConfig, RunRequest
    from backend.eval_agent.services import run_service
    from backend.evaluation_engine.engine import FullRunResult
    from backend.evaluation_engine.domain import (
        DialogueTrace,
        EvaluationResult,
        Report,
        RubricItem,
        RubricSpec,
        Scenario,
        ScenarioSet,
        TaskSpec,
    )

    captured = {}

    class RoleProvider:
        def __init__(self, role: str):
            self.role = role

    def fake_run_full_evaluation(**kwargs):
        captured.update(kwargs)
        task = TaskSpec(
            task_id="task_001",
            task_name="合同生效通知",
            role="站长",
            target_user="骑手",
            task_goal="通知合同生效",
            opening_line="你好",
        )
        rubric = RubricSpec(
            rubric_id="rubric_001",
            task_id=task.task_id,
            items=[
                RubricItem(
                    item_id="step_01",
                    dimension="task_completion",
                    criterion="通知合同生效",
                    source="Call Flow",
                    check_type="semantic",
                    weight=10,
                )
            ],
        )
        scenarios = ScenarioSet(
            suite_id="suite_task_001_v1",
            task_id=task.task_id,
            scenarios=[
                Scenario(
                    scenario_id="scenario_001",
                    task_id=task.task_id,
                    user_profile={"role": "骑手"},
                    coverage_targets=["normal_confirmation"],
                    initial_user_intent="我可以配送",
                    expected_test_focus="正常确认",
                )
            ],
        )
        trace = DialogueTrace(
            trace_id="trace_001",
            run_id="run_001",
            task_id=task.task_id,
            scenario_id="scenario_001",
            turns=[],
            termination_reason="task_completed",
        )
        result = EvaluationResult(
            trace_id=trace.trace_id,
            scenario_id=trace.scenario_id,
            total_score=0,
            dimension_scores={},
            evidence=[],
        )
        return FullRunResult(
            run_id="run_001",
            task_spec=task,
            rubric_spec=rubric,
            scenario_set=scenarios,
            input_data_summary={"format": "empty"},
            stage_model_config_summary=kwargs["stage_model_config_summary"],
            traces=[trace],
            results=[result],
            report=Report(run_id="run_001", task_id=task.task_id, markdown="# 报告"),
        )

    monkeypatch.setattr(run_service, "RUN_ROOT", tmp_path)
    monkeypatch.setattr(run_service, "run_full_evaluation", fake_run_full_evaluation)
    monkeypatch.setattr(
        run_service,
        "build_assistant_provider",
        lambda config: RoleProvider("target:%s" % config.model_name),
    )
    monkeypatch.setattr(
        run_service,
        "build_user_provider",
        lambda config: RoleProvider("user:%s" % config.model_name),
    )
    monkeypatch.setattr(
        run_service,
        "build_semantic_judge_provider",
        lambda config: RoleProvider("judge:%s" % config.model_name),
    )
    monkeypatch.setattr(
        run_service,
        "build_scenario_generator_provider",
        lambda config: RoleProvider("scenario:%s" % config.model_name),
    )
    monkeypatch.setattr(
        run_service,
        "build_instruction_parser_provider",
        lambda config: RoleProvider("parser:%s" % config.model_name),
    )
    monkeypatch.setattr(
        run_service,
        "build_rubric_generator_provider",
        lambda config: RoleProvider("rubric:%s" % config.model_name),
    )
    monkeypatch.setattr(
        run_service,
        "build_report_generator_provider",
        lambda config: RoleProvider("report:%s" % config.model_name),
    )
    monkeypatch.setenv("EVAL_CHAIN_PROVIDER", "openrouter")
    monkeypatch.setenv("EVAL_CHAIN_API_BASE", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("EVAL_CHAIN_API_KEY", "sk-chain-secret")
    monkeypatch.setenv("EVAL_USER_SIMULATOR_MODEL", "openai/gpt-4.1-mini")
    monkeypatch.setenv("EVAL_SEMANTIC_JUDGE_MODEL", "anthropic/claude-sonnet-4.6")
    monkeypatch.setenv("EVAL_SCENARIO_GENERATOR_MODEL", "google/gemini-2.5-flash")
    monkeypatch.setenv("EVAL_INSTRUCTION_PARSER_MODEL", "anthropic/claude-sonnet-4.6")
    monkeypatch.setenv("EVAL_RUBRIC_GENERATOR_MODEL", "anthropic/claude-sonnet-4.6")
    monkeypatch.setenv("EVAL_REPORT_GENERATOR_MODEL", "openai/gpt-4.1-mini")

    response = run_service.create_run_payload(
        RunRequest(
            instruction="# Role\n你是站长\n# Task\n通知骑手合同生效",
            minimum_scenarios=1,
            model_config=ModelConfig(
                provider="openrouter",
                model_name="deepseek/deepseek-chat",
                api_base="https://openrouter.ai/api/v1",
                api_key="",
            ),
        )
    )

    assert captured["assistant_provider"].role == "target:deepseek/deepseek-chat"
    assert captured["user_provider"].role == "user:openai/gpt-4.1-mini"
    assert captured["judge_provider"].role == "judge:anthropic/claude-sonnet-4.6"
    assert captured["scenario_provider"].role == "scenario:google/gemini-2.5-flash"
    assert captured["parser_provider"].role == "parser:anthropic/claude-sonnet-4.6"
    assert captured["rubric_provider"].role == "rubric:anthropic/claude-sonnet-4.6"
    assert captured["report_provider"].role == "report:openai/gpt-4.1-mini"
    assert response["stage_model_config_summary"]["target_model"]["api_key_configured"] is True
    assert "sk-chain-secret" not in json.dumps(response, ensure_ascii=False)


def test_parser_rubric_and_report_model_adapters_return_valid_domain_objects():
    from backend.eval_agent.api.routes.runs import ModelConfig
    from backend.eval_agent.services.run_service import (
        build_instruction_parser_provider,
        build_report_generator_provider,
        build_rubric_generator_provider,
    )
    from backend.evaluation_engine.domain import EvaluationResult, Scenario, ScenarioSet

    parser_model = RecordingModelProvider(
        content=json.dumps(
            {
                "task_id": "task_001",
                "version": "v1",
                "task_name": "飞毛腿通知",
                "role": "美团外卖骑手站长",
                "target_user": "骑手",
                "task_goal": "通知合同生效并提醒配送任务",
                "opening_line": "你好，请问是王师傅吗？",
                "required_steps": ["通知合同生效", "确认是否开始配送"],
                "constraints": ["每次回复约30字以内"],
                "faq": [],
                "edge_cases": [],
                "forbidden_actions": ["承诺额外奖励"],
            },
            ensure_ascii=False,
        )
    )
    parser = build_instruction_parser_provider(
        ModelConfig(
            provider="openrouter",
            model_name="parser-model",
            api_base="https://openrouter.ai/api/v1",
            api_key="sk-parser",
        ),
        model_provider=parser_model,
    )

    task = parser.parse("# Role\n你是站长", task_id="task_001")

    rubric_model = RecordingModelProvider(
        content=json.dumps(
            {
                "rubric_id": "task_001_rubric",
                "task_id": "task_001",
                "version": "v1",
                "items": [
                    {
                        "item_id": "step_01",
                        "dimension": "task_completion",
                        "criterion": "通知合同生效",
                        "source": "Call Flow 第1步",
                        "check_type": "semantic",
                        "weight": 10,
                        "critical": False,
                    }
                ],
            },
            ensure_ascii=False,
        )
    )
    rubric_provider = build_rubric_generator_provider(
        ModelConfig(
            provider="openrouter",
            model_name="rubric-model",
            api_base="https://openrouter.ai/api/v1",
            api_key="sk-rubric",
        ),
        model_provider=rubric_model,
    )
    rubric = rubric_provider.build(task, "# raw instruction")

    report_model = RecordingModelProvider(content="# 模型报告\n\n## 解释\n证据链清晰。")
    report_provider = build_report_generator_provider(
        ModelConfig(
            provider="openrouter",
            model_name="report-model",
            api_base="https://openrouter.ai/api/v1",
            api_key="sk-report",
        ),
        model_provider=report_model,
    )
    report = report_provider.write(
        "run_001",
        task,
        ScenarioSet(
            suite_id="suite_task_001_v1",
            task_id="task_001",
            scenarios=[
                Scenario(
                    scenario_id="scenario_001",
                    task_id="task_001",
                    user_profile={"role": "骑手"},
                    coverage_targets=["normal_completion"],
                    initial_user_intent="可以配送",
                    expected_test_focus="正常完成",
                )
            ],
        ),
        [EvaluationResult(trace_id="trace_001", scenario_id="scenario_001", total_score=10, dimension_scores={}, evidence=[])],
        input_data_summary={"format": "json"},
    )

    assert task.task_name == "飞毛腿通知"
    assert rubric.items[0].criterion == "通知合同生效"
    assert report.markdown.startswith("# 模型报告")
    assert parser_model.calls[0]["config"].model_name == "parser-model"
    assert rubric_model.calls[0]["config"].model_name == "rubric-model"
    assert report_model.calls[0]["config"].model_name == "report-model"
    assert parser.model_call_diagnostic()["prompt_ids"] == {
        "instruction_parser_v1": 1
    }
    assert rubric_provider.model_call_diagnostic()["prompt_ids"] == {
        "rubric_generator_v1": 1
    }
    assert report_provider.model_call_diagnostic()["prompt_ids"] == {
        "report_generator_v1": 1
    }
    serialized_diagnostics = json.dumps(
        {
            "parser": parser.model_call_diagnostic(),
            "rubric": rubric_provider.model_call_diagnostic(),
            "report": report_provider.model_call_diagnostic(),
        },
        ensure_ascii=False,
    )
    assert "sk-parser" not in serialized_diagnostics
    assert "sk-rubric" not in serialized_diagnostics
    assert "sk-report" not in serialized_diagnostics


def test_scenario_adapter_retries_malformed_json_with_same_model():
    from backend.eval_agent.api.routes.runs import ModelConfig
    from backend.eval_agent.services.run_service import build_scenario_generator_provider
    from backend.evaluation_engine.instruction_parser import parse_instruction
    from backend.evaluation_engine.rubric_builder import build_rubric

    class SequentialModelProvider:
        def __init__(self):
            self.responses = [
                '{"scenarios":[{"scenario_id":"truncated"',
                json.dumps(
                    {
                        "scenarios": [
                            {
                                "scenario_id": "model_repaired",
                                "user_profile": {
                                    "role": "用户",
                                    "attitude": "谨慎",
                                },
                                "coverage_targets": ["normal_completion"],
                                "initial_user_intent": "请说明合同状态。",
                                "expected_test_focus": "确认合同生效",
                                "difficulty": "L2",
                                "scenario_type": "model_generated",
                                "expected_behavior": "准确说明合同已生效",
                                "risk_tags": ["model_generated"],
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
            ]
            self.calls = []

        def generate(self, messages, config):
            self.calls.append({"messages": messages, "config": config})
            return ModelResponse(content=self.responses.pop(0), raw={"ok": True})

    model = SequentialModelProvider()
    adapter = build_scenario_generator_provider(
        ModelConfig(
            provider="openrouter",
            model_name="google/gemini-3.1-pro-preview",
            api_base="https://openrouter.ai/api/v1",
            api_key="sk-scenario",
        ),
        model_provider=model,
    )
    task = parse_instruction(
        "# Role\n你是合同通知专员。\n# Task\n告知用户合同已生效。",
        task_id="task_001",
    )
    scenarios = adapter.generate(
        task,
        build_rubric(task),
        '{"contract_status":"active"}',
        minimum=1,
    )

    assert len(model.calls) == 2
    assert scenarios.scenarios[0].scenario_id == "model_repaired"
    assert model.calls[1]["config"].model_name == "google/gemini-3.1-pro-preview"
    assert model.calls[1]["config"].temperature == 0
    assert model.calls[1]["config"].max_tokens >= 6000
    assert model.calls[1]["config"].cache_enabled is False
    assert model.calls[1]["messages"][-2]["role"] == "assistant"
    assert "truncated" in model.calls[1]["messages"][-2]["content"]
    diagnostic = adapter.model_call_diagnostic()
    assert diagnostic["prompt_ids"] == {
        "scenario_generator_v1": 1,
        "scenario_generator_json_repair_v1": 1,
    }
    assert diagnostic["retry_count"] == 1


def test_report_prompt_requires_quality_gate_headings():
    from backend.eval_agent.services.run_service import (
        _report_generator_system_message,
        _report_generator_user_message,
    )
    from backend.evaluation_engine.domain import (
        EvaluationResult,
        Scenario,
        ScenarioSet,
        TaskSpec,
    )

    task = TaskSpec(
        task_id="task_001",
        task_name="合同通知",
        role="合同通知专员",
        target_user="用户",
        task_goal="告知合同已生效",
        opening_line="您好",
    )
    scenarios = ScenarioSet(
        suite_id="suite_001",
        task_id=task.task_id,
        scenarios=[
            Scenario(
                scenario_id="scenario_001",
                task_id=task.task_id,
                user_profile={"role": "用户"},
                coverage_targets=["normal_completion"],
                initial_user_intent="请说明合同状态。",
                expected_test_focus="确认合同生效",
            )
        ],
    )
    results = [
        EvaluationResult(
            trace_id="trace_001",
            scenario_id="scenario_001",
            total_score=0,
            dimension_scores={},
            evidence=[],
        )
    ]

    prompt = "\n".join(
        [
            _report_generator_system_message()["content"],
            _report_generator_user_message(
                "run_001",
                task,
                scenarios,
                results,
                {"format": "json"},
            ),
        ]
    )

    assert "## 量化结果" in prompt
    assert "## 证据链" in prompt


def test_visualized_scenario_stage_falls_back_when_model_output_is_invalid():
    from backend.eval_agent.services.stage_service import scenarios_stage_payload

    class BadScenarioProvider:
        def generate(self, task_spec, rubric, input_data, minimum):
            raise RuntimeError("scenario model returned invalid JSON")

    payload = scenarios_stage_payload(
        "# Role\n你是美团站长\n# Task\n通知骑手合同生效",
        minimum_scenarios=3,
        input_data='{"rider_name":"王师傅"}',
        scenario_provider=BadScenarioProvider(),
    )

    scenarios = payload["scenario_set"]["scenarios"]
    assert len(scenarios) >= 3
    assert all("scenario_id" in item for item in scenarios)
    assert not all("model_generated" in item.get("risk_tags", []) for item in scenarios)


def test_visualized_parse_and_rubric_stages_can_use_model_providers():
    from backend.eval_agent.services.stage_service import (
        parse_stage_payload,
        rubric_stage_payload,
    )
    from backend.evaluation_engine.domain import RubricItem, RubricSpec, TaskSpec

    class StaticParserProvider:
        def parse(self, raw_instruction, task_id):
            return TaskSpec(
                task_id=task_id,
                task_name="模型解析任务",
                role="模型解析站长",
                target_user="骑手",
                task_goal="模型解析目标",
                opening_line="你好",
                required_steps=["模型解析步骤"],
            )

    class StaticRubricProvider:
        def build(self, task_spec, raw_instruction):
            return RubricSpec(
                rubric_id="%s_model_rubric" % task_spec.task_id,
                task_id=task_spec.task_id,
                items=[
                        RubricItem(
                            item_id="model_step_01",
                            dimension="task_completion",
                            criterion="完成任务步骤：模型解析步骤",
                            source="required_steps",
                            check_type="semantic",
                            weight=10,
                        )
                ],
            )

    parse_payload = parse_stage_payload(
        "# Role\n你是站长",
        input_data="",
        parser_provider=StaticParserProvider(),
    )
    rubric_payload = rubric_stage_payload(
        "# Role\n你是站长",
        parser_provider=StaticParserProvider(),
        rubric_provider=StaticRubricProvider(),
    )

    assert parse_payload["task_spec"]["task_name"] == "模型解析任务"
    assert rubric_payload["rubric_spec"]["items"][0]["item_id"] == "model_step_01"


def test_end_to_end_run_falls_back_when_parser_rubric_or_report_model_fails(tmp_path):
    from backend.evaluation_engine.engine import run_full_evaluation
    from backend.evaluation_engine.providers import FakeAssistantProvider, FakeUserProvider

    class FailingParserProvider:
        def parse(self, raw_instruction, task_id):
            raise RuntimeError("parser timeout")

    class FailingRubricProvider:
        def build(self, task_spec, raw_instruction):
            raise RuntimeError("rubric invalid JSON")

    class FailingReportProvider:
        def write(self, run_id, task_spec, scenario_set, results, input_data_summary):
            raise RuntimeError("report model unavailable")

    result = run_full_evaluation(
        raw_instruction=(
            "# Role\n你是美团外卖骑手的站长。\n"
            "# Task\n通知骑手飞毛腿合同生效。\n"
            "# Call Flow\n1. 告知合同生效。"
        ),
        run_root=tmp_path,
        assistant_provider=FakeAssistantProvider(),
        user_provider=FakeUserProvider(),
        minimum_scenarios=1,
        parser_provider=FailingParserProvider(),
        rubric_provider=FailingRubricProvider(),
        report_provider=FailingReportProvider(),
    )

    assert result.task_spec.task_name == "飞毛腿通知"
    assert result.rubric_spec.items
    assert result.report.markdown.startswith("# 评测报告")
    assert result.stage_diagnostics["instruction_parsing"]["fallback_used"] is True
    assert result.stage_diagnostics["rubric_generation"]["fallback_used"] is True
    assert result.stage_diagnostics["report_generation"]["fallback_used"] is True
    assert (
        result.stage_diagnostics["rubric_generation"]["output_source"]
        == "local_rubric_builder"
    )


def test_report_generator_prompt_compacts_large_evidence_payload(monkeypatch):
    from backend.eval_agent.api.routes.runs import ModelConfig
    from backend.eval_agent.services.run_service import build_report_generator_provider
    from backend.evaluation_engine.domain import (
        EvaluationResult,
        EvidenceItem,
        RubricItem,
        Scenario,
        ScenarioSet,
        TaskSpec,
    )

    monkeypatch.setenv("EVAL_REPORT_MAX_EVIDENCE_ITEMS", "2")
    model_provider = RecordingModelProvider(content="# 压缩报告")
    report_provider = build_report_generator_provider(
        ModelConfig(
            provider="openrouter",
            model_name="report-model",
            api_base="https://openrouter.ai/api/v1",
            api_key="sk-report",
        ),
        model_provider=model_provider,
    )
    task = TaskSpec(
        task_id="task_001",
        task_name="飞毛腿通知",
        role="站长",
        target_user="骑手",
        task_goal="通知合同生效",
        opening_line="你好",
    )
    scenarios = ScenarioSet(
        suite_id="suite_001",
        task_id=task.task_id,
        scenarios=[
            Scenario(
                scenario_id="scenario_001",
                task_id=task.task_id,
                user_profile={"role": "骑手"},
                coverage_targets=["normal"],
                initial_user_intent="正常接听",
                expected_test_focus="通知合同",
            )
        ],
    )
    evidence = [
        EvidenceItem(
            rubric_item_id="item_%d" % index,
            verdict="fail" if index == 3 else "pass",
            source="Call Flow",
            turn_ids=[1],
            reason="原因_%d" % index,
            score=0 if index == 3 else 1,
            max_score=1,
            instruction_quote="标准_%d" % index,
            expected_behavior="期望_%d" % index,
            actual_behavior="实际_%d" % index,
            explanation="解释_%d" % index,
        )
        for index in range(1, 5)
    ]
    results = [
        EvaluationResult(
            trace_id="trace_001",
            scenario_id="scenario_001",
            total_score=3,
            dimension_scores={"task_completion": 3},
            evidence=evidence,
        )
    ]

    report_provider.write("run_001", task, scenarios, results, {})

    prompt_payload = json.loads(model_provider.calls[0]["messages"][1]["content"])
    compacted = prompt_payload["EvaluationResults"][0]["evidence"]
    assert len(compacted) == 2
    assert compacted[0]["rubric_item_id"] == "item_3"
    assert prompt_payload["evidence_compaction"]["omitted_evidence_items"] == 2
