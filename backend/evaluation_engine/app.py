from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field

from backend.evaluation_engine.engine import run_full_evaluation, summarize_input_data
from backend.evaluation_engine.domain import (
    DialogueTrace,
    EvaluationResult,
    RubricSpec,
    ScenarioSet,
    TaskSpec,
)
from backend.evaluation_engine.calibration_dataset import (
    calibration_payload,
    load_calibration_dataset,
    summarize_calibration_dataset,
)
from backend.evaluation_engine.instruction_parser import parse_instruction
from backend.evaluation_engine.providers import FakeAssistantProvider, FakeUserProvider
from backend.evaluation_engine.quality_summary import build_quality_summary
from backend.evaluation_engine.rubric_builder import build_rubric
from backend.evaluation_engine.sample_tasks import load_sample_tasks
from backend.evaluation_engine.scenario_generator import generate_scenarios
from backend.evaluation_engine.scoring import (
    SCORING_SCALE,
    normalized_percent,
    result_dict_with_normalized_score,
    result_payload_with_normalized_score,
)


app = FastAPI(title="Dialogue Eval Platform")
RUN_ROOT = Path("runs")
WEB_INDEX = Path(__file__).parent / "web" / "index.html"

DEMO_CONTEXT = {
    "user": {"user_id": "demo_user", "display_name": "Demo User"},
    "workspace": {"workspace_id": "workspace_demo", "name": "美团履约评测空间"},
    "project": {"project_id": "project_meituan_fulfillment", "name": "美团履约外呼评测"},
}


class ModelConfig(BaseModel):
    provider: str = "mock"
    model_name: str = ""
    api_base: str = ""
    api_key: str = ""
    judge_mode: str = "hybrid"


class StageRequest(BaseModel):
    instruction: str
    input_data: str = ""
    minimum_scenarios: int = Field(default=5, ge=1, le=20)


class RunRequest(StageRequest):
    model_config = ConfigDict(populate_by_name=True)

    eval_model_config: ModelConfig = Field(
        default_factory=ModelConfig,
        alias="model_config",
    )
    selected_scenario_ids: list[str] = Field(default_factory=list)
    workspace_id: str = "workspace_demo"
    project_id: str = "project_meituan_fulfillment"
    created_by: str = "demo_user"


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return WEB_INDEX.read_text(encoding="utf-8")


@app.get("/api/sample-tasks")
def sample_tasks() -> dict[str, object]:
    return {"tasks": load_sample_tasks()}


@app.get("/api/context")
def current_context() -> dict[str, object]:
    return DEMO_CONTEXT


@app.get("/api/calibration/summary")
def calibration_summary() -> dict[str, object]:
    return summarize_calibration_dataset(load_calibration_dataset())


@app.get("/api/calibration/samples")
def calibration_samples() -> dict[str, object]:
    return calibration_payload()


@app.post("/api/stages/parse")
def parse_stage(request: StageRequest) -> dict[str, object]:
    task_spec = parse_instruction(request.instruction, task_id="task_001")
    return {
        "stage": "parse",
        "task_spec": task_spec.model_dump(mode="json"),
        "input_data_summary": summarize_input_data(request.input_data),
    }


@app.post("/api/stages/rubric")
def rubric_stage(request: StageRequest) -> dict[str, object]:
    task_spec = parse_instruction(request.instruction, task_id="task_001")
    rubric_spec = build_rubric(task_spec)
    return {
        "stage": "rubric",
        "task_spec": task_spec.model_dump(mode="json"),
        "rubric_spec": rubric_spec.model_dump(mode="json"),
    }


@app.post("/api/stages/scenarios")
def scenarios_stage(request: StageRequest) -> dict[str, object]:
    task_spec = parse_instruction(request.instruction, task_id="task_001")
    rubric_spec = build_rubric(task_spec)
    scenario_set = generate_scenarios(
        task_spec,
        rubric_spec,
        minimum=request.minimum_scenarios,
    )
    return {
        "stage": "scenarios",
        "task_spec": task_spec.model_dump(mode="json"),
        "rubric_spec": rubric_spec.model_dump(mode="json"),
        "scenario_set": scenario_set.model_dump(mode="json"),
    }


@app.post("/api/runs")
def create_run(request: RunRequest) -> dict[str, object]:
    model_config_summary = _model_config_summary(request.eval_model_config)
    run_context = _run_context(request)
    result = run_full_evaluation(
        raw_instruction=request.instruction,
        run_root=RUN_ROOT,
        assistant_provider=FakeAssistantProvider(),
        user_provider=FakeUserProvider(),
        minimum_scenarios=request.minimum_scenarios,
        input_data=request.input_data,
        selected_scenario_ids=request.selected_scenario_ids,
        model_config_summary=model_config_summary,
        run_context=run_context,
    )
    return _run_response_payload(result, model_config_summary, run_context)


@app.get("/api/runs/history")
def run_history() -> dict[str, object]:
    return _run_history_payload(RUN_ROOT)


@app.get("/api/runs/comparison")
def run_comparison() -> dict[str, object]:
    return _run_comparison_payload(RUN_ROOT)


@app.get("/api/runs/{run_id}")
def run_detail(run_id: str) -> dict[str, object]:
    return _run_detail_payload(RUN_ROOT, run_id)


def _run_response_payload(result, model_config_summary, run_context) -> dict[str, object]:
    return {
        "run_id": result.run_id,
        "trace_count": len(result.traces),
        "result_count": len(result.results),
        "stages": [
            _stage_payload(result, "instruction_parsing", "指令解析"),
            _stage_payload(result, "rubric_generation", "Rubric 生成"),
            _stage_payload(result, "scenario_generation", "场景生成"),
            _stage_payload(result, "scenario_execution", "多轮对话执行与自动评测"),
            _stage_payload(result, "report_generation", "报告生成"),
        ],
        "task_spec": result.task_spec.model_dump(mode="json"),
        "rubric_spec": result.rubric_spec.model_dump(mode="json"),
        "scenario_set": result.scenario_set.model_dump(mode="json"),
        "input_data_summary": result.input_data_summary,
        "model_config_summary": model_config_summary,
        "stage_model_config_summary": result.stage_model_config_summary,
        "run_context": run_context,
        "traces": [trace.model_dump(mode="json") for trace in result.traces],
        "results": [result_payload_with_normalized_score(item) for item in result.results],
        "score_summary": _score_summary_with_quality(
            _score_summary(result.results),
            getattr(result, "quality_summary", {}),
        ),
        "dimension_summary": _dimension_summary(result.results, result.rubric_spec),
        "scenario_summary": _scenario_summary(result.scenario_set, result.results),
        "failure_summary": _failure_summary(result.results),
        "stage_timings_ms": getattr(result, "stage_timings_ms", {}),
        "stage_diagnostics": getattr(result, "stage_diagnostics", {}),
        "quality_summary": getattr(result, "quality_summary", {}),
        "report": result.report.markdown,
    }


