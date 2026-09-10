from __future__ import annotations

import threading
import time
from dataclasses import dataclass

import uvicorn
from loguru import logger

from .port import find_free_loopback_port


@dataclass
class ServerRuntime:
    server: uvicorn.Server
    thread: threading.Thread
    host: str
    port: int

    def stop(self) -> None:
        logger.info("Stopping local API server")
        self.server.should_exit = True
        self.thread.join(timeout=15)
        if self.thread.is_alive():
            logger.warning("API server did not stop within the grace period")


class LocalServerSupervisor:
    """Own the local API process/thread lifecycle and restart unexpected failures."""

    def __init__(self, host: str = "127.0.0.1", requested_port: int = 0) -> None:
        self.host = host
        self.requested_port = requested_port
        self.runtime: ServerRuntime | None = None
        self._stop = threading.Event()
        self._watcher: threading.Thread | None = None
        self._lock = threading.Lock()

    @property
    def port(self) -> int:
        if self.runtime is None:
            raise RuntimeError("Local server has not started")
        return self.runtime.port

    def start(self) -> ServerRuntime:
        with self._lock:
            self.runtime = start_local_server(self.host, self.requested_port)
        self._watcher = threading.Thread(target=self._watch, name="triada-api-supervisor", daemon=True)
        self._watcher.start()
        return self.runtime

    def _watch(self) -> None:
        while not self._stop.wait(2.0):
            runtime = self.runtime
            if runtime is None:
                continue
            if runtime.server.should_exit:
                return
            if runtime.thread.is_alive():
                continue
            logger.error("Local API thread exited unexpectedly; restarting")
            try:
                with self._lock:
                    self.runtime = start_local_server(self.host, runtime.port)
                if wait_until_serving(self.runtime, timeout=10):
                    logger.info("Local API recovered on port {}", self.runtime.port)
                else:
                    logger.error("Local API recovery did not become ready")
            except Exception:
                logger.exception("Local API recovery failed")

    def stop(self) -> None:
        self._stop.set()
        runtime = self.runtime
        if runtime:
            runtime.stop()
        if self._watcher:
            self._watcher.join(timeout=3)


def start_local_server(host: str = "127.0.0.1", requested_port: int = 0) -> ServerRuntime:
    from camoufox_pm.main import app

    port = requested_port or find_free_loopback_port(host)
    config = uvicorn.Config(app, host=host, port=port, log_level="info", access_log=False)
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="triada-api", daemon=True)
    thread.start()
    return ServerRuntime(server, thread, host, port)


def wait_until_serving(runtime: ServerRuntime, timeout: float = 30.0) -> bool:
    import socket

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            try:
                sock.connect((runtime.host, runtime.port))
                return True
            except OSError:
                time.sleep(0.2)
    return False
