#!/usr/bin/env python3
"""Static checks for the Windows installer contract."""
from __future__ import annotations
from pathlib import Path
import re, sys

root=Path(__file__).resolve().parents[2]
iss=(root/"packaging/installer/triada-network.iss").read_text(encoding="utf-8")
checks={
    "version": 'MyAppVersion "2.3.0"' in iss,
    "exe": 'MyAppExeName "TriadaNetwork.exe"' in iss,
    "per_user": r'DefaultDirName={localappdata}\Programs\Triada Network' in iss,
    "release_label": 'MyAppReleaseLabel "2.3.0-rc.1"' in iss,
    "preserve_data": 'Never delete %LOCALAPPDATA%\\Triada Network\\ data here' in iss,
}
failed=[k for k,v in checks.items() if not v]
if failed:
    raise SystemExit("Installer preflight failed: "+", ".join(failed))
print("Installer preflight: PASS")
