# API Service Split Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the production backend entrypoint into focused routes and services while preserving the current MVP API behavior.

**Architecture:** Keep the legacy `backend.evaluation_engine.app` serving the existing UI during migration. Add production `backend.eval_agent.api.routes` modules and `backend.eval_agent.services` wrappers that delegate to the existing engine and app helpers. The new `backend.eval_agent.api.main` builds its own FastAPI app, includes focused routers, and serves the same HTML.

**Tech Stack:** Python, FastAPI, Pydantic, pytest.

---

## File Structure

- Modify `backend/eval_agent/api/main.py`: build a production FastAPI app and include routers.
- Create `backend/eval_agent/api/routes/__init__.py`: routes package marker.
- Create `backend/eval_agent/api/routes/context.py`: `/api/context`.
- Create `backend/eval_agent/api/routes/stages.py`: `/api/stages/parse`, `/api/stages/rubric`, `/api/stages/scenarios`.
- Create `backend/eval_agent/api/routes/runs.py`: `/api/runs`, `/api/runs/history`, `/api/runs/{run_id}`.
- Create `backend/eval_agent/services/__init__.py`: services package marker.
- Create `backend/eval_agent/services/context_service.py`: returns current demo context.
- Create `backend/eval_agent/services/stage_service.py`: wraps parser, rubric builder, scenario generator.
- Create `backend/eval_agent/services/run_service.py`: wraps run creation and persisted run lookup.
- Modify `tests/test_backend_scaffold.py`: add route/service compatibility tests.

## Task 1: Context Route And Production App Builder

**Files:**
- Modify: `backend/eval_agent/api/main.py`
- Create: `backend/eval_agent/api/routes/__init__.py`
- Create: `backend/eval_agent/api/routes/context.py`
- Create: `backend/eval_agent/services/__init__.py`
- Create: `backend/eval_agent/services/context_service.py`
- Modify: `tests/test_backend_scaffold.py`

- [ ] **Step 1: Write failing context route test**

Append to `tests/test_backend_scaffold.py`:

```python
from fastapi.testclient import TestClient

from backend.eval_agent.api.main import create_app


def test_production_app_context_route_matches_mvp_context():
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/context")

    assert response.status_code == 200
    assert response.json()["workspace"]["name"] == "美团履约评测空间"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_backend_scaffold.py::test_production_app_context_route_matches_mvp_context -q`

Expected: FAIL because `create_app` is missing.

- [ ] **Step 3: Implement context service**

Create `backend/eval_agent/services/__init__.py` as an empty file.

Create `backend/eval_agent/services/context_service.py`:

```python
from __future__ import annotations

from copy import deepcopy

from backend.evaluation_engine.app import DEMO_CONTEXT


def get_current_context() -> dict[str, object]:
    return deepcopy(DEMO_CONTEXT)
```

- [ ] **Step 4: Implement context route**

Create `backend/eval_agent/api/routes/__init__.py` as an empty file.

Create `backend/eval_agent/api/routes/context.py`:

```python
from __future__ import annotations

from fastapi import APIRouter

from backend.eval_agent.services.context_service import get_current_context

router = APIRouter(prefix="/api/context", tags=["context"])


@router.get("")
def current_context() -> dict[str, object]:
    return get_current_context()
```

- [ ] **Step 5: Implement production app builder**

Replace `backend/eval_agent/api/main.py` with:

```python
from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from backend.eval_agent.api.routes import context
from backend.evaluation_engine.app import WEB_INDEX


def create_app() -> FastAPI:
    app = FastAPI(title="Dialogue Eval Platform")
    app.include_router(context.router)

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return WEB_INDEX.read_text(encoding="utf-8")

    return app


app = create_app()

__all__ = ["app", "create_app"]
```

- [ ] **Step 6: Run context route test**

Run: `python3 -m pytest tests/test_backend_scaffold.py::test_production_app_context_route_matches_mvp_context -q`

Expected: PASS.

## Task 2: Stage Routes And Service

**Files:**
- Modify: `backend/eval_agent/api/main.py`
- Create: `backend/eval_agent/api/routes/stages.py`
- Create: `backend/eval_agent/services/stage_service.py`
- Modify: `tests/test_backend_scaffold.py`

- [ ] **Step 1: Write failing stage route test**

Append to `tests/test_backend_scaffold.py`:

