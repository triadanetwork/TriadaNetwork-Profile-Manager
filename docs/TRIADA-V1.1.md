# Triada Network v1.2 — Production Infrastructure

## Runtime split
- Local plane: browser engine, profile storage, cookies and local secrets.
- Cloud control plane: PostgreSQL-backed metadata, auth, workspaces, API keys, sync and audit.

## Production components
- Caddy: TLS termination and reverse proxy.
- PostgreSQL: durable control-plane storage.
- Redis: rate limiting and future background jobs.
- Cloud API: FastAPI + Alembic migrations.
- Backup worker: daily `pg_dump` custom-format backups with retention.

## Health endpoints
- `/health/live` = process liveness only.
- `/health/ready` = PostgreSQL + Redis readiness; returns HTTP 503 if a dependency is unavailable.

## Production startup
1. Copy `deploy.example.env` to `.env` and replace all placeholders.
2. Make sure DNS for `TRIADA_DOMAIN` points to the server and ports 80/443 are reachable.
3. Run `docker compose -f docker-compose.production.yml up -d --build`.
4. Verify `https://<domain>/health/live` and `/health/ready`.
5. Confirm the first migration completed before accepting traffic.

## Backups
The backup service keeps daily custom-format dumps. Store a second copy off-host (S3-compatible storage or another region) before calling the deployment production-ready.

## Logging
Cloud emits one JSON object per request with request id, method, path, status and latency. Do not add credentials, cookies or tokens to log fields.

## Rate limiting
Cloud API requests are limited per client IP in Redis. Authentication endpoints use a separate bucket. This is intentionally a coarse first layer; account/user-aware limits should be added with billing/plan entitlements.
