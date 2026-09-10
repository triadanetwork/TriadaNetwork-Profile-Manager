# Triada Network v2.0 — Desktop Production Release

This release establishes a production-oriented local data lifecycle:

- deterministic local data migrations
- verified backup preflight and rollback of the last restore
- orphan quarantine instead of destructive cleanup
- redacted support bundles
- staged, checksum-verified update packages
- Windows DPAPI-backed secret storage remains local
- encrypted cookie bundles remain local and are never uploaded by the desktop sync worker

Sensitive browser state remains local. Cloud control-plane sync is metadata-only.
