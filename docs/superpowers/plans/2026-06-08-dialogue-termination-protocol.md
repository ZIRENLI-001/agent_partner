# Dialogue Termination Protocol Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give end-to-end and staged evaluations up to eight complete interaction rounds while ending deterministically on explicit user and target-model control signals.

**Architecture:** Add a small dialogue protocol module that owns control markers and sanitization. Keep `run_dialogue()` as the single state machine used by both evaluation entry points, update only the target and user-simulator prompts, and preserve all existing model routing, judging, reporting, queue, and frontend contracts.

**Tech Stack:** Python 3.13, Pydantic, pytest, FastAPI, existing OpenAI-compatible model adapters

---

## File Structure

- Create `backend/evaluation_engine/dialogue_protocol.py`: marker constants, minimum completion length, and role-aware marker parsing.
- Modify `backend/evaluation_engine/domain.py`: default `RunConfig.max_turns` to 17 messages.
- Modify `backend/evaluation_engine/dialogue_runner.py`: enforce the shared explicit termination state machine.
- Modify `backend/evaluation_engine/user_simulator.py`: validate natural user text while preserving the user control marker.
- Modify `backend/evaluation_engine/providers.py`: make fake providers exercise a realistic five-message completed dialogue.
- Modify `backend/eval_agent/services/run_service.py`: document the protocol in target and user-simulator prompts.
- Modify `tests/test_dialogue_runner.py`: unit coverage for early markers, terminal users, hard caps, sanitization, and eight rounds.
- Modify `tests/test_prompt_quality.py`: prompt contract coverage.
- Modify `tests/test_engine.py`: prove generated and confirmed-artifact evaluations share the protocol.

### Task 1: Add The Dialogue Protocol Primitive

**Files:**
- Create: `backend/evaluation_engine/dialogue_protocol.py`
- Modify: `backend/evaluation_engine/domain.py`
- Test: `tests/test_dialogue_runner.py`

- [ ] **Step 1: Write failing protocol and default-budget tests**

Add imports and tests:

```python
from backend.evaluation_engine.dialogue_protocol import (
    ASSISTANT_DONE_MARKER,
    USER_END_MARKER,
    parse_controlled_text,
)


def test_run_config_defaults_to_eight_complete_interaction_rounds():
    config = RunConfig(run_id="run_default", task_id="task_001")
    assert config.max_turns == 17


def test_parse_controlled_text_strips_both_markers_but_only_accepts_expected_role():
    content, signaled = parse_controlled_text(
        "好的，先这样。<END_CONVERSATION><DONE>",
        expected_marker=USER_END_MARKER,
    )
    assert content == "好的，先这样。"
    assert signaled is True

    content, signaled = parse_controlled_text(
        "好的。<END_CONVERSATION>",
        expected_marker=ASSISTANT_DONE_MARKER,
    )
    assert content == "好的。"
    assert signaled is False
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m pytest -q tests/test_dialogue_runner.py -k "defaults_to_eight or parse_controlled"
```

Expected: collection/import failure because `dialogue_protocol.py` does not exist, or assertion failure because the default is still 8.

- [ ] **Step 3: Implement the protocol module and new default**

Create:

```python
from __future__ import annotations

ASSISTANT_DONE_MARKER = "<DONE>"
USER_END_MARKER = "<END_CONVERSATION>"
MIN_TASK_COMPLETION_MESSAGES = 5
CONTROL_MARKERS = (ASSISTANT_DONE_MARKER, USER_END_MARKER)


def parse_controlled_text(
    content: str,
    *,
    expected_marker: str,
) -> tuple[str, bool]:
    signaled = expected_marker in content
    cleaned = content
    for marker in CONTROL_MARKERS:
        cleaned = cleaned.replace(marker, "")
    return cleaned.strip(), signaled
```

Change:

```python
class RunConfig(BaseModel):
    ...
    max_turns: int = 17
```

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```powershell
python -m pytest -q tests/test_dialogue_runner.py -k "defaults_to_eight or parse_controlled"
```

