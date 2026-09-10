# Triada Network — Build / Run

## Backend

```bash
uv sync
uv run triada-network
```

## Web UI from source

```bash
cd web
npm ci
npm run build:static
cd ..
uv run triada-network
```

The generated web bundle is intentionally not committed or shipped inside the source archive.

## Desktop

```bash
uv sync --extra desktop
uv run triada-network --desktop
```

## API

Canonical API: `/api/v1`
Legacy aliases: `/api`

## Environment

Copy `.env.example` to `.env` and set `CPM_SECRET_KEY` for encrypted proxy credentials.
For protected machine access, configure `CPM_API_KEY`.


## Proxy Manager v0.6
The application now includes proxy inventory under `web` > `Proxy Manager`. Install frontend dependencies with `npm ci`, then run the UI with `npm run dev` or build it with `npm run build`.


## v0.7 Team / RBAC

Team invite flow: an owner/admin creates a one-time token in the Team screen. The recipient opens `/invite?token=...`, chooses the invited username and a password (10+ chars), and receives a session.

Roles: `owner`, `admin`, `team_lead`, `buyer`, `viewer`. Audit access is granted to owner/admin/team_lead. Workspace administration is restricted to owner/admin. Profile and proxy permissions are enforced server-side.


## v1.2 observability

Development Compose also starts Prometheus on `127.0.0.1:9090` and Grafana on `127.0.0.1:3001`. Production keeps both services internal and exposes only Caddy on 80/443.
