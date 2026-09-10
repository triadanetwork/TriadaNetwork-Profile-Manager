#!/usr/bin/env python3
"""Build the static UI if needed, then launch the native Triada desktop shell."""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"


def npm_executable() -> str:
    return shutil.which("npm.cmd") or shutil.which("npm") or "npm.cmd"


def main() -> int:
    npm = npm_executable()
    if not (WEB / "node_modules").exists():
        subprocess.run([npm, "ci"], cwd=WEB, check=True)
    subprocess.run([npm, "run", "build:static"], cwd=WEB, check=True)
    subprocess.run([sys.executable, "-m", "triada_desktop.app"], cwd=ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
