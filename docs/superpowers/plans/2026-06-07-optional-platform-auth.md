# Optional Platform Authentication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a default-on platform authentication switch and disable the shared-token prompt for the invited deployment.

**Architecture:** Parse `APP_AUTH_REQUIRED` into `Settings.auth_required`. Use that value in both the production startup gate and token middleware so configuration and request behavior cannot diverge. The frontend remains unchanged because it prompts only after a `401`.

**Tech Stack:** Python 3.12, FastAPI, pytest, React/Vite, systemd

---

### Task 1: Define Authentication Switch Behavior

**Files:**
- Modify: `tests/test_production_readiness.py`
- Modify: `backend/eval_agent/core/config.py`
- Modify: `backend/eval_agent/core/security.py`
- Modify: `backend/eval_agent/api/main.py`

- [ ] **Step 1: Add failing tests**

Add tests asserting:

```python
def test_platform_authentication_defaults_to_required(monkeypatch):
    monkeypatch.delenv("APP_AUTH_REQUIRED", raising=False)
    assert settings_from_env().auth_required is True


def test_production_allows_anonymous_access_when_auth_is_disabled(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_AUTH_REQUIRED", "false")
    monkeypatch.delenv("APP_ACCESS_TOKEN", raising=False)
    app = create_app()
    assert TestClient(app).get("/api/context").status_code == 200
```

Also assert an invalid value raises `ValueError`.

- [ ] **Step 2: Verify RED**

Run:

```powershell
python -m pytest tests/test_production_readiness.py -k "authentication_defaults or anonymous_access or invalid_auth" -q
```

Expected: failures because `auth_required` does not exist and production still
requires `APP_ACCESS_TOKEN`.

- [ ] **Step 3: Implement minimal configuration and gates**

Add a strict boolean parser accepting `true/false`, `1/0`, `yes/no`, and
`on/off`. Add `auth_required: bool = True` to `Settings`, load it from
`APP_AUTH_REQUIRED`, skip token enforcement when false, and require the token
at production startup only when true.

- [ ] **Step 4: Verify GREEN**

Run:

```powershell
python -m pytest tests/test_production_readiness.py -q
```

Expected: all production-readiness tests pass.

### Task 2: Document And Verify The Release

**Files:**
- Modify: `.env.example`
- Modify: `README.md`

- [ ] **Step 1: Document the setting**

Add `APP_AUTH_REQUIRED=true` to `.env.example`. Explain in README that
disabling it makes all business APIs public and should only be used for a
controlled temporary deployment.

- [ ] **Step 2: Run full verification**

Run:

```powershell
python -m pytest -q
cd frontend
npm run build
```

Expected: all tests pass and the production frontend build succeeds.

### Task 3: Deploy Anonymous Access

**Files:**
- Modify remotely: `/etc/agent-partner/agent-partner.env`

- [ ] **Step 1: Commit and upload a clean release**

Commit the tested source changes, upload a release excluding `.env`, keys,
caches, local runs, and build dependencies, then activate it with the existing
deployment script.

- [ ] **Step 2: Disable authentication on the server**

Set:

```text
APP_AUTH_REQUIRED=false
```

Preserve `APP_ACCESS_TOKEN` for quick recovery, retain mode `0600`, and restart
the API and workers.

- [ ] **Step 3: Verify public behavior**

Verify without an authorization header:

- `/api/context` returns 200.
- `/api/health/ready` returns 200.
- The frontend loads without invoking the token prompt.
- Nginx, API, Redis, and both workers are active.
