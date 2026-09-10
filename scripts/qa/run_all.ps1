$ErrorActionPreference = 'Stop'
uv run python scripts/qa/release_gate.py
uv run pytest -q
Push-Location web
npm ci
npm run lint
npm run build:static
Pop-Location
Write-Host 'Triada QA: PASS'
