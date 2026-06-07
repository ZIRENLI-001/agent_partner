from __future__ import annotations

import json
import math
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol
from uuid import uuid4

from backend.evaluation_engine.dialogue_runner import run_dialogue
from backend.evaluation_engine.domain import (
    DialogueTrace,
    EvaluationResult,
    EvidenceItem,
    Report,
    RubricSpec,
    RunConfig,
    ScenarioSet,
    TaskSpec,
)
from backend.evaluation_engine.instruction_parser import parse_instruction
from backend.evaluation_engine.judge_evaluator import judge_trace
from backend.evaluation_engine.providers import AssistantProvider, UserProvider
from backend.evaluation_engine.quality_summary import build_quality_summary
from backend.evaluation_engine.report_writer import (
    append_quality_summary_section,
    write_markdown_report,
)
from backend.evaluation_engine.rubric_builder import build_rubric
from backend.evaluation_engine.rubric_quality import rubric_quality_report, standardize_rubric
from backend.evaluation_engine.rule_evaluator import evaluate_rules
from backend.evaluation_engine.scenario_generator import generate_scenarios
from backend.evaluation_engine.storage import RunStore


@dataclass
class FullRunResult:
    run_id: str
    task_spec: TaskSpec
    rubric_spec: RubricSpec
    scenario_set: ScenarioSet
    input_data_summary: dict[str, object]
    stage_model_config_summary: dict[str, object]
    traces: list[DialogueTrace]
    results: list[EvaluationResult]
    report: Report
    stage_timings_ms: dict[str, int] = field(default_factory=dict)
    stage_diagnostics: dict[str, dict[str, object]] = field(default_factory=dict)
    quality_summary: dict[str, object] = field(default_factory=dict)


class ScenarioGeneratorProvider(Protocol):
    def generate(
        self,
        task_spec: TaskSpec,
        rubric: RubricSpec,
        input_data: str,
        minimum: int,
    ) -> ScenarioSet:
        ...


class InstructionParserProvider(Protocol):
    def parse(self, raw_instruction: str, task_id: str) -> TaskSpec:
        ...


class RubricGeneratorProvider(Protocol):
    def build(self, task_spec: TaskSpec, raw_instruction: str) -> RubricSpec:
        ...


class ReportGeneratorProvider(Protocol):
    def write(
        self,
        run_id: str,
        task_spec: TaskSpec,
        scenario_set: ScenarioSet,
        results: list[EvaluationResult],
        input_data_summary: dict[str, object],
    ) -> Report:
        ...


def merge_evaluation_results(
    rule_result: EvaluationResult,
    judge_result: EvaluationResult,
    rubric: RubricSpec,
) -> EvaluationResult:
    dimension_scores = dict(rule_result.dimension_scores)
    for dimension, score in judge_result.dimension_scores.items():
        dimension_scores[dimension] = dimension_scores.get(dimension, 0) + score

    critical_failures = []
    for item_id in rule_result.critical_failures + judge_result.critical_failures:
        if item_id not in critical_failures:
            critical_failures.append(item_id)

    return EvaluationResult(
        trace_id=rule_result.trace_id,
        scenario_id=rule_result.scenario_id,
        total_score=rule_result.total_score + judge_result.total_score,
        dimension_scores=dimension_scores,
        evidence=rule_result.evidence + judge_result.evidence,
        critical_failures=critical_failures,
    )


