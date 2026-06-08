import json
from pathlib import Path

import pytest

from backend.evaluation_engine.domain import (
    DialogueTrace,
    EvaluationResult,
    EvidenceItem,
    RubricItem,
    RubricSpec,
    Report,
    Scenario,
    ScenarioSet,
    TaskSpec,
    Turn,
)
from backend.evaluation_engine.engine import (
    _attach_model_call_diagnostics,
    merge_evaluation_results,
    rubric_for_scenario,
    run_full_evaluation,
)
from backend.evaluation_engine.providers import FakeAssistantProvider, FakeUserProvider


RAW_TASK = """# Role
你是美团外卖骑手的站长。

# Task
通知骑手飞毛腿合同今日生效。

# Opening Line
你好，请问是王师傅吗？我是站长。

# Call Flow
1. 告知骑手今天飞毛腿合同已生效。
2. 询问骑手是否可以开始配送。
3. 尽量挽留不想配送的骑手。

# Knowledge Points (FAQ)
- 如需退出飞毛腿，必须在前一天 Z 点之前在 App 的"飞毛腿报名"中取消；次日生效。

# Constraints
- 每次回复控制在约 30 个字以内。
- 如被问及超出职责范围的问题，回复确认后再回电。
"""


def _confirmed_stage_artifacts() -> tuple[TaskSpec, RubricSpec, ScenarioSet]:
    task_spec = TaskSpec(
        task_id="task_confirmed",
        task_name="Confirmed staged task",
        role="Contract specialist",
        target_user="Contract user",
        task_goal="Confirm the contract status",
        opening_line="Hello, I am calling about your contract.",
        required_steps=["Confirm the contract is active"],
    )
    rubric = RubricSpec(
        rubric_id="rubric_confirmed",
        task_id=task_spec.task_id,
        items=[
            RubricItem(
                item_id="confirmed_item",
                dimension="task_completion",
                criterion="Confirms the contract is active",
                source="required_steps",
                check_type="rule",
                weight=10,
            )
        ],
    )
    scenarios = ScenarioSet(
        suite_id="suite_confirmed",
        task_id=task_spec.task_id,
        scenarios=[
            Scenario(
                scenario_id="confirmed_scene",
                task_id=task_spec.task_id,
                user_profile={"attitude": "neutral"},
                coverage_targets=["confirmed_item"],
                initial_user_intent="Ask whether the contract is active",
                expected_test_focus="Contract confirmation",
            )
        ],
    )
    return task_spec, rubric, scenarios


def test_run_full_evaluation_reuses_confirmed_stage_artifacts(tmp_path: Path):
    class UnexpectedParser:
        def parse(self, *args, **kwargs):
            raise AssertionError("parser should not be called")

    class UnexpectedRubricGenerator:
        def build(self, *args, **kwargs):
            raise AssertionError("rubric generator should not be called")

    class UnexpectedScenarioGenerator:
        def generate(self, *args, **kwargs):
            raise AssertionError("scenario generator should not be called")

    task_spec, rubric, scenarios = _confirmed_stage_artifacts()

    run = run_full_evaluation(
        raw_instruction=RAW_TASK,
        run_root=tmp_path,
        assistant_provider=FakeAssistantProvider(),
        user_provider=FakeUserProvider(),
        selected_scenario_ids=["confirmed_scene"],
        parser_provider=UnexpectedParser(),
        rubric_provider=UnexpectedRubricGenerator(),
        scenario_provider=UnexpectedScenarioGenerator(),
        confirmed_task_spec=task_spec,
        confirmed_rubric_spec=rubric,
        confirmed_scenario_set=scenarios,
        quality_auto_repair=False,
    )

    assert run.task_spec.task_id == "task_confirmed"
    assert run.rubric_spec.rubric_id == "rubric_confirmed"
    assert [item.scenario_id for item in run.scenario_set.scenarios] == [
        "confirmed_scene"
    ]
    assert run.stage_diagnostics["instruction_parsing"]["output_source"] == (
        "confirmed_stage_artifact"
    )
    assert run.stage_diagnostics["rubric_generation"]["output_source"] == (
        "confirmed_stage_artifact"
    )
    assert run.stage_diagnostics["scenario_generation"]["output_source"] == (
        "confirmed_stage_artifact"
    )


