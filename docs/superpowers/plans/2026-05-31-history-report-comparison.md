# History Report Comparison Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a stable historical comparison workflow that compares same-scenario performance across models, same-model performance across scenarios, and summarizes real failure reasons.

**Architecture:** Add a dedicated backend comparison payload at `GET /api/runs/comparison`, leaving `/api/runs/history` lightweight. The React history page consumes both history and comparison data, then applies local UI filters without inventing scenario or failure data.

**Tech Stack:** Python FastAPI/TestClient, existing artifact files under run directories, React/Vite/TypeScript, Ant Design tables/selects/progress, pytest, npm typecheck/build.

---

## File Map

- Modify `eval_agent/app.py`: comparison route helper, scenario row extraction, failure reason aggregation, score anomaly handling.
- Modify `backend/eval_agent/api/routes/runs.py`: expose `/api/runs/comparison` from split backend route.
- Modify `backend/eval_agent/services/run_service.py`: delegate comparison payload to legacy app helper, matching existing history/detail patterns.
- Modify `frontend/src/api/runs.ts`: add comparison response interfaces and `getRunComparison()`.
- Modify `frontend/src/pages/RunHistoryPage.tsx`: add comparison query, filters, two comparison modes, failure reason summary.
- Modify `frontend/src/styles/globals.css`: add compact comparison layout styles.
- Modify `tests/test_app.py`: backend comparison endpoint and score anomaly tests.
- Modify `tests/test_frontend_scaffold.py`: frontend scaffold assertions for comparison UI and API client.

## Task 1: Backend Comparison Payload

**Files:**
- Modify: `tests/test_app.py`
- Modify: `eval_agent/app.py`

- [ ] **Step 1: Write failing backend tests**

Add tests near existing history/detail tests:

```python
def test_run_comparison_endpoint_returns_scenario_rows_and_filters(tmp_path: Path, monkeypatch):
    client = TestClient(web_app.app)
    monkeypatch.setattr(web_app, "RUN_ROOT", tmp_path)

    first = client.post(
        "/api/runs",
        json={"instruction": RAW_TASK, "model_config": {"model_name": "model-a"}},
    ).json()
    second = client.post(
        "/api/runs",
        json={"instruction": RAW_TASK, "model_config": {"model_name": "model-b"}},
    ).json()

    response = client.get("/api/runs/comparison")

    assert response.status_code == 200
    data = response.json()
    assert {first["run_id"], second["run_id"]} <= {item["run_id"] for item in data["runs"]}
    assert data["scenario_rows"]
    assert {"model-a", "model-b"} <= set(data["filters"]["model_names"])
    assert data["filters"]["scenario_ids"]
    assert all("raw_pass_rate" in item for item in data["scenario_rows"])
    assert all("score_anomaly" in item for item in data["scenario_rows"])
    assert all(item["pass_rate"] <= 100 for item in data["scenario_rows"])
```

Add a direct anomaly test:

```python
def test_comparison_scenario_row_marks_score_anomaly():
    row = web_app._comparison_scenario_row(
        run_id="run_demo",
        task_name="Demo",
        model_name="model-a",
        updated_at=100,
        result={
            "scenario_id": "scenario_001",
            "total_score": 12,
            "critical_failures": ["missing_confirmation"],
            "evidence": [{"max_score": 10}],
        },
    )

    assert row["raw_pass_rate"] == 120.0
    assert row["pass_rate"] == 100.0
    assert row["score_anomaly"] is True
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest tests/test_app.py::test_run_comparison_endpoint_returns_scenario_rows_and_filters tests/test_app.py::test_comparison_scenario_row_marks_score_anomaly -q
```

Expected: FAIL because route/helper does not exist.

- [ ] **Step 3: Implement minimal backend payload**

In `eval_agent/app.py`:

```python
@app.get("/api/runs/comparison")
def run_comparison() -> dict[str, object]:
    return _run_comparison_payload(RUN_ROOT)
```

Add helpers:

