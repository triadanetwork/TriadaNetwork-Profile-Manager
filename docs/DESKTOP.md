# Triada Network Desktop Foundation

## Development

From the repository root:

```powershell
uv sync --extra desktop
uv run python -m triada_desktop.app
```

The desktop shell selects a free loopback port automatically when `--port 0` is used.

## Build

```powershell
uv sync --extra desktop --extra build
uv run python scripts/build_desktop.py
```

The output is `dist/TriadaNetwork/TriadaNetwork.exe`.

## Runtime data

On Windows, mutable data and logs live under `%LOCALAPPDATA%\Triada Network\`.

## Desktop guarantees

- one running instance per user/machine
- free local port selection by default
- graceful API shutdown when the window closes
- optional system tray
- durable rotating application logs
- no console window in packaged builds
