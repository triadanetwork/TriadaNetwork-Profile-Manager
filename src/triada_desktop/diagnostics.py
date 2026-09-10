from __future__ import annotations

import shutil
import socket
from urllib.parse import urlparse
import sys
from pathlib import Path
from typing import Any

import psutil

from .paths import app_data_dir, logs_dir


def collect_diagnostics(api_url: str, *, browser_available: bool) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    try:
        parsed = urlparse(api_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 80
        with socket.create_connection((host, port), timeout=0.5):
            checks["loopback"] = "ok"
    except OSError:
        checks["loopback"] = "warn"
    checks["python"] = sys.version.split()[0]
    checks["browser_engine"] = "available" if browser_available else "missing"
    usage = shutil.disk_usage(app_data_dir())
    checks["disk_free_gb"] = round(usage.free / (1024 ** 3), 2)
    checks["memory_percent"] = psutil.virtual_memory().percent
    checks["logs_dir"] = str(logs_dir())
    checks["api_url"] = api_url
    return checks
