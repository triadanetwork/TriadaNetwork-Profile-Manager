from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from loguru import logger

from .backup import inspect_backup
from .paths import app_data_dir
from .integrity import check_data_integrity


def recovery_status() -> dict[str, Any]:
    root = app_data_dir()
    before = root / "data" / "profiles.db.before-restore"
    quarantine = root / "quarantine"
    reports = []
    if before.exists():
        reports.append({"type": "pre_restore_database", "path": str(before), "size": before.stat().st_size})
    return {"integrity": check_data_integrity(), "rollback_available": before.exists(), "quarantine_entries": len([p for p in quarantine.iterdir() if p.exists()]) if quarantine.exists() else 0, "artifacts": reports}


def rollback_last_restore() -> dict[str, Any]:
    root = app_data_dir()
    data = root / "data"
    current = data / "profiles.db"
    previous = data / "profiles.db.before-restore"
    if not previous.exists():
        raise FileNotFoundError("No pre-restore database is available")
    backup = data / "profiles.db.before-rollback"
    if current.exists():
        shutil.copy2(current, backup)
    shutil.copy2(previous, current)
    logger.warning("Rolled back local database to the last pre-restore snapshot")
    return {"restored": True, "database": str(current), "rollback_backup": str(backup)}


def quarantine_orphans() -> dict[str, Any]:
    report = check_data_integrity()
    root = app_data_dir()
    profiles_root = root / "data" / "profiles"
    quarantine = root / "quarantine" / "profiles"
    quarantine.mkdir(parents=True, exist_ok=True)
    moved = []
    for profile_id in report.get("profiles", {}).get("orphaned", []):
        src = profiles_root / str(profile_id)
        if not src.exists():
            continue
        dst = quarantine / str(profile_id)
        if dst.exists():
            dst = quarantine / f"{profile_id}-{int(src.stat().st_mtime)}"
        shutil.move(str(src), str(dst))
        moved.append(str(dst))
    return {"moved": moved, "count": len(moved)}


def verify_backup_for_restore(path: str | Path) -> dict[str, Any]:
    manifest = inspect_backup(path)
    return {"verified": True, "manifest": manifest}