Expected: selected tests pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/evaluation_engine/dialogue_protocol.py backend/evaluation_engine/domain.py tests/test_dialogue_runner.py
git commit -m "feat: define dialogue termination protocol"
```

### Task 2: Enforce Explicit Termination In The Shared Runner

**Files:**
- Modify: `backend/evaluation_engine/dialogue_runner.py`
- Test: `tests/test_dialogue_runner.py`

- [ ] **Step 1: Write failing state-machine tests**

Add deterministic sequence providers and tests covering:

```python
class SequenceAssistant:
    def __init__(self, replies):
        self.replies = iter(replies)

    def generate(self, task_spec, history):
        return next(self.replies)


class SequenceUser:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.calls = 0

    def generate(self, scenario, history):
        self.calls += 1
        return next(self.replies)


def test_early_assistant_done_is_ignored_until_user_signals_end():
    user = SequenceUser(["我还没说完。", "好的，先这样。<END_CONVERSATION>"])
    trace = run_dialogue(
        _task(),
        _scenario(),
        RunConfig(run_id="run_early", task_id="task_001", max_turns=9),
        SequenceAssistant(
            [
                "您好。",
                "我先说明一下。<DONE>",
                "好的，再见。<DONE>",
            ]
        ),
        user,
    )
    assert len(trace.turns) == 5
    assert trace.termination_reason == "task_completed"
    assert user.calls == 2
    assert all("<" not in turn.content for turn in trace.turns)


def test_terminal_user_gets_one_closing_response_without_another_user_turn():
    user = SequenceUser(["不用再联系了。<END_CONVERSATION>"])
    trace = run_dialogue(
        _task(),
        _scenario(),
        RunConfig(run_id="run_hangup", task_id="task_001", max_turns=17),
        SequenceAssistant(["您好。", "明白，后续不再打扰。"]),
        user,
    )
    assert [turn.speaker for turn in trace.turns] == [
        "assistant",
        "user_simulator",
        "assistant",
    ]
    assert trace.termination_reason == "user_ended"
    assert user.calls == 1


def test_default_budget_allows_eight_complete_rounds_and_ends_on_assistant():
    user = SequenceUser(["还需要说明。"] * 8)
    assistant = SequenceAssistant(["您好。"] + ["继续说明。"] * 8)
    trace = run_dialogue(
        _task(),
        _scenario(),
        RunConfig(run_id="run_budget", task_id="task_001"),
        assistant,
        user,
    )
    assert len(trace.turns) == 17
    assert trace.turns[-1].speaker == "assistant"
    assert trace.termination_reason == "max_turns"
```

Also add a wrong-role-marker test where the user emits `<DONE>` and assistant
emits `<END_CONVERSATION>`; both markers must be stripped and neither may
complete the dialogue.

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m pytest -q tests/test_dialogue_runner.py -k "early_assistant or terminal_user or default_budget or wrong_role"
```

Expected: failures because the current runner accepts early `<DONE>`, lacks the user marker, and can stop on a user message.

- [ ] **Step 3: Implement the minimal runner state machine**

Use `parse_controlled_text()` for opening, user, and assistant outputs. Ignore
an opening or early assistant `<DONE>`. Only append a user turn when two message
slots remain:

```python
while len(turns) + 2 <= run_config.max_turns:
    raw_user = next_user_turn(user_provider, scenario, turns)
    user_content, user_ended = parse_controlled_text(
        raw_user,
        expected_marker=USER_END_MARKER,
    )
    _append_turn(turns, "user_simulator", user_content)

    raw_assistant = assistant_provider.generate(task_spec, turns)
    assistant_content, assistant_done = parse_controlled_text(
        raw_assistant,
        expected_marker=ASSISTANT_DONE_MARKER,
    )
    _append_turn(turns, "assistant", assistant_content)

    if user_ended:
        if assistant_done and len(turns) >= MIN_TASK_COMPLETION_MESSAGES:
            termination_reason = "task_completed"
        else:
            termination_reason = "user_ended"
        break
```

Opening output must also pass through marker sanitization, with its signal
ignored.

- [ ] **Step 4: Run the full runner tests**

Run:

```powershell
python -m pytest -q tests/test_dialogue_runner.py
```

Expected: all runner tests pass. Update old tests that expected a first-response
`<DONE>` to complete; their expected reason is now `max_turns` unless the user
also sends `<END_CONVERSATION>`.

