# PostgreSQL restore

1. Stop writes to the Cloud Control Plane.
2. Create a fresh database or a verified restore target.
3. Restore the custom dump with `pg_restore --clean --if-exists --no-owner --dbname=...`.
4. Run `alembic upgrade head` from `cloud_control_plane`.
5. Start the cloud service and verify `/health/ready`.

Never test restore procedures against the only production database.
