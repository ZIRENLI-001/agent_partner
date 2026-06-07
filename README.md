# Dialogue Eval Platform

复杂指令下的多轮对话自动评测平台，面向履约数字人外呼场景。当前服务由 FastAPI 提供 API 和 React 静态页面托管，默认监听 `127.0.0.1:8070`。

## Requirements

- Python 3.9+
- Node.js 18+ and npm

## Setup

```bash
make install
```

This installs Python package dependencies from `pyproject.toml` and frontend dependencies with `npm ci`.

## Build

```bash
make build
```

This runs the React production build. FastAPI serves `frontend/dist` when it exists.

## Test

```bash
make test
```

This runs the Python test suite and the frontend TypeScript/Vite build.

## Run

```bash
make dev
```

Equivalent command:

```bash
python3 -m uvicorn backend.eval_agent.api.main:app --host 127.0.0.1 --port 8070
```

Open:

```text
http://127.0.0.1:8070/
```

## Smoke Check

```bash
make smoke
```

This checks the home page and `/api/context` endpoint.

## Configuration

Copy `.env.example` if your shell workflow sources environment files, or export the variables directly.

Important variables:

- `APP_ENV`: set to `production` for public deployment
- `APP_AUTH_REQUIRED`: defaults to `true`; set to `false` only when the deployment is intentionally public
- `APP_ACCESS_TOKEN`: required in production when `APP_AUTH_REQUIRED=true`; shared Bearer token used to protect business APIs
- `ALLOWED_MODEL_API_BASES`: comma-separated exact allowlist for model API base URLs
- `MAX_UPLOAD_BYTES`: maximum uploaded file size, default 10 MiB
- `HOST`: server host for `make dev`
- `PORT`: server port for `make dev`
- `EVAL_ARTIFACT_ROOT`: run artifact directory
- `EVAL_FRONTEND_DIST`: React build directory
- `DEFAULT_PROVIDER_TYPE`: `mock`, `openrouter`, `openai_compatible`, or `internal_gateway`
- `DEFAULT_API_BASE`: OpenAI-compatible API base URL
- `DEFAULT_MODEL_NAME`: fallback model name
- `REQUEST_TIMEOUT_SECONDS`: model provider timeout
- `REQUEST_RETRY_COUNT`: retry count for transient model provider failures
- `REQUEST_RETRY_BACKOFF_SECONDS`: retry backoff interval multiplier
- `EVAL_SCENARIO_CONCURRENCY`: maximum concurrent scenario executions
- `EVAL_SCENARIO_BATCH_SIZE`: scenario batch size for throttling large runs
- `EVAL_MODEL_CACHE_TTL_SECONDS`: cache TTL for backend-owned evaluation-chain model calls; set `0` to disable
- `EVAL_MODEL_CACHE_MAX_ENTRIES`: in-process model call cache size
- `EVAL_REPORT_MAX_EVIDENCE_ITEMS`: maximum evidence items sent to the report model; failures are kept first
- `EVAL_RUN_STATUS_TTL_SECONDS`: Redis or memory run status TTL
- `EVAL_CHAIN_PROVIDER`: backend-owned evaluation-chain provider, usually `openrouter`
- `EVAL_CHAIN_API_BASE`: evaluation-chain API base, usually `https://openrouter.ai/api/v1`
- `EVAL_CHAIN_API_KEY`: evaluation-chain API key; keep this on the server side only
- `EVAL_USER_SIMULATOR_MODEL`: user simulator model, default `openai/gpt-4.1-mini`
- `EVAL_SEMANTIC_JUDGE_MODEL`: semantic judge model, default `anthropic/claude-sonnet-4.6`
- `EVAL_RUBRIC_GENERATOR_MODEL`: rubric generator model, default `anthropic/claude-sonnet-4.6`
- `EVAL_SCENARIO_GENERATOR_MODEL`: scenario generator model, default `google/gemini-2.5-flash`
- `EVAL_REPORT_GENERATOR_MODEL`: report generator model, default `openai/gpt-4.1-mini`
- `EVAL_INSTRUCTION_PARSER_MODEL`: instruction parser fallback model, default `anthropic/claude-sonnet-4.6`

The default `mock` provider is suitable for local demos without network access. OpenRouter and self-hosted model gateways should use an OpenAI-compatible `/chat/completions` API.

Frontend users only configure the target model being evaluated. Evaluation-chain models are controlled by backend environment variables. If `EVAL_CHAIN_API_KEY` is empty, the platform falls back to mock user simulation and heuristic judging so local demos remain runnable.

## Public Beta Safety

For an internet-facing test deployment, configure at least:

```bash
APP_ENV=production
APP_AUTH_REQUIRED=true
APP_ACCESS_TOKEN=<a-long-random-secret>
ALLOWED_MODEL_API_BASES=https://openrouter.ai/api/v1
MAX_UPLOAD_BYTES=10485760
HOST=127.0.0.1
```

Put Nginx or Caddy in front of the service and expose only HTTPS ports `80/443`.
Keep port `8070`, Redis, and any database bound to localhost or a private network.
The frontend asks for `APP_ACCESS_TOKEN` after the first protected API request and
stores it only in the current browser session.

This shared token is suitable for a controlled beta, not full multi-user isolation.
Do not allow untrusted users until per-user authentication, authorization, durable
workers, and database-backed ownership checks are implemented.

For a deliberately anonymous temporary deployment, set
`APP_AUTH_REQUIRED=false`. This makes every business API and shared report
accessible to anyone who discovers or receives the URL. HTTPS, rate limits,
queue limits, upload limits, and model egress restrictions remain enabled.

## Deployment Notes

Do not copy local generated directories between developer machines:

- `frontend/node_modules/`
- `frontend/dist/`
- `runs/run_*/`
- `artifacts/`
- `__pycache__/`
- `.pytest_cache/`

Regenerate dependencies and builds with `make install` and `make build`.

## Temporary Public Beta Deployment

The temporary invited-test deployment is served at
`https://agentpartner.top` using a publicly trusted Let's Encrypt certificate.
`https://www.agentpartner.top` redirects to the canonical root domain.

Business API requests require the shared `APP_ACCESS_TOKEN` when
`APP_AUTH_REQUIRED=true`. When `APP_AUTH_REQUIRED=false`, the site is
intentionally anonymous and the token prompt is not shown. Restore the access
gate by setting the switch back to `true` and restarting the API.
The shared test environment also shares run history and artifacts between
testers; do not submit sensitive production data.

On a fresh Ubuntu 24.04 host, upload a clean source release below
`/srv/agent_partner/releases/`, then run:

```bash
sudo ./deploy/bootstrap-ubuntu.sh
sudo ./deploy/install-release.sh /srv/agent_partner/releases/<release>
```

Nginx is the only public service. FastAPI listens on `127.0.0.1:8070`, Redis
listens on localhost only, and UFW permits only TCP ports 22, 80, and 443.
