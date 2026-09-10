from __future__ import annotations

import socket


def find_free_loopback_port(host: str = "127.0.0.1") -> int:
    """Ask the OS for a free TCP port on loopback."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])
