# Triada Network v1.2.3

## Profile operations

- Bulk cookie export for selected profiles.
- Bulk account import from a ZIP of standard cookie JSON files. Each valid cookie file creates one new local profile.
- Existing single-profile cookie portability remains available.
- Session/cookie material is never written to the audit log or cloud metadata sync.

## Desktop

- `triada-network --desktop` opens the Triada UI in a native `pywebview` window.
- New PyInstaller spec: `packaging/triada-network.spec`.
- Build helper: `python scripts/build_desktop.py`.
- Release bundle name: `TriadaNetwork`.

Bulk cookie import is intended for session portability of accounts the operator owns or is authorized to manage.
