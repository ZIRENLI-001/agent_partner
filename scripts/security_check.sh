#!/usr/bin/env bash
set -euo pipefail

python -m pytest -q -p no:cacheprovider \
  --basetemp="${TMPDIR:-/tmp}/agent-partner-security-$$"
(
  cd frontend
  npm run build
  npm audit --omit=dev
)
uvx pip-audit -r requirements.lock
uvx bandit -r backend -ll -iii

if git grep -n -I -E \
  '(BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY|sk-[A-Za-z0-9]{20,}|APP_ACCESS_TOKEN=[A-Za-z0-9]{32,})' \
  -- . ':(exclude)scripts/security_check.ps1' \
  ':(exclude)scripts/security_check.sh'; then
  echo "Potential tracked secret found." >&2
  exit 1
fi
