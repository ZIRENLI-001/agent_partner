# Developer Machine Deployment Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the evaluation platform predictable to install, build, configure, and run on another developer machine.

**Architecture:** Keep the current FastAPI + React/Vite architecture. Move deployment-sensitive paths behind configuration helpers, keep defaults local-friendly, and document a single root-level startup flow. Preserve the mock model path for demos while allowing OpenRouter/OpenAI-compatible model calls through the existing provider abstraction.

**Tech Stack:** Python 3.9+, FastAPI, Pydantic v2, pytest, uvicorn, React 18, TypeScript, Vite, npm.

---

### Task 1: Deployment Documentation And Entrypoints

**Files:**
- Create: `README.md`
- Create: `.env.example`
- Create: `Makefile`
- Modify: `frontend/README.md`
- Test: `tests/test_deployment_readiness.py`

- [ ] **Step 1: Write failing documentation tests**

Add `tests/test_deployment_readiness.py` with tests that assert root deployment files exist and contain exact install, build, run, and smoke commands.

- [ ] **Step 2: Run the new tests**

Run: `python3 -m pytest tests/test_deployment_readiness.py -q`

Expected: fail because `README.md`, `.env.example`, and `Makefile` do not exist yet.

- [ ] **Step 3: Add root deployment files**

Create:
- `README.md` with Python and frontend setup, `make install`, `make build`, `make test`, `make dev`, and `make smoke`.
- `.env.example` with `APP_ENV`, `HOST`, `PORT`, `EVAL_ARTIFACT_ROOT`, `EVAL_FRONTEND_DIST`, `DEFAULT_PROVIDER_TYPE`, `DEFAULT_API_BASE`, `DEFAULT_MODEL_NAME`, and `REQUEST_TIMEOUT_SECONDS`.
- `Makefile` with deterministic root-level commands.

- [ ] **Step 4: Update frontend README**

Replace the outdated statement that the runnable MVP is still `eval_agent/web/index.html`. Document that React is the primary frontend and `eval_agent/web/index.html` is a legacy fallback.

- [ ] **Step 5: Verify**

Run: `python3 -m pytest tests/test_deployment_readiness.py -q`

Expected: pass.

### Task 2: Configuration And Path Resolution

**Files:**
- Modify: `backend/eval_agent/core/config.py`
- Modify: `backend/eval_agent/api/main.py`
- Modify: `backend/eval_agent/services/run_service.py`
- Test: `tests/test_deployment_readiness.py`

- [ ] **Step 1: Write failing path tests**

Add tests that assert:
- `settings_from_env()` reads env vars.
- frontend dist is resolved relative to the project root, not the shell working directory.
- run artifacts use configured `EVAL_ARTIFACT_ROOT`.

- [ ] **Step 2: Run tests**

Run: `python3 -m pytest tests/test_deployment_readiness.py -q`

Expected: fail because current code uses `Path("frontend/dist")` and `Path("runs")`.

- [ ] **Step 3: Implement config helpers**

Add `project_root()`, `resolve_project_path()`, and `settings_from_env()` in `backend/eval_agent/core/config.py`.

- [ ] **Step 4: Use config in API and run service**

Use `settings_from_env().frontend_dist` in `backend/eval_agent/api/main.py`.
Use `settings_from_env().artifact_root` in `backend/eval_agent/services/run_service.py`.

- [ ] **Step 5: Verify**

Run: `python3 -m pytest tests/test_deployment_readiness.py tests/test_backend_scaffold.py tests/test_frontend_scaffold.py -q`

Expected: pass.

### Task 3: Real Model Provider Selection

**Files:**
- Modify: `backend/eval_agent/services/run_service.py`
- Test: `tests/test_deployment_readiness.py`

- [ ] **Step 1: Write failing provider tests**

Add tests that assert:
- mock provider keeps the existing `FakeAssistantProvider`.
- `openrouter`, `openai_compatible`, and `internal_gateway` create an assistant adapter backed by `OpenAICompatibleProvider`.
- the assistant adapter converts dialogue history to chat messages and includes task instruction context.

- [ ] **Step 2: Run tests**

Run: `python3 -m pytest tests/test_deployment_readiness.py -q`

Expected: fail because run service always uses `FakeAssistantProvider`.

- [ ] **Step 3: Implement provider adapter**

Add an `AssistantModelAdapter` in `run_service.py` that implements the legacy `AssistantProvider.generate(task_spec, history)` protocol by calling `OpenAICompatibleProvider.generate(messages, ModelConfig(...))`.

- [ ] **Step 4: Use provider selection in run creation**

Use fake providers only when provider is empty or `mock`. Use the adapter for OpenAI-compatible provider types.

- [ ] **Step 5: Verify**

Run: `python3 -m pytest tests/test_deployment_readiness.py tests/test_production_readiness.py tests/test_service_chain.py -q`

Expected: pass.

### Task 4: Full Verification

**Files:**
- No new source files.

- [ ] **Step 1: Backend tests**

Run: `python3 -m pytest -q`

Expected: all tests pass.

- [ ] **Step 2: Frontend build**

Run: `npm run build` in `frontend/`

Expected: build passes; Vite chunk-size warning is acceptable for now.

- [ ] **Step 3: Service smoke**

Run: `python3 -m uvicorn backend.eval_agent.api.main:app --host 127.0.0.1 --port 8070`

In another shell, run:
- `curl -s -o /tmp/dialogue-eval-home.html -w "%{http_code}" http://127.0.0.1:8070/`
- `curl -s http://127.0.0.1:8070/api/context`

Expected: page returns `200`; API returns JSON context.

---

## Self-Review

- Spec coverage: covers deployment docs, env config, path resolution, model provider selection, and verification.
- Placeholder scan: no deferred TODO or TBD tasks.
- Type consistency: provider types match frontend request payload names and backend `ModelConfig` usage.