def _stage_payload(result, stage_key: str, name: str) -> dict[str, object]:
    timings = getattr(result, "stage_timings_ms", {}) or {}
    payload: dict[str, object] = {"name": name, "status": "completed"}
    if stage_key in timings:
        payload["duration_ms"] = timings[stage_key]
    return payload


def _run_history_payload(run_root: Path) -> dict[str, object]:
    if not run_root.exists():
        return {"runs": []}
    runs = []
    for run_dir in sorted(run_root.glob("run_*"), key=lambda item: item.stat().st_mtime, reverse=True):
        if not run_dir.is_dir():
            continue
        try:
            runs.append(_run_history_item(run_dir))
        except (OSError, json.JSONDecodeError):
            continue
    return {"runs": runs}


def _run_detail_payload(run_root: Path, run_id: str) -> dict[str, object]:
    run_dir = run_root / run_id
    if not run_dir.exists() or not run_dir.is_dir():
        raise HTTPException(status_code=404, detail="Run not found")
    try:
        run_config = _read_json(run_dir / "run_config.json")
        task_spec = _read_json(run_dir / "task_spec.json")
        rubric_spec = _read_json(run_dir / "rubric_spec.json")
        scenario_set = _read_json(run_dir / "scenarios.json")
        results = _read_json(run_dir / "evaluation_results.json")
        traces = _read_jsonl(run_dir / "traces.jsonl")
        input_data_summary = _read_json(run_dir / "input_data.json")
        report = (run_dir / "report.md").read_text(encoding="utf-8")
        stage_timings_path = run_dir / "stage_timings.json"
        stage_timings = _read_json(stage_timings_path) if stage_timings_path.exists() else {}
        stage_diagnostics_path = run_dir / "stage_diagnostics.json"
        stage_diagnostics = (
            _read_json(stage_diagnostics_path)
            if stage_diagnostics_path.exists()
            else {}
        )
        quality_summary_path = run_dir / "quality_summary.json"
        quality_summary = (
            _read_json(quality_summary_path) if quality_summary_path.exists() else {}
        )
        quality_summary = _fresh_quality_summary(
            existing=quality_summary,
            task_spec=task_spec,
            rubric_spec=rubric_spec,
            scenario_set=scenario_set,
            traces=traces,
            results=results,
            report=report,
            stage_timings=stage_timings,
            stage_diagnostics=stage_diagnostics,
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail="Run artifacts are incomplete") from exc
    return {
        "run_id": run_id,
        "updated_at": run_dir.stat().st_mtime,
        "trace_count": len(traces),
        "result_count": len(results),
        "run_config": run_config,
        "task_spec": task_spec,
        "rubric_spec": rubric_spec,
        "scenario_set": scenario_set,
        "input_data_summary": input_data_summary,
        "traces": traces,
        "results": [result_dict_with_normalized_score(item) for item in results],
        "score_summary": _score_summary_with_quality(
            _score_summary_from_dicts(results),
            quality_summary,
        ),
        "dimension_summary": _dimension_summary_from_dicts(results, rubric_spec),
        "scenario_summary": _scenario_summary_from_dicts(scenario_set, results),
        "failure_summary": _failure_summary_from_dicts(results),
        "optimization_insights": _optimization_insights_from_dicts(
            scenario_set=scenario_set,
            results=results,
            quality_summary=quality_summary,
            stage_diagnostics=stage_diagnostics,
        ),
        "stage_timings_ms": stage_timings,
        "stage_diagnostics": stage_diagnostics,
        "quality_summary": quality_summary,
        "model_config_summary": run_config.get("model_config_summary", {}),
        "stage_model_config_summary": run_config.get(
            "stage_model_config_summary", {}
        ),
        "run_context": _context_from_config(run_config),
        "report": report,
    }


def _fresh_quality_summary(
    existing: dict[str, object],
    task_spec: dict[str, object],
    rubric_spec: dict[str, object],
    scenario_set: dict[str, object],
    traces: list[dict[str, object]],
    results: list[dict[str, object]],
    report: str,
    stage_timings: dict[str, int],
    stage_diagnostics: dict[str, dict[str, object]],
) -> dict[str, object]:
    try:
        return build_quality_summary(
            task_spec=TaskSpec.model_validate(task_spec),
            rubric=RubricSpec.model_validate(rubric_spec),
            scenario_set=ScenarioSet.model_validate(scenario_set),
            traces=[DialogueTrace.model_validate(item) for item in traces],
            results=[EvaluationResult.model_validate(item) for item in results],
            report_markdown=report,
            stage_timings_ms=stage_timings,
            stage_diagnostics=stage_diagnostics,
        )
    except Exception:
        return existing


def _model_config_summary(model_config: ModelConfig) -> dict[str, Any]:
    return {
        "provider": model_config.provider,
        "model_name": model_config.model_name,
        "api_base": model_config.api_base,
        "judge_mode": model_config.judge_mode,
        "api_key_configured": bool(model_config.api_key),
    }


def _run_context(request: RunRequest) -> dict[str, object]:
    return {
        "workspace_id": request.workspace_id,
        "project_id": request.project_id,
        "created_by": request.created_by,
    }


