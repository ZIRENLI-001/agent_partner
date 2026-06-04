# Production Home And History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a production-oriented landing workbench with end-to-end quick evaluation, step-by-step custom evaluation, and file-backed evaluation history with user/workspace/project isolation placeholders.

**Architecture:** Keep the current FastAPI and file-backed `runs/` storage. Add small metadata fields to run creation, expose history/detail APIs from persisted artifacts, and extend the existing vanilla HTML/JS UI with a home screen and quick-run/history views while preserving the current 7-step wizard as the custom mode.

**Tech Stack:** FastAPI, Pydantic, pathlib/json file storage, vanilla HTML/CSS/JavaScript, pytest.

---

## Task 1: Backend Context And History APIs

**Files:**
- Modify: `eval_agent/app.py`
- Modify: `eval_agent/engine.py`
- Test: `tests/test_app.py`

Steps:
- Add `RunContext` fields: `workspace_id`, `project_id`, `created_by`, with defaults `workspace_demo`, `project_meituan_fulfillment`, `demo_user`.
- Extend `/api/runs` request and persisted `run_config.json` with context fields.
- Add `GET /api/context` returning current demo user/workspace/project.
- Add `GET /api/runs/history` reading `runs/run_*/run_config.json`, `task_spec.json`, `evaluation_results.json`, and `report.md`, sorted newest first.
- Add `GET /api/runs/{run_id}` returning persisted details for one run.
- Add tests for context, history, detail, and context persistence.

## Task 2: Home Screen And Mode Selection

**Files:**
- Modify: `eval_agent/web/index.html`
- Test: `tests/test_app.py`

Steps:
- Add a home screen before the wizard with three entry cards:
  - 端到端快速评测
  - 按步骤自定义评测
  - 评测历史
- Keep the existing 7-step wizard available behind the custom mode.
- Add current demo user/workspace/project display in the topbar.
- Add tests asserting the home screen and production terms are present.

## Task 3: Quick End-To-End Evaluation

**Files:**
- Modify: `eval_agent/web/index.html`

Steps:
- Add a quick-run view with model config, task instruction, input data, and sample loading.
- Quick-run `生成` calls `/api/runs` once and renders the same report components already used by the wizard.
- Add a “进入按步骤自定义” action for users who need calibration.

## Task 4: Evaluation History UI

**Files:**
- Modify: `eval_agent/web/index.html`

Steps:
- Add history view loading `/api/runs/history`.
- Show run id, task name, model, score, scenario count, created by, workspace, project, and updated time.
- Allow opening one run detail via `/api/runs/{run_id}` and render the visual report.

## Task 5: Verification

**Files:**
- Modify: `docs/verification.md`

Steps:
- Run `python3 -m pytest -v`.
- Start local uvicorn on a fresh port.
- Smoke test homepage, quick-run, history API, and run detail API.
- Update verification notes.

