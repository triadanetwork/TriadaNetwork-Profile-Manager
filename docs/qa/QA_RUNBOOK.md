# Triada Network QA & Release Engineering

## Local fast gate

From the repository root:

```powershell
uv sync --extra dev --extra desktop --extra build
uv run python scripts/qa/release_gate.py
uv run pytest -q
cd web
npm ci
npm run lint
npm run build:static
cd ..
```

## Browser tests

Browser tests are intentionally opt-in because they require a fetched Camoufox
runtime. Run them only in an environment with the runtime installed:

```powershell
uv run camoufox fetch
uv run pytest -m browser
```

Use `--no-network` for suites that must prove they stay local:

```powershell
uv run pytest --no-network -m browser
```

## Windows desktop smoke

```powershell
uv run python scripts/build_desktop.py
.dist\TriadaNetwork\TriadaNetwork.exe
```

The GUI artifact should be tested on a clean Windows VM or runner in CI.

## Release gate

A release is not considered ready unless all of these pass:

1. Python compile/pytest.
2. TypeScript/Next production build.
3. Source-release hygiene gate.
4. Windows PyInstaller build.
5. Installer compile (Inno Setup on Windows).
6. Backup/restore tests.
7. Migration tests.
8. Browser launch smoke (opt-in, real runtime).

CI does not publish releases automatically; publishing is a separate, manual job.
