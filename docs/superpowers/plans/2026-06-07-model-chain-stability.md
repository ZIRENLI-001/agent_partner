# Model Chain Stability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every evaluation stage reliably call its `.env`-configured model and prompt, recover from malformed structured output, and persist proof of actual model invocations.

**Architecture:** Keep model selection in `backend_stage_model_config()` unchanged. Add bounded recovery inside the model adapters, preserve model-first behavior during report quality repair, and expose sanitized call diagnostics from adapters to the evaluation engine.

**Tech Stack:** Python 3.12, dataclasses, FastAPI, Pydantic, pytest, OpenRouter OpenAI-compatible API, Redis workers.

---

### Task 1: Scenario JSON Recovery

**Files:**
- Modify: `backend/eval_agent/services/run_service.py`
- Test: `tests/test_model_chain_boundaries.py`

- [ ] **Step 1: Write the failing test**

Add a sequential recording provider that returns truncated JSON on the first
call and a valid `ScenarioSet` payload on the second. Assert:

```python
assert len(model.calls) == 2
assert scenarios.scenarios[0].scenario_id == "model_repaired"
assert model.calls[1]["config"].temperature == 0
assert model.calls[1]["config"].max_tokens >= 6000
assert adapter.model_call_diagnostic()["prompt_ids"] == {
    "scenario_generator_v1": 1,
    "scenario_generator_json_repair_v1": 1,
}
assert adapter.model_call_diagnostic()["retry_count"] == 1
```

- [ ] **Step 2: Run the test to verify RED**

Run:

```powershell
python -m pytest tests/test_model_chain_boundaries.py::test_scenario_adapter_retries_malformed_json_with_same_model -q
```

Expected: failure because the adapter currently makes one call and raises
`JSONDecodeError`.

- [ ] **Step 3: Implement one bounded repair call**

Use `dataclasses.replace()` to derive a retry config with temperature `0`,
cache disabled, and at least `6000` max tokens. Reuse the original messages,
append the invalid assistant response and a JSON-only repair instruction, then
parse the second response.

- [ ] **Step 4: Run the test to verify GREEN**

Run the same targeted pytest command. Expected: `1 passed`.

### Task 2: Report Model Quality Repair

**Files:**
- Modify: `backend/eval_agent/services/run_service.py`
- Modify: `backend/evaluation_engine/engine.py`
- Test: `tests/test_engine.py`
- Test: `tests/test_model_chain_boundaries.py`

- [ ] **Step 1: Write failing report tests**

Add assertions that the report prompt contains the exact required headings:

```python
assert "## 量化结果" in report_prompt
assert "## 证据链" in report_prompt
```

Replace the always-broken report provider in the auto-repair test with a
provider that returns an invalid report once and a valid report on its second
call. Assert:

```python
assert provider.call_count == 2
assert run.stage_diagnostics["report_generation"]["output_source"] == "model"
assert run.stage_diagnostics["report_generation"]["fallback_used"] is False
```

Add a separate always-broken case asserting two model calls occur before the
template fallback and that diagnostics retain `model_attempted=true`.

- [ ] **Step 2: Run the tests to verify RED**

Run:

```powershell
python -m pytest tests/test_engine.py::test_run_full_evaluation_auto_repairs_failed_quality_gate_once tests/test_engine.py::test_report_auto_repair_falls_back_only_after_second_invalid_model_report tests/test_model_chain_boundaries.py::test_report_prompt_requires_quality_gate_headings -q
```

Expected: failures because auto-repair passes `report_provider=None` and the
prompt does not require exact headings.

- [ ] **Step 3: Preserve the report provider during auto-repair**

Pass `report_provider` into `_auto_repair_quality_once()`. Retry with that
provider. If the rebuilt quality summary still reports missing report sections,
write the template report and record a model-attempted fallback reason.

- [ ] **Step 4: Strengthen the report prompt**

Require the exact quality-gate headings in the system and user prompts without
changing locked metric handling.

- [ ] **Step 5: Run the tests to verify GREEN**

