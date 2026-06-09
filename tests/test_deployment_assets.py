from __future__ import annotations

import os
from pathlib import Path
import json

import pytest

from scripts.cleanup_artifacts import cleanup_artifacts


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def _make_run(root: Path, run_id: str, *, age_days: int, now: float) -> Path:
    path = root / run_id
    path.mkdir()
    timestamp = now - age_days * 86_400
    os.utime(path, (timestamp, timestamp))
    return path


def test_cleanup_removes_only_expired_valid_run_directories(tmp_path):
    now = 2_000_000_000.0
    old = _make_run(tmp_path, "run_deadbeef", age_days=8, now=now)
    recent = _make_run(tmp_path, "run_1234abcd", age_days=1, now=now)
    malformed = _make_run(tmp_path, "other", age_days=8, now=now)

    removed = cleanup_artifacts(tmp_path, retention_days=7, now=now)

    assert removed == [old]
    assert not old.exists()
    assert recent.exists()
    assert malformed.exists()


def test_cleanup_never_follows_symlinks(tmp_path):
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    link = tmp_path / "run_deadbeef"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Directory symlinks are unavailable in this environment")

    cleanup_artifacts(tmp_path, retention_days=0, now=2_000_000_000.0)

    assert outside.exists()
    assert link.is_symlink()


def test_nginx_limits_tls_and_security_headers_are_configured():
    config = _read("deploy/nginx/agent-partner.conf")

    assert "listen 443 ssl" in config
    assert "listen 80" in config
    assert "server_name agentpartner.top" in config
    assert "server_name www.agentpartner.top" in config
    assert "return 301 https://agentpartner.top$request_uri" in config
    assert "/etc/letsencrypt/live/agentpartner.top/fullchain.pem" in config
    assert "/etc/letsencrypt/live/agentpartner.top/privkey.pem" in config
    assert "client_max_body_size 10m" in config
    assert "limit_req_zone" in config
    assert "limit_req zone=agent_partner_api" in config
    assert "zone=agent_partner_status:10m rate=120r/m" in config
    assert "limit_req zone=agent_partner_status" in config
    assert "limit_req_status 429" in config
    assert 'location ~ "^/api/runs/run_[0-9a-f]{8}/status$"' in config
    assert "location /api/stages/" in config
    assert config.count("proxy_read_timeout 420s;") >= 2
    assert config.count("proxy_send_timeout 420s;") >= 2
    assert "proxy_pass http://127.0.0.1:8070" in config
    assert "proxy_set_header X-Forwarded-For $remote_addr" in config
    assert "Content-Security-Policy" in config


def test_systemd_services_run_unprivileged_and_are_hardened():
    api = _read("deploy/systemd/agent-partner-api.service")
    worker = _read("deploy/systemd/agent-partner-worker@.service")

    for service in (api, worker):
        assert "User=agent-partner" in service
        assert "Group=agent-partner" in service
        assert "EnvironmentFile=/etc/agent-partner/agent-partner.env" in service
        assert "NoNewPrivileges=true" in service
        assert "PrivateTmp=true" in service
        assert "ProtectSystem=strict" in service
        assert "ReadWritePaths=/srv/agent_partner/runs" in service
        assert "Requires=redis-server.service" not in service
    assert "--host 127.0.0.1 --port 8070" in api
    assert "backend.eval_agent.worker" in worker


def test_cleanup_timer_runs_daily():
    service = _read("deploy/systemd/agent-partner-cleanup.service")
    timer = _read("deploy/systemd/agent-partner-cleanup.timer")

    assert "scripts.cleanup_artifacts" in service
    assert "OnCalendar=daily" in timer
    assert "Persistent=true" in timer


def test_redis_is_local_and_non_persistent():
    config = _read("deploy/redis/agent-partner.conf")

    assert "bind 127.0.0.1 ::1" in config
    assert "protected-mode yes" in config
    assert 'save ""' in config
    assert "appendonly no" in config


def test_bootstrap_installs_host_dependencies_and_ip_certificate():
    script = _read("deploy/bootstrap-ubuntu.sh")

    for package in (
        "nginx",
        "redis-server",
        "python3-venv",
        "nodejs",
        "npm",
        "openssl",
        "ufw",
        "rsync",
    ):
        assert package in script
    assert "agent-partner" in script
    assert 'PUBLIC_IP="163.7.11.194"' in script
    assert "subjectAltName=IP:${PUBLIC_IP}" in script
    assert "\nEOF\n" in script
    assert "\n  EOF\n" not in script
    assert "ufw allow 22/tcp" in script
    assert "ufw allow 80/tcp" in script
    assert "ufw allow 443/tcp" in script


def test_install_release_rejects_local_secrets_and_activates_atomically():
    script = _read("deploy/install-release.sh")

    for forbidden in (
        ".env",
        "*.pem",
        "node_modules",
        "frontend/dist",
        "runs",
        ".git",
    ):
        assert forbidden in script
    assert "requirements.lock" in script
    assert "--index-url https://pypi.org/simple" in script
    assert "npm ci" in script
    assert "npm run build" in script
    assert "-m pytest" in script
    assert "ln -sfn" in script
    assert "/api/health/ready" in script
    assert '"runs/run_*"' in script


def test_readme_documents_temporary_public_beta_access():
    readme = _read("README.md")

    assert "https://agentpartner.top" in readme
    assert "Let's Encrypt" in readme
    assert "APP_AUTH_REQUIRED" in readme
    assert "APP_ACCESS_TOKEN" in readme
    assert "intentionally anonymous" in readme


def test_python_dependencies_are_exactly_locked():
    lock = _read("requirements.lock")
    requirement_lines = [
        line.strip()
        for line in lock.splitlines()
        if line.strip() and not line.lstrip().startswith(("#", "--"))
    ]

    assert requirement_lines
    assert all("==" in line for line in requirement_lines)
    assert any(line.startswith("defusedxml==") for line in requirement_lines)
    assert any(line.startswith("httpx2==") for line in requirement_lines)
    assert any(line.startswith("pytest==") for line in requirement_lines)


def test_security_gate_scripts_cover_required_checks():
    powershell = _read("scripts/security_check.ps1")
    bash = _read("scripts/security_check.sh")

    for script in (powershell, bash):
        assert "pytest" in script
        assert "npm run build" in script
        assert "pip-audit" in script
        assert "npm audit --omit=dev" in script
        assert "bandit -r backend -ll -iii" in script
        assert "git grep" in script


def test_frontend_uses_patched_vite_release():
    package = json.loads(_read("frontend/package.json"))
    vite_version = package["devDependencies"]["vite"].lstrip("^~")
    major, minor, patch = (int(part) for part in vite_version.split("."))

    assert (major, minor, patch) >= (6, 1, 0)


def test_linux_deployment_files_use_lf_line_endings():
    paths = [
        PROJECT_ROOT / "deploy/bootstrap-ubuntu.sh",
        PROJECT_ROOT / "deploy/install-release.sh",
        PROJECT_ROOT / "scripts/security_check.sh",
    ]

    assert all(b"\r\n" not in path.read_bytes() for path in paths)