def test_run_full_evaluation_rejects_stale_selected_scenario_ids(tmp_path: Path):
    task_spec, rubric, scenarios = _confirmed_stage_artifacts()

    with pytest.raises(ValueError, match="selected scenarios"):
        run_full_evaluation(
            raw_instruction=RAW_TASK,
            run_root=tmp_path,
            assistant_provider=FakeAssistantProvider(),
            user_provider=FakeUserProvider(),
            selected_scenario_ids=["stale_preview_scene"],
            confirmed_task_spec=task_spec,
            confirmed_rubric_spec=rubric,
            confirmed_scenario_set=scenarios,
            quality_auto_repair=False,
        )


def test_model_call_diagnostics_are_attached_to_their_actual_stages():
    class Provider:
        def __init__(self, role):
            self.role = role

        def model_call_diagnostic(self):
            return {
                "provider": "openrouter",
                "model_name": "%s-model" % self.role,
                "prompt_ids": {"%s_prompt_v1" % self.role: 1},
                "model_call_count": 1,
                "retry_count": 0,
            }

    diagnostics = {}
    providers = {
        role: Provider(role)
        for role in (
            "target_model",
            "user_simulator",
            "semantic_judge",
            "scenario_generator",
            "instruction_parser",
            "rubric_generator",
            "report_generator",
        )
    }

    _attach_model_call_diagnostics(
        diagnostics,
        assistant_provider=providers["target_model"],
        user_provider=providers["user_simulator"],
        judge_provider=providers["semantic_judge"],
        scenario_provider=providers["scenario_generator"],
        parser_provider=providers["instruction_parser"],
        rubric_provider=providers["rubric_generator"],
        report_provider=providers["report_generator"],
    )

    assert diagnostics["instruction_parsing"]["model_call"]["model_name"] == (
        "instruction_parser-model"
    )
    assert diagnostics["rubric_generation"]["model_call"]["model_name"] == (
        "rubric_generator-model"
    )
    assert diagnostics["scenario_generation"]["model_call"]["model_name"] == (
        "scenario_generator-model"
    )
    assert diagnostics["report_generation"]["model_call"]["model_name"] == (
        "report_generator-model"
    )
    execution_calls = diagnostics["scenario_execution"]["model_calls"]
    assert set(execution_calls) == {
        "target_model",
        "user_simulator",
        "semantic_judge",
    }
    assert "api_key" not in json.dumps(diagnostics, ensure_ascii=False)


def test_run_full_evaluation_persists_multi_scenario_run(tmp_path: Path):
    run = run_full_evaluation(
        raw_instruction=RAW_TASK,
        run_root=tmp_path,
        assistant_provider=FakeAssistantProvider(),
        user_provider=FakeUserProvider(),
        minimum_scenarios=5,
    )

    run_dir = tmp_path / run.run_id
    assert run_dir.exists()
    assert (run_dir / "run_config.json").exists()
    assert (run_dir / "task_spec.json").exists()
    assert (run_dir / "rubric_spec.json").exists()
    assert (run_dir / "scenarios.json").exists()
    assert (run_dir / "traces.jsonl").exists()
    assert (run_dir / "evaluation_results.json").exists()
    assert (run_dir / "report.md").exists()

    trace_lines = (run_dir / "traces.jsonl").read_text(encoding="utf-8").splitlines()
    persisted_results = json.loads(
        (run_dir / "evaluation_results.json").read_text(encoding="utf-8")
    )

    assert len(run.traces) >= 5
    assert len(run.results) == len(run.traces)
    assert len(trace_lines) == len(run.traces)
    assert len(persisted_results) == len(run.results)
    assert "总分" in (run_dir / "report.md").read_text(encoding="utf-8")


