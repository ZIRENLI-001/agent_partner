# Invited Public Beta Deployment Design

## Goal

Deploy the dialogue evaluation platform on `163.7.11.194` as a temporary,
invitation-only public beta. The deployment must provide encrypted transport,
shared-token access control, bounded resource consumption, durable task
execution, and basic operational recovery without introducing a full user
account system.

## Scope

This design covers:

- Local code hardening before deployment.
- HTTPS termination with an IP-address self-signed certificate.
- Shared bearer-token authentication for invited testers.
- Per-IP request limits and evaluation quotas.
- Durable Redis-backed evaluation jobs.
- File-backed evaluation artifacts with retention and access controls.
- Nginx, systemd, Redis, backup, cleanup, and deployment verification.

This design does not cover:

- Public registration or password-based user accounts.
- Per-user or multi-tenant data isolation.
- Billing or persistent per-user quota accounting.
- PostgreSQL, object storage, or high-availability deployment.
- Browser-trusted TLS certificates. A domain is required for that.

## Deployment Topology

Nginx is the only internet-facing process.

```text
Internet
  |
  | TCP 80/443
  v
Nginx
  |-- HTTP to HTTPS redirect
  |-- self-signed TLS certificate with IP SAN 163.7.11.194
  |-- security headers
  |-- request size limits
  |-- per-IP request limiting
  |
  v
FastAPI API on 127.0.0.1:8070
  |
  |-- shared bearer-token authentication
  |-- request validation
  |-- per-IP evaluation quota
  |-- bounded job submission
  |
  +--> Redis on 127.0.0.1:6379
  |      |-- job queue
  |      |-- job status
  |      |-- quota counters
  |      +-- queue and concurrency accounting
  |
  +--> two evaluation worker processes
  |
  +--> /srv/agent_partner/runs
         +-- evaluation artifacts retained for seven days
```

The FastAPI port, Redis port, and artifact storage are not exposed publicly.
The host firewall permits inbound SSH, HTTP, and HTTPS only.

## Authentication

Production startup requires `APP_ACCESS_TOKEN`. Business API routes require:

```http
Authorization: Bearer <shared-token>
```

`/api/health/live` remains unauthenticated and reports only process liveness.
`/api/health/ready` remains unauthenticated but returns only aggregate
dependency status without paths, credentials, hostnames, or exception text.

The token:

- Is generated as at least 32 random bytes.
- Is stored in the server environment file with mode `0600`.
- Is not embedded in frontend assets, command history, logs, or repository
  files.
- Is entered by invited users and stored in browser session storage.
- Can be rotated by changing the environment file and restarting the API.

The shared token grants access to all beta data. This limitation is displayed
in deployment documentation and is acceptable only for the invited beta.

## API Boundaries

The production API enforces:

- JSON request bodies no larger than 2 MiB.
- Uploaded files no larger than 10 MiB.
- `instruction` no longer than 100,000 characters.
- `input_data` no longer than 1,000,000 characters.
- At most 20 selected scenario IDs.
- Scenario IDs and run IDs restricted to safe identifier formats.
- Model name and API base fields with explicit length limits.
- No synchronous evaluation endpoint in production.

`POST /api/runs` returns `404` or `405` in production. Clients submit work
through `POST /api/runs/async`.

The legacy `backend.evaluation_engine.app:app` entrypoint must not provide an
independent unauthenticated server. It becomes an internal compatibility
module or delegates to the production application. All deployment and
verification documentation uses:

```text
backend.eval_agent.api.main:app
```

## Rate Limits And Quotas

Nginx applies a general per-IP rate limit:

- Sustained rate: 5 requests per second.
- Burst: 10 requests.
- Excess requests receive `429`.

The application applies an evaluation quota:

- 10 submitted evaluation jobs per source IP per rolling hour.
- At most 2 actively running evaluation jobs globally.
- At most 10 queued evaluation jobs globally.
- A full queue returns `503` with a retryable public message.
- An exhausted IP quota returns `429` with `Retry-After`.
- Each evaluation job has a 15-minute execution deadline.

