# Invited Public Beta Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the application for an invitation-only public beta and deploy it to Ubuntu 24.04 at `163.7.11.194` behind self-signed HTTPS.

**Architecture:** Keep FastAPI, React, Redis, and file-backed artifacts. Add strict production middleware, bounded Redis-backed job submission, dedicated worker processes, safe artifact/import boundaries, and reproducible Nginx/systemd deployment assets. Nginx is the only public service; FastAPI and Redis remain bound to localhost.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, Redis, pytest, React 18, TypeScript, Vite, Nginx, systemd, OpenSSL, UFW.

---

## File Structure

- `backend/eval_agent/core/config.py`: production settings and numeric limits.
- `backend/eval_agent/core/security.py`: authentication, trusted proxy IP extraction, request-size checks, and public security headers.
- `backend/eval_agent/api/main.py`: production startup validation and route exposure.
- `backend/eval_agent/api/routes/health.py`: liveness and readiness endpoints.
- `backend/eval_agent/api/routes/runs.py`: bounded request models and production sync-route policy.
- `backend/eval_agent/services/health_service.py`: dependency readiness checks.
- `backend/eval_agent/services/job_queue.py`: Redis quota, bounded queue, payload TTL, leases, and reconciliation.
- `backend/eval_agent/services/run_service.py`: queue submission and reusable queued-run execution.
- `backend/eval_agent/worker.py`: long-running Redis worker entrypoint.
- `backend/eval_agent/storage/artifact_store.py`: canonical artifact path validation.
- `backend/evaluation_engine/app.py`: safe run-detail lookup and compatibility-only legacy app.
- `backend/evaluation_engine/storage.py`: use the canonical artifact path boundary.
- `backend/eval_agent/services/import_service.py`: safe XML and bounded tabular parsing.
- `backend/eval_agent/providers/openai_compatible.py`: HTTPS policy and bounded response reads.
- `scripts/cleanup_artifacts.py`: seven-day safe artifact cleanup.
- `deploy/nginx/agent-partner.conf`: TLS proxy, limits, and headers.
- `deploy/systemd/*.service`, `deploy/systemd/*.timer`: API, workers, and cleanup.
- `deploy/redis/agent-partner.conf`: localhost-only, non-persistent job Redis.
- `deploy/bootstrap-ubuntu.sh`: one-time Ubuntu 24.04 host setup.
- `deploy/install-release.sh`: repeatable release installation and rollback-ready activation.
- `tests/test_public_beta_security.py`: API and production-boundary tests.
- `tests/test_job_queue.py`: quota, queue, leases, and worker tests.
- `tests/test_import_service.py`: malicious and oversized import tests.
- `tests/test_deployment_assets.py`: deployment file contract tests.

### Task 1: Production Settings And Request Validation

**Files:**
- Modify: `backend/eval_agent/core/config.py`
- Modify: `backend/eval_agent/api/routes/runs.py`
- Modify: `.env.example`
- Test: `tests/test_public_beta_security.py`

- [ ] **Step 1: Write failing settings and request-model tests**

Add tests that require production defaults and bounded fields:

```python
def test_public_beta_settings_are_loaded(monkeypatch):
    monkeypatch.setenv("MAX_JSON_BODY_BYTES", "2097152")
    monkeypatch.setenv("RUNS_PER_IP_PER_HOUR", "10")
    monkeypatch.setenv("MAX_QUEUED_RUNS", "10")
    monkeypatch.setenv("RUN_JOB_TIMEOUT_SECONDS", "900")
    settings = settings_from_env()
    assert settings.max_json_body_bytes == 2 * 1024 * 1024
    assert settings.runs_per_ip_per_hour == 10
    assert settings.max_queued_runs == 10
    assert settings.run_job_timeout_seconds == 900


def test_run_request_rejects_oversized_fields():
    with pytest.raises(ValidationError):
        RunRequest(instruction="x" * 100_001)
    with pytest.raises(ValidationError):
        RunRequest(instruction="ok", input_data="x" * 1_000_001)
    with pytest.raises(ValidationError):
        RunRequest(
            instruction="ok",
            selected_scenario_ids=["scenario_%d" % i for i in range(21)],
        )
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/test_public_beta_security.py -q
```

Expected: fail because the settings and length constraints do not exist.

- [ ] **Step 3: Add settings and Pydantic constraints**

