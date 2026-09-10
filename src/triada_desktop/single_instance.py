from __future__ import annotations

import os
from contextlib import suppress


def focus_existing_window(title: str = "Triada Network") -> None:
    """Best-effort focus of an existing desktop window on Windows."""
    if os.name != "nt":
        return
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        found = []

        @EnumWindowsProc
        def callback(hwnd, _lparam):
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            if buf.value == title:
                found.append(hwnd)
                return False
            return True

        user32.EnumWindows(callback, 0)
        if found:
            hwnd = found[0]
            if user32.IsIconic(hwnd):
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            user32.SetForegroundWindow(hwnd)
    except Exception:
        pass


class SingleInstance:
    """Process-wide single-instance guard with a Windows named mutex."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._handle = None
        self._lock_path = None
        self._fd = None
        self.already_running = False

    def acquire(self) -> bool:
        if os.name == "nt":
            import ctypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            handle = kernel32.CreateMutexW(None, False, self.name)
            if not handle:
                raise ctypes.WinError(ctypes.get_last_error())
            self._handle = handle
            self.already_running = ctypes.get_last_error() == 183
            return not self.already_running

        import tempfile

        self._lock_path = os.path.join(tempfile.gettempdir(), "triada-network.instance.lock")
        try:
            self._fd = os.open(self._lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            return True
        except FileExistsError:
            self.already_running = True
            return False

    def release(self) -> None:
        if os.name == "nt":
            if self._handle:
                import ctypes

                ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(self._handle)
                self._handle = None
            return
        with suppress(Exception):
            if self._fd is not None:
                os.close(self._fd)
        if self._lock_path:
            with suppress(FileNotFoundError):
                os.unlink(self._lock_path)
