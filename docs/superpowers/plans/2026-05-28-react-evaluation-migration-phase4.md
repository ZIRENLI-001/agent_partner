# React Evaluation Migration Phase 4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the core evaluation workflow from the legacy static MVP into the React frontend.

**Architecture:** Keep the backend API unchanged. Implement the React evaluation page as a controlled, step-oriented workflow that calls existing stage and run APIs, stores generated results in local component state, and renders concise structured summaries with expandable JSON/evidence details.

**Tech Stack:** React, TypeScript, Ant Design, TanStack Query, existing FastAPI APIs.

---

## File Structure

- Modify `frontend/src/pages/EvaluationWizardPage.tsx`: replace placeholder with functional model/data input, stage generation, run execution, and report summary.
- Modify `frontend/src/api/stages.ts`: strengthen response types for scenario summaries.
- Modify `frontend/src/api/runs.ts`: strengthen run response fields used by report rendering.
- Modify `frontend/src/styles/globals.css`: add form, step result, report, trace styles.
- Modify `tests/test_frontend_scaffold.py`: add static tests for functional evaluation workflow terms and API usage.

## Task 1: Static Test For Functional Evaluation Workflow

**Files:**
- Modify: `tests/test_frontend_scaffold.py`

Steps:
- [ ] Add a test asserting the React evaluation page contains controlled input labels, generate buttons, next-step control, API function calls, and report rendering terms.
- [ ] Run `python3 -m pytest tests/test_frontend_scaffold.py::test_react_evaluation_page_contains_functional_workflow -q`.
- [ ] Expected failure: missing workflow terms in `EvaluationWizardPage.tsx`.

## Task 2: Implement React Evaluation Workflow

**Files:**
- Modify: `frontend/src/pages/EvaluationWizardPage.tsx`

Steps:
- [ ] Add state for active step, instruction, input data, model config, selected scenario IDs, and generated outputs.
- [ ] Add handlers for parse, rubric, scenarios, run, and report stage.
- [ ] Render current step result after clicking “生成”.
- [ ] Keep “下一步” separate from “生成”, matching the corrected UX requirement.
- [ ] Ensure upstream input edits reset downstream generated outputs.

## Task 3: Improve Types And Report Rendering

**Files:**
- Modify: `frontend/src/api/runs.ts`
- Modify: `frontend/src/api/stages.ts`

Steps:
- [ ] Add minimal typed fields for scenarios, traces, evidence, score summary, dimension summary, and failure summary.
- [ ] Keep unknown fallback fields for backend compatibility.

## Task 4: Add Styles

**Files:**
- Modify: `frontend/src/styles/globals.css`

Steps:
- [ ] Add grid form styles, result cards, code blocks, compact evidence list, and responsive behavior.

## Task 5: Verification

Steps:
- [ ] Run `python3 -m pytest tests/test_frontend_scaffold.py -q`.
- [ ] Run `cd frontend && npm run build`.
- [ ] Run `python3 -m pytest -q`.
- [ ] Restart or reuse `http://127.0.0.1:8071/` and smoke test React routes.