- [ ] **Step 5: Commit**

```powershell
git add backend/evaluation_engine/dialogue_runner.py tests/test_dialogue_runner.py
git commit -m "feat: require explicit dialogue termination"
```

### Task 3: Preserve Natural User Text And Update Fake Providers

**Files:**
- Modify: `backend/evaluation_engine/user_simulator.py`
- Modify: `backend/evaluation_engine/providers.py`
- Test: `tests/test_dialogue_runner.py`

- [ ] **Step 1: Write failing user normalization tests**

Add:

```python
def test_next_user_turn_preserves_end_marker_after_validating_natural_text():
    class EndingUser:
        def generate(self, scenario, history):
            return "好的，我知道了。<END_CONVERSATION>"

    result = next_user_turn(EndingUser(), _scenario(), [])
    assert result == "好的，我知道了。<END_CONVERSATION>"


def test_marker_only_user_output_uses_natural_fallback_and_keeps_end_signal():
    class MarkerOnlyUser:
        def generate(self, scenario, history):
            return "<END_CONVERSATION>"

    result = next_user_turn(MarkerOnlyUser(), _scenario(), [])
    assert result.endswith("<END_CONVERSATION>")
    assert result != "<END_CONVERSATION>"
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m pytest -q tests/test_dialogue_runner.py -k "preserves_end_marker or marker_only"
```

Expected: marker-only output is currently accepted without a natural utterance.

- [ ] **Step 3: Normalize before validation and preserve the signal**

In `next_user_turn()`:

```python
raw_content = provider.generate(scenario, history).strip()
content, user_ended = parse_controlled_text(
    raw_content,
    expected_marker=USER_END_MARKER,
)
if not content or not is_valid_user_turn(content, scenario, history):
    content = _fallback_user_turn(scenario, history)
suffix = USER_END_MARKER if user_ended else ""
return f"{content}{suffix}"
```

Update `FakeUserProvider.generate()` so the first user response remains open and
the second user response is natural text ending in `<END_CONVERSATION>`.
`FakeAssistantProvider` keeps `<DONE>`; the runner will ignore its first early
marker and accept the second after the user signal.

- [ ] **Step 4: Run runner and provider tests**

Run:

```powershell
python -m pytest -q tests/test_dialogue_runner.py tests/test_deployment_readiness.py tests/test_multi_role_model_routing.py
```

Expected: all selected tests pass and fake evaluations complete in five
messages instead of three.

- [ ] **Step 5: Commit**

```powershell
git add backend/evaluation_engine/user_simulator.py backend/evaluation_engine/providers.py tests/test_dialogue_runner.py
git commit -m "fix: normalize terminal user responses"
```

### Task 4: Teach Both Dialogue Models The Protocol

**Files:**
- Modify: `backend/eval_agent/services/run_service.py`
- Modify: `tests/test_prompt_quality.py`

- [ ] **Step 1: Write failing prompt contract tests**

Extend the execution and simulator prompt tests:

```python
assert "<END_CONVERSATION>" in content
assert "用户明确结束" in content
assert "不得提前输出 <DONE>" in content
```

For the simulator:

```python
assert "<END_CONVERSATION>" in simulator
assert "真实结束状态" in simulator
assert "继续推进" in simulator
assert "第一句" in simulator
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m pytest -q tests/test_prompt_quality.py -k "dialogue_simulation or execution_prompt"
```

Expected: prompt assertions fail because the protocol is absent.

- [ ] **Step 3: Add narrowly scoped prompt instructions**

Append to `_system_message()`:

```text
只有当最近一条 user_simulator 回复包含 <END_CONVERSATION> 时，才可在自然收尾回复后追加 <DONE>。
在用户仍有疑问、仍在补充信息或尚未明确结束时，不得提前输出 <DONE>，应继续推进 required_steps。
控制标记不得作为口头内容解释给用户。
```

Append to `_user_simulator_system_message()`:

```text
按场景逐步回应，不要为了缩短评测而提前结束。
只有达到真实结束状态时，才在自然用户话语末尾追加 <END_CONVERSATION>。
除错号、立即挂断、明确拒绝继续等天然终局外，第一句用户回复不得追加结束标记。
```