Run the targeted command. Expected: all selected tests pass.

### Task 3: Sanitized Model and Prompt Diagnostics

**Files:**
- Modify: `backend/eval_agent/services/run_service.py`
- Modify: `backend/evaluation_engine/engine.py`
- Test: `tests/test_multi_role_model_routing.py`
- Test: `tests/test_model_chain_boundaries.py`

- [ ] **Step 1: Write failing diagnostics tests**

Exercise parser, rubric, scenario, assistant, user simulator, semantic judge,
and report adapters. Assert diagnostics expose:

```python
{
    "provider": "openrouter",
    "model_name": "...",
    "prompt_ids": {"role_prompt_v1": 1},
    "model_call_count": 1,
    "retry_count": 0,
}
```

Assert serialized diagnostics contain no API key.

- [ ] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/test_multi_role_model_routing.py tests/test_model_chain_boundaries.py -q
```

Expected: diagnostics assertions fail because adapters do not track calls.

- [ ] **Step 3: Implement a thread-safe adapter call tracker**

Add a private tracker using `threading.Lock`. Record stable prompt IDs before
each `model_provider.generate()` call. Expose a `model_call_diagnostic()` method
from each real adapter.

- [ ] **Step 4: Attach diagnostics in the engine**

Before artifacts are persisted, merge adapter summaries into the corresponding
stage diagnostics. Ignore fake/local providers that do not expose diagnostics.

- [ ] **Step 5: Run tests to verify GREEN**

Run the same targeted pytest command. Expected: all tests pass.

### Task 4: Local Verification and Commit

**Files:**
- Verify all modified files

- [ ] **Step 1: Run focused tests**

```powershell
python -m pytest tests/test_model_chain_boundaries.py tests/test_multi_role_model_routing.py tests/test_engine.py tests/test_public_beta_security.py tests/test_job_queue.py -q
```

- [ ] **Step 2: Run the full backend suite**

```powershell
python -m pytest -q
```

Expected: zero failures.

- [ ] **Step 3: Run frontend production build**

```powershell
Set-Location frontend
npm run build
```

Expected: Vite exits with code `0`.

- [ ] **Step 4: Check the diff**

```powershell
git diff --check
git status --short
```

Expected: no whitespace errors and only intended files modified.

- [ ] **Step 5: Commit**

```powershell
git add backend tests docs/superpowers
git commit -m "fix: stabilize configured model chain"
```

### Task 5: Deploy and Verify the Development Machine

**Files:**
- Deploy committed release to `163.7.11.194`

- [ ] **Step 1: Build a clean git archive**

Create an archive from `HEAD` and verify it excludes `.env`, `.git`,
`node_modules`, and `dist`.

- [ ] **Step 2: Upload and install**

Upload with the existing SSH key and run:

```bash
bash <release>/deploy/install-release.sh <release>
```

The server's `/etc/agent-partner/agent-partner.env` remains authoritative and
must not be overwritten.

- [ ] **Step 3: Verify services**

Check `agent-partner-api`, `agent-partner-worker@1`,
`agent-partner-worker@2`, `nginx`, and `redis-server` are active. Verify:

```bash
curl -fsS https://agentpartner.top/api/health
```

- [ ] **Step 4: Submit a real evaluation**

Submit one minimum-scenario run using target model
`openai/gpt-4.1-mini`, poll until completion, and inspect:

```text
stage_model_config_summary
stage_diagnostics
stage_timings_ms
quality_summary
```

- [ ] **Step 5: Enforce production acceptance criteria**

The run is accepted only when:

```text
instruction_parser.model_call.model_call_count > 0
rubric_generator.model_call.model_call_count > 0
scenario_generator.model_call.model_call_count > 0
target_model.model_call_count > 0
user_simulator.model_call_count > 0
semantic_judge.model_call_count > 0
report_generator.model_call.model_call_count > 0
all prompt IDs match their role
no unexpected fallback is present
```

If a fallback occurs, inspect its exact reason, add a regression test, and
repeat the RED/GREEN/deploy cycle.
