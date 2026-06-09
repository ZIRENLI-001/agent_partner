#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="/srv/agent_partner"
APP_LINK="${APP_ROOT}/app"
CONFIG_ROOT="/etc/agent-partner"
RELEASE="${1:-}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root." >&2
  exit 1
fi
if [[ -z "${RELEASE}" || ! -d "${RELEASE}" ]]; then
  echo "Usage: $0 /srv/agent_partner/releases/<release>" >&2
  exit 1
fi

RELEASE="$(realpath "${RELEASE}")"
case "${RELEASE}" in
  "${APP_ROOT}/releases/"*) ;;
  *) echo "Release must be below ${APP_ROOT}/releases." >&2; exit 1 ;;
esac

for forbidden in \
  ".env" "*.pem" "node_modules" "frontend/dist" "runs/run_*" ".git"; do
  if find "${RELEASE}" -path "*/${forbidden}" -print -quit | grep -q .; then
    echo "Release contains forbidden local content: ${forbidden}" >&2
    exit 1
  fi
done

test -f "${RELEASE}/requirements.lock"
test -f "${RELEASE}/frontend/package-lock.json"
test -f "${CONFIG_ROOT}/agent-partner.env"

python3 -m venv "${RELEASE}/.venv"
"${RELEASE}/.venv/bin/python" -m pip install \
  --index-url https://pypi.org/simple --upgrade pip
"${RELEASE}/.venv/bin/python" -m pip install \
  --index-url https://pypi.org/simple -r "${RELEASE}/requirements.lock"
npm ci --prefix "${RELEASE}/frontend"
npm run build --prefix "${RELEASE}/frontend"

(
  cd "${RELEASE}"
  APP_ENV=development "${RELEASE}/.venv/bin/python" -m pytest -q
)

chown -R agent-partner:agent-partner "${RELEASE}"
previous="$(readlink -f "${APP_LINK}" || true)"
switched=0

rollback() {
  if [[ "${switched}" -eq 1 && -n "${previous}" && -d "${previous}" ]]; then
    ln -sfn "${previous}" "${APP_LINK}.rollback"
    mv -Tf "${APP_LINK}.rollback" "${APP_LINK}"
    systemctl restart agent-partner-api.service
    systemctl restart agent-partner-worker@1.service agent-partner-worker@2.service
  fi
}
trap rollback ERR

ln -sfn "${RELEASE}" "${APP_LINK}.next"
mv -Tf "${APP_LINK}.next" "${APP_LINK}"
switched=1

install -m 0644 "${RELEASE}/deploy/nginx/agent-partner.conf" \
  /etc/nginx/sites-available/agent-partner.conf
install -m 0644 "${RELEASE}/deploy/systemd/"*.service /etc/systemd/system/
install -m 0644 "${RELEASE}/deploy/systemd/"*.timer /etc/systemd/system/
systemctl daemon-reload
nginx -t
systemctl enable agent-partner-api.service
systemctl enable agent-partner-worker@1.service agent-partner-worker@2.service
systemctl enable agent-partner-cleanup.timer
systemctl restart agent-partner-worker@1.service agent-partner-worker@2.service
systemctl restart agent-partner-api.service
systemctl restart nginx
systemctl start agent-partner-cleanup.timer

for attempt in {1..30}; do
  if curl --fail --silent --show-error \
    http://127.0.0.1:8070/api/health/ready >/dev/null; then
    switched=0
    trap - ERR
    exit 0
  fi
  sleep 1
done

echo "Release failed readiness check." >&2
exit 1
