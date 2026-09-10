from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from .paths import app_data_dir, backup_dir

FORMAT_VERSION = 1


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def create_backup(include_browser_data: bool = False) -> Path:
    """Create a point-in-time local backup.

    The SQLite database is copied with SQLite's backup API, avoiding a torn WAL
    snapshot. Browser data is opt-in because it can contain sensitive sessions.
    """
    root = app_data_dir()
    db = root / "data" / "profiles.db"
    if not db.exists():
        raise FileNotFoundError(f"Database not found: {db}")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_root = backup_dir()
    backup_root.mkdir(parents=True, exist_ok=True)
    target = backup_root / f"triada-backup-{timestamp}.tnb"
    with tempfile.TemporaryDirectory(prefix="triada-backup-") as tmp:
        temp_root = Path(tmp)
        snapshot = temp_root / "profiles.db"
        source = sqlite3.connect(str(db))
        try:
            dest = sqlite3.connect(str(snapshot))
            try:
                source.backup(dest)
            finally:
                dest.close()
        finally:
            source.close()

        manifest = {
            "format_version": FORMAT_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "database_sha256": _sha256(snapshot),
            "include_browser_data": include_browser_data,
        }
        manifest_path = temp_root / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(snapshot, "profiles.db")
            archive.write(manifest_path, "manifest.json")
            if include_browser_data:
                profiles_root = root / "data" / "profiles"
                if profiles_root.exists():
                    for path in profiles_root.rglob("*"):
                        if path.is_file():
                            archive.write(path, str(Path("profiles") / path.relative_to(profiles_root)))

    logger.info("Created desktop backup {}", target)
    return target


def inspect_backup(archive_path: str | Path) -> dict:
    archive = Path(archive_path)
    with zipfile.ZipFile(archive, "r") as zf:
        if "manifest.json" not in zf.namelist() or "profiles.db" not in zf.namelist():
            raise ValueError("Invalid Triada backup: required files are missing")
        manifest = json.loads(zf.read("manifest.json"))
        if int(manifest.get("format_version", 0)) != FORMAT_VERSION:
            raise ValueError("Unsupported backup format version")
        extracted_db = Path(tempfile.mkstemp(prefix="triada-verify-", suffix=".db")[1])
        try:
            extracted_db.write_bytes(zf.read("profiles.db"))
            if _sha256(extracted_db) != manifest.get("database_sha256"):
                raise ValueError("Backup database checksum mismatch")
            with sqlite3.connect(str(extracted_db)) as conn:
                result = conn.execute("PRAGMA integrity_check").fetchone()
                if not result or result[0] != "ok":
                    raise ValueError("Backup SQLite integrity check failed")
        finally:
            extracted_db.unlink(missing_ok=True)
        return manifest


def restore_backup(archive_path: str | Path, *, include_browser_data: bool = False) -> None:
    """Restore a verified backup over local data. Call while no browsers run."""
    archive = Path(archive_path)
    manifest = inspect_backup(archive)
    root = app_data_dir() / "data"
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="triada-restore-") as tmp:
        staging = Path(tmp)
        with zipfile.ZipFile(archive, "r") as zf:
            zf.extract("profiles.db", staging)
            if include_browser_data or manifest.get("include_browser_data"):
                for name in zf.namelist():
                    if name.startswith("profiles/") and not name.endswith("/"):
                        rel = Path(name)
                        if rel.is_absolute() or ".." in rel.parts:
                            raise ValueError("Backup contains an unsafe profile path")
                        zf.extract(name, staging)
        source = staging / "profiles.db"
        target = root / "profiles.db"
        backup_old = root / "profiles.db.before-restore"
        if target.exists():
            shutil.copy2(target, backup_old)
        shutil.copy2(source, target)
        if include_browser_data or manifest.get("include_browser_data"):
            source_profiles = staging / "profiles"
            target_profiles = root / "profiles"
            if source_profiles.exists():
                target_profiles.mkdir(parents=True, exist_ok=True)
                for path in source_profiles.rglob("*"):
                    rel = path.relative_to(source_profiles)
                    dest = target_profiles / rel
                    if path.is_dir():
                        dest.mkdir(parents=True, exist_ok=True)
                    else:
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(path, dest)
    logger.warning("Restored desktop backup {}", archive)
