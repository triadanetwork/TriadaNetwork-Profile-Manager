# Triada Network v0.9 — Cloud Control Plane

## Scope
The v0.9 control plane adds accounts, multiple workspaces, workspace-scoped API keys, device metadata, and revisioned metadata sync. Browser identity, cookies, storage, fingerprint material, proxy credentials and raw browser settings remain local.

## Local-first deployment
The current implementation uses SQLite as the embedded control-plane store so development and desktop deployments do not require a hosted service. The API contract is intentionally independent of that storage choice and can later be backed by PostgreSQL/object storage in a hosted service. The v0.9 implementation is a control-plane foundation, not a hosted multi-tenant service: local profile/browser operations still use the embedded workspace boundary.

## API
- `GET /api/v1/cloud/me`
- `GET|POST /api/v1/cloud/workspaces`
- `GET|POST /api/v1/cloud/api-keys`
- `DELETE /api/v1/cloud/api-keys/{id}`
- `GET|POST /api/v1/cloud/devices`
- `GET|POST /api/v1/cloud/sync`
- `POST /api/v1/cloud/sync/profiles`

## Sync model
Profile sync stores operational metadata only: ID, name, group, status, timestamps, ownership/assignment, proxy pool/proxy references and tags. Every record has a monotonically increasing workspace revision. `expected_revision` enables optimistic-concurrency conflict detection.

## API-key model
Keys are random opaque secrets; only SHA-256 hashes are stored. Each key carries explicit scopes and may expire/revoke independently.