```python
def _run_comparison_payload(run_root: Path) -> dict[str, object]:
    if not run_root.exists():
        return {"runs": [], "scenario_rows": [], "failure_reasons": [], "filters": _comparison_filters([], [])}
    runs: list[dict[str, object]] = []
    rows: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    for run_dir in sorted(run_root.glob("run_*"), key=lambda item: item.stat().st_mtime, reverse=True):
        if not run_dir.is_dir():
            continue
        try:
            run_config = _read_json(run_dir / "run_config.json")
            task_spec = _read_json(run_dir / "task_spec.json")
            results = _read_json(run_dir / "evaluation_results.json")
        except (OSError, json.JSONDecodeError):
            continue
        model_config = run_config.get("model_config_summary", {})
        model_name = model_config.get("model_name", "") if isinstance(model_config, dict) else ""
        run_item = _run_history_item(run_dir)
        runs.append(run_item)
        for result in results:
            if isinstance(result, dict):
                rows.append(_comparison_scenario_row(run_dir.name, str(task_spec.get("task_name", "")), model_name, run_dir.stat().st_mtime, result))
                failures.extend(_comparison_failure_examples(run_dir.name, model_name, result))
    return {
        "runs": runs,
        "scenario_rows": rows,
        "failure_reasons": _aggregate_failure_reasons(failures),
        "filters": _comparison_filters(runs, rows),
    }
```

Keep helpers pure and deterministic:

```python
def _comparison_scenario_row(run_id: str, task_name: str, model_name: str, updated_at: float, result: dict[str, object]) -> dict[str, object]:
    score = float(result.get("total_score", 0) or 0)
    possible = sum(float(item.get("max_score", 0) or 0) for item in result.get("evidence", []) if isinstance(item, dict))
    raw_pass_rate = round(score * 100 / possible, 1) if possible else 0.0
    return {
        "run_id": run_id,
        "task_name": task_name,
        "model_name": model_name,
        "scenario_id": str(result.get("scenario_id", "")),
        "score": score,
        "possible_score": possible,
        "raw_pass_rate": raw_pass_rate,
        "pass_rate": min(100.0, raw_pass_rate),
        "score_anomaly": bool(possible and score > possible),
        "status": "failed" if result.get("critical_failures") else "partial",
        "critical_failure_count": len(result.get("critical_failures", []) or []),
        "updated_at": updated_at,
    }
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
pytest tests/test_app.py::test_run_comparison_endpoint_returns_scenario_rows_and_filters tests/test_app.py::test_comparison_scenario_row_marks_score_anomaly -q
```

Expected: PASS.

## Task 2: Split Backend Route Delegation

**Files:**
- Modify: `backend/eval_agent/services/run_service.py`
- Modify: `backend/eval_agent/api/routes/runs.py`
- Test: `tests/test_service_chain.py`

- [ ] **Step 1: Write failing route test**

Add to `tests/test_service_chain.py`:

```python
def test_service_exposes_run_comparison_payload(tmp_path, monkeypatch):
    from backend.eval_agent.services import run_service

    monkeypatch.setattr(run_service, "artifact_root", lambda: tmp_path)
    client = TestClient(app)

    client.post(
        "/api/runs",
        json={"instruction": "用户要取消订单，需要确认身份和订单号", "model_config": {"model_name": "chain-comparison-model"}},
    )
    response = client.get("/api/runs/comparison")

    assert response.status_code == 200
    assert "scenario_rows" in response.json()
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
pytest tests/test_service_chain.py::test_service_exposes_run_comparison_payload -q
```

Expected: FAIL because split route does not expose comparison.

- [ ] **Step 3: Add service delegation and route**

In `backend/eval_agent/services/run_service.py`:

```python
def run_comparison_payload() -> dict[str, object]:
    return legacy_app._run_comparison_payload(artifact_root())
```

In `backend/eval_agent/api/routes/runs.py`, import and expose:

```python
@router.get("/comparison")
def run_comparison() -> dict[str, object]:
    return run_comparison_payload()
```

- [ ] **Step 4: Run test to verify pass**

Run:

```bash
pytest tests/test_service_chain.py::test_service_exposes_run_comparison_payload -q
```

Expected: PASS.

## Task 3: Frontend API Types and History UI

**Files:**
- Modify: `tests/test_frontend_scaffold.py`
- Modify: `frontend/src/api/runs.ts`
- Modify: `frontend/src/pages/RunHistoryPage.tsx`
- Modify: `frontend/src/styles/globals.css`

- [ ] **Step 1: Write failing frontend scaffold test**

Add:

```python
def test_history_page_supports_filterable_comparison_analysis():
    api = (FRONTEND / "src" / "api" / "runs.ts").read_text(encoding="utf-8")
    page = (FRONTEND / "src" / "pages" / "RunHistoryPage.tsx").read_text(encoding="utf-8")
    styles = (FRONTEND / "src" / "styles" / "globals.css").read_text(encoding="utf-8")

    assert "RunComparisonResponse" in api
    assert "getRunComparison" in api
    assert 'request<RunComparisonResponse>("/api/runs/comparison")' in api
    assert "同一场景不同模型" in page
    assert "同一模型不同场景" in page
    assert "失败原因汇总" in page
    assert "comparisonMode" in page
    assert "selectedScenarioId" in page
    assert "selectedModelName" in page
    assert "score_anomaly" in page
    assert ".history-comparison-panel" in styles
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
pytest tests/test_frontend_scaffold.py::test_history_page_supports_filterable_comparison_analysis -q
```

