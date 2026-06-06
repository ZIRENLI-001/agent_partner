$ErrorActionPreference = "Stop"

python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Push-Location frontend
try {
    npm run build
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    npm audit --omit=dev
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    Pop-Location
}

uvx pip-audit -r requirements.lock
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

uvx bandit -r backend -ll -iii
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

git grep -n -I -E `
    "(BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY|sk-[A-Za-z0-9]{20,}|APP_ACCESS_TOKEN=[A-Za-z0-9]{32,})" `
    -- .
if ($LASTEXITCODE -eq 0) {
    throw "Potential tracked secret found."
}
if ($LASTEXITCODE -gt 1) {
    throw "git grep failed."
}
