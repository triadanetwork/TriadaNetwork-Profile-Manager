# Triada Network Desktop Runtime Manager v1.8

- Native runtime manager page at `/runtime/`.
- Uses `python -m camoufox` (the documented upstream CLI) for sync/fetch/set/list/remove operations.
- Shows active/installed runtime state and supports install/activate/remove.
- Browser runtime management is separate from the Triada application version.
- Runtime actions run locally; cloud sync never receives browser binaries or local browser storage.
- Removal of the active version is disabled in the UI.

## Windows
The runtime manager expects the project virtual environment to contain the `camoufox` package. A first-run install can run `python -m camoufox fetch`.
