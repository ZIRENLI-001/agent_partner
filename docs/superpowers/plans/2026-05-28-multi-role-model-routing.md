# Multi Role Model Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-stage model configuration so the target model, user simulator, semantic judge, and future chain models can each use OpenRouter or another OpenAI-compatible API.

**Architecture:** Keep the existing deterministic engine as the fallback path. Add a typed stage-model configuration layer in the backend service, route target/user/judge providers independently, and expose safe summaries to the UI and persisted run artifacts. Frontend changes are limited to the model configuration step.

**Tech Stack:** Python 3.9+, FastAPI, Pydantic v2, pytest, React + TypeScript + Vite.

---

### Task 1: Backend Stage Model Config Contract

**Files:**
- Modify: `backend/eval_agent/api/routes/runs.py`
- Modify: `backend/eval_agent/services/run_service.py`
- Test: `tests/test_multi_role_model_routing.py`

- [x] **Step 1: Write failing tests for stage model request parsing and safe summary.**

Create tests that post both legacy `model_config` and new `stage_model_config` payloads. Assert that API keys never appear in responses or persisted `run_config.json`, and that summary fields include target, user simulator, semantic judge, and report roles.

- [x] **Step 2: Run the focused tests and confirm failure.**

Run: `python3 -m pytest tests/test_multi_role_model_routing.py -q`

- [x] **Step 3: Add request models.**

Add `StageModelConfig` with optional `target_model`, `user_simulator`, `semantic_judge`, `report_generator`, `rubric_generator`, `scenario_generator`, and `instruction_parser` fields. Keep `model_config` as legacy alias for `target_model`.

- [x] **Step 4: Add safe summary helpers.**

Summaries must include provider, model name, api base, judge mode, and `api_key_configured`, but never the key itself.

- [x] **Step 5: Run focused tests.**

Run: `python3 -m pytest tests/test_multi_role_model_routing.py -q`

### Task 2: Provider Adapters For User Simulator And Semantic Judge

**Files:**
- Modify: `backend/eval_agent/services/run_service.py`
- Modify: `eval_agent/providers.py`
- Modify: `eval_agent/judge_evaluator.py`
- Test: `tests/test_multi_role_model_routing.py`

- [x] **Step 1: Write failing tests for per-role provider routing.**

Use a recording `ModelProvider` to assert target, user simulator, and semantic judge calls use their own model names and prompts.

- [x] **Step 2: Run the tests and confirm failure.**

Run: `python3 -m pytest tests/test_multi_role_model_routing.py -q`

- [x] **Step 3: Implement `UserModelAdapter`.**

Generate user simulator turns from the scenario card and dialogue history. The adapter must return plain user text, stripping `<DONE>` if a model emits it.

- [x] **Step 4: Implement semantic judge provider injection.**

Keep the existing heuristic judge when no semantic judge model is configured. When configured, call the model with one rubric item at a time and parse conservative JSON: `verdict`, `score`, `reason`, `turn_ids`, `explanation`.

- [x] **Step 5: Run focused tests.**

Run: `python3 -m pytest tests/test_multi_role_model_routing.py -q`

### Task 3: Engine Wiring And Artifact Persistence

**Files:**
- Modify: `eval_agent/engine.py`
- Modify: `backend/eval_agent/services/run_service.py`
- Test: `tests/test_multi_role_model_routing.py`

- [x] **Step 1: Write failing tests for persisted multi-role summaries.**

Assert `run_config.json` includes `stage_model_config_summary` and existing `model_config_summary` remains present for compatibility.

- [x] **Step 2: Run the tests and confirm failure.**

Run: `python3 -m pytest tests/test_multi_role_model_routing.py -q`

- [x] **Step 3: Thread optional `judge_provider` through `run_full_evaluation`.**

Default behavior must remain unchanged when no judge provider is passed.

- [x] **Step 4: Persist summaries.**

Store `stage_model_config_summary` in `run_config.json` and include it in create/detail API responses.

- [x] **Step 5: Run focused tests.**

Run: `python3 -m pytest tests/test_multi_role_model_routing.py -q`

### Task 4: Frontend Multi Role Model Form

**Files:**
- Modify: `frontend/src/api/runs.ts`
- Modify: `frontend/src/pages/EvaluationWizardPage.tsx`
- Test: `tests/test_frontend_scaffold.py`

- [x] **Step 1: Write static scaffold tests.**

Assert frontend source includes `stage_model_config`, `被测模型`, `用户模拟模型`, and `语义裁判模型`.

- [x] **Step 2: Run the test and confirm failure.**

Run: `python3 -m pytest tests/test_frontend_scaffold.py -q`

- [x] **Step 3: Update TypeScript request types.**

Add `StageModelConfig` and optional `stage_model_config` to `RunRequest`.

- [x] **Step 4: Replace single model form with multi-role fields.**

Keep target model visible first. Add compact controls for user simulator and semantic judge. Default optional roles to mock/heuristic unless explicitly set.

- [x] **Step 5: Send `stage_model_config` in `createRun`.**

Preserve `model_config` for legacy target model compatibility.

- [x] **Step 6: Run frontend scaffold tests.**

Run: `python3 -m pytest tests/test_frontend_scaffold.py -q`

### Task 5: Verification

**Files:** no new source files.

- [x] **Step 1: Run backend tests.**

Run: `python3 -m pytest -q`

- [x] **Step 2: Run frontend build.**

Run: `npm run build` in `frontend/`.

- [x] **Step 3: Restart 8070 and smoke test.**

Start: `python3 -m uvicorn backend.eval_agent.api.main:app --host 127.0.0.1 --port 8070`

Smoke:
- `GET /` returns 200.
- `POST /api/runs` with `stage_model_config.target_model.provider=openrouter` uses the real-model path when a key is supplied.
- Response summaries do not contain API keys.

---

## Self-Review

- Covers target/user/judge/report role configuration and preserves legacy `model_config`.
- Keeps mock and heuristic defaults for low-cost demos.
- Avoids adding live network tests; provider routing is tested with injected recording providers.
- No placeholders or unresolved model names are required by the plan.
