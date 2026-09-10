# Triada Network v0.6 — Proxy Manager

Proxy Manager introduces a separate proxy inventory layer on top of existing profiles.

## Model
- Proxy Pools: organizational containers.
- Proxy Inventory: individual endpoints with encrypted credentials.
- Health: reachability, latency and exit location.
- Assignment: one inventory proxy can be assigned to at most one profile.

## API
- `GET /api/v1/ops/proxies`
- `POST /api/v1/ops/proxies`
- `GET /api/v1/ops/proxies/{id}`
- `PATCH /api/v1/ops/proxies/{id}`
- `DELETE /api/v1/ops/proxies/{id}`
- `POST /api/v1/ops/proxies/{id}/check`
- `POST /api/v1/ops/proxies/{id}/assign`
- `POST /api/v1/ops/proxies/{id}/unassign`

Credentials are never returned by the inventory API. Assignment synchronizes the managed proxy into the existing browser profile so current launch code remains compatible.

## Assignment behavior
A managed proxy becomes the browser profile's active proxy configuration. Editing the inventory record synchronizes the assigned profile. Unassigning removes the managed proxy from the profile; the profile can then be configured manually again.

## Pool selection
`POST /api/v1/ops/proxy-pools/{pool_id}/assign-next` selects an unassigned proxy, preferring healthy, then active, then unknown, and breaking ties with lower measured latency. Disabled, retired and unhealthy proxies are excluded.