def run_full_evaluation(
    raw_instruction: str,
    run_root: Path,
    assistant_provider: AssistantProvider,
    user_provider: UserProvider,
    minimum_scenarios: int = 5,
    input_data: str = "",
    selected_scenario_ids: list[str] | None = None,
    model_config_summary: dict[str, object] | None = None,
    stage_model_config_summary: dict[str, object] | None = None,
    run_context: dict[str, object] | None = None,
    judge_provider=None,
    scenario_provider: ScenarioGeneratorProvider | None = None,
    parser_provider: InstructionParserProvider | None = None,
    rubric_provider: RubricGeneratorProvider | None = None,
    report_provider: ReportGeneratorProvider | None = None,
    scenario_concurrency: int = 1,
    scenario_batch_size: int | None = None,
    run_id: str | None = None,
    progress_callback: Callable[[str, str], None] | None = None,
    quality_auto_repair: bool = True,
) -> FullRunResult:
    run_id = run_id or "run_%s" % uuid4().hex[:8]
    store = RunStore(run_root)
    stage_timings_ms: dict[str, int] = {}
    stage_diagnostics: dict[str, dict[str, object]] = {}
    input_data_summary = summarize_input_data(input_data)
    task_spec = _timed_stage(
        "instruction_parsing",
        stage_timings_ms,
        progress_callback,
        lambda: parse_task_spec(
            raw_instruction,
            task_id="task_001",
            input_data=input_data,
            parser_provider=parser_provider,
            stage_diagnostics=stage_diagnostics,
        ),
    )
    rubric = _timed_stage(
        "rubric_generation",
        stage_timings_ms,
        progress_callback,
        lambda: build_rubric_spec(
            task_spec,
            raw_instruction=raw_instruction,
            rubric_provider=rubric_provider,
            stage_diagnostics=stage_diagnostics,
        ),
    )
    scenario_set = _timed_stage(
        "scenario_generation",
        stage_timings_ms,
        progress_callback,
        lambda: generate_scenario_set(
            task_spec,
            rubric,
            minimum=minimum_scenarios,
            input_data=input_data,
            scenario_provider=scenario_provider,
            stage_diagnostics=stage_diagnostics,
        ),
    )
    selected_scenario_ids = selected_scenario_ids or []
    if selected_scenario_ids:
        selected_ids = set(selected_scenario_ids)
        scenario_set.scenarios = [
            scenario
            for scenario in scenario_set.scenarios
            if scenario.scenario_id in selected_ids
        ]
    run_config = RunConfig(run_id=run_id, task_id=task_spec.task_id)

    traces, results = _timed_stage(
        "scenario_execution",
        stage_timings_ms,
        progress_callback,
        lambda: _run_scenarios(
            scenario_set,
            task_spec,
            rubric,
            run_config,
            assistant_provider,
            user_provider,
            judge_provider,
            scenario_concurrency,
            scenario_batch_size,
        ),
    )

    report = _timed_stage(
        "report_generation",
        stage_timings_ms,
        progress_callback,
        lambda: write_report(
            run_id,
            task_spec,
            scenario_set,
            results,
            input_data_summary=input_data_summary,
            report_provider=report_provider,
            stage_diagnostics=stage_diagnostics,
        ),
    )
    quality_summary = build_quality_summary(
        task_spec=task_spec,
        rubric=rubric,
        scenario_set=scenario_set,
        traces=traces,
        results=results,
        report_markdown=report.markdown,
        stage_timings_ms=stage_timings_ms,
        stage_diagnostics=stage_diagnostics,
    )
    if quality_auto_repair:
        scenario_set, traces, results, report, quality_summary = _auto_repair_quality_once(
            quality_summary=quality_summary,
            run_id=run_id,
            task_spec=task_spec,
            rubric=rubric,
            scenario_set=scenario_set,
            traces=traces,
            results=results,
            report=report,
            input_data=input_data,
            input_data_summary=input_data_summary,
            minimum_scenarios=minimum_scenarios,
            selected_scenario_ids=selected_scenario_ids,
            run_config=run_config,
            assistant_provider=assistant_provider,
            user_provider=user_provider,
            judge_provider=judge_provider,
            report_provider=report_provider,
            scenario_provider=scenario_provider,
            scenario_concurrency=scenario_concurrency,
            scenario_batch_size=scenario_batch_size,
            stage_timings_ms=stage_timings_ms,
            stage_diagnostics=stage_diagnostics,
        )
    else:
        quality_summary["auto_repair"] = {
            "attempted": False,
            "attempt_count": 0,
            "actions": [],
            "before_status": quality_summary.get("overall_status", "unknown"),
            "after_status": quality_summary.get("overall_status", "unknown"),
        }
    _attach_model_call_diagnostics(
        stage_diagnostics,
        assistant_provider=assistant_provider,
        user_provider=user_provider,
        judge_provider=judge_provider,
        scenario_provider=scenario_provider,
        parser_provider=parser_provider,
        rubric_provider=rubric_provider,
        report_provider=report_provider,
    )
    report.markdown = append_quality_summary_section(report.markdown, quality_summary)

    run_config_payload = run_config.model_dump(mode="json")
    run_config_payload["selected_scenario_ids"] = selected_scenario_ids
    run_config_payload["model_config_summary"] = model_config_summary or {}
    run_config_payload["stage_model_config_summary"] = (
        stage_model_config_summary or {}
    )
    run_config_payload.update(run_context or {})
    store.write_json(run_id, "run_config.json", run_config_payload)
    store.write_json(run_id, "input_data.json", input_data_summary)
    store.write_model(run_id, "task_spec.json", task_spec)
    store.write_model(run_id, "rubric_spec.json", rubric)
    store.write_model(run_id, "scenarios.json", scenario_set)
    store.write_jsonl(run_id, "traces.jsonl", traces)
    store.write_json(
        run_id,
        "evaluation_results.json",
        [result.model_dump(mode="json") for result in results],
    )
    store.write_text(run_id, "report.md", report.markdown)
    store.write_json(run_id, "stage_timings.json", stage_timings_ms)
    store.write_json(run_id, "stage_diagnostics.json", stage_diagnostics)
    store.write_json(run_id, "quality_summary.json", quality_summary)

    return FullRunResult(
        run_id=run_id,
        task_spec=task_spec,
        rubric_spec=rubric,
        scenario_set=scenario_set,
        input_data_summary=input_data_summary,
        stage_model_config_summary=stage_model_config_summary or {},
        traces=traces,
        results=results,
        report=report,
        stage_timings_ms=stage_timings_ms,
        stage_diagnostics=stage_diagnostics,
        quality_summary=quality_summary,
    )