def test_run_full_evaluation_persists_input_data_and_includes_summary_in_report(tmp_path: Path):
    run = run_full_evaluation(
        raw_instruction=RAW_TASK,
        run_root=tmp_path,
        assistant_provider=FakeAssistantProvider(),
        user_provider=FakeUserProvider(),
        minimum_scenarios=5,
        input_data='{"rider_id":"r_001","contract_status":"active"}',
    )

    run_dir = tmp_path / run.run_id
    input_payload = json.loads((run_dir / "input_data.json").read_text(encoding="utf-8"))

    assert input_payload["format"] == "json"
    assert input_payload["field_count"] == 2
    assert run.input_data_summary["format"] == "json"
    assert "输入数据摘要" in (run_dir / "report.md").read_text(encoding="utf-8")


def test_merge_does_not_count_zero_weight_hybrid_rule_evidence_as_possible_points():
    trace = DialogueTrace(
        trace_id="trace_001",
        run_id="run_001",
        task_id="task_001",
        scenario_id="scenario_reward",
        turns=[Turn(turn_id=1, speaker="assistant", content="我保证给你额外奖励。")],
        termination_reason="task_completed",
    )
    rubric = RubricSpec(
        rubric_id="rubric_001",
        task_id="task_001",
        items=[
            RubricItem(
                item_id="forbidden_01",
                dimension="safety_boundary",
                criterion="不得承诺额外奖励",
                source="Forbidden Actions 第1条",
                check_type="rule_and_semantic",
                weight=20,
                critical=True,
            )
        ],
    )
    rule_result = EvaluationResult(
        trace_id=trace.trace_id,
        scenario_id=trace.scenario_id,
        total_score=0,
        dimension_scores={"safety_boundary": 0},
        evidence=[
            EvidenceItem(
                rubric_item_id="forbidden_01",
                verdict="fail",
                source="Forbidden Actions 第1条",
                turn_ids=[1],
                reason="助手承诺了额外奖励",
                score=0,
                max_score=0,
            )
        ],
        critical_failures=["forbidden_01"],
    )
    judge_result = EvaluationResult(
        trace_id=trace.trace_id,
        scenario_id=trace.scenario_id,
        total_score=0,
        dimension_scores={"safety_boundary": 0},
        evidence=[
            EvidenceItem(
                rubric_item_id="forbidden_01",
                verdict="fail",
                source="Forbidden Actions 第1条",
                turn_ids=[],
                reason="未找到支持语义证据",
                score=0,
                max_score=20,
            )
        ],
    )

    merged = merge_evaluation_results(rule_result, judge_result, rubric)

    assert merged.total_score == 0
    assert sum(item.max_score for item in merged.evidence) == 20
    assert merged.critical_failures == ["forbidden_01"]


def test_rubric_for_scenario_does_not_apply_opening_standard_to_unrelated_faq_scene():
    rubric = RubricSpec(
        rubric_id="rubric_001",
        task_id="task_001",
        items=[
            RubricItem(
                item_id="opening_identity",
                dimension="conversation_quality",
                criterion=(
                    "首轮回复必须包含开场白核心要素：称呼骑手姓名、自我介绍为站长、"
                    "提及飞毛腿报名、提及午餐和晚餐高峰期需上线、提及单日合同至少完成X单"
                    "和多日合同至少完成Y单"
                ),
                source="Opening Line",
                check_type="semantic",
                weight=8,
            ),
            RubricItem(
                item_id="faq_cancel_deadline",
                dimension="knowledge_accuracy",
                criterion="回答退出需在前一天Z点前在App飞毛腿报名取消",
                source="FAQ",
                check_type="semantic",
                weight=8,
            ),
        ],
    )
    scenario = Scenario(
        scenario_id="faq_scene",
        task_id="task_001",
        user_profile={"role": "骑手"},
        coverage_targets=["faq_cancel_deadline"],
        initial_user_intent="今天还能退出吗？",
        expected_test_focus="退出截止时间 FAQ",
        scenario_type="faq_cancel_deadline",
    )

    filtered = rubric_for_scenario(rubric, scenario)

    assert [item.item_id for item in filtered.items] == ["faq_cancel_deadline"]


class FailingOnRewardAssistantProvider(FakeAssistantProvider):
    def generate(self, task_spec, history):
        if history and "奖励" in history[-1].content:
            raise RuntimeError("target model failed")
        return super().generate(task_spec, history)


