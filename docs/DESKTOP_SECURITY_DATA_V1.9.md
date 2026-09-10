# Triada Network Desktop Security & Data Layer v1.9

- Windows local secrets use DPAPI.
- Portable secure bundles use PBKDF2-HMAC-SHA256 + AES-256-GCM.
- Backups are verified with checksums and SQLite integrity checks.
- Data integrity reports missing profile storage and orphaned profile directories.
- Browser/session material is not uploaded to cloud by the desktop security layer.
- Secure bundle endpoints accept metadata envelopes; raw cookies remain handled by the existing local-only cookie APIs.
