# Model Chain Stability Design

## Goal

Ensure every evaluation role uses the model configured in `.env`, sends the
role-specific prompt, records proof of the invocation, and only falls back to
local behavior after bounded model recovery fails.

## Confirmed Production Failures

1. The HTTP transport passed `timeout_seconds` as positional request data.
   This caused every model call to fail before network I/O. Commit `fac5a9e`
   fixed that transport bug.
2. The scenario generator can return truncated or malformed JSON. The current
   adapter immediately falls back to local scenarios instead of asking the
   configured scenario model to regenerate valid JSON.
3. A model-generated report that misses exact quality-gate headings triggers
   auto-repair. Auto-repair currently calls the template writer with
   `report_provider=None`, discarding the configured report model and masking
   the first model attempt in diagnostics.
4. Existing artifacts declare configured models but do not prove which prompt
   was invoked or how many model calls occurred.

## Design

### Structured Scenario Recovery

The scenario adapter makes the normal call with prompt
`scenario_generator_v1`. If JSON parsing fails, it performs one bounded retry
with the same configured model, temperature `0`, cache disabled, and at least
`6000` output tokens. The retry conversation includes the original generation
messages, the invalid assistant output, and a correction prompt identified as
`scenario_generator_json_repair_v1`.

If the retry is also invalid, the existing engine-level local scenario fallback
remains active. No unbounded retry loop is introduced.

### Report Quality Recovery

The report prompt explicitly requires the exact headings used by the quality
gate, including `## 量化结果` and `## 证据链`.

When report integrity still fails, auto-repair invokes the configured report
provider again with the same report prompt. If the second model result still
misses required sections, the engine writes the deterministic template report
and records that a model retry was attempted before fallback.

### Invocation Diagnostics

Each model-backed adapter records:

- configured provider and model name;
- prompt IDs used;
- total adapter model-call count;
- retry count.

The engine attaches these summaries to:

- `instruction_parsing.model_call`;
- `rubric_generation.model_call`;
- `scenario_generation.model_call`;
- `scenario_execution.model_calls.target_model`;
- `scenario_execution.model_calls.user_simulator`;
- `scenario_execution.model_calls.semantic_judge`;
- `report_generation.model_call`.

Diagnostics contain no API keys or raw prompts. Prompt IDs are stable,
versioned identifiers that allow artifacts and tests to prove routing without
persisting sensitive input content.

## Error Handling

- Network/provider failures retain existing retry and fallback behavior.
- Scenario JSON recovery runs once.
- Report quality recovery runs once.
- Local fallback remains the final safety mechanism and must set
  `fallback_used=true`, preserve `model_attempted=true`, and provide a safe
  fallback reason.
- Model-call diagnostics must survive later auto-repair updates.

## Verification

1. Unit tests prove malformed scenario JSON triggers one model repair call.
2. Unit tests prove report auto-repair reuses the report provider before
   template fallback.
3. Unit tests prove all seven roles publish model and prompt diagnostics.
4. Full backend tests and frontend production build pass.
5. A production run on `https://agentpartner.top` completes with the models
   configured in `.env`.
6. The production artifact shows non-zero calls for all seven roles, expected
   prompt IDs, no unexpected fallback, and plausible stage durations.

