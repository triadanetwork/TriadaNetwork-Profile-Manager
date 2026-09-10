# Triada Network Desktop Runtime v1.4

## Runtime
- Dynamic loopback port
- Single-instance Windows mutex
- Local API supervisor with automatic restart after unexpected thread exit
- System tray: Open / Close all browsers / Diagnostics / Exit
- Logs under `%LOCALAPPDATA%\Triada Network\logs`
- Local secrets store: Windows DPAPI (fallback Fernet outside Windows)
- Backups under `%LOCALAPPDATA%\Triada Network\backups`
- Optional HTTPS cloud readiness worker
- Update manifest checker with HTTPS + SHA-256 validation; no automatic execution of unverified packages

## Backup
Create without browser data by default:

```powershell
uv run python scripts/backup_desktop.py
```

Include local browser data explicitly:

```powershell
uv run python scripts/backup_desktop.py --include-browser-data
```

Restore only while no browsers are running.