def _context_from_config(config: dict[str, object]) -> dict[str, object]:
    return {
        "workspace_id": config.get("workspace_id", "workspace_demo"),
        "project_id": config.get("project_id", "project_meituan_fulfillment"),
        "created_by": config.get("created_by", "demo_user"),
    }


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _run_history_item(run_dir: Path) -> dict[str, object]:
    run_config = _read_json(run_dir / "run_config.json")
    task_spec = _read_json(run_dir / "task_spec.json")
    results = _read_json(run_dir / "evaluation_results.json")
    report_path = run_dir / "report.md"
    model_config = run_config.get("model_config_summary", {})
    score_summary = _score_summary_from_dicts(results)
    return {
        "run_id": run_dir.name,
        "task_name": task_spec.get("task_name", ""),
        "task_goal": task_spec.get("task_goal", ""),
        "workspace_id": run_config.get("workspace_id", "workspace_demo"),
        "project_id": run_config.get("project_id", "project_meituan_fulfillment"),
        "created_by": run_config.get("created_by", "demo_user"),
        "model_name": model_config.get("model_name", "") if isinstance(model_config, dict) else "",
        "pass_rate": score_summary["pass_rate"],
        "normalized_score": score_summary["normalized_score"],
        "normalized_pass_rate": score_summary["normalized_pass_rate"],
        "scoring_scale": score_summary["scoring_scale"],
        "total_score": score_summary["total_score"],
        "possible_score": score_summary["possible_score"],
        "scenario_count": len(results),
        "updated_at": run_dir.stat().st_mtime,
        "has_report": report_path.exists(),
    }


def _run_comparison_payload(run_root: Path) -> dict[str, object]:
    if not run_root.exists():
        return {
            "runs": [],
            "scenario_rows": [],
            "failure_reasons": [],
            "optimization_insights": [],
            "filters": _comparison_filters([], []),
        }

    runs: list[dict[str, object]] = []
    scenario_rows: list[dict[str, object]] = []
    failure_examples: list[dict[str, object]] = []
    optimization_insights: list[dict[str, object]] = []
    for run_dir in sorted(
        run_root.glob("run_*"), key=lambda item: item.stat().st_mtime, reverse=True
    ):
        if not run_dir.is_dir():
            continue
        try:
            run_config = _read_json(run_dir / "run_config.json")
            task_spec = _read_json(run_dir / "task_spec.json")
            results = _read_json(run_dir / "evaluation_results.json")
            scenario_set = _read_json(run_dir / "scenarios.json")
            run_item = _run_history_item(run_dir)
        except (OSError, json.JSONDecodeError):
            continue

        model_config = run_config.get("model_config_summary", {})
        model_name = (
            model_config.get("model_name", "") if isinstance(model_config, dict) else ""
        )
        task_name = str(task_spec.get("task_name", ""))
        task_goal = str(task_spec.get("task_goal", ""))
        updated_at = run_dir.stat().st_mtime
        runs.append(run_item)
        optimization_insights.extend(
            _comparison_optimization_examples(
                run_id=run_dir.name,
                model_name=model_name,
                insights=_optimization_insights_from_dicts(
                    scenario_set=scenario_set,
                    results=results,
                    quality_summary={},
                    stage_diagnostics={},
                ),
            )
        )
        for result in results:
            if not isinstance(result, dict):
                continue
            scenario_rows.append(
                _comparison_scenario_row(
                    run_id=run_dir.name,
                    task_name=task_name,
                    task_goal=task_goal,
                    model_name=model_name,
                    updated_at=updated_at,
                    result=result,
                )
            )
            failure_examples.extend(
                _comparison_failure_examples(
                    run_id=run_dir.name,
                    model_name=model_name,
                    result=result,
                )
            )

    return {
        "runs": runs,
        "scenario_rows": scenario_rows,
        "failure_reasons": _aggregate_failure_reasons(failure_examples),
        "optimization_insights": _aggregate_comparison_optimization_insights(
            optimization_insights
        ),
        "filters": _comparison_filters(runs, scenario_rows),
    }


def _comparison_optimization_examples(
    run_id: str,
    model_name: str,
    insights: list[dict[str, object]],
) -> list[dict[str, object]]:
    enriched = []
    for insight in insights:
        item = dict(insight)
        examples = [
            dict(example, run_id=run_id, model_name=model_name)
            for example in item.get("examples", [])
            if isinstance(example, dict)
        ]
        item["examples"] = examples
        item["run_ids"] = [run_id]
        item["model_names"] = [model_name] if model_name else []
        enriched.append(item)
    return enriched


def _aggregate_comparison_optimization_insights(
    insights: list[dict[str, object]],
) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str], dict[str, object]] = {}
    for insight in insights:
        key = (
            str(insight.get("category", "")),
            str(insight.get("business_context", "")),
            str(insight.get("decision", "")),
        )
        entry = grouped.setdefault(
            key,
            {
                "category": insight.get("category", ""),
                "category_label": insight.get("category_label", ""),
                "priority": insight.get("priority", "medium"),
                "title": insight.get("title", ""),
                "decision": insight.get("decision", ""),
                "recommended_action": insight.get("recommended_action", ""),
                "issue_summary": insight.get("issue_summary", ""),
                "evidence_summary": insight.get("evidence_summary", ""),
                "next_action": insight.get("next_action", ""),
                "business_context": insight.get("business_context", ""),
                "evidence_count": 0,
                "scenario_ids": set(),
                "rubric_item_ids": set(),
                "run_ids": set(),
                "model_names": set(),
                "examples": [],
            },
        )
        entry["evidence_count"] = int(entry["evidence_count"]) + int(
            insight.get("evidence_count", 0)
        )
        entry["scenario_ids"] = set(entry["scenario_ids"]) | set(
            _string_values(insight.get("scenario_ids", []))
        )
        entry["rubric_item_ids"] = set(entry["rubric_item_ids"]) | set(
            _string_values(insight.get("rubric_item_ids", []))
        )
        entry["run_ids"] = set(entry["run_ids"]) | set(
            _string_values(insight.get("run_ids", []))
        )
        entry["model_names"] = set(entry["model_names"]) | set(
            _string_values(insight.get("model_names", []))
        )
        if _priority_rank(str(insight.get("priority", "medium"))) < _priority_rank(
            str(entry.get("priority", "medium"))
        ):
            entry["priority"] = insight.get("priority", "medium")
        for example in insight.get("examples", []):
            if isinstance(example, dict) and len(entry["examples"]) < 3:
                entry["examples"].append(example)
        for field in ["issue_summary", "evidence_summary", "next_action", "recommended_action"]:
            if not entry.get(field) and insight.get(field):
                entry[field] = insight.get(field)

    summaries = []
    for entry in grouped.values():
        summary = dict(entry)
        summary["scenario_ids"] = sorted(entry["scenario_ids"])
        summary["rubric_item_ids"] = sorted(entry["rubric_item_ids"])
        summary["run_ids"] = sorted(entry["run_ids"])
        summary["model_names"] = sorted(entry["model_names"])
        summaries.append(summary)
    return sorted(
        summaries,
        key=lambda item: (
            _priority_rank(str(item.get("priority", "medium"))),
            -int(item.get("evidence_count", 0)),
            str(item.get("category", "")),
        ),
    )[:8]


