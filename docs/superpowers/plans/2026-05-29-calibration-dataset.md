# Calibration Dataset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Meituan fulfillment calibration sample library that validates evaluator reliability without changing the single-dialogue evaluation flow.

**Architecture:** Store curated JSONL samples under `data/calibration`, load and summarize them through a focused backend module, expose read-only API endpoints, and add a frontend page for coverage and sample inspection. The run engine remains unchanged.

**Tech Stack:** Python/FastAPI/Pydantic-style validation, JSONL data asset, React/Vite/Ant Design frontend, pytest scaffold checks.

---

### Task 1: Calibration Data Asset And Loader

**Files:**
- Create: `data/calibration/meituan_fulfillment_calibration.jsonl`
- Create: `eval_agent/calibration_dataset.py`
- Test: `tests/test_calibration_dataset.py`

- [ ] Write tests that require L1-L5 coverage, pass/fail label diversity, evidence turn ids, and Meituan fulfillment risk tags.
- [ ] Add 10-15 curated calibration samples derived from the official Meituan fulfillment instruction style.
- [ ] Implement a loader that validates required fields and returns dataset, coverage summary, difficulty summary, and label summary.
- [ ] Run `python3 -m pytest -q tests/test_calibration_dataset.py`.

### Task 2: Backend API

**Files:**
- Modify: `eval_agent/app.py`
- Create: `backend/eval_agent/services/calibration_service.py`
- Create: `backend/eval_agent/api/routes/calibration.py`
- Modify: `backend/eval_agent/api/main.py`
- Test: `tests/test_app.py`
- Test: `tests/test_backend_scaffold.py`

- [ ] Add `/api/calibration/samples` and `/api/calibration/summary`.
- [ ] Ensure both legacy and production FastAPI entrypoints expose the same contract.
- [ ] Run focused API tests.

### Task 3: Frontend Page

**Files:**
- Create: `frontend/src/api/calibration.ts`
- Create: `frontend/src/pages/CalibrationDatasetPage.tsx`
- Modify: `frontend/src/app/router.tsx`
- Modify: `frontend/src/components/layout/AppLayout.tsx`
- Modify: `frontend/src/styles/globals.css`
- Test: `tests/test_frontend_scaffold.py`

- [ ] Add left-nav entry “校准数据集”.
- [ ] Show summary cards for sample count, difficulty coverage, label diversity, and evidence coverage.
- [ ] Show sample list with expandable dialogue, expected labels, evidence turns, and score band.
- [ ] Keep this page read-only and separate from end-to-end evaluation.
- [ ] Run frontend scaffold tests and Vite build.

### Verification

- [ ] `python3 -m pytest -q tests/test_calibration_dataset.py`
- [ ] `python3 -m pytest -q tests/test_app.py tests/test_backend_scaffold.py tests/test_frontend_scaffold.py`
- [ ] `cd frontend && npm run build`