```python
def test_production_app_stage_routes_generate_parse_rubric_and_scenarios():
    app = create_app()
    client = TestClient(app)
    payload = {
        "instruction": "# Role\n你是站长\n# Task\n通知骑手合同生效",
        "input_data": "{\"city\":\"北京\"}",
        "minimum_scenarios": 5,
    }

    parse_response = client.post("/api/stages/parse", json=payload)
    rubric_response = client.post("/api/stages/rubric", json=payload)
    scenarios_response = client.post("/api/stages/scenarios", json=payload)

    assert parse_response.status_code == 200
    assert parse_response.json()["stage"] == "parse"
    assert parse_response.json()["input_data_summary"]["format"] == "json"
    assert rubric_response.status_code == 200
    assert rubric_response.json()["stage"] == "rubric"
    assert scenarios_response.status_code == 200
    assert scenarios_response.json()["stage"] == "scenarios"
    assert len(scenarios_response.json()["scenario_set"]["scenarios"]) >= 5
```

- [ ] **Step 2: Run stage test to verify it fails**

Run: `python3 -m pytest tests/test_backend_scaffold.py::test_production_app_stage_routes_generate_parse_rubric_and_scenarios -q`

Expected: FAIL with 404 for stage routes.

- [ ] **Step 3: Implement stage service**

Create `backend/eval_agent/services/stage_service.py`:

```python
from __future__ import annotations

from backend.evaluation_engine.engine import summarize_input_data
from backend.evaluation_engine.instruction_parser import parse_instruction
from backend.evaluation_engine.rubric_builder import build_rubric
from backend.evaluation_engine.scenario_generator import generate_scenarios


def parse_stage_payload(instruction: str, input_data: str) -> dict[str, object]:
    task_spec = parse_instruction(instruction, task_id="task_001")
    return {
        "stage": "parse",
        "task_spec": task_spec.model_dump(mode="json"),
        "input_data_summary": summarize_input_data(input_data),
    }


def rubric_stage_payload(instruction: str) -> dict[str, object]:
    task_spec = parse_instruction(instruction, task_id="task_001")
    rubric_spec = build_rubric(task_spec)
    return {
        "stage": "rubric",
        "task_spec": task_spec.model_dump(mode="json"),
        "rubric_spec": rubric_spec.model_dump(mode="json"),
    }


def scenarios_stage_payload(instruction: str, minimum_scenarios: int) -> dict[str, object]:
    task_spec = parse_instruction(instruction, task_id="task_001")
    rubric_spec = build_rubric(task_spec)
    scenario_set = generate_scenarios(task_spec, rubric_spec, minimum=minimum_scenarios)
    return {
        "stage": "scenarios",
        "task_spec": task_spec.model_dump(mode="json"),
        "rubric_spec": rubric_spec.model_dump(mode="json"),
        "scenario_set": scenario_set.model_dump(mode="json"),
    }
```

- [ ] **Step 4: Implement stage routes**

Create `backend/eval_agent/api/routes/stages.py`:

```python
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.eval_agent.services.stage_service import (
    parse_stage_payload,
    rubric_stage_payload,
    scenarios_stage_payload,
)

router = APIRouter(prefix="/api/stages", tags=["stages"])


class StageRequest(BaseModel):
    instruction: str
    input_data: str = ""
    minimum_scenarios: int = Field(default=5, ge=1, le=20)


@router.post("/parse")
def parse_stage(request: StageRequest) -> dict[str, object]:
    return parse_stage_payload(request.instruction, request.input_data)


@router.post("/rubric")
def rubric_stage(request: StageRequest) -> dict[str, object]:
    return rubric_stage_payload(request.instruction)


@router.post("/scenarios")
def scenarios_stage(request: StageRequest) -> dict[str, object]:
    return scenarios_stage_payload(request.instruction, request.minimum_scenarios)
```

- [ ] **Step 5: Include stage router**

Modify `backend/eval_agent/api/main.py` imports and `create_app`:

```python
from backend.eval_agent.api.routes import context, stages
```

and:

```python
app.include_router(stages.router)
```

- [ ] **Step 6: Run stage route test**

Run: `python3 -m pytest tests/test_backend_scaffold.py::test_production_app_stage_routes_generate_parse_rubric_and_scenarios -q`

Expected: PASS.

## Task 3: Run Routes And Service

**Files:**
- Modify: `backend/eval_agent/api/main.py`
- Create: `backend/eval_agent/api/routes/runs.py`
- Create: `backend/eval_agent/services/run_service.py`
- Modify: `tests/test_backend_scaffold.py`