def _auto_repair_quality_once(
    quality_summary: dict[str, object],
    run_id: str,
    task_spec: TaskSpec,
    rubric: RubricSpec,
    scenario_set: ScenarioSet,
    traces: list[DialogueTrace],
    results: list[EvaluationResult],
    report: Report,
    input_data: str,
    input_data_summary: dict[str, object],
    minimum_scenarios: int,
    selected_scenario_ids: list[str],
    run_config: RunConfig,
    assistant_provider: AssistantProvider,
    user_provider: UserProvider,
    judge_provider,
    report_provider: ReportGeneratorProvider | None,
    scenario_provider: ScenarioGeneratorProvider | None,
    scenario_concurrency: int,
    scenario_batch_size: int | None,
    stage_timings_ms: dict[str, int],
    stage_diagnostics: dict[str, dict[str, object]],
) -> tuple[
    ScenarioSet,
    list[DialogueTrace],
    list[EvaluationResult],
    Report,
    dict[str, object],
]:
    actions = _quality_repair_actions(quality_summary)
    if not actions:
        quality_summary["auto_repair"] = {
            "attempted": False,
            "attempt_count": 0,
            "actions": [],
            "before_status": quality_summary.get("overall_status", "unknown"),
            "after_status": quality_summary.get("overall_status", "unknown"),
        }
        return scenario_set, traces, results, report, quality_summary

    before_status = quality_summary.get("overall_status", "unknown")
    selected_ids = set(selected_scenario_ids or [])
    should_regenerate_scenarios = any(
        action.get("stage") == "scenarios" for action in actions
    ) and not selected_ids
    should_rerun = should_regenerate_scenarios or any(
        action.get("stage") == "run" for action in actions
    )
    should_regenerate_report = should_rerun or any(
        action.get("stage") == "report" or "报告" in str(action.get("action", ""))
        for action in actions
    )

    if should_regenerate_scenarios:
        scenario_set = generate_scenario_set(
            task_spec,
            rubric,
            minimum=max(2, minimum_scenarios),
            input_data=input_data,
            scenario_provider=scenario_provider,
            stage_diagnostics=stage_diagnostics,
        )

    if should_rerun:
        traces, results = _run_scenarios(
            scenario_set,
            task_spec,
            rubric,
            run_config,
            assistant_provider,
            user_provider,
            judge_provider,
            scenario_concurrency,
            scenario_batch_size,
        )

    if should_regenerate_report:
        report_repair_started = time.perf_counter()
        if report_provider is not None and hasattr(
            report_provider,
            "mark_next_model_call_as_retry",
        ):
            report_provider.mark_next_model_call_as_retry()
        report = write_report(
            run_id,
            task_spec,
            scenario_set,
            results,
            input_data_summary=input_data_summary,
            report_provider=report_provider,
            stage_diagnostics=stage_diagnostics,
        )
        stage_timings_ms["report_generation"] = (
            stage_timings_ms.get("report_generation", 0)
            + _elapsed_ms(report_repair_started)
        )

    repaired_summary = build_quality_summary(
        task_spec=task_spec,
        rubric=rubric,
        scenario_set=scenario_set,
        traces=traces,
        results=results,
        report_markdown=report.markdown,
        stage_timings_ms=stage_timings_ms,
        stage_diagnostics=stage_diagnostics,
    )
    if (
        should_regenerate_report
        and report_provider is not None
        and repaired_summary["report_integrity"]["missing_sections"]
    ):
        report = write_markdown_report(
            run_id,
            task_spec,
            scenario_set,
            results,
            input_data_summary=input_data_summary,
        )
        _record_stage_diagnostic(
            stage_diagnostics,
            "report_generation",
            output_source="template_report",
            model_attempted=True,
            fallback_used=True,
            fallback_reason="model report failed integrity check after retry",
        )
        repaired_summary = build_quality_summary(
            task_spec=task_spec,
            rubric=rubric,
            scenario_set=scenario_set,
            traces=traces,
            results=results,
            report_markdown=report.markdown,
            stage_timings_ms=stage_timings_ms,
            stage_diagnostics=stage_diagnostics,
        )
    repaired_summary["auto_repair"] = {
        "attempted": True,
        "attempt_count": 1,
        "actions": actions,
        "before_status": before_status,
        "after_status": repaired_summary.get("overall_status", "unknown"),
    }
    return scenario_set, traces, results, report, repaired_summary


