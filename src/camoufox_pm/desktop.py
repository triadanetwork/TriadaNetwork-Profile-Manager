"""Compatibility wrapper for the Triada Network desktop shell."""

from triada_desktop.app import DesktopApplication


def run_desktop(host: str = "127.0.0.1", port: int = 0, title: str = "Triada Network") -> None:
    DesktopApplication(host, port).run()