def _comparison_scenario_row(
    run_id: str,
    task_name: str,
    task_goal: str,
    model_name: str,
    updated_at: float,
    result: dict[str, object],
) -> dict[str, object]:
    score = _number(result.get("total_score", 0))
    evidence_items = [
        item for item in result.get("evidence", []) if isinstance(item, dict)
    ]
    possible_score = sum(_number(item.get("max_score", 0)) for item in evidence_items)
    raw_pass_rate = normalized_percent(score, possible_score)
    critical_failures = result.get("critical_failures", []) or []
    critical_failure_count = (
        len(critical_failures) if isinstance(critical_failures, list) else 0
    )
    return {
        "run_id": run_id,
        "task_name": task_name,
        "task_goal": task_goal,
        "model_name": model_name,
        "scenario_id": str(result.get("scenario_id", "")),
        "score": score,
        "possible_score": possible_score,
        "raw_pass_rate": raw_pass_rate,
        "pass_rate": min(100.0, raw_pass_rate),
        "normalized_score": min(100.0, raw_pass_rate),
        "normalized_pass_rate": min(100.0, raw_pass_rate),
        "scoring_scale": SCORING_SCALE,
        "score_anomaly": bool(possible_score and score > possible_score),
        "status": "failed" if critical_failure_count else "partial",
        "critical_failure_count": critical_failure_count,
        "updated_at": updated_at,
    }


def _comparison_failure_examples(
    run_id: str,
    model_name: str,
    result: dict[str, object],
) -> list[dict[str, object]]:
    examples = []
    scenario_id = str(result.get("scenario_id", ""))
    for evidence in result.get("evidence", []):
        if not isinstance(evidence, dict) or not _is_failure_evidence(evidence):
            continue
        rubric_item_id = str(evidence.get("rubric_item_id", "unknown"))
        label = str(
            evidence.get("expected_behavior")
            or evidence.get("reason")
            or rubric_item_id
        )
        examples.append(
            {
                "key": rubric_item_id,
                "label": label,
                "run_id": run_id,
                "scenario_id": scenario_id,
                "model_name": model_name,
                "reason": str(evidence.get("reason", "")),
                "rubric_item_id": rubric_item_id,
            }
        )
    return examples


def _aggregate_failure_reasons(
    examples: list[dict[str, object]],
) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, object]] = {}
    for example in examples:
        key = str(example.get("key", "unknown"))
        entry = grouped.setdefault(
            key,
            {
                "key": key,
                "label": str(example.get("label", key)),
                "count": 0,
                "scenario_ids": set(),
                "model_names": set(),
                "run_ids": set(),
                "examples": [],
            },
        )
        entry["count"] = int(entry["count"]) + 1
        entry["scenario_ids"].add(str(example.get("scenario_id", "")))
        entry["model_names"].add(str(example.get("model_name", "")))
        entry["run_ids"].add(str(example.get("run_id", "")))
        if len(entry["examples"]) < 3:
            entry["examples"].append(
                {
                    "run_id": example.get("run_id", ""),
                    "scenario_id": example.get("scenario_id", ""),
                    "model_name": example.get("model_name", ""),
                    "reason": example.get("reason", ""),
                    "rubric_item_id": example.get("rubric_item_id", ""),
                }
            )

    return [
        {
            "key": item["key"],
            "label": item["label"],
            "count": item["count"],
            "scenario_ids": sorted(value for value in item["scenario_ids"] if value),
            "model_names": sorted(value for value in item["model_names"] if value),
            "run_ids": sorted(value for value in item["run_ids"] if value),
            "examples": item["examples"],
        }
        for item in sorted(
            grouped.values(), key=lambda value: (-int(value["count"]), str(value["key"]))
        )
    ]


def _comparison_filters(
    runs: list[dict[str, object]],
    scenario_rows: list[dict[str, object]],
) -> dict[str, list[str]]:
    return {
        "model_names": sorted(
            {
                str(item.get("model_name", ""))
                for item in runs
                if str(item.get("model_name", ""))
            }
        ),
        "scenario_ids": sorted(
            {
                str(item.get("scenario_id", ""))
                for item in scenario_rows
                if str(item.get("scenario_id", ""))
            }
        ),
        "task_names": sorted(
            {
                str(item.get("task_name", ""))
                for item in runs
                if str(item.get("task_name", ""))
            }
        ),
    }


def _is_failure_evidence(evidence: dict[str, object]) -> bool:
    score = _number(evidence.get("score", 0))
    max_score = _number(evidence.get("max_score", 0))
    verdict = str(evidence.get("verdict", "")).lower()
    return score < max_score or verdict in {"fail", "failed", "partial", "risk"}


def _number(value: object) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _score_summary(results) -> dict[str, object]:
    total_score = sum(result.total_score for result in results)
    possible_score = sum(
        evidence.max_score
        for result in results
        for evidence in result.evidence
    )
    pass_rate = normalized_percent(total_score, possible_score)
    return {
        "total_score": total_score,
        "possible_score": possible_score,
        "pass_rate": pass_rate,
        "raw_total_score": total_score,
        "raw_possible_score": possible_score,
        "normalized_score": pass_rate,
        "normalized_pass_rate": pass_rate,
        "scoring_scale": SCORING_SCALE,
        "scenario_count": len(results),
        "failure_count": sum(
            1
            for result in results
            for evidence in result.evidence
            if evidence.verdict in ("fail", "partial", "needs_review")
        ),
        "critical_failure_count": sum(len(result.critical_failures) for result in results),
    }


def _score_summary_from_dicts(results: list[dict[str, object]]) -> dict[str, object]:
    total_score = sum(int(result.get("total_score", 0)) for result in results)
    possible_score = sum(
        int(evidence.get("max_score", 0))
        for result in results
        for evidence in result.get("evidence", [])
        if isinstance(evidence, dict)
    )
    pass_rate = normalized_percent(total_score, possible_score)
    return {
        "total_score": total_score,
        "possible_score": possible_score,
        "pass_rate": pass_rate,
        "raw_total_score": total_score,
        "raw_possible_score": possible_score,
        "normalized_score": pass_rate,
        "normalized_pass_rate": pass_rate,
        "scoring_scale": SCORING_SCALE,
        "scenario_count": len(results),
        "failure_count": sum(
            1
            for result in results
            for evidence in result.get("evidence", [])
            if isinstance(evidence, dict)
            and evidence.get("verdict") in ("fail", "partial", "needs_review")
        ),
        "critical_failure_count": sum(
            len(result.get("critical_failures", []))
            for result in results
        ),
    }


