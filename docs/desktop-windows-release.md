# Windows release flow

## Install

Triada Network installs per-user under `%LOCALAPPDATA%\Programs\Triada Network`. User data remains under `%LOCALAPPDATA%\Triada Network`.

## Upgrade

Run the newer installer. Application files are replaced in-place; user data is preserved.

## Uninstall

The uninstaller removes the installed application directory and intentionally preserves `%LOCALAPPDATA%\Triada Network` so profiles, backups, logs and local settings survive. A future data-purge action should be explicit and separately confirmed.

## Update channels

`stable` is the default channel. `beta` is opt-in and must never replace stable metadata silently. Manifests include a channel field and are verified with HTTPS, SHA-256, and optionally Ed25519.

## Rollback

A failed update must leave the previous installation usable. The installer flow should be tested on a clean Windows VM before publishing.
