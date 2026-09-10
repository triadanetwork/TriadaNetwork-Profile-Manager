from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from .paths import app_data_dir

CURRENT_SCHEMA = 2
STATE_FILE = "config/local-schema.json"

@dataclass(frozen=True)
class MigrationState:
    version: int
    updated_at: str


def _state_path() -> Path:
    return app_data_dir() / STATE_FILE


def current_version() -> int:
    path = _state_path()
    if not path.exists():
        return 1
    try:
        return int(json.loads(path.read_text(encoding="utf-8")).get("version", 1))
    except Exception:
        logger.warning("Invalid local schema state; treating as version 1")
        return 1


def _write(version: int) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": version, "updated_at": datetime.now(timezone.utc).isoformat()}
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(path)


def plan() -> dict:
    version = current_version()
    pending = list(range(version + 1, CURRENT_SCHEMA + 1))
    return {"current": version, "target": CURRENT_SCHEMA, "pending": pending, "up_to_date": not pending}


def apply() -> MigrationState:
    version = current_version()
    if version > CURRENT_SCHEMA:
        raise RuntimeError(f"Local data schema {version} is newer than this application supports ({CURRENT_SCHEMA})")
    for target in range(version + 1, CURRENT_SCHEMA + 1):
        _apply_one(target)
        _write(target)
    return MigrationState(current_version(), datetime.now(timezone.utc).isoformat())


def _apply_one(target: int) -> None:
    # v2: normalize the expected local directory layout and create future-proof dirs.
    if target == 2:
        root = app_data_dir()
        for name in ("logs", "data", "backups", "cache", "config", "temp", "runtime", "quarantine", "updates"):
            (root / name).mkdir(parents=True, exist_ok=True)
        logger.info("Applied local data migration v2")
        return
    raise RuntimeError(f"Unknown local migration {target}")