def _quality_repair_actions(quality_summary: dict[str, object]) -> list[dict[str, object]]:
    if quality_summary.get("overall_status") != "fail":
        return []
    actions = quality_summary.get("remediation_actions", [])
    if not isinstance(actions, list):
        return []
    return [action for action in actions if isinstance(action, dict)]


def _attach_model_call_diagnostics(
    stage_diagnostics: dict[str, dict[str, object]],
    *,
    assistant_provider,
    user_provider,
    judge_provider,
    scenario_provider,
    parser_provider,
    rubric_provider,
    report_provider,
) -> None:
    stage_providers = {
        "instruction_parsing": parser_provider,
        "rubric_generation": rubric_provider,
        "scenario_generation": scenario_provider,
        "report_generation": report_provider,
    }
    for stage_name, provider in stage_providers.items():
        diagnostic = _provider_model_call_diagnostic(provider)
        if diagnostic is not None:
            stage_diagnostics.setdefault(stage_name, {})["model_call"] = diagnostic

    execution_calls = {}
    for role, provider in {
        "target_model": assistant_provider,
        "user_simulator": user_provider,
        "semantic_judge": judge_provider,
    }.items():
        diagnostic = _provider_model_call_diagnostic(provider)
        if diagnostic is not None:
            execution_calls[role] = diagnostic
    if execution_calls:
        stage_diagnostics.setdefault("scenario_execution", {})[
            "model_calls"
        ] = execution_calls


def _provider_model_call_diagnostic(provider) -> dict[str, object] | None:
    if provider is None or not hasattr(provider, "model_call_diagnostic"):
        return None
    diagnostic = provider.model_call_diagnostic()
    return diagnostic if isinstance(diagnostic, dict) else None


def _timed_stage(
    stage_name: str,
    timings: dict[str, int],
    progress_callback: Callable[[str, str], None] | None,
    action,
):
    if progress_callback is not None:
        progress_callback(stage_name, "running")
    started = time.perf_counter()
    try:
        result = action()
    except Exception:
        timings[stage_name] = _elapsed_ms(started)
        if progress_callback is not None:
            progress_callback(stage_name, "failed")
        raise
    timings[stage_name] = _elapsed_ms(started)
    if progress_callback is not None:
        progress_callback(stage_name, "completed")
    return result


def _elapsed_ms(started: float) -> int:
    return max(1, math.ceil((time.perf_counter() - started) * 1000))


def _run_scenarios(
    scenario_set: ScenarioSet,
    task_spec: TaskSpec,
    rubric: RubricSpec,
    run_config: RunConfig,
    assistant_provider: AssistantProvider,
    user_provider: UserProvider,
    judge_provider,
    scenario_concurrency: int,
    scenario_batch_size: int | None,
) -> tuple[list[DialogueTrace], list[EvaluationResult]]:
    scenarios = list(scenario_set.scenarios)
    if not scenarios:
        return [], []
    max_workers = max(1, min(int(scenario_concurrency or 1), len(scenarios)))
    batch_size = max_workers
    if scenario_batch_size:
        batch_size = max(1, min(int(scenario_batch_size), len(scenarios)))
    if max_workers == 1:
        pairs = [
            _run_single_scenario(
                scenario,
                task_spec,
                rubric,
                run_config,
                assistant_provider,
                user_provider,
                judge_provider,
            )
            for scenario in scenarios
        ]
    else:
        pairs_by_index: dict[int, tuple[DialogueTrace, EvaluationResult]] = {}
        for start in range(0, len(scenarios), batch_size):
            batch = list(enumerate(scenarios[start : start + batch_size], start=start))
            workers_for_batch = min(max_workers, len(batch), batch_size)
            with ThreadPoolExecutor(max_workers=workers_for_batch) as executor:
                future_to_index = {
                    executor.submit(
                        _run_single_scenario,
                        scenario,
                        task_spec,
                        rubric,
                        run_config,
                        assistant_provider,
                        user_provider,
                        judge_provider,
                    ): index
                    for index, scenario in batch
                }
                for future in as_completed(future_to_index):
                    pairs_by_index[future_to_index[future]] = future.result()
        pairs = [pairs_by_index[index] for index in range(len(scenarios))]
    return [pair[0] for pair in pairs], [pair[1] for pair in pairs]


