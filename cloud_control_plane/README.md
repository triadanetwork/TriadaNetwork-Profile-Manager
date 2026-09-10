# Triada Network Cloud Control Plane v1.2

Standalone control-plane service for accounts, workspaces, members, scoped machine/API authentication, devices, and metadata synchronization.

## Boundary

The control plane intentionally stores **metadata only**. It does not store cookies, browser profile directories, raw fingerprints, proxy credentials, or other local browser secrets.

## Local

```bash
cd cloud_control_plane
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --host 127.0.0.1 --port 8100
```

## Docker

The root `docker-compose.yml` starts Postgres + the cloud service. Set `TRIADA_CLOUD_JWT_SECRET` before exposing it outside localhost.

## Observability

The runtime exposes Prometheus metrics at `/metrics`. Caddy blocks that path from the public domain; Prometheus scrapes it over the internal Docker network. Grafana is provisioned from `ops/monitoring/grafana`. Optional Sentry and OpenTelemetry are enabled by environment variables.

Enable OpenTelemetry by setting `TRIADA_CLOUD_OTEL_ENABLED=1` and an OTLP HTTP endpoint. Sentry is enabled by setting `TRIADA_CLOUD_SENTRY_DSN`.
