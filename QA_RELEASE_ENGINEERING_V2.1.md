# v2.1 — QA & Release Engineering

This release introduces a deterministic quality gate around the existing Triada Network desktop product.

## Gates
- Python AST/TOML/version/release-hygiene gate
- Unit tests for desktop security/data/runtime helpers
- CI matrix for Python 3.11–3.13
- Web lint and production/static build gate
- Windows PyInstaller artifact verification
- Optional real-browser smoke tests, explicitly opt-in
- SHA-256 release-manifest generation
- Release checklist and Windows smoke script

## Philosophy

The source archive is kept clean. Build dependencies and generated output are produced by CI/local build commands rather than committed or shipped inside the source ZIP.

Browser tests remain opt-in because they require a real Camoufox runtime and may be slow. They can be run with `--no-network` for local-only pages/fixtures.
