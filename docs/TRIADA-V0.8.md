# Triada Network v0.8 — Production Team Layer

## Workspace modes
- Personal workspace: single-user operational surface.
- Team workspace: multi-member workspace with RBAC and profile visibility.

## Profile visibility
- Owner/Admin/Team Lead: workspace-wide profile visibility.
- Buyer: only profiles owned by or assigned to the current buyer.
- Viewer: workspace-wide read-only profile visibility.

## RBAC
Permissions are enforced on the backend. UI hiding is only a presentation aid.

## Activity
Audit events are workspace-scoped and can be filtered by action and actor. Secret proxy credentials are never written to audit metadata.

## Cloud sync foundation
The current release remains local-first. Workspace IDs, member ownership, audit records and isolated operational entities form the persistence boundary required for a future remote API/sync service. No remote sync is enabled in v0.8.
