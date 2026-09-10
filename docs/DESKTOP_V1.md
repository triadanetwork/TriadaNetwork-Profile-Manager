# Triada Network Desktop Foundation v1.0

## Goal

The desktop shell owns the native window, local API lifecycle, single-instance guard, optional tray, logs and Windows packaging. Browser/profile business logic remains in `camoufox_pm`.

## Development

```powershell
uv sync --extra desktop
uv run python -m triada_desktop.app
```

## Build

```powershell
uv sync --extra desktop --extra build
uv run python scripts/build_desktop.py
```

Output:

```text
dist/TriadaNetwork/TriadaNetwork.exe
```

## Windows installer

Install Inno Setup 6 and compile:

```text
packaging/installer/triada-network.iss
```

## Runtime

- loopback-only local API
- dynamic local port by default
- one process per machine/user
- second launch focuses the existing window
- closing the main window shuts down the local API
- optional tray remains lightweight and cannot block startup
- logs live under `%LOCALAPPDATA%\Triada Network\logs`
- user data lives under `%LOCALAPPDATA%\Triada Network\data`

## Future desktop milestones

1. Signed installer and executable
2. Auto-updater with signature/hash verification
3. Diagnostics/support bundle
4. Backup/restore UI
5. Offline-first cloud sync worker