def _score_summary_with_quality(
    score_summary: dict[str, object],
    quality_summary: dict[str, object] | None,
) -> dict[str, object]:
    summary = dict(score_summary)
    if not isinstance(quality_summary, dict) or not quality_summary:
        summary.setdefault("quality_gate_status", "unknown")
        summary.setdefault("score_reliable", True)
        summary.setdefault("score_reliability_reason", "")
        return summary

    status = str(quality_summary.get("overall_status", "unknown") or "unknown")
    judge_integrity = quality_summary.get("judge_integrity", {})
    missing_count = 0
    if isinstance(judge_integrity, dict):
        missing_count = int(_number(judge_integrity.get("missing_item_count", 0)))

    summary["quality_gate_status"] = status
    summary["score_reliable"] = status != "fail"
    if status == "fail":
        reason_parts = ["质量门禁失败，分数仅代表已执行证据子集"]
        if missing_count:
            reason_parts.append("Judge 漏评 %d 项" % missing_count)
        summary["score_reliability_reason"] = "；".join(reason_parts)
    elif status == "warn":
        summary["score_reliability_reason"] = "质量门禁有警告，建议结合链路健康度和证据覆盖解读"
    else:
        summary["score_reliability_reason"] = ""
    return summary


def _dimension_summary(results, rubric_spec=None) -> list[dict[str, object]]:
    scores = {}
    dimension_by_item = _rubric_dimension_by_item(rubric_spec)
    for result in results:
        for dimension, score in result.dimension_scores.items():
            current = scores.get(dimension, {"score": 0, "possible_score": 0})
            current["score"] += score
            scores[dimension] = current
        for evidence in result.evidence:
            dimension = dimension_by_item.get(evidence.rubric_item_id)
            if not dimension:
                dimension = _dimension_for_evidence(evidence, result.dimension_scores)
            current = scores.get(dimension, {"score": 0, "possible_score": 0})
            current["possible_score"] += evidence.max_score
            scores[dimension] = current

    summary = []
    for dimension in sorted(scores):
        item = scores[dimension]
        possible_score = item["possible_score"]
        pass_rate = 0.0
        if possible_score:
            pass_rate = normalized_percent(item["score"], possible_score)
        summary.append(
            {
                "dimension": dimension,
                "score": item["score"],
                "possible_score": possible_score,
                "pass_rate": pass_rate,
            }
        )
    return summary


def _dimension_summary_from_dicts(
    results: list[dict[str, object]],
    rubric_spec: dict[str, object] | None = None,
) -> list[dict[str, object]]:
    scores: dict[str, dict[str, int]] = {}
    dimension_by_item = _rubric_dimension_by_item_dict(rubric_spec or {})
    for result in results:
        for dimension, score in result.get("dimension_scores", {}).items():
            current = scores.get(dimension, {"score": 0, "possible_score": 0})
            current["score"] += int(score)
            scores[dimension] = current
        for evidence in result.get("evidence", []):
            if not isinstance(evidence, dict):
                continue
            rubric_item_id = str(evidence.get("rubric_item_id", ""))
            dimension = dimension_by_item.get(rubric_item_id)
            if not dimension:
                dimension = _dimension_for_evidence_dict(
                    evidence,
                    result.get("dimension_scores", {}),
                )
            current = scores.get(dimension, {"score": 0, "possible_score": 0})
            current["possible_score"] += int(evidence.get("max_score", 0))
            scores[dimension] = current
    return [
        {
            "dimension": dimension,
            "score": item["score"],
            "possible_score": item["possible_score"],
            "pass_rate": normalized_percent(item["score"], item["possible_score"]),
        }
        for dimension, item in sorted(scores.items())
    ]


def _rubric_dimension_by_item(rubric_spec) -> dict[str, str]:
    if rubric_spec is None:
        return {}
    return {
        item.item_id: item.dimension
        for item in getattr(rubric_spec, "items", [])
        if getattr(item, "item_id", "") and getattr(item, "dimension", "")
    }


def _rubric_dimension_by_item_dict(rubric_spec: dict[str, object]) -> dict[str, str]:
    items = rubric_spec.get("items", [])
    if not isinstance(items, list):
        return {}
    mapping = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("item_id", ""))
        dimension = str(item.get("dimension", ""))
        if item_id and dimension:
            mapping[item_id] = dimension
    return mapping


def _scenario_summary(scenario_set, results) -> list[dict[str, object]]:
    result_by_scenario = {result.scenario_id: result for result in results}
    summary = []
    for scenario in scenario_set.scenarios:
        result = result_by_scenario.get(scenario.scenario_id)
        possible_score = 0
        score = 0
        status = "not_run"
        critical_failures = []
        if result is not None:
            score = result.total_score
            possible_score = sum(evidence.max_score for evidence in result.evidence)
            critical_failures = result.critical_failures
            status = "critical_failed" if critical_failures else "evaluated"
        pass_rate = normalized_percent(score, possible_score)
        summary.append(
            {
                "scenario_id": scenario.scenario_id,
                "coverage_targets": scenario.coverage_targets,
                "expected_test_focus": scenario.expected_test_focus,
                "score": score,
                "possible_score": possible_score,
                "pass_rate": pass_rate,
                "normalized_score": pass_rate,
                "normalized_pass_rate": pass_rate,
                "scoring_scale": SCORING_SCALE,
                "status": status,
                "critical_failures": critical_failures,
            }
        )
    return summary


