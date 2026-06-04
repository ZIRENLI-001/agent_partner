from __future__ import annotations

from backend.evaluation_engine.domain import DialogueTrace, RunConfig, Scenario, TaskSpec, Turn
from backend.evaluation_engine.providers import AssistantProvider, UserProvider
from backend.evaluation_engine.user_simulator import next_user_turn


DONE_MARKER = "<DONE>"


def run_dialogue(
    task_spec: TaskSpec,
    scenario: Scenario,
    run_config: RunConfig,
    assistant_provider: AssistantProvider,
    user_provider: UserProvider,
) -> DialogueTrace:
    turns = []
    termination_reason = "max_turns"

    _append_turn(turns, "assistant", assistant_provider.generate(task_spec, turns))

    while len(turns) < run_config.max_turns:
        user_content = next_user_turn(user_provider, scenario, turns)
        _append_turn(turns, "user_simulator", user_content)

        if len(turns) >= run_config.max_turns:
            break

        assistant_content = assistant_provider.generate(task_spec, turns).strip()
        if DONE_MARKER in assistant_content:
            assistant_content = assistant_content.replace(DONE_MARKER, "").strip()
            termination_reason = "task_completed"
        _append_turn(turns, "assistant", assistant_content)

        if termination_reason == "task_completed":
            break

    return DialogueTrace(
        trace_id="trace_%s_%s" % (run_config.run_id, scenario.scenario_id),
        run_id=run_config.run_id,
        task_id=task_spec.task_id,
        scenario_id=scenario.scenario_id,
        turns=turns,
        termination_reason=termination_reason,
    )


def _append_turn(turns: list[Turn], speaker: str, content: str) -> None:
    turns.append(
        Turn(
            turn_id=len(turns) + 1,
            speaker=speaker,
            content=content.strip(),
        )
    )