def _run_single_scenario(
    scenario,
    task_spec: TaskSpec,
    rubric: RubricSpec,
    run_config: RunConfig,
    assistant_provider: AssistantProvider,
    user_provider: UserProvider,
    judge_provider,
) -> tuple[DialogueTrace, EvaluationResult]:
    try:
        trace = run_dialogue(
            task_spec,
            scenario,
            run_config,
            assistant_provider,
            user_provider,
        )
    except Exception as exc:
        trace = _error_trace(run_config, task_spec, scenario, exc)
        return trace, _error_result(trace, exc)

    try:
        scenario_rubric = rubric_for_scenario(rubric, scenario)
        rule_result = evaluate_rules(trace, scenario_rubric)
        judge_result = judge_trace(
            trace,
            scenario_rubric,
            semantic_provider=judge_provider,
        )
        return trace, merge_evaluation_results(rule_result, judge_result, scenario_rubric)
    except Exception as exc:
        return trace, _error_result(trace, exc)


def rubric_for_scenario(rubric: RubricSpec, scenario) -> RubricSpec:
    coverage_targets = set(getattr(scenario, "coverage_targets", []) or [])
    risk_tags = set(getattr(scenario, "risk_tags", []) or [])
    if not coverage_targets and not risk_tags:
        return rubric

    selected_items = [
        item
        for item in rubric.items
        if _rubric_item_matches_scenario(item, coverage_targets, risk_tags)
    ]
    if not selected_items:
        return rubric
    return RubricSpec(
        rubric_id=rubric.rubric_id,
        task_id=rubric.task_id,
        version=rubric.version,
        items=selected_items,
    )


def _rubric_item_matches_scenario(
    item,
    coverage_targets: set[str],
    risk_tags: set[str],
) -> bool:
    if item.item_id in coverage_targets or item.item_id in risk_tags:
        return True
    if item.dimension in coverage_targets or item.dimension in risk_tags:
        return True
    item_text = " ".join([item.item_id, item.dimension, item.source, item.criterion])
    if _is_opening_item(item_text):
        return "opening_identity" in coverage_targets
    if item.critical and _is_boundary_scene(coverage_targets | risk_tags):
        return True
    return any(target and target in item_text for target in coverage_targets | risk_tags)


def _is_opening_item(item_text: str) -> bool:
    return any(term in item_text for term in ["Opening Line", "开场", "首轮", "自我介绍"])


def _is_boundary_scene(targets: set[str]) -> bool:
    return any(
        term in target
        for target in targets
        for term in ["boundary", "forbidden", "no_extra", "safety", "hallucination"]
    )


def generate_scenario_set(
    task_spec: TaskSpec,
    rubric: RubricSpec,
    minimum: int = 5,
    input_data: str = "",
    scenario_provider: ScenarioGeneratorProvider | None = None,
    stage_diagnostics: dict[str, dict[str, object]] | None = None,
) -> ScenarioSet:
    fallback_scenario_set = generate_scenarios(task_spec, rubric, minimum=minimum)
    return _scenario_set_from_provider(
        scenario_provider,
        task_spec,
        rubric,
        input_data,
        minimum,
        fallback_scenario_set,
        stage_diagnostics,
    )


