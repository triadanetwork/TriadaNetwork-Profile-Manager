# Windows installer

The installer is designed for per-user installs under `%LOCALAPPDATA%\Programs\Triada Network` so an ordinary user does not need elevation.

User data is stored separately under `%LOCALAPPDATA%\Triada Network` and is intentionally not removed by uninstall/upgrade.

For an upgrade, run the new installer over the existing installation. Inno Setup will replace application files while keeping the user data directory intact.
