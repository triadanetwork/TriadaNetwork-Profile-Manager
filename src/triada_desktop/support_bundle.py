from __future__ import annotations

import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from .diagnostics import collect_diagnostics
from .integrity import check_data_integrity
from .paths import app_data_dir, logs_dir

_SECRET_PATTERNS = [
    re.compile(r'(?i)(password|token|secret|api[_-]?key|authorization)\s*[:=]\s*[^\s,;]+'),
    re.compile(r'(?i)Bearer\s+[A-Za-z0-9._-]+'),
]


def _redact(text: str) -> str:
    out = text
    for pattern in _SECRET_PATTERNS:
        out = pattern.sub(lambda m: m.group(1) + "=<redacted>" if m.lastindex else "<redacted>", out)
    return out


def create_support_bundle(api_url: str = "") -> Path:
    root = app_data_dir()
    target = root / "backups" / f"triada-support-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.zip"
    diagnostics = collect_diagnostics(api_url, browser_available=False)
    integrity = check_data_integrity()
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("diagnostics.json", json.dumps(diagnostics, indent=2, default=str))
        zf.writestr("integrity.json", json.dumps(integrity, indent=2, default=str))
        for path in logs_dir().glob("*.log"):
            try:
                zf.writestr(f"logs/{path.name}", _redact(path.read_text(encoding="utf-8", errors="replace")))
            except OSError:
                continue
    return target
