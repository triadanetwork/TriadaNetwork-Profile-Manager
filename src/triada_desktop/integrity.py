from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

from .paths import app_data_dir


def check_data_integrity() -> dict[str, Any]:
    root = app_data_dir()
    db = root / "data" / "profiles.db"
    profiles_root = root / "data" / "profiles"
    result: dict[str, Any] = {
        "ok": True,
        "database": {"path": str(db), "exists": db.exists(), "integrity": None},
        "profiles": {"referenced": 0, "directories": 0, "missing": [], "orphaned": []},
        "warnings": [],
    }
    if not db.exists():
        result["ok"] = False
        result["warnings"].append("Database file does not exist")
        return result
    with sqlite3.connect(str(db)) as conn:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()
        result["database"]["integrity"] = integrity[0] if integrity else None
        if not integrity or integrity[0] != "ok":
            result["ok"] = False
            result["warnings"].append("SQLite integrity check failed")
        rows = conn.execute("SELECT id, storage_path FROM profiles").fetchall()
    referenced = 0
    missing: list[str] = []
    for profile_id, storage_path in rows:
        referenced += 1
        p = Path(storage_path) if storage_path else profiles_root / str(profile_id)
        if not p.exists():
            missing.append(str(profile_id))
    directories = {p.name for p in profiles_root.iterdir() if p.is_dir()} if profiles_root.exists() else set()
    referenced_ids = {str(row[0]) for row in rows}
    orphaned = sorted(directories - referenced_ids)
    result["profiles"] = {
        "referenced": referenced,
        "directories": len(directories),
        "missing": missing[:200],
        "orphaned": orphaned[:200],
    }
    if missing or orphaned:
        result["ok"] = False
        if missing:
            result["warnings"].append(f"{len(missing)} profiles reference missing storage directories")
        if orphaned:
            result["warnings"].append(f"{len(orphaned)} orphaned profile directories detected")
    return result
