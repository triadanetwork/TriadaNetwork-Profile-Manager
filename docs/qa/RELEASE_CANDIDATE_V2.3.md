# Triada Network 2.3.0-rc.1 — Release Candidate

## Mandatory release gates

1. `uv run python scripts/qa/release_gate.py`
2. `uv run python scripts/qa/installer_preflight.py`
3. `uv run pytest -q -m "not browser"`
4. `cd web && npm ci && npm run lint && npm run typecheck && npm run build:static`
5. Windows: `uv sync --extra desktop --extra build && uv run python scripts/build_desktop.py`
6. Windows: compile `packaging/installer/triada-network.iss` and test install, upgrade, uninstall, and clean-machine startup.

## Clean release-state contract

The source release must contain no developer profile history or desktop runtime state: local databases, audit/activity logs, browser profile directories, cookies/session bundles, backups, caches, or generated build directories.

Use `scripts/qa/build_source_release.py` to create the ZIP without deleting anything from the working tree. Existing runtime data under `%LOCALAPPDATA%\Triada Network\` is intentionally not packaged.