def _scenario_summary_from_dicts(
    scenario_set: dict[str, object],
    results: list[dict[str, object]],
) -> list[dict[str, object]]:
    result_by_scenario = {result.get("scenario_id"): result for result in results}
    summary = []
    for scenario in scenario_set.get("scenarios", []):
        if not isinstance(scenario, dict):
            continue
        scenario_id = scenario.get("scenario_id")
        result = result_by_scenario.get(scenario_id)
        possible_score = 0
        score = 0
        status = "not_run"
        critical_failures = []
        if isinstance(result, dict):
            score = int(result.get("total_score", 0))
            possible_score = sum(
                int(evidence.get("max_score", 0))
                for evidence in result.get("evidence", [])
                if isinstance(evidence, dict)
            )
            critical_failures = result.get("critical_failures", [])
            status = "critical_failed" if critical_failures else "evaluated"
        pass_rate = normalized_percent(score, possible_score)
        summary.append(
            {
                "scenario_id": scenario_id,
                "coverage_targets": scenario.get("coverage_targets", []),
                "expected_test_focus": scenario.get("expected_test_focus", ""),
                "score": score,
                "possible_score": possible_score,
                "pass_rate": pass_rate,
                "normalized_score": pass_rate,
                "normalized_pass_rate": pass_rate,
                "scoring_scale": SCORING_SCALE,
                "status": status,
                "critical_failures": critical_failures,
            }
        )
    return summary


def _failure_summary(results) -> list[dict[str, object]]:
    failures = []
    for result in results:
        for evidence in result.evidence:
            if evidence.verdict not in ("fail", "partial", "needs_review"):
                continue
            severity = "critical" if evidence.rubric_item_id in result.critical_failures else "normal"
            failures.append(
                {
                    "scenario_id": result.scenario_id,
                    "rubric_item_id": evidence.rubric_item_id,
                    "verdict": evidence.verdict,
                    "score": evidence.score,
                    "max_score": evidence.max_score,
                    "source": evidence.source,
                    "turn_ids": evidence.turn_ids,
                    "reason": evidence.reason,
                    "severity": severity,
                }
            )
    return failures


def _failure_summary_from_dicts(results: list[dict[str, object]]) -> list[dict[str, object]]:
    failures = []
    for result in results:
        critical_failures = result.get("critical_failures", [])
        for evidence in result.get("evidence", []):
            if not isinstance(evidence, dict):
                continue
            if evidence.get("verdict") not in ("fail", "partial", "needs_review"):
                continue
            rubric_item_id = evidence.get("rubric_item_id", "")
            failures.append(
                {
                    "scenario_id": result.get("scenario_id", ""),
                    "rubric_item_id": rubric_item_id,
                    "verdict": evidence.get("verdict", ""),
                    "score": evidence.get("score", 0),
                    "max_score": evidence.get("max_score", 0),
                    "source": evidence.get("source", ""),
                    "turn_ids": evidence.get("turn_ids", []),
                    "reason": evidence.get("reason", ""),
                    "severity": "critical" if rubric_item_id in critical_failures else "normal",
                }
            )
    return failures


def _optimization_insights_from_dicts(
    scenario_set: dict[str, object],
    results: list[dict[str, object]],
    quality_summary: dict[str, object] | None,
    stage_diagnostics: dict[str, dict[str, object]] | None,
) -> list[dict[str, object]]:
    scenario_by_id = {
        str(scenario.get("scenario_id", "")): scenario
        for scenario in scenario_set.get("scenarios", [])
        if isinstance(scenario, dict)
    }
    samples = load_calibration_dataset()
    grouped: dict[tuple[str, str], dict[str, object]] = {}

    for result in results:
        if not isinstance(result, dict):
            continue
        scenario_id = str(result.get("scenario_id", ""))
        scenario = scenario_by_id.get(scenario_id, {})
        matched_samples = _matching_calibration_samples(scenario, samples)
        for evidence in result.get("evidence", []):
            if not isinstance(evidence, dict):
                continue
            if evidence.get("verdict") not in ("fail", "partial", "needs_review"):
                continue
            category = _optimization_category(evidence, scenario, quality_summary or {}, stage_diagnostics or {})
            target_key = _primary_business_target(evidence, scenario, matched_samples)
            key = (category, target_key)
            insight = grouped.setdefault(
                key,
                _new_optimization_insight(category, target_key, scenario, evidence, matched_samples),
            )
            insight["evidence_count"] = int(insight["evidence_count"]) + 1
            insight["scenario_ids"] = sorted(
                set(insight["scenario_ids"]) | {scenario_id}
            )
            insight["rubric_item_ids"] = sorted(
                set(insight["rubric_item_ids"]) | {str(evidence.get("rubric_item_id", ""))}
            )
            if len(insight["examples"]) < 3:
                insight["examples"].append(
                    {
                        "scenario_id": scenario_id,
                        "rubric_item_id": evidence.get("rubric_item_id", ""),
                        "reason": evidence.get("reason", ""),
                        "expected_behavior": evidence.get("expected_behavior", ""),
                        "actual_behavior": evidence.get("actual_behavior", ""),
                        "turn_ids": evidence.get("turn_ids", []),
                    }
                )
            if evidence.get("rubric_item_id") in result.get("critical_failures", []):
                insight["priority"] = "high"

    for insight in grouped.values():
        insight["issue_summary"] = _issue_summary_for_insight(insight)
        insight["evidence_summary"] = _evidence_summary_for_insight(insight)
        insight["next_action"] = _next_action_for_insight(insight)
        insight["recommended_action"] = _recommended_action_for_insight(insight)
        insight["decision"] = _decision_for_insight(insight)

    return sorted(
        grouped.values(),
        key=lambda item: (
            {"high": 0, "medium": 1, "low": 2}.get(str(item.get("priority")), 3),
            -int(item.get("evidence_count", 0)),
            str(item.get("category", "")),
        ),
    )


def _new_optimization_insight(
    category: str,
    target_key: str,
    scenario: dict[str, object],
    evidence: dict[str, object],
    matched_samples: list[dict[str, object]],
) -> dict[str, object]:
    sample = matched_samples[0] if matched_samples else {}
    return {
        "category": category,
        "category_label": _optimization_category_label(category),
        "priority": "medium",
        "title": "%s · %s" % (_optimization_category_label(category), target_key),
        "business_context": _business_context_from_sample_or_scenario(sample, scenario, evidence),
        "sample_task_instruction": str(sample.get("task_instruction", "")),
        "scenario_ids": [],
        "rubric_item_ids": [],
        "evidence_count": 0,
        "sample_references": [
            {
                "sample_id": str(item.get("sample_id", "")),
                "domain": str(item.get("domain", "")),
                "scenario_type": str(item.get("scenario_type", "")),
                "difficulty": str(item.get("difficulty", "")),
                "coverage_targets": item.get("coverage_targets", []),
                "risk_tags": item.get("risk_tags", []),
            }
            for item in matched_samples[:3]
        ],
        "examples": [],
        "decision": "",
        "recommended_action": "",
        "issue_summary": "",
        "evidence_summary": "",
        "next_action": "",
    }