- [ ] **Step 1: Write failing run route test**

Append to `tests/test_backend_scaffold.py`:

```python
def test_production_app_run_routes_create_history_and_detail(tmp_path, monkeypatch):
    from backend.eval_agent.services import run_service

    monkeypatch.setattr(run_service, "RUN_ROOT", tmp_path)
    app = create_app()
    client = TestClient(app)

    created = client.post(
        "/api/runs",
        json={
            "instruction": "# Role\n你是站长\n# Task\n通知骑手合同生效",
            "model_config": {"model_name": "openrouter-demo"},
        },
    )

    assert created.status_code == 200
    run_id = created.json()["run_id"]
    assert created.json()["trace_count"] >= 1

    history = client.get("/api/runs/history")
    detail = client.get(f"/api/runs/{run_id}")

    assert history.status_code == 200
    assert history.json()["runs"][0]["run_id"] == run_id
    assert detail.status_code == 200
    assert detail.json()["run_id"] == run_id
    assert detail.json()["model_config_summary"]["model_name"] == "openrouter-demo"
```

- [ ] **Step 2: Run run route test to verify it fails**

Run: `python3 -m pytest tests/test_backend_scaffold.py::test_production_app_run_routes_create_history_and_detail -q`

Expected: FAIL with 404 for run routes.

- [ ] **Step 3: Implement run service**

Create `backend/eval_agent/services/run_service.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.evaluation_engine import app as legacy_app
from backend.evaluation_engine.engine import run_full_evaluation
from backend.evaluation_engine.providers import FakeAssistantProvider, FakeUserProvider

RUN_ROOT = Path("runs")


def model_config_summary(model_config: Any) -> dict[str, Any]:
    return legacy_app._model_config_summary(model_config)


def run_context(request: Any) -> dict[str, object]:
    return legacy_app._run_context(request)


def create_run_payload(request: Any) -> dict[str, object]:
    summary = model_config_summary(request.eval_model_config)
    context = run_context(request)
    result = run_full_evaluation(
        raw_instruction=request.instruction,
        run_root=RUN_ROOT,
        assistant_provider=FakeAssistantProvider(),
        user_provider=FakeUserProvider(),
        minimum_scenarios=request.minimum_scenarios,
        input_data=request.input_data,
        selected_scenario_ids=request.selected_scenario_ids,
        model_config_summary=summary,
        run_context=context,
    )
    return legacy_app._run_response_payload(result, summary, context)


def run_history_payload() -> dict[str, object]:
    return legacy_app._run_history_payload(RUN_ROOT)


def run_detail_payload(run_id: str) -> dict[str, object]:
    return legacy_app._run_detail_payload(RUN_ROOT, run_id)
```

This task depends on Task 4 adding legacy helper extraction.

- [ ] **Step 4: Implement run routes**

Create `backend/eval_agent/api/routes/runs.py`:

```python
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from fastapi import APIRouter

from backend.eval_agent.services.run_service import (
    create_run_payload,
    run_detail_payload,
    run_history_payload,
)

router = APIRouter(prefix="/api/runs", tags=["runs"])


class ModelConfig(BaseModel):
    provider: str = "mock"
    model_name: str = ""
    api_base: str = ""
    api_key: str = ""
    judge_mode: str = "hybrid"


class RunRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    instruction: str
    input_data: str = ""
    minimum_scenarios: int = Field(default=5, ge=1, le=20)
    eval_model_config: ModelConfig = Field(
        default_factory=ModelConfig,
        alias="model_config",
    )
    selected_scenario_ids: list[str] = Field(default_factory=list)
    workspace_id: str = "workspace_demo"
    project_id: str = "project_meituan_fulfillment"
    created_by: str = "demo_user"


@router.post("")
def create_run(request: RunRequest) -> dict[str, object]:
    return create_run_payload(request)


@router.get("/history")
def run_history() -> dict[str, object]:
    return run_history_payload()


@router.get("/{run_id}")
def run_detail(run_id: str) -> dict[str, object]:
    return run_detail_payload(run_id)
```

- [ ] **Step 5: Include runs router**

Modify `backend/eval_agent/api/main.py` imports and `create_app`:

```python
from backend.eval_agent.api.routes import context, runs, stages
```

and:

```python
app.include_router(runs.router)
```

- [ ] **Step 6: Run run route test**

Run: `python3 -m pytest tests/test_backend_scaffold.py::test_production_app_run_routes_create_history_and_detail -q`