def parse_task_spec(
    raw_instruction: str,
    task_id: str,
    input_data: str = "",
    parser_provider: InstructionParserProvider | None = None,
    stage_diagnostics: dict[str, dict[str, object]] | None = None,
) -> TaskSpec:
    if parser_provider is None:
        task_spec = parse_instruction(raw_instruction, task_id=task_id)
        task_spec = enrich_task_spec_from_input_data(task_spec, input_data)
        _record_stage_diagnostic(
            stage_diagnostics,
            "instruction_parsing",
            output_source="local_parser",
            model_attempted=False,
            fallback_used=False,
            input_context_used=bool(input_data.strip()),
        )
        return task_spec
    try:
        try:
            result = parser_provider.parse(raw_instruction, task_id, input_data=input_data)
        except TypeError as exc:
            if "input_data" not in str(exc):
                raise
            result = parser_provider.parse(raw_instruction, task_id)
        _record_stage_diagnostic(
            stage_diagnostics,
            "instruction_parsing",
            output_source="model",
            model_attempted=True,
            fallback_used=False,
            input_context_used=bool(input_data.strip()),
        )
        return result
    except Exception as exc:
        task_spec = parse_instruction(raw_instruction, task_id=task_id)
        task_spec = enrich_task_spec_from_input_data(task_spec, input_data)
        _record_stage_diagnostic(
            stage_diagnostics,
            "instruction_parsing",
            output_source="local_parser",
            model_attempted=True,
            fallback_used=True,
            fallback_reason=_safe_error_message(exc),
            input_context_used=bool(input_data.strip()),
        )
        return task_spec