def _matching_calibration_samples(
    scenario: dict[str, object],
    samples: list[dict[str, object]],
) -> list[dict[str, object]]:
    scenario_targets = set(_string_values(scenario.get("coverage_targets", []))) | set(
        _string_values(scenario.get("focus_points", []))
    )
    scenario_risks = set(_string_values(scenario.get("risk_tags", []))) | set(
        _string_values(scenario.get("expected_risks", []))
    )
    scenario_type = str(scenario.get("scenario_type", ""))
    focus = " ".join(
        _string_values(scenario.get("expected_test_focus", ""))
        + _string_values(scenario.get("focus_points", []))
    )

    scored = []
    for sample in samples:
        sample_targets = set(_string_values(sample.get("coverage_targets", [])))
        sample_risks = set(_string_values(sample.get("risk_tags", [])))
        score = 0
        score += 5 * len(scenario_targets & sample_targets)
        score += 3 * len(scenario_risks & sample_risks)
        if scenario_type and scenario_type == str(sample.get("scenario_type", "")):
            score += 8
        if scenario_type and scenario_type in str(sample.get("scenario_type", "")):
            score += 3
        if focus and any(token in str(sample.get("task_instruction", "")) for token in _meaningful_business_tokens(focus)):
            score += 2
        if score:
            scored.append((score, sample))
    return [sample for _, sample in sorted(scored, key=lambda item: item[0], reverse=True)[:5]]


def _optimization_category(
    evidence: dict[str, object],
    scenario: dict[str, object],
    quality_summary: dict[str, object],
    stage_diagnostics: dict[str, dict[str, object]],
) -> str:
    text = " ".join(
        str(evidence.get(key, ""))
        for key in ["rubric_item_id", "reason", "expected_behavior", "actual_behavior", "explanation", "source"]
    )
    scenario_text = " ".join(
        str(value)
        for value in [
            scenario.get("scenario_type", ""),
            scenario.get("coverage_targets", []),
            scenario.get("risk_tags", []),
            scenario.get("expected_test_focus", ""),
        ]
    )
    if evidence.get("verdict") == "needs_review" or "非法JSON" in text or "Judge" in text or "漏评" in text:
        return "algorithm"
    if "initial_user_intent_sanitized" in _string_values(scenario.get("risk_tags", [])):
        return "data"
    if "Rubric" in text or "rubric" in text or "不适配" in text:
        return "data"
    if any(marker in text for marker in ["未说明", "未告知", "没有回答", "缺少", "未完成", "未确认", "未传达"]):
        return "prompt"
    if any(marker in text for marker in ["承诺", "越权", "编造", "职责范围", "优惠", "折扣", "奖励"]):
        return "process"
    if any(marker in scenario_text for marker in ["handoff_boundary", "safety_boundary", "dispatch_policy", "coupon_boundary"]):
        return "process"
    if quality_summary.get("overall_status") == "fail":
        return "algorithm"
    if any(
        isinstance(value, dict) and value.get("fallback_used")
        for value in stage_diagnostics.values()
    ):
        return "algorithm"
    return "prompt"


def _primary_business_target(
    evidence: dict[str, object],
    scenario: dict[str, object],
    matched_samples: list[dict[str, object]],
) -> str:
    rubric_item_id = str(evidence.get("rubric_item_id", ""))
    for sample in matched_samples:
        for target in _string_values(sample.get("coverage_targets", [])):
            if target == rubric_item_id:
                return target
    targets = _string_values(scenario.get("coverage_targets", []))
    if rubric_item_id:
        return rubric_item_id
    if targets:
        return targets[0]
    return str(scenario.get("scenario_type", "业务场景"))


def _business_context_from_sample_or_scenario(
    sample: dict[str, object],
    scenario: dict[str, object],
    evidence: dict[str, object],
) -> str:
    domain = str(sample.get("domain") or "")
    scenario_type = str(sample.get("scenario_type") or scenario.get("scenario_type") or "")
    targets = _string_values(
        sample.get("coverage_targets")
        or scenario.get("coverage_targets")
        or scenario.get("focus_points")
        or []
    )
    risks = _string_values(
        sample.get("risk_tags")
        or scenario.get("risk_tags")
        or scenario.get("expected_risks")
        or []
    )
    label_reasons = [
        str(label.get("expected_reason", ""))
        for label in sample.get("expected_labels", [])
        if isinstance(label, dict) and label.get("rubric_item_id") == evidence.get("rubric_item_id")
    ]
    parts = []
    if domain:
        parts.append("业务域：%s" % domain)
    if scenario_type:
        parts.append("场景：%s" % scenario_type)
    if targets:
        parts.append("覆盖目标：%s" % "、".join(targets[:5]))
    if risks:
        parts.append("风险标签：%s" % "、".join(risks[:5]))
    if label_reasons:
        parts.append("样本标准：%s" % label_reasons[0])
    return "；".join(parts) or str(evidence.get("expected_behavior", ""))


def _recommended_action_for_insight(insight: dict[str, object]) -> str:
    issue = str(insight.get("issue_summary", "")).strip()
    action = str(insight.get("next_action", "")).strip()
    evidence = str(insight.get("evidence_summary", "")).strip()
    if issue or action:
        return "；".join(part for part in [issue, evidence, action] if part)
    category = str(insight.get("category", "prompt"))
    task = str(insight.get("sample_task_instruction", "")).strip()
    context = str(insight.get("business_context", "")).strip()
    target = "、".join(_string_values(insight.get("rubric_item_ids", []))) or str(insight.get("title", ""))
    if category == "prompt":
        return "优化被测模型提示词：把样本库中该业务场景的任务要求写成必答清单，并针对 %s 增加遗漏检测与收口确认。%s" % (target, task[:120])
    if category == "algorithm":
        return "优化评测算法链路：检查 Judge 输出、证据轮次和质量门禁，对该业务场景增加重试、补判或证据抽取规则。%s" % context
    if category == "data":
        return "优化样本/Rubric 数据：补充或修正该场景的覆盖目标、风险标签、expected_labels 和首轮用户意图，确保生成场景与样本标准一致。%s" % context
    if category == "process":
        return "优化业务流程策略：把该场景的权限边界、FAQ、转人工/回电、安全或费用处理写成明确分支，避免模型临场编造。%s" % context
    if category == "model":
        return "优化模型配置：该类场景需要更强的多轮一致性和指令遵循能力，可降低温度或更换目标模型后复测。%s" % context
    return "结合样本库标准复核该失败项，并补充对应链路优化动作。%s" % context