The source IP is accepted from proxy headers only when the direct peer is the
local Nginx proxy. Arbitrary client-supplied forwarding headers are not
trusted.

Redis implements counters with atomic operations and expiration. Production
does not silently fall back to in-memory counters or job status when Redis is
unavailable.

## Job Execution

The in-process `ThreadPoolExecutor` is replaced for production submissions by
a Redis-backed durable queue. Two systemd-managed worker processes consume
jobs.

Submission flow:

1. Authenticate the request.
2. Validate request size and fields.
3. Atomically consume the IP hourly quota.
4. Atomically check and reserve queue capacity.
5. Store a sanitized job payload in Redis.
6. Return `202` with run and status URLs.
7. A worker marks the job running, executes it, persists artifacts, and updates
   final status.

The user-provided target-model API key is needed by the worker. For this
temporary beta, it is stored only in the Redis job payload, Redis is bound to
localhost, persistence is disabled for the job database, and the payload key
expires after the job deadline. API keys are never written to artifacts,
status responses, or logs.

Worker termination or timeout marks the job failed and releases active-job
capacity. Stale reservations are reconciled using expiring Redis leases.

## Model Network Access

Model API bases use an exact configuration allowlist. Production defaults to
HTTPS-only model endpoints. Plain HTTP endpoints require an explicit
development-only override and cannot target loopback, link-local, private, or
cloud metadata addresses unless the server operator explicitly configures an
internal gateway allowlist.

Outbound responses have:

- Connection and read timeout.
- Maximum response body size.
- Bounded retry count and backoff.
- Sanitized provider errors.

Raw task instructions and input data may be sent to configured model
providers. Deployment documentation must warn operators not to submit personal,
confidential, or regulated data unless the provider and data-processing terms
permit it.

## File Import Security

Uploaded spreadsheets are processed with `defusedxml`. ZIP validation enforces:

- Maximum compressed upload size: 10 MiB.
- Maximum expanded size: 50 MiB.
- Maximum single entry size: 20 MiB.
- Maximum archive entry count: 1,000.
- Maximum parsed rows: 10,000.
- Maximum parsed columns: 200.
- No external relationships or paths escaping the `xl` archive subtree.

CSV, JSON, and JSONL parsing also enforce row and field-size limits.

## Artifact Storage

Artifacts live under `/srv/agent_partner/runs`, owned by the dedicated service
account with directory mode `0700`.

All artifact reads and writes:

- Validate `run_id` against `^run_[0-9a-f]{8}$`.
- Resolve paths and verify they remain beneath the configured artifact root.
- Use fixed server-controlled filenames.
- Never persist target-model or evaluation-chain API keys.

Artifacts contain task instructions, summarized input data, generated
scenarios, dialogue traces, evaluation evidence, and reports. The system does
not persist the complete raw `input_data`; previews must avoid exposing values
from JSON objects.

A systemd timer deletes run directories older than seven days. Cleanup refuses
to follow symlinks and operates only under the resolved artifact root. Disk
usage is monitored and deployment reserves sufficient free space.

## Application Security Headers

Nginx adds:

```text
Strict-Transport-Security: max-age=86400
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: no-referrer
Permissions-Policy: camera=(), microphone=(), geolocation=()
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'
```

The temporary one-day HSTS duration avoids long-lived browser pinning to an
IP-address self-signed deployment.

FastAPI enables trusted-host validation for `163.7.11.194` and localhost.
Production disables API documentation and refuses to start if the React
production build is missing. It does not fall back to the legacy inline HTML
page.

## Health, Logging, And Error Handling

Health endpoints are separated:

- Liveness checks only that the API process can respond.
- Readiness verifies Redis connectivity, artifact-root writability, frontend
  build presence, and required production configuration.

Readiness failure returns `503`.

Public API errors use stable messages and request IDs. Internal exception text,
filesystem paths, Redis addresses, model API keys, and provider response bodies
are not returned to clients.

API and worker logs include:

