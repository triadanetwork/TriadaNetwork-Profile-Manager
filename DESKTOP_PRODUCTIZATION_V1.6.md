# Triada Network Desktop Productization v1.8

## Development
`uv sync --extra desktop` then `uv run python -m triada_desktop.app`.

## Build (Windows)
`uv sync --extra desktop --extra build` then `uv run python scripts/build_desktop.py`. Output: `dist/TriadaNetwork/TriadaNetwork.exe`.

## Installer
Install Inno Setup 6 and compile `packaging/installer/triada-network.iss`.

## Desktop runtime
- single instance
- dynamic loopback port
- local API supervisor
- tray controls
- crash logs
- diagnostics
- local backups
- optional cloud sync worker
- runtime status
- user data under `%LOCALAPPDATA%\Triada Network`

## Updating
Update manifests require HTTPS and SHA-256. Optional Ed25519 signatures are supported. Downloaded packages are verified and never executed automatically by the updater.
