from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from .paths import app_data_dir
from .updater import UpdateInfo, check_update, download_verified


def _updates_dir() -> Path:
    p = app_data_dir() / "updates"
    p.mkdir(parents=True, exist_ok=True)
    return p


def check(manifest_url: str | None, current_version: str, public_key_b64: str | None = None, channel: str = "stable") -> dict:
    if not manifest_url:
        return {"configured": False, "update_available": False, "channel": channel}
    info = check_update(manifest_url, current_version, public_key_b64, channel)
    return {
        "configured": True,
        "update_available": info is not None,
        "channel": channel,
        "version": info.version if info else current_version,
        "download_url": info.download_url if info else None,
        "sha256": info.sha256 if info else None,
        "installer_args": list(info.installer_args) if info else [],
    }


def stage(info: UpdateInfo) -> dict:
    path = download_verified(info)
    staging = _updates_dir()
    target = staging / path.name
    shutil.copy2(path, target)
    marker = staging / "pending-update.json"
    marker.write_text(
        json.dumps(
            {
                "version": info.version,
                "channel": info.channel,
                "package": str(target),
                "staged_at": datetime.now(timezone.utc).isoformat(),
                "sha256": info.sha256,
                "installer_args": list(info.installer_args),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    logger.info("Staged Triada update {} at {}", info.version, target)
    return {"staged": True, "version": info.version, "channel": info.channel, "package": str(target), "marker": str(marker)}


def pending() -> dict | None:
    marker = _updates_dir() / "pending-update.json"
    if not marker.exists():
        return None
    try:
        return json.loads(marker.read_text(encoding="utf-8"))
    except Exception:
        return None


def clear_pending() -> None:
    (_updates_dir() / "pending-update.json").unlink(missing_ok=True)


def install_pending() -> dict:
    marker = pending()
    if not marker:
        raise FileNotFoundError("No pending update")
    package = Path(str(marker.get("package", ""))).resolve()
    if not package.exists() or package.stat().st_size < 1024 * 1024:
        raise ValueError("Staged update package is missing or invalid")
    sha = str(marker.get("sha256", "")).lower()
    import hashlib
    h = hashlib.sha256(package.read_bytes()).hexdigest()
    if h != sha:
        raise ValueError("Staged update checksum mismatch")

    args = [str(a) for a in marker.get("installer_args", [])]
    if os.name != "nt" or package.suffix.lower() != ".exe":
        raise RuntimeError("Automatic install is currently supported only for verified Windows installer EXE packages")

    subprocess.Popen([str(package), *args, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS"], close_fds=True)
    logger.info("Launched verified installer update {}", marker.get("version"))
    return {"install_started": True, "version": marker.get("version"), "channel": marker.get("channel", "stable")}


def rollback_marker() -> dict | None:
    marker = _updates_dir() / "rollback.json"
    if not marker.exists():
        return None
    try:
        return json.loads(marker.read_text(encoding="utf-8"))
    except Exception:
        return None