def _issue_summary_for_insight(insight: dict[str, object]) -> str:
    category = str(insight.get("category", "prompt"))
    targets = "、".join(_string_values(insight.get("rubric_item_ids", []))) or str(
        insight.get("title", "关键项")
    )
    examples = insight.get("examples", [])
    first_reason = ""
    if examples and isinstance(examples[0], dict):
        first_reason = str(examples[0].get("reason", "")).strip()
    prefix = {
        "prompt": "被测模型回复缺失关键要求",
        "algorithm": "评测链路存在判定或证据抽取风险",
        "data": "样本、场景标签或 Rubric 可能不匹配",
        "process": "业务边界或处理 SOP 不够明确",
        "model": "模型配置可能影响稳定遵循",
    }.get(category, "链路存在待复核问题")
    if first_reason:
        return "%s：%s。示例原因：%s" % (prefix, targets, first_reason[:90])
    return "%s：%s。" % (prefix, targets)


def _evidence_summary_for_insight(insight: dict[str, object]) -> str:
    context = str(insight.get("business_context", "")).strip()
    scenario_count = len(_string_values(insight.get("scenario_ids", [])))
    rubric_count = len(_string_values(insight.get("rubric_item_ids", [])))
    evidence_count = int(insight.get("evidence_count", 0))
    refs = insight.get("sample_references", [])
    domains = sorted(
        {
            str(ref.get("domain", ""))
            for ref in refs
            if isinstance(ref, dict) and ref.get("domain")
        }
    )
    parts = [
        "影响 %s 个场景、%s 个评判项、%s 条证据" % (scenario_count, rubric_count, evidence_count)
    ]
    if domains:
        parts.append("样本库业务域：%s" % "、".join(domains[:3]))
    if context:
        parts.append(context)
    return "；".join(parts)


def _next_action_for_insight(insight: dict[str, object]) -> str:
    category = str(insight.get("category", "prompt"))
    target = "、".join(_string_values(insight.get("rubric_item_ids", []))) or str(
        insight.get("title", "关键要求")
    )
    task = str(insight.get("sample_task_instruction", "")).strip()
    if category == "prompt":
        return "下一步：把 %s 写入被测模型必答清单，并增加回复前自检：是否已覆盖样本库对应任务要求。%s" % (
            target,
            task[:90],
        )
    if category == "algorithm":
        return "下一步：复核 Judge 证据轮次和漏评项，对该类失败增加补判或重试，避免只按已抽取证据给低分。"
    if category == "data":
        return "下一步：补齐该任务的 coverage_targets、risk_tags 和 expected_labels，重新生成专属 Rubric 后复测。"
    if category == "process":
        return "下一步：把权限边界、转人工/回电、安全和费用规则写成业务分支，避免模型临场补政策。"
    if category == "model":
        return "下一步：降低温度或更换更强指令遵循模型，对同一场景复测稳定性。"
    return "下一步：按样本库标准复核该失败项，并明确归属到提示词、数据或算法链路。"


def _decision_for_insight(insight: dict[str, object]) -> str:
    category = str(insight.get("category", "prompt"))
    labels = {
        "prompt": "优先改被测模型提示词/系统约束",
        "algorithm": "优先修评测链路和 Judge 可靠性",
        "data": "优先补样本、场景标签或 Rubric",
        "process": "优先沉淀业务处理 SOP",
        "model": "优先复核模型选择和采样参数",
    }
    return labels.get(category, "优先人工复核后再决策")


def _optimization_category_label(category: str) -> str:
    return {
        "prompt": "提示词优化",
        "algorithm": "算法链路优化",
        "data": "样本数据优化",
        "process": "业务流程优化",
        "model": "模型配置优化",
    }.get(category, "链路优化")


def _priority_rank(priority: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(priority, 3)


def _string_values(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def _meaningful_business_tokens(text: str) -> list[str]:
    return [token for token in text.replace("，", " ").replace("、", " ").split() if len(token) >= 2]


def _dimension_for_evidence(evidence, dimension_scores: dict[str, int]) -> str:
    evidence_text = " ".join(
        [
            evidence.instruction_quote,
            evidence.source,
            evidence.reason,
            evidence.expected_behavior,
        ]
    )
    return _dimension_for_item(
        evidence.rubric_item_id,
        dimension_scores,
        evidence_text,
    )


def _dimension_for_evidence_dict(
    evidence: dict[str, object],
    dimension_scores: dict[str, object],
) -> str:
    evidence_text = " ".join(
        str(evidence.get(key, ""))
        for key in ["instruction_quote", "source", "reason", "expected_behavior"]
    )
    return _dimension_for_item(
        str(evidence.get("rubric_item_id", "")),
        {str(key): int(value) for key, value in dimension_scores.items()},
        evidence_text,
    )


def _dimension_for_item(
    rubric_item_id: str,
    dimension_scores: dict[str, int] | None = None,
    evidence_text: str = "",
) -> str:
    dimension_scores = dimension_scores or {}
    if rubric_item_id.startswith("step_"):
        return "task_completion"
    if rubric_item_id.startswith("process_"):
        return "process_adherence"
    if rubric_item_id.startswith("constraint_"):
        if "conversation_quality" in dimension_scores and "constraint_following" not in dimension_scores:
            return "conversation_quality"
        if "constraint_following" in dimension_scores and "conversation_quality" not in dimension_scores:
            return "constraint_following"
        if (
            "conversation_quality" in dimension_scores
            and ("30" in evidence_text or "字" in evidence_text or "长度" in evidence_text)
        ):
            return "conversation_quality"
        if (
            "constraint_following" in dimension_scores
            and ("超出职责范围" in evidence_text or "约束" in evidence_text)
        ):
            return "constraint_following"
        return "communication_quality"
    if rubric_item_id.startswith("faq_"):
        return "knowledge_accuracy"
    if rubric_item_id.startswith("edge_"):
        return "edge_case_handling"
    if rubric_item_id.startswith("forbidden_"):
        if "boundary_safety" in dimension_scores:
            return "boundary_safety"
        return "safety_boundary"
    return "other"
