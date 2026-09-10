from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger

from .paths import runtime_dir


@dataclass(frozen=True)
class RuntimeVersion:
    version: str
    path: str | None = None
    installed: bool = False
    active: bool = False


@dataclass(frozen=True)
class RuntimeStatus:
    available: bool
    executable: str | None
    message: str
    active_version: str | None = None
    installed_versions: tuple[RuntimeVersion, ...] = ()
    python: str = sys.executable


def _run_camoufox(*args: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, "-m", "camoufox", *args]
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)


def _find_cli() -> str | None:
    candidates = [Path(sys.executable).with_name("camoufox.exe"), Path(sys.executable).with_name("camoufox")]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def _parse_active(text: str) -> str | None:
    value = text.strip()
    if not value:
        return None
    # `camoufox active` prints the selector on one line; keep it opaque.
    return value.splitlines()[-1].strip() or None


def _parse_installed(text: str) -> tuple[RuntimeVersion, ...]:
    items: list[RuntimeVersion] = []
    for line in text.splitlines():
        raw = line.strip()
        if not raw or raw.startswith(("Camoufox", "Installed", "Available")):
            continue
        # The CLI is intentionally human-readable; accept likely version/path lines.
        if "/" in raw or raw[:1].isdigit():
            items.append(RuntimeVersion(version=raw, installed=True))
    return tuple(items)


def list_versions() -> dict[str, Any]:
    try:
        active = _parse_active(_run_camoufox("active", timeout=30).stdout)
        installed_cp = _run_camoufox("list", timeout=30)
        versions = list(_parse_installed(installed_cp.stdout))
        if active:
            versions = [RuntimeVersion(v.version, v.path, v.installed, v.version == active) for v in versions]
        return {"active": active, "versions": [v.__dict__ for v in versions], "raw": installed_cp.stdout[-8000:]}
    except Exception as exc:
        return {"active": None, "versions": [], "error": str(exc)}


def find_camoufox() -> str | None:
    return _find_cli()


def status() -> RuntimeStatus:
    try:
        check = _run_camoufox("version", timeout=30)
        if check.returncode != 0:
            return RuntimeStatus(False, _find_cli(), check.stderr.strip() or "Camoufox CLI unavailable")
        active = _parse_active(_run_camoufox("active", timeout=30).stdout)
        versions = tuple(RuntimeVersion(**{k: x[k] for k in ("version", "path", "installed", "active") if k in x}) for x in list_versions().get("versions", []))
        return RuntimeStatus(True, _find_cli() or sys.executable, "Camoufox runtime manager is available", active, versions)
    except Exception as exc:
        return RuntimeStatus(False, _find_cli(), f"Runtime manager unavailable: {exc}")


def ensure_runtime(*, fetch: bool = False, version: str | None = None) -> RuntimeStatus:
    current = status()
    if current.available and current.active_version and not fetch and not version:
        return current
    args = ["fetch"]
    if version:
        args.append(version)
    try:
        result = _run_camoufox(*args, timeout=900)
        if result.returncode != 0:
            return RuntimeStatus(False, current.executable, result.stderr.strip() or result.stdout.strip() or "Runtime fetch failed")
        return status()
    except Exception as exc:
        logger.exception("Camoufox runtime bootstrap failed")
        return RuntimeStatus(False, current.executable, f"Runtime bootstrap failed: {exc}")


def set_active(specifier: str) -> dict[str, Any]:
    if not specifier.strip():
        raise ValueError("Runtime specifier cannot be empty")
    result = _run_camoufox("set", specifier.strip(), timeout=120)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Could not set active browser runtime")
    return {"active": _parse_active(_run_camoufox("active", timeout=30).stdout), "output": result.stdout[-4000:]}


def install(specifier: str | None = None) -> dict[str, Any]:
    args = ["fetch"]
    if specifier:
        args.append(specifier)
    result = _run_camoufox(*args, timeout=900)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Could not install browser runtime")
    return {"output": result.stdout[-4000:], "active": _parse_active(_run_camoufox("active", timeout=30).stdout)}


def remove(specifier: str) -> dict[str, Any]:
    if not specifier.strip():
        raise ValueError("Runtime specifier cannot be empty")
    # Non-interactive safety: require explicit CLI yes if supported by upstream.
    result = _run_camoufox("remove", specifier.strip(), "-y", timeout=180)
    if result.returncode != 0:
        # Older releases may not accept -y. Never fall back to an interactive process in Desktop.
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Could not remove browser runtime")
    return {"output": result.stdout[-4000:]}