Do not alter model names, provider configuration, temperature, token limits, or
prompt IDs.

- [ ] **Step 4: Run prompt and routing tests**

Run:

```powershell
python -m pytest -q tests/test_prompt_quality.py tests/test_multi_role_model_routing.py tests/test_model_chain_boundaries.py
```

Expected: all selected tests pass and prompt IDs remain
`target_dialogue_v1`/`user_simulator_v1`.

- [ ] **Step 5: Commit**

```powershell
git add backend/eval_agent/services/run_service.py tests/test_prompt_quality.py
git commit -m "feat: prompt explicit conversation endings"
```

### Task 5: Prove Both Evaluation Entry Paths Share The Behavior

**Files:**
- Modify: `tests/test_engine.py`

- [ ] **Step 1: Add failing generated and confirmed-artifact integration tests**

Create deterministic providers that produce:

- opening assistant text;
- first user response without a marker;
- early assistant `<DONE>`;
- second user response with `<END_CONVERSATION>`;
- final assistant `<DONE>`.

Call `run_full_evaluation()` once with generated artifacts and once with
`confirmed_task_spec`, `confirmed_rubric_spec`, and `confirmed_scenario_set`.
Assert for both:

```python
assert len(run.traces[0].turns) == 5
assert run.traces[0].termination_reason == "task_completed"
assert all(
    "<DONE>" not in turn.content and "<END_CONVERSATION>" not in turn.content
    for turn in run.traces[0].turns
)
```

Also assert confirmed-stage diagnostics remain
`output_source="confirmed_stage_artifact"` so the staged fix is not regressed.

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m pytest -q tests/test_engine.py -k "termination_protocol"
```

Expected: tests fail under the old early-`<DONE>` behavior.

- [ ] **Step 3: Make only compatibility adjustments required by integration**

Do not add a second runner or entry-point-specific condition. If integration
reveals a mismatch, thread data through the existing `RunConfig` and
`run_dialogue()` call only.

- [ ] **Step 4: Run engine and service-chain tests**

Run:

```powershell
python -m pytest -q tests/test_engine.py tests/test_service_chain.py tests/test_chain_regression_batch.py
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit**

```powershell
git add tests/test_engine.py
git commit -m "test: cover dialogue termination across entry paths"
```

### Task 6: Full Verification, Deployment, And Online Acceptance

**Files:**
- No additional source files expected.

- [ ] **Step 1: Run the complete backend suite**

```powershell
python -m pytest -q
```

Expected: zero failures.

- [ ] **Step 2: Build the frontend to prove unchanged contracts**

```powershell
npm run build
```

Run from `frontend/`. Expected: successful Vite production build.

- [ ] **Step 3: Review the final diff**

```powershell
git diff --check
git status --short
git log --oneline -8
```

Expected: no whitespace errors and only intended files changed.

- [ ] **Step 4: Deploy through the existing release process**

Create a clean release excluding `.env`, keys, caches, local runs,
`node_modules`, and `.git`. Install it under
`/srv/agent_partner/releases/<timestamp>-<sha>`, activate the symlink, and
confirm Nginx, API, Redis, and both workers are active.

- [ ] **Step 5: Run two online acceptance evaluations**

Submit:

1. one quick/end-to-end evaluation without confirmed artifacts;
2. one staged evaluation with confirmed task, rubric, and scenario artifacts.

For each completed run, inspect `traces`, `run_config`, and
`stage_diagnostics`. Verify:

- `max_turns` is 17;
- normal completion contains at least five messages;
- no control marker is persisted;
- the final turn is from `assistant`;
- termination is `task_completed`, `user_ended`, or `max_turns` according to
  the actual transcript;
- staged artifacts remain confirmed and no parse/rubric/scenario regeneration
  occurs in the final staged run;
- target, user, judge, and report model diagnostics still use their configured
  model and prompt IDs.

- [ ] **Step 6: Push and verify GitHub**

```powershell
git push origin feature/invited-public-beta
git ls-remote origin refs/heads/feature/invited-public-beta
```

Expected: remote SHA equals local `HEAD`.
