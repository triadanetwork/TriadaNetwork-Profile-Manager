# Triada Network v1.2 — Observability & Reliability

## Observability

- Prometheus metrics at `/metrics` (internal-only through Caddy).
- HTTP request count, latency histogram, in-flight gauge, readiness gauge, rate-limit failures.
- Optional Sentry integration via `TRIADA_CLOUD_SENTRY_DSN`.
- Optional OpenTelemetry FastAPI + SQLAlchemy instrumentation via the `observability` extra.
- Every request carries an `X-Request-ID` response header and structured JSON logs.

## Reliability

- `/health/live` is a liveness probe; `/health/ready` checks PostgreSQL and Redis and returns HTTP 503 when dependencies are unavailable.
- Cloud schema is managed exclusively through Alembic.
- Redis-backed rate limiting fails closed when Redis is unavailable.
- PostgreSQL backups use custom `pg_dump` format with retention. `ops/backup/verify_latest.sh` verifies the newest dump with `pg_restore --list`.
- A dedicated worker process is present for idempotent background operational jobs.

## Monitoring

Docker Compose includes Prometheus and Grafana for local/infrastructure environments. Grafana is bound to localhost in development and not exposed by the production Caddy config.

## Production checklist

1. Configure a strong PostgreSQL password and JWT secret.
2. Configure Grafana admin credentials.
3. Put Prometheus/Grafana behind an internal network or VPN if remote access is required.
4. Configure Sentry and/or an OTLP collector.
5. Ship PostgreSQL backups off-host; the local Docker volume is not a disaster-recovery boundary.
6. Test a restore from a real backup on a scheduled cadence.
