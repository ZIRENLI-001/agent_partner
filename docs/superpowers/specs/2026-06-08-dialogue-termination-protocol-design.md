# Dialogue Termination Protocol Design

## Goal

Make multi-turn evaluations continue until the simulated user and target model
reach an explicit conversational ending, while preserving the existing model
routing, scenario generation, judging, reporting, async queue, and staged
artifact flow.

The end-to-end and staged evaluation entry points already converge on
`run_full_evaluation()` and `run_dialogue()`. The change therefore belongs in
the shared dialogue execution boundary and its two dialogue prompts.

## Current Problem

`RunConfig.max_turns` defaults to eight individual messages, not eight
assistant-user exchanges. An even message cap can stop immediately after a
user message without an assistant closing response.

The target model can also emit `<DONE>` after its first response. The runner
accepts that marker without requiring any explicit user acknowledgement,
refusal, hang-up, transfer, or inability to continue. Recent traces can
therefore end after only three messages.

The user simulator has no machine-readable way to say that the simulated user
has reached a natural ending.

## Termination Protocol

The target model keeps the existing `<DONE>` marker. The user simulator gains
an `<END_CONVERSATION>` marker.

Both markers are control data and are removed before turns are persisted.

A normal completed dialogue requires this sequence:

1. The user simulator produces a natural final user utterance and appends
   `<END_CONVERSATION>`.
2. The target model produces an appropriate closing response and appends
   `<DONE>`.
3. The runner records `termination_reason="task_completed"`.

The user simulator may emit its marker when the user has:

- clearly acknowledged the completed task;
- definitively refused and does not want further persuasion;
- said they are unavailable or cannot continue;
- identified a wrong person or required transfer;
- ended or hung up the call;
- reached another scenario-appropriate safe terminal state.

The target model prompt must state that `<DONE>` is only valid after an
explicit terminal user signal. An early `<DONE>` is stripped and ignored.

## Turn Budget

The default budget becomes six complete user interaction rounds:

- one opening assistant message;
- up to six user messages;
- up to six assistant responses;
- at most thirteen persisted messages.

`RunConfig.max_turns` remains the persisted compatibility field and defaults
to `13`. Existing callers that provide a custom value continue to work.

A normal completion is not accepted before five persisted messages. This
prevents a first user reply and first target reply from prematurely ending the
evaluation. The maximum-turn budget remains a hard safety fallback and records
`termination_reason="max_turns"`.

If the user signals an ending on the last available user slot, the runner
reserves the final slot for the target model's closing response. It does not
end on a user message when a closing assistant slot is available by design.

## Runner State

`run_dialogue()` owns the protocol state:

- whether the latest user response carried `<END_CONVERSATION>`;
- whether the assistant response carried `<DONE>`;
- whether the minimum message count has been met;
- whether the hard message budget has been reached.

The runner does not infer termination from arbitrary Chinese phrases. Natural
language interpretation stays in the two models, while explicit markers make
execution deterministic and testable.

Malformed output is handled defensively:

- markers are removed wherever they appear in model text;
- an empty user utterance after marker removal receives the existing natural
  fallback;
- an empty assistant utterance after marker removal is persisted as an empty
  response only under existing provider behavior;
- user and assistant markers from the wrong role do not terminate the run.

## Prompt Changes

The target dialogue prompt will:

- explain the user-side `<END_CONVERSATION>` protocol without exposing it in
  natural dialogue;
- require a concise closing response after the user terminal signal;
- forbid `<DONE>` before the user terminal signal;
- preserve all existing task, constraint, FAQ, and safety instructions.

The user simulator prompt will:

- require gradual scenario progression instead of immediate closure;
- require a natural final utterance plus `<END_CONVERSATION>` only when a
  terminal state is genuinely reached;
- forbid emitting the marker on the first user response except for inherently
  terminal scenarios such as wrong number, immediate hang-up, or hard refusal;
- preserve all existing role, domain, identity, and anti-echo constraints.

## Scope Isolation

No API request shape changes are required.

No changes are made to:

- stage model selection or `.env` routing;
- instruction, rubric, or scenario generation;
- confirmed staged artifacts;
- semantic judging and rule evaluation;
- report generation;
- async job submission, polling, quotas, or worker concurrency;
- frontend entry points.

Both end-to-end and staged evaluations receive the behavior because they share
the same engine runner.

## Tests

Tests will verify:

- early assistant `<DONE>` does not terminate;
- user `<END_CONVERSATION>` alone does not terminate before an assistant
  closing response;
- paired user and assistant markers terminate after the minimum length;
- markers do not appear in persisted traces;
- the default budget allows six complete user interaction rounds and cannot
  stop on a user message;
- missing markers still terminate at the hard cap;
- wrong-role markers do not terminate;
- engine entry points continue to call the same runner;
- existing model routing, staged artifact, judge, report, and deployment tests
  remain green.

## Rollout And Verification

Run focused dialogue and prompt tests first, then the complete backend suite and
frontend build. Deploy through the existing release flow, execute one staged
and one end-to-end online evaluation, and inspect their traces for turn count,
clean marker removal, termination reason, and unchanged stage model
diagnostics.
