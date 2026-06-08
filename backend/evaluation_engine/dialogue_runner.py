from __future__ import annotations

from backend.evaluation_engine.dialogue_protocol import (
    ASSISTANT_DONE_MARKER,
    MIN_TASK_COMPLETION_MESSAGES,
    USER_END_MARKER,
    parse_controlled_text,
)
from backend.evaluation_engine.domain import DialogueTrace, RunConfig, Scenario, TaskSpec, Turn
from backend.evaluation_engine.providers import AssistantProvider, UserProvider
from backend.evaluation_engine.user_simulator import next_user_turn


def run_dialogue(
    task_spec: TaskSpec,
    scenario: Scenario,
    run_config: RunConfig,
    assistant_provider: AssistantProvider,
    user_provider: UserProvider,
) -> DialogueTrace:
    turns = []
    termination_reason = "max_turns"

    opening_content, _ = parse_controlled_text(
        assistant_provider.generate(task_spec, turns),
        expected_marker=ASSISTANT_DONE_MARKER,
    )
    _append_turn(turns, "assistant", opening_content)

    while len(turns) + 2 <= run_config.max_turns:
        user_content, user_ended = parse_controlled_text(
            next_user_turn(user_provider, scenario, turns),
            expected_marker=USER_END_MARKER,
        )
        _append_turn(turns, "user_simulator", user_content)

        assistant_history = turns
        if user_ended:
            terminal_user_turn = turns[-1]
            assistant_history = [
                *turns[:-1],
                Turn(
                    turn_id=terminal_user_turn.turn_id,
                    speaker=terminal_user_turn.speaker,
                    content=terminal_user_turn.content + USER_END_MARKER,
                ),
            ]
        assistant_content, assistant_done = parse_controlled_text(
            assistant_provider.generate(task_spec, assistant_history),
            expected_marker=ASSISTANT_DONE_MARKER,
        )
        _append_turn(turns, "assistant", assistant_content)

        if user_ended:
            termination_reason = (
                "task_completed"
                if assistant_done and len(turns) >= MIN_TASK_COMPLETION_MESSAGES
                else "user_ended"
            )
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