- Timestamp.
- Request or job ID.
- Route or evaluation stage.
- Status and duration.
- Sanitized error category.

Logs exclude authorization headers, model API keys, request bodies, dialogue
contents, and imported data. Journald rotation controls log retention.

## Dependency And Build Controls

Python dependencies are locked to exact versions in a generated lock file.
Frontend installation continues to use `npm ci` and the committed lock file.

Deployment verification includes:

- Full Python test suite.
- Frontend production build.
- `pip-audit` against locked Python dependencies.
- `npm audit --omit=dev` for runtime dependencies.
- Bandit scan with reviewed suppressions only.
- Secret scan over tracked files and Git history.

Vite development or preview servers are never exposed on the production host.

## Server Process Model

The server uses a dedicated unprivileged account, for example
`agent-partner`. Root is used only for package installation and service setup.

Systemd manages:

- `agent-partner-api.service`
- Two instances of `agent-partner-worker@.service`
- `agent-partner-cleanup.timer`

The API listens on `127.0.0.1:8070`. Services use:

- `NoNewPrivileges=true`
- `PrivateTmp=true`
- Restricted writable paths
- Automatic restart on failure
- Environment loaded from a root-owned `0600` file

The deployment directory is `/srv/agent_partner/app`. Releases are uploaded to
a staging directory, dependencies and assets are built, tests and smoke checks
run, and an atomic symlink selects the active release. The previous release is
retained for rollback.

## Nginx And TLS

Nginx:

- Listens on port 80 and redirects to `https://163.7.11.194`.
- Listens on port 443 with TLS 1.2 and 1.3.
- Uses a self-signed certificate whose subject alternative name contains
  `IP:163.7.11.194`.
- Sets `client_max_body_size 10m`.
- Uses separate stricter limiting for evaluation submission.
- Applies upstream connect, send, and read timeouts.
- Proxies only to `127.0.0.1:8070`.

Invited users must manually accept the browser certificate warning. The
certificate does not provide public identity assurance; it only encrypts the
connection after acceptance.

## Deployment Flow

1. Complete and verify code changes locally.
2. Connect with `meituan.pem` to `root@163.7.11.194`.
3. Create the unprivileged service account and deployment directories.
4. Install system packages, Python, Node.js, Nginx, and Redis.
5. Upload a release without `.env`, private keys, caches, local runs, or
   `node_modules`.
6. Install locked Python and frontend dependencies.
7. Build the frontend and run tests and security checks.
8. Generate the shared token and self-signed certificate on the server.
9. Install systemd, cleanup timer, firewall, Redis, and Nginx configuration.
10. Start services and verify local readiness.
11. Verify external HTTPS, authentication, rate limits, quotas, queue capacity,
    task completion, restart recovery, and artifact cleanup.

## Acceptance Criteria

The deployment is accepted when:

- Only ports 22, 80, and 443 are externally reachable.
- HTTP redirects to HTTPS.
- HTTPS uses the expected IP SAN self-signed certificate.
- Missing or invalid bearer tokens receive `401`.
- A valid token can load the frontend and use business APIs.
- The legacy entrypoint cannot expose an unauthenticated API.
- Oversized requests and files are rejected.
- General rate limits and the 10-jobs-per-hour quota return `429`.
- More than 2 jobs remain queued rather than running concurrently.
- An 11th queued job is rejected with `503`.
- Redis loss makes readiness fail and prevents new job submission.
- API restart does not lose queued or completed job status.
- Path traversal attempts cannot read outside the artifact root.
- Model API keys do not appear in responses, artifacts, or logs.
- Production fails to start without a token or frontend build.
- Artifacts older than seven days are removed by the cleanup timer.
- Full tests, frontend build, dependency audits, and security smoke checks pass.

## Known Limitations

- Every invited tester shares one credential and can view all beta reports.
- Browsers show a certificate warning because no domain is available.
- The deployment is single-host and has no high availability.
- File-backed artifacts are suitable for temporary beta data only.
- Per-user authorization and durable user identities are required before
  opening registration or accepting mutually untrusted users.