Add these settings and environment mappings:

```python
max_json_body_bytes: int = 2 * 1024 * 1024
runs_per_ip_per_hour: int = 10
max_queued_runs: int = 10
run_job_timeout_seconds: int = 900
trusted_hosts: tuple[str, ...] = ("127.0.0.1", "localhost")
trusted_proxy_ips: tuple[str, ...] = ("127.0.0.1", "::1")
model_response_max_bytes: int = 10 * 1024 * 1024
artifact_retention_days: int = 7
```

Use `StringConstraints` or `Field` to enforce:

```python
instruction: str = Field(min_length=1, max_length=100_000)
input_data: str = Field(default="", max_length=1_000_000)
selected_scenario_ids: list[str] = Field(default_factory=list, max_length=20)
model_name: str = Field(default="", max_length=256)
api_base: str = Field(default="", max_length=2048)
api_key: str = Field(default="", max_length=4096)
```

Document exact values in `.env.example`.

- [ ] **Step 4: Verify GREEN**

Run:

```powershell
python -m pytest tests/test_public_beta_security.py tests/test_production_readiness.py -q
```

Expected: pass.

### Task 2: Canonical Artifact Path Boundary

**Files:**
- Modify: `backend/eval_agent/storage/artifact_store.py`
- Modify: `backend/evaluation_engine/storage.py`
- Modify: `backend/evaluation_engine/app.py`
- Test: `tests/test_public_beta_security.py`

- [ ] **Step 1: Write a failing traversal regression test**

```python
def test_run_detail_rejects_windows_and_posix_path_traversal(tmp_path):
    outside = tmp_path / "run_deadbeef"
    outside.mkdir()
    (outside / "run_config.json").write_text("{}", encoding="utf-8")
    nested = tmp_path / "nested"
    nested.mkdir()

    for run_id in ("../run_deadbeef", r"..\run_deadbeef", "run_deadbeef/extra"):
        with pytest.raises(HTTPException) as exc:
            _run_detail_payload(nested, run_id)
        assert exc.value.status_code == 404
```

Also test that only `run_[0-9a-f]{8}` is accepted.

- [ ] **Step 2: Run the traversal test to verify RED**

Run:

```powershell
python -m pytest tests/test_public_beta_security.py::test_run_detail_rejects_windows_and_posix_path_traversal -q
```

Expected: fail because `..\run_deadbeef` escapes on Windows.

- [ ] **Step 3: Implement one canonical path helper**

Add:

```python
RUN_ID_PATTERN = re.compile(r"^run_[0-9a-f]{8}$")


def safe_run_dir(root: str | Path, run_id: str, *, create: bool = False) -> Path:
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise ValueError("Invalid run_id")
    resolved_root = Path(root).resolve()
    candidate = (resolved_root / run_id).resolve()
    if candidate.parent != resolved_root:
        raise ValueError("Invalid run_id")
    if create:
        candidate.mkdir(parents=True, exist_ok=True)
    return candidate
```

Use it from both artifact stores and translate invalid public lookups to `404`.

- [ ] **Step 4: Verify artifact and run-detail tests**

Run:

```powershell
python -m pytest tests/test_public_beta_security.py tests/test_production_readiness.py tests/test_app.py -q
```

Expected: pass.

### Task 3: Production Middleware, Startup Gates, And Legacy Entrypoint

**Files:**
- Modify: `backend/eval_agent/core/security.py`
- Modify: `backend/eval_agent/api/main.py`
- Modify: `backend/evaluation_engine/app.py`
- Modify: `docs/verification.md`
- Test: `tests/test_public_beta_security.py`

- [ ] **Step 1: Write failing production-boundary tests**

Tests must assert:

```python
def test_production_rejects_large_json_before_route(monkeypatch):
    configure_production(monkeypatch)
    client = TestClient(create_app())
    response = client.post(
        "/api/stages/parse",
        content=b"x" * (2 * 1024 * 1024 + 1),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer shared-test-token",
        },
    )
    assert response.status_code == 413


def test_production_disables_sync_run(monkeypatch):
    configure_production(monkeypatch)
    response = authorized_client(create_app()).post(
        "/api/runs",
        json={"instruction": "test"},
    )
    assert response.status_code in {404, 405}


def test_production_requires_frontend_build(monkeypatch, tmp_path):
    configure_production(monkeypatch)
    monkeypatch.setenv("EVAL_FRONTEND_DIST", str(tmp_path / "missing"))
    with pytest.raises(RuntimeError, match="frontend"):
        create_app()


def test_legacy_app_uses_production_security(monkeypatch):
    configure_production(monkeypatch)
    from backend.evaluation_engine.app import app
    assert TestClient(app).get("/api/context").status_code == 401
```