Expected: PASS after Task 4 helper extraction is complete.

## Task 4: Extract Legacy App Response Helpers

**Files:**
- Modify: `eval_agent/app.py`
- Test: `tests/test_app.py`
- Test: `tests/test_backend_scaffold.py`

- [ ] **Step 1: Write failing helper availability test**

Append to `tests/test_app.py`:

```python
def test_legacy_app_exposes_reusable_run_payload_helpers():
    assert callable(web_app._run_response_payload)
    assert callable(web_app._run_history_payload)
    assert callable(web_app._run_detail_payload)
```

- [ ] **Step 2: Run helper test to verify it fails**

Run: `python3 -m pytest tests/test_app.py::test_legacy_app_exposes_reusable_run_payload_helpers -q`

Expected: FAIL with missing helper.

- [ ] **Step 3: Extract create_run response payload helper**

In `eval_agent/app.py`, add:

```python
def _run_response_payload(result, model_config_summary, run_context) -> dict[str, object]:
    return {
        "run_id": result.run_id,
        "trace_count": len(result.traces),
        "result_count": len(result.results),
        "stages": [
            {"name": "指令解析", "status": "completed"},
            {"name": "Rubric 生成", "status": "completed"},
            {"name": "场景生成", "status": "completed"},
            {"name": "多轮对话执行", "status": "completed"},
            {"name": "自动评测", "status": "completed"},
            {"name": "报告生成", "status": "completed"},
        ],
        "task_spec": result.task_spec.model_dump(mode="json"),
        "rubric_spec": result.rubric_spec.model_dump(mode="json"),
        "scenario_set": result.scenario_set.model_dump(mode="json"),
        "input_data_summary": result.input_data_summary,
        "model_config_summary": model_config_summary,
        "run_context": run_context,
        "traces": [trace.model_dump(mode="json") for trace in result.traces],
        "results": [item.model_dump(mode="json") for item in result.results],
        "score_summary": _score_summary(result.results),
        "dimension_summary": _dimension_summary(result.results),
        "scenario_summary": _scenario_summary(result.scenario_set, result.results),
        "failure_summary": _failure_summary(result.results),
        "report": result.report.markdown,
    }
```

Then replace the body of `create_run` after `result = run_full_evaluation(...)` with:

```python
return _run_response_payload(result, model_config_summary, run_context)
```

- [ ] **Step 4: Extract history payload helper**

In `eval_agent/app.py`, add:

```python
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
```

Then replace `run_history()` body with:

```python
return _run_history_payload(RUN_ROOT)
```

- [ ] **Step 5: Extract detail payload helper**

In `eval_agent/app.py`, add:

```python
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
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail="Run artifacts are incomplete") from exc
    return {
        "run_id": run_id,
        "run_config": run_config,
        "task_spec": task_spec,
        "rubric_spec": rubric_spec,
        "scenario_set": scenario_set,
        "input_data_summary": input_data_summary,
        "traces": traces,
        "results": results,
        "score_summary": _score_summary_from_dicts(results),
        "dimension_summary": _dimension_summary_from_dicts(results),
        "scenario_summary": _scenario_summary_from_dicts(scenario_set, results),
        "failure_summary": _failure_summary_from_dicts(results),
        "model_config_summary": run_config.get("model_config_summary", {}),
        "run_context": _context_from_config(run_config),
        "report": report,
    }
```

Then replace `run_detail(run_id)` body with:

```python
return _run_detail_payload(RUN_ROOT, run_id)
```

- [ ] **Step 6: Run helper and run route tests**

Run:

```bash
python3 -m pytest tests/test_app.py::test_legacy_app_exposes_reusable_run_payload_helpers tests/test_backend_scaffold.py::test_production_app_run_routes_create_history_and_detail -q
```

Expected: PASS.

## Task 5: Verification

**Files:**
- No code changes.

- [ ] **Step 1: Run scaffold tests**

Run: `python3 -m pytest tests/test_backend_scaffold.py -q`

Expected: PASS.

- [ ] **Step 2: Run full suite**

Run: `python3 -m pytest -q`

Expected: PASS.

- [ ] **Step 3: Run frontend syntax check**

Run:

```bash
node -e "const fs=require('fs');const html=fs.readFileSync('eval_agent/web/index.html','utf8');const m=html.match(/<script>([\s\S]*)<\/script>/);new Function(m[1]);console.log('script syntax ok')"
```

Expected: `script syntax ok`.
