# Triada Network

**Open-source desktop browser infrastructure and profile management platform for teams, operators, and independent users.**

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Next.js 16](https://img.shields.io/badge/Next.js-16-black.svg)](https://nextjs.org/)
[![Status](https://img.shields.io/badge/Status-Release%20Candidate-orange.svg)](docs/qa/RELEASE_CANDIDATE_V2.3.md)


Triada Network is a self-hosted browser infrastructure platform built around [Camoufox](https://github.com/daijro/camoufox). It combines long-lived browser profiles, fingerprint persistence, proxy inventory, session/process management, team access controls, auditability, local data protection, cloud control-plane primitives, and a Windows desktop shell.

The project is designed for users who need reproducible browser environments and operational control over a large number of isolated profiles without handing profile data to a third-party SaaS by default.

## Core capabilities

### Browser profiles

Each profile is a persistent browser workspace with its own local browser data and pinned identity configuration.

- Create, edit, clone, archive, restore, and permanently delete profiles.
- Keep browser storage and profile data isolated per profile.
- Persist a profile's browser configuration between launches.
- Search, filter, tag, group, assign, and bulk-manage profiles.
- Export and import compatible profile data for local migration.

### Fingerprint and browser runtime management

Triada Network uses Camoufox as its browser engine and provides application-level management around it.

- Manage installed browser runtimes.
- Inspect the active runtime version.
- Activate or remove installed runtime versions.
- Keep the application version and browser-runtime version independent.
- Launch and control browser sessions per profile.

Triada Network does **not** attempt to replace the Camoufox engine itself; the project provides the surrounding profile and operations layer.

### Proxy Manager

The proxy subsystem is built as an inventory rather than a single field attached to a profile.

- Proxy inventory.
- Proxy pools.
- HTTP / HTTPS / SOCKS support.
- Provider, country and type metadata.
- Health checks.
- Exit IP, location and latency information.
- Profile-to-proxy assignment.
- Bulk proxy import.
- Pool-based proxy selection.

Proxy credentials are treated as sensitive data and are not returned in normal API responses.

### Browser Session Manager

Desktop users can monitor browser sessions as operational processes rather than just UI state.

- Running / stopped / crashed / orphaned session states.
- PID and session timestamps.
- Uptime and resource information.
- Restart and force-close controls.
- Reconciliation of tracked sessions with actual OS processes.
- Desktop supervisor and recovery primitives.

### Team and RBAC

Triada Network supports both **solo users** and **media / operations teams** from the same product model.

Personal workspaces keep the interface lightweight. Team workspaces add:

- Owner
- Admin
- Team Lead
- Buyer
- Viewer

The permissions layer is enforced server-side and is intended to control access to profiles, assignments, proxy infrastructure, workspace operations and audit data.

### Activity and audit

Operational actions can be recorded with:

- actor;
- action;
- entity;
- entity ID;
- timestamp;
- structured metadata.

The audit model is workspace-scoped and is designed for accountability in shared environments.

### Cloud Control Plane

Triada Network has a local-first cloud architecture foundation.

The cloud layer can manage:

- accounts;
- multiple workspaces;
- workspace members;
- scoped API keys;
- registered devices;
- profile metadata synchronization;
- revision-based synchronization and conflict detection.

Sensitive local browser state is deliberately kept outside the cloud metadata model. Cookies, browser storage, raw fingerprint material, and proxy credentials are not part of the normal metadata sync payload.

### Desktop security and data management

The Windows desktop layer includes:

- local secret storage;
- Windows DPAPI integration;
- encrypted cookie/session bundles;
- backup and restore;
- backup integrity verification;
- orphan-profile detection and quarantine;
- data migrations;
- recovery/rollback primitives;
- diagnostics and support bundles.

Sensitive session exports should always be treated as credentials and stored accordingly.

## Desktop application

The desktop architecture separates the browser/runtime layer from the UI shell:

```text
┌───────────────────────────────────────────┐
│              Triada Network               │
├───────────────────────┬───────────────────┤
│ Desktop Shell         │ Application Core   │
│                       │                   │
│ • window lifecycle    │ • profiles        │
│ • tray                │ • proxy manager   │
│ • single instance     │ • browser runtime │
│ • supervisor          │ • sessions        │
│ • updater             │ • team/RBAC       │
│ • diagnostics         │ • cloud sync      │
└───────────────┬───────┴───────────┬───────┘
                │                   │
                ▼                   ▼
          Local Storage        Cloud Metadata
```

Browser/session material remains local to the machine unless a feature explicitly says otherwise.

## Web UI

The web application is a Next.js frontend served by the local FastAPI application.

For development:

```bash
cd web
npm ci
npm run dev
```

Then open:

```text
http://localhost:3000
```

The API is available at:

```text
http://localhost:8000
```

For a single-process local build:

```bash
cd web
npm ci
npm run build:static

cd ..
uv sync
uv run triada-network
```

## Windows desktop build

Install Python dependencies:

```powershell
uv sync --extra desktop --extra build
```

Build the desktop application:

```powershell
uv run python scripts/build_desktop.py
```

The expected executable is:

```text
dist\TriadaNetwork\TriadaNetwork.exe
```

The Inno Setup definition is located at:

```text
packaging\installer\triada-network.iss
```

See [the release checklist](docs/qa/RELEASE_CHECKLIST.md) and [Windows clean-machine procedure](docs/qa/windows-clean-machine.md) before publishing a Windows release.

## Development

Backend dependencies:

```bash
uv sync --extra dev
```

Frontend:

```bash
cd web
npm ci
```

Fast backend tests:

```bash
uv run pytest -q -m "not browser"
```

Browser tests are opt-in because they require the Camoufox browser runtime:

```bash
uv run camoufox fetch
uv run pytest -m browser
```

Release gate:

```bash
uv run python scripts/qa/release_gate.py
```

Release artifacts are built from a clean source tree. User data is intentionally excluded from source releases.

## Repository layout

```text
src/camoufox_pm/      Core application, API and browser/profile management
src/triada_desktop/    Windows desktop shell and local runtime management
web/                   Next.js UI
cloud_control_plane/   Cloud control-plane service
tests/                 Unit, integration, QA and opt-in browser tests
docs/                  Architecture, API, QA and release documentation
ops/                   Deployment and observability assets
packaging/             PyInstaller and Inno Setup packaging
scripts/               Build, migration, backup and release tooling
extras/                Optional integrations
```

## Project status

`2.3.0-rc.1` is a **Release Candidate**, not a claim of broad production certification.

Before a public release, the project should pass:

1. backend QA and release gates;
2. frontend lint, typecheck and static build;
3. Windows PyInstaller build;
4. clean-machine installation;
5. upgrade and uninstall tests;
6. backup/restore verification;
7. browser session lifecycle testing.

See [RELEASE_CANDIDATE_V2.3.md](docs/qa/RELEASE_CANDIDATE_V2.3.md).

## Support the project

If Triada Network is useful to you, you can support development with cryptocurrency.

### USDT — TRC20

```text
TKjUobpMSR23Vwpw6nTHpRFFR7C5yZN7RB
```

### BTC

```text
bc1qd0nekagryuwqsd2vfmw2qlk5nx4ycy30693lse
```

### ETH

```text
0x4aF1Bd629eCAAe494da0503D1b2ef05Dd6622046
```

> 

## Social links

### Telegram

```text
https://t.me/+ny3V6yCzdkFjZGI1
```

### Instagram

```text
https://www.instagram.com/triada.network
```

Replace the placeholders with your official accounts before publishing.

## Third-party software and attribution

Triada Network is built on and/or incorporates open-source components including:

- [Camoufox](https://github.com/daijro/camoufox)
- [FastAPI](https://github.com/fastapi/fastapi)
- [Next.js](https://github.com/vercel/next.js)
- [Playwright](https://github.com/microsoft/playwright)
- [pywebview](https://github.com/r0x0r/pywebview)
- [PyInstaller](https://github.com/pyinstaller/pyinstaller)

The repository retains the applicable upstream licenses and notices. See [LICENSE](LICENSE) and [NOTICE.md](NOTICE.md).

## Security

Do not commit:

- passwords;
- API keys;
- proxy credentials;
- cookies or session bundles;
- local profile data;
- production database files;
- private backup archives.

See [SECURITY.md](SECURITY.md) for the security model and vulnerability-reporting process.

## License

Triada Network is distributed under the MIT License for the project code, subject to the third-party licenses and notices included with the repository.

---

**Built for operators who want control over their browser infrastructure instead of another opaque dashboard.**