def enrich_task_spec_from_input_data(task_spec: TaskSpec, input_data: str) -> TaskSpec:
    context = _input_data_context(input_data)
    if not context:
        return task_spec

    required_steps = list(task_spec.required_steps)
    coverage_targets = _string_list(context.get("coverage_targets"))
    risk_tags = _string_list(context.get("risk_tags"))
    for target in coverage_targets:
        step = "覆盖导入样本目标：%s" % target
        if target and step not in required_steps:
            required_steps.append(step)

    faq = list(task_spec.faq)
    for label in context.get("expected_labels", []):
        rubric_item_id = str(label.get("rubric_item_id", ""))
        expected_reason = str(label.get("expected_reason", ""))
        if rubric_item_id and expected_reason:
            faq.append({"intent": rubric_item_id, "expected_answer": expected_reason})

    edge_cases = list(task_spec.edge_cases)
    scenario_type = str(context.get("scenario_type", ""))
    if scenario_type:
        expected_behavior_parts = []
        if context.get("input_variables"):
            expected_behavior_parts.append(
                "样本变量：%s"
                % json.dumps(
                    context["input_variables"],
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
        if risk_tags:
            expected_behavior_parts.append(
                "风险标签：%s" % "、".join(risk_tags)
            )
        edge_case = {
            "trigger": scenario_type,
            "expected_behavior": "；".join(expected_behavior_parts)
            or "按导入样本上下文处理，但不改变原始指令关键要素",
        }
        if edge_case not in edge_cases:
            edge_cases.append(edge_case)

    return task_spec.model_copy(
        update={
            "required_steps": required_steps,
            "faq": faq,
            "edge_cases": edge_cases,
        }
    )


def _input_data_context(input_data: str) -> dict[str, object]:
    content = input_data.strip()
    if not content:
        return {}
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return {"raw_context": content[:500]} if len(content) >= 12 else {}
    if isinstance(parsed, list):
        parsed = parsed[0] if parsed and isinstance(parsed[0], dict) else {}
    if not isinstance(parsed, dict):
        return {}
    context: dict[str, object] = {}
    input_variables = (
        parsed.get("input_variables") if isinstance(parsed.get("input_variables"), dict) else {}
    )
    for key in [
        "case_name",
        "scenario_type",
        "coverage_targets",
        "risk_tags",
        "input_variables",
        "expected_labels",
        "expected_score_band",
    ]:
        if key in parsed:
            context[key] = parsed[key]
    for key in ["coverage_targets", "risk_tags"]:
        if key in context:
            context[key] = _string_list(context[key])
        elif key in input_variables:
            context[key] = _string_list(input_variables[key])
    return context


def _string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = re.split(r"[,，、;；|]\s*", value)
        return [part.strip() for part in parts if part.strip()]
    if isinstance(value, (list, tuple, set)):
        values: list[str] = []
        for item in value:
            values.extend(_string_list(item))
        return values
    return [str(value).strip()] if str(value).strip() else []


def build_rubric_spec(
    task_spec: TaskSpec,
    raw_instruction: str,
    rubric_provider: RubricGeneratorProvider | None = None,
    stage_diagnostics: dict[str, dict[str, object]] | None = None,
) -> RubricSpec:
    if rubric_provider is None:
        fallback = standardize_rubric(build_rubric(task_spec))
        _record_stage_diagnostic(
            stage_diagnostics,
            "rubric_generation",
            output_source="local_rubric_builder",
            model_attempted=False,
            fallback_used=False,
            quality_report=rubric_quality_report(task_spec, fallback),
        )
        return fallback
    try:
        rubric = rubric_provider.build(task_spec, raw_instruction)
    except Exception as exc:
        _record_stage_diagnostic(
            stage_diagnostics,
            "rubric_generation",
            output_source="local_rubric_builder",
            model_attempted=True,
            fallback_used=True,
            fallback_reason=_safe_error_message(exc),
        )
        fallback = standardize_rubric(build_rubric(task_spec))
        if stage_diagnostics is not None:
            stage_diagnostics["rubric_generation"]["quality_report"] = rubric_quality_report(
                task_spec,
                fallback,
            )
        return fallback
    if not rubric.items:
        _record_stage_diagnostic(
            stage_diagnostics,
            "rubric_generation",
            output_source="local_rubric_builder",
            model_attempted=True,
            fallback_used=True,
            fallback_reason="model returned empty rubric",
        )
        fallback = standardize_rubric(build_rubric(task_spec))
        if stage_diagnostics is not None:
            stage_diagnostics["rubric_generation"]["quality_report"] = rubric_quality_report(
                task_spec,
                fallback,
            )
        return fallback
    rubric = standardize_rubric(rubric)
    quality_report = rubric_quality_report(task_spec, rubric)
    if not quality_report["is_suitable"]:
        fallback = standardize_rubric(build_rubric(task_spec))
        fallback_quality = rubric_quality_report(task_spec, fallback)
        _record_stage_diagnostic(
            stage_diagnostics,
            "rubric_generation",
            output_source="local_rubric_builder",
            model_attempted=True,
            fallback_used=True,
            fallback_reason="model rubric failed task suitability check",
            quality_report=quality_report,
            fallback_quality_report=fallback_quality,
        )
        return fallback
    _record_stage_diagnostic(
        stage_diagnostics,
        "rubric_generation",
        output_source="model",
        model_attempted=True,
        fallback_used=False,
        quality_report=quality_report,
    )
    return rubric


def write_report(
    run_id: str,
    task_spec: TaskSpec,
    scenario_set: ScenarioSet,
    results: list[EvaluationResult],
    input_data_summary: dict[str, object],
    report_provider: ReportGeneratorProvider | None = None,
    stage_diagnostics: dict[str, dict[str, object]] | None = None,
) -> Report:
    if report_provider is None:
        _record_stage_diagnostic(
            stage_diagnostics,
            "report_generation",
            output_source="template_report",
            model_attempted=False,
            fallback_used=False,
        )
        return write_markdown_report(
            run_id,
            task_spec,
            scenario_set,
            results,
            input_data_summary=input_data_summary,
        )
    try:
        report = report_provider.write(
            run_id,
            task_spec,
            scenario_set,
            results,
            input_data_summary,
        )
        _record_stage_diagnostic(
            stage_diagnostics,
            "report_generation",
            output_source="model",
            model_attempted=True,
            fallback_used=False,
        )
    except Exception as exc:
        _record_stage_diagnostic(
            stage_diagnostics,
            "report_generation",
            output_source="template_report",
            model_attempted=True,
            fallback_used=True,
            fallback_reason=_safe_error_message(exc),
        )
        return write_markdown_report(
            run_id,
            task_spec,
            scenario_set,
            results,
            input_data_summary=input_data_summary,
        )
    if not report.markdown.strip():
        _record_stage_diagnostic(
            stage_diagnostics,
            "report_generation",
            output_source="template_report",
            model_attempted=True,
            fallback_used=True,
            fallback_reason="model returned empty report",
        )
        return write_markdown_report(
            run_id,
            task_spec,
            scenario_set,
            results,
            input_data_summary=input_data_summary,
        )
    return report


def _scenario_set_from_provider(
    scenario_provider: ScenarioGeneratorProvider | None,
    task_spec: TaskSpec,
    rubric: RubricSpec,
    input_data: str,
    minimum_scenarios: int,
    fallback_scenario_set: ScenarioSet,
    stage_diagnostics: dict[str, dict[str, object]] | None = None,
) -> ScenarioSet:
    if scenario_provider is None:
        _record_stage_diagnostic(
            stage_diagnostics,
            "scenario_generation",
            output_source="local_scenario_generator",
            model_attempted=False,
            fallback_used=False,
            scenario_count=len(fallback_scenario_set.scenarios),
        )
        return fallback_scenario_set

    try:
        generated = scenario_provider.generate(
            task_spec,
            rubric,
            input_data,
            minimum_scenarios,
        )
    except Exception as exc:
        _record_stage_diagnostic(
            stage_diagnostics,
            "scenario_generation",
            output_source="local_scenario_generator",
            model_attempted=True,
            fallback_used=True,
            fallback_reason=_safe_error_message(exc),
            scenario_count=len(fallback_scenario_set.scenarios),
        )
        return fallback_scenario_set

    merged_scenarios = []
    seen_ids = set()
    for scenario in generated.scenarios + fallback_scenario_set.scenarios:
        if scenario.scenario_id in seen_ids:
            continue
        merged_scenarios.append(scenario)
        seen_ids.add(scenario.scenario_id)
        if len(merged_scenarios) >= minimum_scenarios:
            break

    if not merged_scenarios:
        _record_stage_diagnostic(
            stage_diagnostics,
            "scenario_generation",
            output_source="local_scenario_generator",
            model_attempted=True,
            fallback_used=True,
            fallback_reason="model returned no valid scenarios",
            scenario_count=len(fallback_scenario_set.scenarios),
        )
        return fallback_scenario_set

    _record_stage_diagnostic(
        stage_diagnostics,
        "scenario_generation",
        output_source="model_with_local_backfill",
        model_attempted=True,
        fallback_used=len(merged_scenarios) > len(generated.scenarios),
        model_scenario_count=len(generated.scenarios),
        scenario_count=len(merged_scenarios),
    )
    return ScenarioSet(
        suite_id=generated.suite_id or fallback_scenario_set.suite_id,
        task_id=task_spec.task_id,
        version=task_spec.version,
        scenarios=merged_scenarios,
    )


def _record_stage_diagnostic(
    diagnostics: dict[str, dict[str, object]] | None,
    stage_name: str,
    **payload: object,
) -> None:
    if diagnostics is None:
        return
    diagnostics[stage_name] = payload


def _safe_error_message(exc: Exception) -> str:
    return "%s: %s" % (exc.__class__.__name__, str(exc)[:240])


def summarize_input_data(input_data: str) -> dict[str, object]:
    content = input_data.strip()
    if not content:
        return {
            "format": "empty",
            "field_count": 0,
            "line_count": 0,
            "char_count": 0,
            "preview": "未提供评测数据",
        }

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return {
            "format": "text",
            "field_count": 0,
            "line_count": len(content.splitlines()),
            "char_count": len(content),
            "preview": content[:160],
        }

    if isinstance(parsed, dict):
        field_count = len(parsed)
        preview = ", ".join(list(parsed.keys())[:8])
    elif isinstance(parsed, list):
        field_count = len(parsed)
        preview = "list[%d]" % len(parsed)
    else:
        field_count = 1
        preview = str(parsed)[:160]

    return {
        "format": "json",
        "field_count": field_count,
        "line_count": len(content.splitlines()),
        "char_count": len(content),
        "preview": preview,
    }


def _error_trace(
    run_config: RunConfig,
    task_spec: TaskSpec,
    scenario,
    exc: Exception,
) -> DialogueTrace:
    return DialogueTrace(
        trace_id="trace_%s_%s" % (run_config.run_id, scenario.scenario_id),
        run_id=run_config.run_id,
        task_id=task_spec.task_id,
        scenario_id=scenario.scenario_id,
        turns=[],
        termination_reason="runtime_error",
        error=str(exc),
    )


def _error_result(trace: DialogueTrace, exc: Exception) -> EvaluationResult:
    return EvaluationResult(
        trace_id=trace.trace_id,
        scenario_id=trace.scenario_id,
        total_score=0,
        dimension_scores={"runtime": 0},
        evidence=[
            EvidenceItem(
                rubric_item_id="runtime_error",
                verdict="fail",
                source="Evaluation Runtime",
                turn_ids=[],
                reason=str(exc),
                score=0,
                max_score=0,
                instruction_quote="运行时错误不来自任务指令",
                expected_behavior="单个场景失败应被记录，不应中断整个 run",
                actual_behavior=str(exc),
                explanation="该场景执行失败，系统已记录错误并继续执行其他场景",
            )
        ],
        critical_failures=["runtime_error"],
    )
