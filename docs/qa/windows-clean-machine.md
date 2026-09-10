# Windows clean-machine release test

1. Start from a clean Windows VM or snapshot.
2. Install `TriadaNetwork-Setup-<version>.exe` as a standard user.
3. Launch Triada Network and confirm the local API + UI start.
4. Create a test profile and a test backup.
5. Install the next version over the existing installation.
6. Confirm `%LOCALAPPDATA%\Triada Network` still contains the user data.
7. Uninstall the application.
8. Confirm the installed program directory is removed while `%LOCALAPPDATA%\Triada Network` remains.
9. Reinstall and confirm the preserved data is detected.
10. Run the rollback drill using the previous installer if the upgrade failed.
