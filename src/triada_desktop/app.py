from __future__ import annotations

import argparse
import os
import platform
import secrets
import threading
import urllib.request

from loguru import logger

from . import DESKTOP_APP_NAME, DESKTOP_MUTEX_NAME
from .cloud_sync import CloudSyncWorker
from .diagnostics import collect_diagnostics
from .crash import install_exception_hook
from .paths import ensure_app_dirs
from .runtime_manager import status as runtime_status
from .backup import create_backup
from .lifecycle import LocalServerSupervisor, wait_until_serving
from .logging import configure_logging
from .single_instance import SingleInstance, focus_existing_window
from .tray import TrayController
from .paths import logs_dir


class DesktopApplication:
    def __init__(self, host: str, port: int, width: int = 1440, height: int = 900) -> None:
        self.host = host
        self.requested_port = port
        self.width = width
        self.height = height
        self.supervisor: LocalServerSupervisor | None = None
        self.window = None
        self.tray: TrayController | None = None
        self.sync_worker: CloudSyncWorker | None = None
        self._shutdown_lock = threading.Lock()
        self._stopped = False
        self.bridge_token = secrets.token_urlsafe(32)

    @property
    def server(self):
        return self.supervisor.runtime if self.supervisor else None

    def run(self) -> int:
        import webview

        ensure_app_dirs()
        configure_logging()
        install_exception_hook()
        os.environ["CPM_DESKTOP_BRIDGE_TOKEN"] = self.bridge_token
        logger.info("Starting {} desktop", DESKTOP_APP_NAME)

        self.supervisor = LocalServerSupervisor(self.host, self.requested_port)
        runtime = self.supervisor.start()
        if not wait_until_serving(runtime):
            self.supervisor.stop()
            raise RuntimeError("Triada local API failed to start")

        url_host = "localhost" if self.host in {"0.0.0.0", "127.0.0.1"} else self.host
        url = f"http://{url_host}:{runtime.port}/"
        self.window = webview.create_window(
            DESKTOP_APP_NAME,
            url,
            width=self.width,
            height=self.height,
            min_size=(1100, 700),
            resizable=True,
        )
        self.tray = TrayController(self.show_window, self.exit, self._tray_close_all, self._tray_diagnostics, self._tray_backup, self._tray_open_tasks, self._tray_status)
        self.tray.start()

        from camoufox_pm.config import get_settings
        settings = get_settings()
        self.sync_worker = CloudSyncWorker(settings.cloud_base_url, settings.cloud_sync_token, settings.cloud_sync_interval_seconds)
        self.sync_worker.start()

        webview.start(debug=False)
        self.shutdown()
        return 0

    def _request_local(self, path: str) -> str:
        runtime = self.server
        if runtime is None:
            return "server unavailable"
        req = urllib.request.Request(
            f"http://127.0.0.1:{runtime.port}{path}",
            headers={"X-Triada-Desktop-Token": self.bridge_token},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.read().decode("utf-8", errors="replace")

    def _tray_close_all(self) -> None:
        try:
            self._request_local("/api/v1/system/desktop/close-all")
        except Exception:
            logger.exception("Tray close-all failed")

    def _tray_backup(self) -> None:
        try:
            path = create_backup(include_browser_data=False)
            logger.info("Tray backup created: {}", path)
        except Exception:
            logger.exception("Tray backup failed")

    def _tray_open_tasks(self) -> None:
        self.show_window()
        if self.window is not None and self.server is not None:
            try:
                self.window.load_url(f"http://127.0.0.1:{self.server.port}/tasks")
            except Exception:
                logger.exception("Could not open Task Center")

    def _tray_status(self) -> str:
        runtime = runtime_status()
        api = "API" if self.server else "API offline"
        return f"Triada Network · {api} · Camoufox {'OK' if runtime.available else 'not installed'}"

    def _tray_diagnostics(self) -> None:
        try:
            result = collect_diagnostics(
                f"http://127.0.0.1:{self.server.port}" if self.server else "",
                browser_available=__import__("camoufox_pm.core.browser_session", fromlist=["CAMOUFOX_AVAILABLE"]).CAMOUFOX_AVAILABLE,
            )
            logger.info("Desktop diagnostics: {}", result)
        except Exception:
            logger.exception("Desktop diagnostics failed")

    def show_window(self) -> None:
        if self.window is not None:
            try:
                self.window.restore()
                self.window.show()
            except Exception:
                logger.exception("Could not restore desktop window")

    def exit(self) -> None:
        try:
            import webview
            if self.window is not None:
                self.window.destroy()
            elif webview.windows:
                webview.windows[0].destroy()
        except Exception:
            self.shutdown()

    def shutdown(self) -> None:
        with self._shutdown_lock:
            if self._stopped:
                return
            self._stopped = True
            if self.sync_worker:
                self.sync_worker.stop()
            if self.tray:
                self.tray.stop()
            if self.supervisor:
                self.supervisor.stop()
            logger.info("Triada desktop stopped; logs at {}", logs_dir())


def configure_local_data_paths() -> None:
    if platform.system() == "Windows" and os.getenv("LOCALAPPDATA"):
        from pathlib import Path
        root = Path(os.environ["LOCALAPPDATA"]) / DESKTOP_APP_NAME
        data_db = root / "data" / "profiles.db"
        os.environ.setdefault("CPM_DB_PATH", str(data_db))
        os.environ.setdefault("CPM_DATA_DIR", str(data_db.parent))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="TriadaNetwork", description="Triada Network desktop application")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0, help="Local port; 0 selects a free loopback port")
    args = parser.parse_args(argv)

    configure_local_data_paths()
    instance = SingleInstance(DESKTOP_MUTEX_NAME)
    if not instance.acquire():
        focus_existing_window(DESKTOP_APP_NAME)
        return 0
    try:
        return DesktopApplication(args.host, args.port).run()
    finally:
        instance.release()
