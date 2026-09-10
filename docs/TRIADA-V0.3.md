# Triada Network v0.3 — Personal + Team foundation

## Product model

Triada Network uses a single workspace model with two UX modes:

- `personal`: optimized for a solo buyer; team-only navigation and ownership columns stay hidden.
- `team`: enables the Team surface plus ownership and assignment metadata on Profiles.

Switching mode does not modify browser identity, fingerprints, cookies, or storage. It only changes workspace metadata and UI exposure.

## Profiles 2.0 operations model

Browser identity remains in `profiles`. Operational metadata is normalized into:

- `profile_assignments` — owner, assigned buyer, proxy pool.
- `tags` + `profile_tags` — reusable workspace tags.
- `proxy_pools` — shared proxy inventory grouping foundation.
- `workspace_members` — user/role mapping.
- `workspaces` — personal/team workspace state.

## API

Canonical endpoints:

- `GET/PATCH /api/v1/ops/workspace`
- `GET /api/v1/ops/members`
- `GET/POST /api/v1/ops/tags`
- `GET/POST /api/v1/ops/proxy-pools`
- `GET/PUT /api/v1/ops/profiles/{profile_id}/operations`
- `POST /api/v1/ops/profiles/bulk`

The legacy `/api/ops/*` aliases are also mounted.

## Next product layer

The schema is intentionally prepared for:

- real RBAC permission checks on backend routes;
- team invitations and workspace membership lifecycle;
- proxy inventory records inside each pool;
- activity/audit events;
- profile ownership/assignment analytics;
- SaaS workspaces and billing.
