# Triada Network v1.2.1 Fix

Fixed cloud bootstrap/persistence methods being indented under StorageManager instead of DatabaseManager.
DatabaseManager.initialize() can now call _ensure_cloud_bootstrap().

This release contains source only; install dependencies with `uv sync` and frontend dependencies with `npm ci`.
