#!/usr/bin/env bash
set -euo pipefail

PUBLIC_IP="163.7.11.194"
APP_USER="agent-partner"
APP_ROOT="/srv/agent_partner"
CONFIG_ROOT="/etc/agent-partner"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root." >&2
  exit 1
fi

source /etc/os-release
if [[ "${ID}" != "ubuntu" || "${VERSION_ID}" != "24.04" ]]; then
  echo "Ubuntu 24.04 is required." >&2
  exit 1
fi

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  nginx redis-server python3-venv python3-pip nodejs npm openssl ufw rsync curl

if ! id "${APP_USER}" >/dev/null 2>&1; then
  useradd --system --home "${APP_ROOT}" --shell /usr/sbin/nologin "${APP_USER}"
fi

install -d -m 0755 "${APP_ROOT}" "${APP_ROOT}/releases"
install -d -o "${APP_USER}" -g "${APP_USER}" -m 0750 "${APP_ROOT}/runs"
install -d -m 0750 "${CONFIG_ROOT}" "${CONFIG_ROOT}/tls"

if [[ ! -f "${CONFIG_ROOT}/tls/server.key" ]]; then
  openssl req -x509 -nodes -newkey rsa:3072 -days 30 \
    -keyout "${CONFIG_ROOT}/tls/server.key" \
    -out "${CONFIG_ROOT}/tls/server.crt" \
    -subj "/CN=${PUBLIC_IP}" \
    -addext "subjectAltName=IP:${PUBLIC_IP}"
  chmod 0600 "${CONFIG_ROOT}/tls/server.key"
  chmod 0644 "${CONFIG_ROOT}/tls/server.crt"
fi

if [[ ! -f "${CONFIG_ROOT}/agent-partner.env" ]]; then
  access_token="$(openssl rand -hex 32)"
  cat >"${CONFIG_ROOT}/agent-partner.env" <<EOF
APP_ENV=production
APP_ACCESS_TOKEN=${access_token}
REDIS_URL=redis://127.0.0.1:6379/0
EVAL_ARTIFACT_ROOT=${APP_ROOT}/runs
EVAL_FRONTEND_DIST=${APP_ROOT}/app/frontend/dist
TRUSTED_HOSTS=${PUBLIC_IP},127.0.0.1,localhost
TRUSTED_PROXY_IPS=127.0.0.1,::1
MAX_JSON_BODY_BYTES=2097152
MAX_UPLOAD_BYTES=10485760
RUNS_PER_IP_PER_HOUR=10
MAX_QUEUED_RUNS=10
RUN_JOB_TIMEOUT_SECONDS=900
ARTIFACT_RETENTION_DAYS=7
ALLOWED_MODEL_API_BASES=https://openrouter.ai/api/v1
EOF
  chmod 0600 "${CONFIG_ROOT}/agent-partner.env"
fi

install -m 0644 "${SCRIPT_DIR}/nginx/agent-partner.conf" \
  /etc/nginx/sites-available/agent-partner.conf
ln -sfn /etc/nginx/sites-available/agent-partner.conf \
  /etc/nginx/sites-enabled/agent-partner.conf
rm -f /etc/nginx/sites-enabled/default

install -m 0644 "${SCRIPT_DIR}/redis/agent-partner.conf" /etc/redis/redis.conf
install -m 0644 "${SCRIPT_DIR}/systemd/"*.service /etc/systemd/system/
install -m 0644 "${SCRIPT_DIR}/systemd/"*.timer /etc/systemd/system/

systemctl daemon-reload
systemctl enable redis-server nginx agent-partner-cleanup.timer
systemctl restart redis-server
nginx -t

ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw default deny incoming
ufw default allow outgoing
ufw --force enable
