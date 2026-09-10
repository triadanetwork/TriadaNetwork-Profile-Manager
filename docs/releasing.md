# Releasing

Triada Network releases are cut from a clean source tree and are expected to pass the QA/release gates before publication.

## Release checks

```bash
uv run python scripts/qa/release_gate.py
uv run python scripts/qa/installer_preflight.py
uv run pytest -q -m "not browser"

cd web
npm ci
npm run lint
npm run typecheck
npm run build:static
```

On Windows:

```powershell
uv sync --extra desktop --extra build
uv run python scripts/build_desktop.py
```

The release tree must not contain local profile data, cookies, backups, databases, logs or generated build directories.

## Building a clean source archive

Use:

```bash
uv run python scripts/qa/build_source_release.py
```

The clean source builder intentionally excludes:

- `data/`
- local databases;
- logs;
- profile directories;
- cookie/session bundles;
- backups;
- `.venv/`;
- `node_modules/`;
- `.next/`;
- `dist/`;
- `build/`;
- Python caches.

The builder is non-destructive: it creates a clean artifact without modifying the developer's local data.

## Windows publication

For a Windows public release:

1. Build and verify `TriadaNetwork.exe`.
2. Compile the Inno Setup installer from `packaging/installer/triada-network.iss`.
3. Test clean install.
4. Test upgrade over the previous supported build.
5. Test uninstall and verify that user data remains where the product promises to retain it.
6. Verify update manifest and checksums.
7. Sign the Windows artifacts before public distribution.
