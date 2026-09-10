# Triada Network v1.0 — Cloud Architecture

## Planes

### Local / Desktop Plane
- Camoufox/Playwright browser runtime
- local profile directories and storage
- local fingerprint material
- local proxy credentials
- SQLite operational cache
- scheduler and browser lifecycle

### Cloud Control Plane
- PostgreSQL
- account/workspace/membership state
- RBAC claims
- scoped API keys
- refresh-token sessions
- device registry
- metadata sync revisions
- audit events

The cloud service never needs cookies, raw browser storage, fingerprint secrets or proxy passwords.

## Local development

```bash
docker compose up --build postgres cloud
```

Cloud API: `http://localhost:8100`

Local app can continue running separately on `http://localhost:8000`.

## Production direction

Place the cloud API behind TLS and a reverse proxy. Use managed PostgreSQL, rotate `TRIADA_CLOUD_JWT_SECRET`, keep the database private, and expose only the HTTPS control-plane endpoint. The desktop plane communicates outbound to the control plane; inbound browser-control ports do not need to be public.
