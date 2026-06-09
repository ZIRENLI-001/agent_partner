# Invited Public Beta Deployment History

## Summary

- Execution time: 2026-06-06 evening, Asia/Shanghai
- Documentation date: 2026-06-07
- Server: `163.7.11.194`, Ubuntu 24.04 LTS
- Public URL: `https://163.7.11.194`
- Deployment branch: `feature/invited-public-beta`
- Active release commit: `187a50c`
- Active release path:
  `/srv/agent_partner/releases/20260606-234640-187a50c`
- Access mode: self-signed HTTPS plus one shared bearer token
- Token storage: `/etc/agent-partner/agent-partner.env`, mode `0600`

The access token value is intentionally not stored in this document or Git.

## Planning Records

- Design:
  `docs/superpowers/specs/2026-06-06-invited-public-beta-deployment-design.md`
- Implementation plan:
  `docs/superpowers/plans/2026-06-06-invited-public-beta-deployment.md`

Work was performed in the isolated worktree:

```text
D:\Code\agent_partner\.worktrees\invited-public-beta
```

## Implemented Controls

- Shared bearer-token authentication for business APIs.
- Self-signed TLS certificate with IP SAN `163.7.11.194`.
- Nginx as the only public application listener.
- FastAPI bound to `127.0.0.1:8070`.
- Redis bound to localhost with persistence disabled.
- UFW default-deny inbound policy; only TCP 22, 80, and 443 allowed.
- Trusted host and trusted proxy validation.
- JSON body and upload size limits.
- Pydantic field, scenario, row, column, archive, and XML limits.
- Canonical run artifact path validation and traversal rejection.
- Redis-backed atomic hourly quota: 10 submissions per IP per hour.
- Redis-backed bounded queue: maximum 10 queued jobs.
- Two independent systemd workers with job timeout and stale lease recovery.
- Split liveness and readiness endpoints.
- Production synchronous evaluation route disabled.
- HTTPS-only model egress policy, exact endpoint allowlist, no redirects, and
  bounded response reads.
- Seven-day artifact retention with symlink-safe cleanup.
- Low-privilege and sandboxed systemd services.
- Exact Python dependency lock and Vite `6.4.3`.
- Cross-platform security gate scripts.

## Main Implementation Commits

```text
fee1950 feat: bound public beta requests
f3773cd fix: contain run artifact paths
46fb60f feat: enforce production web boundaries
f2970c8 feat: split liveness and readiness checks
2de54bb fix: bound and harden file imports
8a21baf feat: add bounded redis job queue
dbaa6f7 feat: route production runs through redis workers
3eba5a5 fix: constrain model provider egress
d98e42c feat: add safe artifact retention cleanup
e052b4b feat: add hardened ubuntu deployment assets
e4d377f build: lock dependencies and add security gate
36e28ac fix: isolate security gate test state
6e7b305 fix: make release validation reproducible
1759e63 fix: enforce linux line endings for deployment
faf54e0 fix: install locked dependencies from pypi
ef40bc8 fix: lock clean test client dependencies
187a50c fix: keep api available during redis outages
```

## Local Verification

The repository security gate completed successfully:

```text
pytest: 281 passed, 1 skipped
frontend: Vite 6.4.3 production build succeeded
npm audit --omit=dev: 0 vulnerabilities
pip-audit: no known vulnerabilities
Bandit: 0 medium/high findings
tracked secret scan: no matches
```

A separate clean virtual environment using only `requirements.lock` completed:

```text
282 passed, 1 skipped
```

## Server Installation

Bootstrap installed and configured:

```text
nginx
redis-server
python3-venv
python3-pip
nodejs
npm
openssl
ufw
rsync
curl
```

Server-side release installation completed:

```text
Python dependencies installed from https://pypi.org/simple
npm ci succeeded
Vite production build succeeded
pytest: 283 passed
nginx -t succeeded
```

Systemd units:

```text
redis-server.service
nginx.service
agent-partner-api.service
agent-partner-worker@1.service
agent-partner-worker@2.service
agent-partner-cleanup.timer
```

All six units were active in the final status check.

## Public Acceptance Results

```text
HTTP /                         -> 301 HTTPS redirect
HTTPS /                        -> 200
GET /api/health/live           -> 200
GET /api/health/ready          -> 200, all checks ok
GET /api/context, no token     -> 401
GET /api/context, valid token  -> 200
POST /api/runs                 -> 404 in production
Async mock evaluation          -> completed, detail 200
Oversized JSON                 -> 413
Oversized upload               -> 413
Path traversal                 -> 404
```

Security headers observed on public HTTPS responses:

```text
Strict-Transport-Security
Content-Security-Policy
X-Content-Type-Options
X-Frame-Options
Referrer-Policy
Permissions-Policy
```

## Quota And Queue Acceptance

Hourly quota test:

```text
Requests 1-10 -> 202
Request 11    -> 429
```

Queue capacity test with workers paused:

```text
Requests 1-10 -> 202
Request 11    -> 503
```

API restart recovery:

```text
Status before restart -> queued
Status after restart  -> queued
Status after workers resumed -> completed
```

## Failure Recovery

Redis outage test:

```text
API service remained active
Readiness while Redis stopped -> 503
Submission while Redis stopped -> 503
Readiness after Redis restart -> 200
```

Rollback test:

```text
Previous release: ef40bc8 -> readiness 200
Current release:  187a50c -> readiness 200
```

Artifact cleanup test:

```text
Expired valid run directory -> removed
Expired malformed directory -> preserved
```

## Final Server State

```text
FastAPI listener: 127.0.0.1:8070
Redis listener:   127.0.0.1:6379 and ::1:6379
Public listeners: 22, 80, 443
Redis queued jobs: 0
Redis processing jobs: 0
Disk usage: 4.8 GB used of 20 GB, 14 GB available
Environment file mode: 0600
TLS private-key mode: 0600
Artifact directory mode: 0750
```

The TLS certificate has IP SAN `163.7.11.194` and expires on
2026-07-06. It must be replaced or regenerated before that date.

The shared access token was not found in generated artifacts or systemd
journal output.

## Operational Commands

Service status:

```bash
systemctl status agent-partner-api.service
systemctl status agent-partner-worker@1.service
systemctl status agent-partner-worker@2.service
systemctl status nginx redis-server
```

Readiness:

```bash
curl -k https://163.7.11.194/api/health/ready
```

Rotate the shared token:

```bash
openssl rand -hex 32
sudoedit /etc/agent-partner/agent-partner.env
systemctl restart agent-partner-api.service
```

Deploy another release:

```bash
bash deploy/install-release.sh /srv/agent_partner/releases/<release>
```

## Repository State

At the time this history was written:

- The implementation branch was not merged into `main`.
- The active branch was `feature/invited-public-beta`.
- The main worktree contained pre-existing untracked `.known_hosts_meituan`
  and `runs/`; they were not modified or committed.
