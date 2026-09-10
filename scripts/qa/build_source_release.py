#!/usr/bin/env python3
"""Create a clean source-release ZIP without mutating the working tree.

The builder intentionally excludes local profile databases, browser/session data,
logs, backups, runtime caches and build artifacts so a release cannot carry over
developer desktop history.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXCLUDE_DIRS = {
    ".git", ".venv", "node_modules", ".next", "out", "dist", "build",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
}
DEFAULT_EXCLUDE_ROOT_DIRS = {"data", "logs", "backups", "cache", "temp", "runtime"}
DEFAULT_EXCLUDE_NAMES = {
    "profiles.db", "profiles.db-shm", "profiles.db-wal", "history.db",
    "app.log", "browser.log", "crash.log", "update.log",
}
DEFAULT_EXCLUDE_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".log", ".tnb", ".tnbx", ".cookies.json"}

def should_exclude(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if any(part in DEFAULT_EXCLUDE_DIRS for part in rel.parts):
        return True
    if rel.parts and rel.parts[0] in DEFAULT_EXCLUDE_ROOT_DIRS:
        return True
    if path.is_file():
        if path.name in DEFAULT_EXCLUDE_NAMES:
            return True
        if path.suffix.lower() in DEFAULT_EXCLUDE_SUFFIXES:
            return True
    return False

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--top-level", default=None)
    args = parser.parse_args()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    prefix = args.top_level or ROOT.name
    count = 0
    with ZipFile(output, "w", ZIP_DEFLATED, compresslevel=9) as zf:
        for path in ROOT.rglob("*"):
            if not path.is_file() or path.resolve() == output or should_exclude(path):
                continue
            arc = Path(prefix) / path.relative_to(ROOT)
            zf.write(path, arcname=arc.as_posix())
            count += 1
    print(f"Created clean source release: {output} ({count} files)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