Also assert `TrustedHostMiddleware` rejects an unknown Host and security headers
appear in production responses.

- [ ] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/test_public_beta_security.py -q
```

Expected: failures for body size, sync route, frontend gate, legacy entrypoint,
trusted hosts, and headers.

- [ ] **Step 3: Implement middleware and startup validation**

Implement:

- A request-body middleware that checks `Content-Length` and streams no more
  than `MAX_JSON_BODY_BYTES` for JSON requests.
- Trusted host validation using configured hosts.
- Request IDs and stable public `500` responses.
- Security response headers.
- Production sync-run rejection.
- Production startup failure when token, Redis, or frontend build is missing.

Keep `/api/health/live` and `/api/health/ready` outside token authentication.

Make `backend.evaluation_engine.app:app` import or construct the secured
production app rather than exposing its old independent routes. Preserve helper
functions used by production services and tests.

Update all verification commands to use:

```text
backend.eval_agent.api.main:app
```

- [ ] **Step 4: Verify security and compatibility tests**

Run:

```powershell
python -m pytest tests/test_public_beta_security.py tests/test_backend_scaffold.py tests/test_app.py -q
```

Expected: pass.

### Task 4: Liveness And Production Readiness

**Files:**
- Modify: `backend/eval_agent/api/routes/health.py`
- Modify: `backend/eval_agent/services/health_service.py`
- Test: `tests/test_public_beta_security.py`

- [ ] **Step 1: Write failing health tests**

```python
def test_liveness_contains_no_dependency_details():
    response = TestClient(create_app()).get("/api/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_production_readiness_fails_when_redis_is_unavailable(monkeypatch):
    configure_production(monkeypatch)
    monkeypatch.setattr(health_service, "redis_ready", lambda settings: False)
    response = TestClient(create_app()).get("/api/health/ready")
    assert response.status_code == 503
    assert response.json()["checks"]["redis"] == "unavailable"
```

Also require checks for artifact-root writability and frontend presence without
returning local paths.

- [ ] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/test_public_beta_security.py -k "liveness or readiness" -q
```

Expected: fail because split endpoints and Redis readiness do not exist.

- [ ] **Step 3: Implement split health endpoints**

Return `200` for liveness. Return `200` or `503` for readiness based on:

- production token configuration;
- Redis `PING`;
- artifact root creation and temporary write/delete;
- production frontend build.

Do not return exception strings or paths.

- [ ] **Step 4: Verify health tests**

Run:

```powershell
python -m pytest tests/test_public_beta_security.py tests/test_production_readiness.py -q
```

Expected: pass.

### Task 5: Safe And Bounded File Imports

**Files:**
- Modify: `backend/eval_agent/services/import_service.py`
- Modify: `pyproject.toml`
- Test: `tests/test_import_service.py`

- [ ] **Step 1: Write failing archive and tabular-limit tests**

Add tests for:

- More than 1,000 ZIP entries.
- Workbook relationship target `../../outside.xml`.
- More than 10,000 CSV rows.
- More than 200 spreadsheet columns.
- XML containing a DTD/entity declaration.

Example:

```python
def test_xlsx_rejects_relationship_target_outside_xl():
    content = build_xlsx_with_relationship("../../outside.xml")
    with pytest.raises(ValueError, match="relationship"):
        parse_evaluation_rows("unsafe.xlsx", content)


def test_csv_rejects_too_many_rows():
    content = ("instruction\n" + "hello\n" * 10_001).encode()
    with pytest.raises(ValueError, match="rows"):
        parse_evaluation_rows("large.csv", content)
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/test_import_service.py -q
```

Expected: new tests fail.

- [ ] **Step 3: Add `defusedxml` and parser bounds**

Use:

```python
from defusedxml import ElementTree
```

Add constants:

```python
MAX_XLSX_ENTRIES = 1_000
MAX_IMPORT_ROWS = 10_000
MAX_IMPORT_COLUMNS = 200
MAX_IMPORT_FIELD_CHARS = 1_000_000
```

Normalize relationship targets with `PurePosixPath`, reject absolute targets,
`..`, external relationships, and paths outside `xl/`.

- [ ] **Step 4: Verify import tests and Bandit findings**

Run:

```powershell
python -m pytest tests/test_import_service.py -q
uvx bandit -r backend/eval_agent/services/import_service.py -ll -iii
```

Expected: tests pass and no medium XML finding remains.

### Task 6: Redis Quota And Bounded Durable Queue

**Files:**
- Create: `backend/eval_agent/services/job_queue.py`
- Test: `tests/test_job_queue.py`

- [ ] **Step 1: Write failing queue contract tests**

Use a small in-memory fake implementing the Redis operations used by the queue.
Tests must cover:

```python
def test_submit_enforces_ten_jobs_per_ip_per_hour():
    queue = build_test_queue(runs_per_hour=10)
    for index in range(10):
        queue.submit("203.0.113.10", f"run_{index:08x}", {"instruction": "ok"})
    with pytest.raises(JobQuotaExceeded):
        queue.submit("203.0.113.10", "run_deadbeef", {"instruction": "blocked"})


def test_submit_rejects_eleventh_queued_job():
    queue = build_test_queue(max_queued=10)
    for index in range(10):
        queue.submit(f"203.0.113.{index}", f"run_{index:08x}", {"instruction": "ok"})
    with pytest.raises(JobQueueFull):
        queue.submit("198.51.100.1", "run_deadbeef", {"instruction": "blocked"})


def test_job_payload_expires_and_is_not_returned_in_status():
    queue = build_test_queue()
    queue.submit("203.0.113.10", "run_deadbeef", {"api_key": "sk-secret"})
    assert "sk-secret" not in json.dumps(queue.status("run_deadbeef"))
```

Also test atomic rollback when payload storage or queue insertion fails.

- [ ] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/test_job_queue.py -q
```

Expected: import failure because the module does not exist.

- [ ] **Step 3: Implement Redis queue primitives**

Define:

```python
class JobQuotaExceeded(RuntimeError): ...
class JobQueueFull(RuntimeError): ...
class JobQueueUnavailable(RuntimeError): ...


class RedisJobQueue:
    def submit(self, source_ip: str, run_id: str, payload: dict[str, object]) -> None: ...
    def claim(self, timeout_seconds: int = 5) -> tuple[str, dict[str, object]] | None: ...
    def heartbeat(self, run_id: str) -> None: ...
    def complete(self, run_id: str) -> None: ...
    def fail(self, run_id: str, public_error: str) -> None: ...
    def reconcile_stale_jobs(self) -> int: ...
```

Use one Lua script for quota increment, queue-capacity check, payload `SETEX`,
initial status `SETEX`, and queue push. Quota keys expire after 3,600 seconds.
Payload and lease keys expire after the job timeout. Status keys use the
configured status TTL.

- [ ] **Step 4: Verify queue unit tests**

Run:

```powershell
python -m pytest tests/test_job_queue.py -q
```

Expected: pass.

### Task 7: API Submission And Worker Execution

**Files:**
- Modify: `backend/eval_agent/core/security.py`
- Modify: `backend/eval_agent/api/routes/runs.py`
- Modify: `backend/eval_agent/services/run_service.py`
- Create: `backend/eval_agent/worker.py`
- Test: `tests/test_job_queue.py`
- Test: `tests/test_public_beta_security.py`

- [ ] **Step 1: Write failing API and worker tests**

Require:

```python
def test_async_submission_uses_trusted_client_ip(monkeypatch):
    queue = RecordingQueue()
    monkeypatch.setattr(run_service, "job_queue", lambda: queue)
    response = authorized_client(create_app()).post(
        "/api/runs/async",
        headers={"X-Forwarded-For": "203.0.113.8"},
        json={"instruction": "test"},
    )
    assert response.status_code == 202
    assert queue.source_ip == "127.0.0.1"


def test_local_proxy_forwarded_ip_is_used(monkeypatch):
    request = request_from("127.0.0.1", {"X-Forwarded-For": "203.0.113.8"})
    assert trusted_client_ip(request, ("127.0.0.1",)) == "203.0.113.8"


def test_queue_errors_map_to_public_status_codes():
    assert submit_with(JobQuotaExceeded()).status_code == 429
    assert submit_with(JobQueueFull()).status_code == 503
```

Worker tests claim a job, execute a fake run, release the lease, and sanitize a
failure without exposing `sk-secret`.

- [ ] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/test_job_queue.py tests/test_public_beta_security.py -q
```

Expected: fail because API submission still uses the thread pool.

- [ ] **Step 3: Replace production thread submission**

Change `/api/runs/async` to accept `Request`, derive a trusted source IP, and
submit a serialized `RunRequest` to `RedisJobQueue`.

Keep the old in-process executor only for development tests when
`APP_ENV != production`; production must require Redis.

Create worker entrypoint:

```python
def run_worker() -> None:
    queue = job_queue(require_redis=True)
    while True:
        queue.reconcile_stale_jobs()
        claimed = queue.claim(timeout_seconds=5)
        if claimed is None:
            continue
        run_id, payload = claimed
        execute_queued_run(payload, run_id, deadline_seconds=settings.run_job_timeout_seconds)
```

On Linux, enforce the 15-minute deadline with a process signal alarm around
one job. Status messages use stable public text; detailed exceptions are
logged after secret redaction.

- [ ] **Step 4: Verify API and worker tests**

Run:

```powershell
python -m pytest tests/test_job_queue.py tests/test_public_beta_security.py tests/test_runtime_performance.py -q
```

Expected: pass.

### Task 8: Model Egress And Response Bounds

**Files:**
- Modify: `backend/eval_agent/providers/openai_compatible.py`
- Modify: `backend/eval_agent/core/config.py`
- Test: `tests/test_public_beta_security.py`

- [ ] **Step 1: Write failing transport tests**

Add tests requiring:

- Production rejects `http://` model bases.
- Redirects are rejected when the final host is outside the allowlist.
- Responses larger than `MODEL_RESPONSE_MAX_BYTES` fail.
- Private and link-local addresses are rejected unless the exact configured
  base is explicitly marked as an internal gateway.

- [ ] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/test_public_beta_security.py -k "model_base or model_response" -q
```

Expected: response-limit and redirect tests fail.

- [ ] **Step 3: Implement bounded HTTPS transport**

Use a redirect handler that rejects redirects. Validate the exact URL before
each request. Read at most `max_response_bytes + 1`, and raise a sanitized
`ModelProviderError` when exceeded.

Replace the production `assert last_exc is not None` with explicit error
handling.

- [ ] **Step 4: Verify provider tests and Bandit**

Run:

```powershell
python -m pytest tests/test_public_beta_security.py tests/test_production_readiness.py tests/test_backend_scaffold.py -q
uvx bandit -r backend/eval_agent/providers/openai_compatible.py -ll -iii
```

Expected: tests pass; any remaining `urlopen` warning is reviewed against the
explicit HTTP(S), redirect, and exact-base validation.

### Task 9: Artifact Retention And Safe Cleanup

**Files:**
- Create: `scripts/cleanup_artifacts.py`
- Test: `tests/test_deployment_assets.py`

- [ ] **Step 1: Write failing cleanup tests**

Tests create recent, expired, malformed, and symlinked directories:

```python
def test_cleanup_removes_only_expired_valid_run_directories(tmp_path):
    old = make_run(tmp_path, "run_deadbeef", age_days=8)
    recent = make_run(tmp_path, "run_1234abcd", age_days=1)
    malformed = make_run(tmp_path, "other", age_days=8)
    removed = cleanup_artifacts(tmp_path, retention_days=7, now=NOW)
    assert removed == [old]
    assert recent.exists()
    assert malformed.exists()


def test_cleanup_never_follows_symlinks(tmp_path):
    outside = tmp_path.parent / "outside"
    outside.mkdir()
    (tmp_path / "run_deadbeef").symlink_to(outside, target_is_directory=True)
    cleanup_artifacts(tmp_path, retention_days=0, now=NOW)
    assert outside.exists()
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/test_deployment_assets.py -q
```

Expected: import failure because cleanup script does not exist.

- [ ] **Step 3: Implement cleanup**

Resolve the configured root once, inspect only direct children matching the run
ID pattern, skip symlinks, and use `shutil.rmtree` only after confirming the
resolved parent equals the artifact root.

- [ ] **Step 4: Verify cleanup tests**

Run:

```powershell
python -m pytest tests/test_deployment_assets.py -q
```

Expected: pass.

### Task 10: Ubuntu Deployment Assets

**Files:**
- Create: `deploy/nginx/agent-partner.conf`
- Create: `deploy/systemd/agent-partner-api.service`
- Create: `deploy/systemd/agent-partner-worker@.service`
- Create: `deploy/systemd/agent-partner-cleanup.service`
- Create: `deploy/systemd/agent-partner-cleanup.timer`
- Create: `deploy/redis/agent-partner.conf`
- Create: `deploy/bootstrap-ubuntu.sh`
- Create: `deploy/install-release.sh`
- Modify: `README.md`
- Test: `tests/test_deployment_assets.py`

- [ ] **Step 1: Write failing deployment contract tests**

Assert exact deployment properties:

```python
def test_nginx_limits_and_security_headers_are_configured():
    config = read("deploy/nginx/agent-partner.conf")
    assert "listen 443 ssl" in config
    assert "client_max_body_size 10m" in config
    assert "limit_req_zone" in config
    assert "proxy_pass http://127.0.0.1:8070" in config
    assert "Content-Security-Policy" in config


def test_systemd_services_run_unprivileged_and_are_hardened():
    api = read("deploy/systemd/agent-partner-api.service")
    assert "User=agent-partner" in api
    assert "NoNewPrivileges=true" in api
    assert "PrivateTmp=true" in api
    assert "127.0.0.1" in api


def test_redis_is_local_and_non_persistent():
    redis = read("deploy/redis/agent-partner.conf")
    assert "bind 127.0.0.1 ::1" in redis
    assert 'save ""' in redis
    assert "appendonly no" in redis
```

Also test that setup scripts do not copy `.env`, `*.pem`, `node_modules`,
`frontend/dist`, or local run artifacts from the workstation.

- [ ] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/test_deployment_assets.py -q
```

Expected: fail because deployment files do not exist.

- [ ] **Step 3: Create deployment assets**

The bootstrap script installs:

```text
nginx redis-server python3-venv python3-pip nodejs npm openssl ufw rsync
```

It creates the `agent-partner` system user, `/srv/agent_partner/releases`,
`/srv/agent_partner/runs`, `/etc/agent-partner`, certificate directories, and
the self-signed IP SAN certificate.

The install script:

- receives an already-uploaded source release;
- creates a virtual environment;
- installs locked dependencies;
- runs `npm ci` and `npm run build`;
- runs backend tests;
- atomically switches `/srv/agent_partner/app`;
- restarts workers, API, Nginx, and cleanup timer;
- rolls back the symlink if readiness fails.

README must state the certificate warning, shared-data limitation, token setup,
and exact deployment entrypoint.

- [ ] **Step 4: Verify deployment assets**

Run:

```powershell
python -m pytest tests/test_deployment_assets.py -q
```

Expected: pass.

### Task 11: Reproducible Dependencies And Local Security Gate

**Files:**
- Modify: `pyproject.toml`
- Create: `requirements.lock`
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Create: `scripts/security_check.ps1`
- Create: `scripts/security_check.sh`
- Test: `tests/test_deployment_assets.py`

- [ ] **Step 1: Write failing reproducibility tests**

Require:

- `requirements.lock` exists and uses exact `==` versions.
- `defusedxml` is present.
- security scripts run pytest, frontend build, `pip-audit`, production
  `npm audit`, Bandit, and tracked-secret checks.
- Vite is upgraded to a non-vulnerable supported version and build succeeds.

- [ ] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest tests/test_deployment_assets.py -q
```

Expected: fail because lock and security scripts are absent.

- [ ] **Step 3: Generate lock and security scripts**

Generate the lock from `pyproject.toml` using `uv pip compile` with exact
versions. Upgrade Vite/esbuild to versions without the audited advisories while
keeping React 18 compatibility.

The security gate runs:

```text
python -m pytest -q
npm run build
uvx pip-audit -r requirements.lock
npm audit --omit=dev
uvx bandit -r backend -ll -iii
git grep secret patterns over tracked files
```

- [ ] **Step 4: Run the full local gate**

Run:

```powershell
python -m pytest -q
npm run build
uvx pip-audit -r requirements.lock
npm audit --omit=dev
uvx bandit -r backend -ll -iii
```

Expected: all tests and builds pass, no known runtime dependency
vulnerabilities, and all remaining Bandit findings are explicitly reviewed.

### Task 12: Local Production Smoke Test

**Files:**
- No new source files.

- [ ] **Step 1: Start local Redis**

Use a local Redis instance or container bound to localhost with persistence
disabled.

- [ ] **Step 2: Start API and two workers with production settings**

Set:

```text
APP_ENV=production
APP_ACCESS_TOKEN=<test-token>
REDIS_URL=redis://127.0.0.1:6379/0
TRUSTED_HOSTS=127.0.0.1,localhost
TRUSTED_PROXY_IPS=127.0.0.1,::1
```

Start the API on `127.0.0.1:8070` and two worker processes.

- [ ] **Step 3: Execute smoke assertions**

Verify:

- liveness `200`;
- readiness `200`;
- business route without token `401`;
- business route with token `200`;
- sync run rejected;
- async mock run completes;
- quota request 11 returns `429`;
- queue request 11 returns `503` when workers are paused;
- path traversal returns `404`;
- oversized JSON returns `413`;
- API restart retains queued status.

- [ ] **Step 4: Stop local processes and verify no secrets**

Search generated artifacts and captured logs for the test token and test model
API key. Expected: no matches.

### Task 13: Deploy To `163.7.11.194`

**Files:**
- No new source files.

- [ ] **Step 1: Back up server state and bootstrap**

Connect with:

```powershell
ssh -i D:\Code\agent_partner\meituan.pem root@163.7.11.194
```

Run the reviewed `deploy/bootstrap-ubuntu.sh`. Confirm Ubuntu 24.04, 16GB free
space, and no public listeners other than SSH before enabling Nginx.

- [ ] **Step 2: Upload a clean release**

Create a source archive from tracked and intended untracked source files only.
Exclude:

```text
.git
.env
*.pem
.known_hosts*
frontend/node_modules
frontend/dist
runs
artifacts
__pycache__
.pytest_cache
```

Upload to `/srv/agent_partner/releases/<timestamp>-<git-sha>`.

- [ ] **Step 3: Configure secrets**

Generate `APP_ACCESS_TOKEN` and write `/etc/agent-partner/agent-partner.env`
with mode `0600`. Configure model credentials only in that file. Never print
the generated token in logs; return it once to the operator through the
current secure session.

- [ ] **Step 4: Install and activate release**

Run `deploy/install-release.sh <release-path>`. Verify systemd units are active,
Redis is local-only, API is local-only, and Nginx configuration passes
`nginx -t`.

- [ ] **Step 5: Configure firewall**

Allow:

```text
22/tcp
80/tcp
443/tcp
```

Deny other inbound traffic and enable UFW without dropping the active SSH
session.

### Task 14: Public Acceptance And Recovery Test

**Files:**
- No new source files.

- [ ] **Step 1: Verify external TLS and ports**

From the workstation:

```powershell
curl.exe -k -I http://163.7.11.194/
curl.exe -k -I https://163.7.11.194/
```

Verify HTTP redirects, HTTPS serves the application, the certificate contains
`IP Address:163.7.11.194`, and only ports 22, 80, and 443 are reachable.

- [ ] **Step 2: Verify authentication and headers**

Confirm invalid token `401`, valid token success, and all specified security
headers.

- [ ] **Step 3: Verify limits and task flow**

Run mock evaluations to verify:

- 10 jobs per IP per hour;
- queue capacity 10;
- two concurrent workers;
- oversized body and upload rejection;
- successful report generation.

- [ ] **Step 4: Verify failure recovery**

Restart the API while a job is queued and verify status remains. Stop Redis and
verify readiness becomes `503` and submission is rejected. Restart Redis and
services and verify readiness recovers.

- [ ] **Step 5: Verify cleanup and rollback**

Create an expired test run directory, run the cleanup service, and verify only
the expired valid run is removed. Activate the previous release symlink and
verify rollback restores readiness, then reactivate the new release.

---

## Plan Self-Review

- Spec coverage: every design requirement is represented by Tasks 1-14.
- Placeholder scan: no deferred or unspecified implementation steps remain.
- Type consistency: settings, queue exceptions, run IDs, and health endpoints
  use the same names throughout the plan.
- Test discipline: every code behavior starts with a failing test and an
  explicit RED command before implementation.
- Deployment fit: commands and packages target the verified Ubuntu 24.04 host.
