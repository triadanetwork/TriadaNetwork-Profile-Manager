from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger

from .paths import cache_dir


@dataclass
class SyncState:
    enabled: bool = False
    status: str = "disabled"
    last_error: str | None = None
    last_sync_at: str | None = None


class CloudSyncWorker:
    """Small local-first metadata sync supervisor.

    The worker never uploads browser storage, cookies, fingerprint material, or
    proxy credentials. It only calls a future cloud metadata endpoint when an
    HTTPS URL and explicit bearer token are configured.
    """

    def __init__(self, base_url: str | None, token: str | None, interval: int = 30) -> None:
        self.base_url = base_url.rstrip("/") if base_url else None
        self.token = token
        self.interval = max(5, int(interval))
        self.state = SyncState(enabled=bool(self.base_url and self.token), status="idle" if self.base_url and self.token else "disabled")
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.state_file = cache_dir() / "cloud-sync.json"

    def start(self) -> None:
        if not self.state.enabled:
            return
        if not self.base_url.lower().startswith("https://"):
            self.state = SyncState(enabled=False, status="disabled", last_error="Cloud sync requires HTTPS")
            return
        self._thread = threading.Thread(target=self._run, name="triada-cloud-sync", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._sync_once()
            except Exception as exc:
                self.state.status = "error"
                self.state.last_error = str(exc)
                logger.warning("Cloud sync failed: {}", exc)
                self._persist()
            self._stop.wait(self.interval)

    def _sync_once(self) -> None:
        request = urllib.request.Request(
            self.base_url + "/health/ready",
            headers={"Authorization": f"Bearer {self.token}", "User-Agent": "TriadaNetwork-Desktop/1"},
            method="GET",
        )
        with urllib.request.urlopen(request, timeout=8) as response:
            if response.status >= 400:
                raise RuntimeError(f"Cloud readiness returned HTTP {response.status}")
        self.state.status = "connected"
        self.state.last_error = None
        from datetime import datetime, timezone
        self.state.last_sync_at = datetime.now(timezone.utc).isoformat()
        self._persist()

    def _persist(self) -> None:
        self.state_file.write_text(json.dumps(self.state.__dict__, indent=2), encoding="utf-8")
