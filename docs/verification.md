# Verification

- Full pytest suite passes: `42 passed`.
- Sample run creates a multi-scenario run under `runs/{run_id}`.
- Latest verified sample run: `run_766f02cb` with `5` traces and `5` evaluation results.
- Run artifacts include `run_config.json`, `task_spec.json`, `rubric_spec.json`, `scenarios.json`, `traces.jsonl`, `evaluation_results.json`, and `report.md`.
- Run artifacts also include `input_data.json` when evaluation data is provided.
- Report contains quantitative score, scenario coverage matrix, failure summary, recommendations, and structured evidence chains.
- Structured evidence chains include instruction basis, expected behavior, actual dialogue evidence, and judgment explanation.
- Web demo supports a Meituan-style 7-step wizard: model input, data/scenario import, instruction parsing, Rubric generation, scenario selection, trace/result review, and final visual report.
- Stage APIs are available for `/api/stages/parse`, `/api/stages/rubric`, and `/api/stages/scenarios`.
- Run API accepts model configuration and selected scenario IDs, and returns a sanitized `model_config_summary`.
- Final report UI includes quantitative score cards, dimension progress bars, scenario coverage matrix, failure summary, dialogue traces, and evidence chains.
- Production editability controls include upstream invalidation, human calibration notes, current-step regeneration, scenario reselection, and run-only evidence regeneration.
- Production home supports three entry modes: end-to-end quick evaluation, step-by-step custom evaluation, and evaluation history.
- Local run history is exposed through `/api/runs/history` and run details through `/api/runs/{run_id}`.
- Demo data isolation context is exposed through `/api/context` and persisted in `run_config.json`.

## 2026-05-21 Meituan Wizard Frontend

- Command: `python3 -m pytest -v`
- Result: `42 passed`.
- Scope verified:
  - 7-step Meituan-style wizard HTML is served at `/`.
  - Stage endpoints return parse, rubric, and scenario artifacts.
  - Run endpoint accepts model configuration and selected scenario IDs.
  - Visual report contains quantitative summary and explainable evidence chains.
  - Evidence cards show `指令依据`, `预期行为`, `实际对话证据`, and `判定解释`.
  - Production editability controls are exposed for parse, Rubric, scenarios, run rerun, and report review notes.
  - Home mode selection, context endpoint, history endpoint, and detail endpoint are verified.

### Local Smoke Test

- Server command: `python3 -m uvicorn backend.eval_agent.api.main:app --host 127.0.0.1 --port 8070`
- URL: `http://127.0.0.1:8000`
- Latest smoke verification used `http://127.0.0.1:8010` because port `8000` was already occupied by another local service.
- Latest production-editability smoke verification used `http://127.0.0.1:8040`.
- Latest production home/history smoke verification used `http://127.0.0.1:8060`.
- Smoke result: homepage served the Meituan wizard, `/api/sample-tasks` returned 2 examples, `/api/stages/scenarios` returned 5 scenarios, `/api/runs` completed one selected scenario, and evidence fields were present.
- Manual path:
  1. Configure model.
  2. Load Meituan Feimaotui sample.
  3. Parse instruction.
  4. Generate Rubric.
  5. Select scenarios.
  6. Run evaluation.
  7. Review final visual report.
