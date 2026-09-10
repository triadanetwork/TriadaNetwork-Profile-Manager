# Triada Network v1.2.2

## New profile operations

- Profile Trash: deletes move browser data to a local trash directory and keep restore metadata.
- Restore / permanent purge from the Trash UI.
- Cookie export/import is local-only profile session portability. Cookie values are never logged or synced to cloud.
- Bulk proxy import accepts `.txt`/`.csv` files. Supported line formats include `host:port`, `user:pass@host:port`, and `socks5://user:pass@host:port`.

### Security

Only use cookie import/export with browser sessions and accounts that the operator is authorised to access. Treat exported cookie files as session credentials: store them securely and delete them when no longer required.
