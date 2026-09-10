# Changelog

## 2.3.0-rc.1 — Release Candidate

- Hardened release-state checks so user profile history, audit logs, backups, cookie bundles, local databases and runtime artifacts cannot ship in source releases.
- Added candidate-version consistency checks across Python, web, desktop and installer metadata.
- Added frontend typecheck release gate.
- Added installer release-label validation and RC manifest example.
- Added QA coverage for release-state cleanliness and candidate metadata.


## 2.1.0 — QA & Release Engineering

- Added deterministic local QA/release gate tooling.
- Added unit/QA coverage for desktop security, backup, runtime, packaging, and release hygiene.
- Added GitHub Actions CI for Python tests, static TypeScript checks, and Windows desktop packaging validation.
- Added Windows packaging smoke checks without publishing artifacts automatically.
- Added Playwright-ready UI test scaffold and documented browser-test opt-in policy.
- Added release manifest/checksum generation and artifact validation helpers.


## 1.6.0 - Desktop UX

- Added Desktop Task Center for live browser sessions.
- Added Diagnostics UI.
- Added Backups/Restore UI.
- Added first-run desktop onboarding.
- Added unified desktop navigation for Tasks, Diagnostics and Backups.
- Kept browser/session material local; backup of browser data remains opt-in.

# v1.4.0 Desktop Runtime

- Added desktop supervisor/recovery, tray controls, diagnostics, encrypted secret storage, backup/restore, cloud sync worker, and verified update downloads.

# Changelog

## 1.3.0 - Desktop Foundation

- Added native desktop shell under `src/triada_desktop`.
- Added Windows single-instance mutex and best-effort window focus.
- Added dynamic loopback port selection.
- Added graceful API lifecycle management.
- Added optional system tray integration.
- Added rotating local desktop logs.
- Added Windows-safe npm invocation in dev/build scripts.
- Added `TriadaNetwork.exe` PyInstaller spec with GUI mode.
- Added Inno Setup installer skeleton.

## v2.0.1 — Desktop Production Release

Production-grade desktop data, recovery, migration, diagnostics and update staging.
