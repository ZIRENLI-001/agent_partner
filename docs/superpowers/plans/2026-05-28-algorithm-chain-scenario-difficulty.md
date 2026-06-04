# Algorithm Chain Scenario And Difficulty Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve evaluation correctness by expanding task scenarios from the provided Excel/background material, adding difficulty tiers, richer rubrics, and per-stage model/evaluation-standard recommendations.

**Architecture:** Keep the existing deterministic engine and file-backed artifacts. Extend domain models with backward-compatible optional scenario metadata, add a focused strategy module for model selection and standards, and enhance scenario/rubric generation with rule-backed templates for fulfillment and course-publishing tasks.

**Tech Stack:** Python 3.9+, Pydantic v2, pytest, FastAPI service layer.

---

### Task 1: Scenario Metadata

**Files:**
- Modify: `eval_agent/domain.py`
- Test: `tests/test_algorithm_chain.py`

- [x] Write tests asserting generated scenarios expose `difficulty`, `scenario_type`, `expected_behavior`, and `risk_tags`.
- [x] Run `python3 -m pytest tests/test_algorithm_chain.py -q` and confirm failure.
- [x] Add backward-compatible defaults to `Scenario`.
- [x] Re-run the test and confirm pass.

### Task 2: Data-Driven Scenario Expansion

**Files:**
- Modify: `eval_agent/sample_tasks.py`
- Modify: `eval_agent/scenario_generator.py`
- Test: `tests/test_algorithm_chain.py`

- [x] Write tests asserting the Excel sample loads both tasks and fulfillment background tags include order dispatch, rider app, ETA, capacity, route optimization, and intelligent dispatch.
- [x] Write tests asserting fulfillment tasks generate L1-L5 scenarios and course tasks generate interruption/price/third-party configuration scenarios.
- [x] Run the tests and confirm failure.
- [x] Add background metadata constants and richer scenario templates.
- [x] Re-run the tests and confirm pass.

### Task 3: Rubric Dimensions And Risk Standards

**Files:**
- Modify: `eval_agent/rubric_builder.py`
- Test: `tests/test_algorithm_chain.py`

- [x] Write tests asserting rubric dimensions include task completion, process adherence, knowledge accuracy, constraint following, boundary safety, conversation quality, and interruption recovery where applicable.
- [x] Run the tests and confirm failure.
- [x] Add dimension templates and critical high-risk items.
- [x] Re-run the tests and confirm pass.

### Task 4: Stage Model Strategy

**Files:**
- Create: `eval_agent/evaluation_strategy.py`
- Test: `tests/test_algorithm_chain.py`

- [x] Write tests asserting strategy stages include instruction parsing, rubric generation, scenario generation, user simulation, target model, semantic judge, rule judge, and report generation.
- [x] Run the tests and confirm failure.
- [x] Implement deterministic recommendations and evaluation standards for each stage.
- [x] Re-run the tests and confirm pass.

### Task 4.5: Surface Strategy In Service Payloads

**Files:**
- Modify: `backend/eval_agent/services/stage_service.py`
- Modify: `frontend/src/api/stages.ts`
- Test: `tests/test_backend_scaffold.py`

- [x] Add service-level assertions that stage payloads include `evaluation_strategy`.
- [x] Return model-choice and standard recommendations from parse/rubric/scenario stage APIs.
- [x] Add front-end response typing for the optional strategy payload.

### Task 5: Full Verification

**Files:** no new source files.

- [x] Run `python3 -m pytest -q`.
- [x] Run `npm run build` in `frontend/`.
- [x] Restart uvicorn and smoke test `/`, `/api/context`, and a one-scenario run.

---

## Self-Review

- Covers sample data expansion, Meituan fulfillment background, difficulty tiers, rubric standards, and model strategy.
- No placeholder tasks.
- Maintains backward compatibility by using default metadata fields on `Scenario`.
