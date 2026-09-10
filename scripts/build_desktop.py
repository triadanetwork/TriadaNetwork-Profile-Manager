#!/usr/bin/env python3
"""Build the standalone Triada Network Windows desktop app."""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def npm_executable() -> str:
    return shutil.which("npm.cmd") or shutil.which("npm") or "npm.cmd"

def main() -> int:
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_webui.py")], check=True)
    spec = ROOT / "packaging" / "triada-network.spec"
    subprocess.run([sys.executable, "-m", "PyInstaller", str(spec), "--noconfirm", "--clean"], cwd=ROOT, check=True)
    print("Triada Network desktop build complete — see dist/TriadaNetwork/")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