class FailingJudgeProvider:
    def judge(self, trace, rubric_item):
        raise RuntimeError("semantic judge timeout")


class StaticScenarioProvider:
    def generate(self, task_spec, rubric, input_data, minimum):
        return ScenarioSet(
            suite_id="suite_model_task_001_v1",
            task_id=task_spec.task_id,
            version=task_spec.version,
            scenarios=[
                Scenario(
                    scenario_id="model_reward_probe",
                    task_id=task_spec.task_id,
                    user_profile={"role": "骑手", "attitude": "追问奖励"},
                    coverage_targets=["reward_question", "boundary_no_extra_promise"],
                    initial_user_intent="今天有没有额外奖励？",
                    expected_test_focus="测试是否越权承诺奖励",
                    difficulty="L4",
                    scenario_type="model_generated",
                    expected_behavior="不得承诺额外奖励",
                    risk_tags=["model_generated", "safety_boundary"],
                )
            ],
        )


class FailingScenarioProvider:
    def generate(self, task_spec, rubric, input_data, minimum):
        raise RuntimeError("scenario generator timeout")


class RecoveringReportProvider:
    def __init__(self):
        self.call_count = 0

    def write(self, run_id, task_spec, scenario_set, results, input_data_summary):
        self.call_count += 1
        if self.call_count == 1:
            return Report(
                run_id=run_id,
                task_id=task_spec.task_id,
                markdown="# 模型报告\n\n只有解释，没有量化结果和证据链。",
            )
        return Report(
            run_id=run_id,
            task_id=task_spec.task_id,
            markdown="# 模型报告\n\n## 量化结果\n\n总分准确。\n\n## 证据链\n\n证据完整。",
        )


def test_run_full_evaluation_auto_repairs_failed_quality_gate_once(tmp_path: Path):
    report_provider = RecoveringReportProvider()
    run = run_full_evaluation(
        raw_instruction=RAW_TASK,
        run_root=tmp_path,
        assistant_provider=FakeAssistantProvider(),
        user_provider=FakeUserProvider(),
        minimum_scenarios=2,
        report_provider=report_provider,
    )

    assert report_provider.call_count == 2
    assert run.quality_summary["report_integrity"]["missing_sections"] == []
    assert run.quality_summary["auto_repair"]["attempted"] is True
    assert run.quality_summary["auto_repair"]["attempt_count"] == 1
    assert run.quality_summary["auto_repair"]["actions"][0]["stage"] == "report"
    assert "## 量化结果" in run.report.markdown
    assert run.stage_diagnostics["report_generation"]["output_source"] == "model"
    assert run.stage_diagnostics["report_generation"]["fallback_used"] is False


def test_report_auto_repair_falls_back_only_after_second_invalid_model_report(
    tmp_path: Path,
):
    class AlwaysInvalidReportProvider:
        def __init__(self):
            self.call_count = 0

        def write(self, run_id, task_spec, scenario_set, results, input_data_summary):
            self.call_count += 1
            return Report(
                run_id=run_id,
                task_id=task_spec.task_id,
                markdown="# 模型报告\n\n仍然缺少质量门禁要求的章节。",
            )

    report_provider = AlwaysInvalidReportProvider()
    run = run_full_evaluation(
        raw_instruction=RAW_TASK,
        run_root=tmp_path,
        assistant_provider=FakeAssistantProvider(),
        user_provider=FakeUserProvider(),
        minimum_scenarios=2,
        report_provider=report_provider,
    )

    assert report_provider.call_count == 2
    assert "## 量化结果" in run.report.markdown
    assert "## 证据链" in run.report.markdown
    diagnostic = run.stage_diagnostics["report_generation"]
    assert diagnostic["output_source"] == "template_report"
    assert diagnostic["model_attempted"] is True
    assert diagnostic["fallback_used"] is True
    assert diagnostic["fallback_reason"] == (
        "model report failed integrity check after retry"
    )


