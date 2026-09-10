#!/usr/bin/env python3
"""Deterministic QA/release gate for Triada Network source releases.

This gate never launches Camoufox or makes network calls. It validates the
properties that can be proven from a clean source tree before CI performs the
full dependency-backed test suite.
"""
from __future__ import annotations

import ast
import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_DIRS = {".venv", "node_modules", ".next", "out", "dist", "build", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
FORBIDDEN_FILES = {"profiles.db", "profiles.db-shm", "profiles.db-wal", "app.log", "browser.log", "crash.log", "update.log", "history.db"}
FORBIDDEN_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".log", ".tnb", ".tnbx", ".cookies.json"}


def fail(msg: str) -> None:
    raise SystemExit(f"QA GATE FAILED: {msg}")


def check_python() -> None:
    errors: list[str] = []
    for path in ROOT.joinpath("src").rglob("*.py"):
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            errors.append(f"{path}: {exc}")
    if errors:
        fail("Python AST errors: " + " | ".join(errors[:10]))


def check_versions() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = project["project"]["version"]
    desktop = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', (ROOT / "src/triada_desktop/__init__.py").read_text())
    web_data = json.loads((ROOT / "web/package.json").read_text(encoding="utf-8"))
    web = web_data["version"]
    lock_data = json.loads((ROOT / "web/package-lock.json").read_text(encoding="utf-8"))
    lock = lock_data["version"]
    if not desktop or desktop.group(1) != version:
        fail(f"desktop version drift: {desktop.group(1) if desktop else 'missing'} != {version}")
    if web != version:
        fail(f"web version drift: {web} != {version}")
    if lock != version or lock_data.get("packages", {}).get("", {}).get("version") != version:
        fail(f"package-lock version drift: {lock} != {version}")
    if not re.fullmatch(r"2\.3\.0-rc\.1", version):
        fail(f"release gate expected 2.3.0-rc.1, found {version}")


def check_frontend_sources() -> None:
    bad: list[str] = []
    for suffix in ("*.ts", "*.tsx"):
        for path in ROOT.joinpath("web/src").rglob(suffix):
            text = path.read_text(encoding="utf-8")
            if "\\n" in text.splitlines()[0:3].__str__():
                bad.append(f"{path}: suspicious literal \\n near top of file")
            if "next/font/google" in text:
                bad.append(f"{path}: next/font/google is not allowed in desktop build")
    if bad:
        fail("frontend source checks: " + " | ".join(bad[:10]))


def check_release_tree() -> None:
    for path in ROOT.rglob("*"):
        if any(part in FORBIDDEN_DIRS for part in path.parts):
            fail(f"forbidden release directory: {path}")
        if path.is_file() and path.name in FORBIDDEN_FILES:
            fail(f"runtime/history artifact in source release: {path}")
        if path.is_file() and path.suffix.lower() in FORBIDDEN_SUFFIXES:
            fail(f"sensitive/user-state artifact in source release: {path}")


def check_pyproject() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    scripts = data["project"]["scripts"]
    if scripts.get("triada-network") != "camoufox_pm.cli:main":
        fail("triada-network entry point drift")
    if "triada-network =" not in (ROOT / "pyproject.toml").read_text(encoding="utf-8"):
        fail("triada-network console script missing")


def main() -> int:
    check_python()
    check_versions()
    check_frontend_sources()
    check_release_tree()
    check_pyproject()
    print("QA release gate: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