Expected: FAIL because API/UI does not exist.

- [ ] **Step 3: Add frontend API types**

In `frontend/src/api/runs.ts`, add interfaces:

```ts
export interface ComparisonScenarioRow {
  run_id: string;
  task_name: string;
  model_name: string;
  scenario_id: string;
  score: number;
  possible_score: number;
  raw_pass_rate: number;
  pass_rate: number;
  score_anomaly: boolean;
  status: string;
  critical_failure_count: number;
  updated_at: number;
}

export interface FailureReasonExample {
  run_id: string;
  scenario_id: string;
  model_name: string;
  reason: string;
  rubric_item_id: string;
}

export interface FailureReasonSummary {
  key: string;
  label: string;
  count: number;
  scenario_ids: string[];
  model_names: string[];
  run_ids: string[];
  examples: FailureReasonExample[];
}

export interface RunComparisonResponse {
  runs: RunSummary[];
  scenario_rows: ComparisonScenarioRow[];
  failure_reasons: FailureReasonSummary[];
  filters: {
    model_names: string[];
    scenario_ids: string[];
    task_names: string[];
  };
}
```

Add:

```ts
export function getRunComparison() {
  return request<RunComparisonResponse>("/api/runs/comparison");
}
```

- [ ] **Step 4: Add history comparison UI**

In `RunHistoryPage.tsx`:

- Import `Select`, `Segmented`, `Tag`, and comparison types.
- Fetch `getRunComparison` via React Query.
- Add `comparisonMode`, `selectedScenarioId`, `selectedModelName` state.
- Use strict filters:
  - Same scenario mode: `row.scenario_id === selectedScenarioId`.
  - Same model mode: `row.model_name === selectedModelName`.
- Render a comparison table with run link, model, scenario, score, pass rate, anomaly tag, critical failure count.
- Render failure reason summary by keeping reasons whose examples overlap the visible rows.

- [ ] **Step 5: Add styles**

Add compact styles:

```css
.history-comparison-panel {
  display: grid;
  gap: 12px;
  margin-bottom: 14px;
}

.history-comparison-toolbar {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) minmax(220px, 1fr) auto;
  gap: 10px;
  align-items: center;
}

.failure-reason-list {
  display: grid;
  gap: 8px;
}
```

- [ ] **Step 6: Run frontend checks**

Run:

```bash
pytest tests/test_frontend_scaffold.py::test_history_page_supports_filterable_comparison_analysis -q
npm run typecheck
npm run build
```

Expected: all pass. Build may keep the existing chunk-size warning.

## Task 4: End-to-End Verification and Restart

**Files:**
- No source edits unless verification reveals a defect.

- [ ] **Step 1: Run focused backend and frontend tests**

Run:

```bash
pytest tests/test_app.py tests/test_service_chain.py tests/test_frontend_scaffold.py -q
```

Expected: PASS.

- [ ] **Step 2: Start or restart backend/frontend**

Use the existing commands:

```bash
python3 -m uvicorn backend.eval_agent.api.main:app --host 127.0.0.1 --port 8070
cd frontend && npm run dev
```

Expected:

- Backend listens on `127.0.0.1:8070`.
- Frontend serves `http://localhost:5173/`.

- [ ] **Step 3: Verify comparison endpoint through backend and proxy**

Run:

```bash
curl -s http://127.0.0.1:8070/api/runs/comparison
curl -s http://127.0.0.1:5173/api/runs/comparison
```

Expected:

- Both return JSON with `runs`, `scenario_rows`, `failure_reasons`, and `filters`.
- `scenario_rows[*].pass_rate` is never above 100.
- Any row with `raw_pass_rate > 100` has `score_anomaly: true`.

## Self-Review

- Spec coverage: dedicated comparison endpoint, strict scenario/model matching, failure reason summary, anomaly handling, UI filters, and tests are covered.
- Placeholder scan: no deferred implementation placeholders remain.
- Type consistency: backend uses `scenario_rows`, `failure_reasons`, `raw_pass_rate`, `score_anomaly`; frontend types and tests use the same names.
- Repository note: this directory is not a git repository, so commit steps are replaced by verification steps.