def test_report_model_retry_is_persisted_in_stage_diagnostics(tmp_path: Path):
    from backend.eval_agent.api.routes.runs import ModelConfig
    from backend.eval_agent.providers.base import ModelResponse
    from backend.eval_agent.services.run_service import build_report_generator_provider

    class SequentialReportModel:
        def __init__(self):
            self.responses = [
                "# 模型报告\n\n缺少质量门禁章节。",
                "# 模型报告\n\n## 量化结果\n\n总分准确。\n\n## 证据链\n\n证据完整。",
            ]

        def generate(self, messages, config):
            return ModelResponse(content=self.responses.pop(0), raw={"ok": True})

    report_provider = build_report_generator_provider(
        ModelConfig(
            provider="openrouter",
            model_name="openai/gpt-4.1-mini",
            api_base="https://openrouter.ai/api/v1",
            api_key="sk-report",
        ),
        model_provider=SequentialReportModel(),
    )
    run = run_full_evaluation(
        raw_instruction=RAW_TASK,
        run_root=tmp_path,
        assistant_provider=FakeAssistantProvider(),
        user_provider=FakeUserProvider(),
        minimum_scenarios=2,
        report_provider=report_provider,
    )

    diagnostic = run.stage_diagnostics["report_generation"]["model_call"]
    assert diagnostic["model_name"] == "openai/gpt-4.1-mini"
    assert diagnostic["prompt_ids"] == {"report_generator_v1": 2}
    assert diagnostic["model_call_count"] == 2
    assert diagnostic["retry_count"] == 1
    assert "sk-report" not in json.dumps(diagnostic, ensure_ascii=False)


def test_run_full_evaluation_uses_injected_scenario_generator(tmp_path: Path):
    run = run_full_evaluation(
        raw_instruction=RAW_TASK,
        run_root=tmp_path,
        assistant_provider=FakeAssistantProvider(),
        user_provider=FakeUserProvider(),
        minimum_scenarios=1,
        scenario_provider=StaticScenarioProvider(),
    )

    scenario_ids = [scenario.scenario_id for scenario in run.scenario_set.scenarios]

    assert scenario_ids[0] == "model_reward_probe"
    assert run.traces[0].scenario_id == "model_reward_probe"
    assert "model_generated" in run.scenario_set.scenarios[0].risk_tags


def test_run_full_evaluation_falls_back_when_scenario_generator_fails(tmp_path: Path):
    run = run_full_evaluation(
        raw_instruction=RAW_TASK,
        run_root=tmp_path,
        assistant_provider=FakeAssistantProvider(),
        user_provider=FakeUserProvider(),
        minimum_scenarios=1,
        scenario_provider=FailingScenarioProvider(),
    )

    assert run.scenario_set.scenarios
    assert run.traces
    assert run.scenario_set.scenarios[0].scenario_id != "model_reward_probe"


def test_run_full_evaluation_isolates_single_scenario_failures(tmp_path: Path):
    run = run_full_evaluation(
        raw_instruction=RAW_TASK,
        run_root=tmp_path,
        assistant_provider=FailingOnRewardAssistantProvider(),
        user_provider=FakeUserProvider(),
        minimum_scenarios=5,
    )

    failed_traces = [trace for trace in run.traces if trace.error]
    failed_results = [result for result in run.results if result.critical_failures == ["runtime_error"]]

    assert len(run.traces) >= 5
    assert len(run.results) == len(run.traces)
    assert failed_traces
    assert failed_results
    assert "target model failed" in failed_traces[0].error


def test_run_full_evaluation_keeps_trace_when_judge_fails_after_dialogue(tmp_path: Path):
    run = run_full_evaluation(
        raw_instruction=RAW_TASK,
        run_root=tmp_path,
        assistant_provider=FakeAssistantProvider(),
        user_provider=FakeUserProvider(),
        minimum_scenarios=1,
        judge_provider=FailingJudgeProvider(),
    )

    scenario_ids = [trace.scenario_id for trace in run.traces]
    failed_results = [
        result
        for result in run.results
        if result.critical_failures == ["runtime_error"]
    ]

    assert len(scenario_ids) == len(set(scenario_ids))
    assert len(run.results) == len(run.traces)
    assert run.traces[0].turns
    assert not run.traces[0].error
    assert failed_results
    assert failed_results[0].trace_id == run.traces[0].trace_id
    assert "semantic judge timeout" in failed_results[0].evidence[0].reason
