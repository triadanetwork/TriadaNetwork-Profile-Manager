from __future__ import annotations

import base64
import hashlib
import json
import ssl
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from .paths import cache_dir

CHANNELS = {"stable", "beta"}

@dataclass(frozen=True)
class UpdateInfo:
    version: str
    download_url: str
    sha256: str
    signature: str | None = None
    channel: str = "stable"
    installer_args: tuple[str, ...] = ()


def _v(v: str):
    out = []
    for p in v.lstrip("v").split(".")[:3]:
        out.append(int("".join(c for c in p if c.isdigit()) or 0))
    return tuple(out + [0, 0, 0])[:3]


def _normalize_channel(channel: str | None) -> str:
    value = (channel or "stable").strip().lower()
    if value not in CHANNELS:
        raise ValueError(f"Unsupported update channel: {value}")
    return value


def check_update(manifest_url, current_version, public_key_b64=None, channel="stable"):
    channel = _normalize_channel(channel)
    if not manifest_url or not manifest_url.lower().startswith("https://"):
        raise ValueError("Update manifest must use HTTPS")
    req = urllib.request.Request(manifest_url, headers={"User-Agent": "TriadaNetwork-Updater/2"})
    with urllib.request.urlopen(req, timeout=10, context=ssl.create_default_context()) as r:
        data = json.load(r)

    version = str(data.get("version", ""))
    url = str(data.get("download_url", ""))
    sha = str(data.get("sha256", "")).lower()
    sig = data.get("signature")
    manifest_channel = _normalize_channel(data.get("channel", channel))
    if manifest_channel != channel:
        raise ValueError(f"Manifest channel mismatch: requested {channel}, got {manifest_channel}")
    installer_args = tuple(str(x) for x in data.get("installer_args", []))
    if not version or not url.startswith("https://") or len(sha) != 64:
        raise ValueError("Invalid update manifest")
    if _v(version) <= _v(current_version):
        return None

    if public_key_b64:
        if not sig:
            raise ValueError("Signed update manifest required")
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        payload_obj = {
            "version": version,
            "download_url": url,
            "sha256": sha,
            "channel": manifest_channel,
            "installer_args": list(installer_args),
        }
        payload = json.dumps(payload_obj, separators=(",", ":"), sort_keys=True).encode()
        try:
            Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64)).verify(
                base64.b64decode(sig), payload
            )
        except Exception as exc:
            raise ValueError(f"Update manifest signature verification failed: {exc}") from exc
    return UpdateInfo(version, url, sha, sig, manifest_channel, installer_args)


def download_verified(update: UpdateInfo) -> Path:
    target = cache_dir() / f"TriadaNetwork-{update.version}-{update.channel}.exe"
    req = urllib.request.Request(update.download_url, headers={"User-Agent": "TriadaNetwork-Updater/2"})
    with urllib.request.urlopen(req, timeout=120, context=ssl.create_default_context()) as r, target.open("wb") as out:
        h = hashlib.sha256()
        while True:
            chunk = r.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
            out.write(chunk)
    if h.hexdigest().lower() != update.sha256:
        target.unlink(missing_ok=True)
        raise ValueError("Update checksum mismatch")
    logger.info("Verified update package {}", target)
    return target
