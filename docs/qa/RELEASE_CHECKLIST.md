# Triada Network release checklist

## Required gates

- [ ] `uv run python scripts/qa/release_gate.py`
- [ ] `uv run pytest -q`
- [ ] `npm ci`
- [ ] `npm run lint`
- [ ] `npm run build:static`
- [ ] Windows PyInstaller build succeeds
- [ ] `TriadaNetwork.exe` exists and has non-trivial size
- [ ] Installer compiles with Inno Setup
- [ ] Backup create/inspect/restore tests pass
- [ ] Migration tests pass
- [ ] Runtime/session tests pass

## Optional slow gates

- [ ] `uv run camoufox fetch`
- [ ] `uv run pytest -m browser --no-network`
- [ ] Playwright end-to-end suite when enabled
- [ ] Clean Windows VM install/upgrade/uninstall
- [ ] Restore test from an artifact produced by the previous release

## Release artifact

Generate a SHA-256 manifest:

```powershell
uv run python scripts/qa/manifest.py dist/TriadaNetwork-Setup-2.1.0.exe --version 2.1.0
```

Publishing is intentionally a separate manual step from CI.
