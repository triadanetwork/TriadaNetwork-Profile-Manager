from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import zipfile
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

MAGIC = b"TRIADA-BUNDLE-1\0"
PBKDF2_ITERS = 600_000


def _key(password: str, salt: bytes) -> bytes:
    if not isinstance(password, str) or len(password) < 8:
        raise ValueError("Password must contain at least 8 characters")
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=PBKDF2_ITERS)
    return kdf.derive(password.encode("utf-8"))


def encrypt_payload(payload: bytes, password: str, *, kind: str = "triada-data") -> bytes:
    salt = os.urandom(16)
    nonce = os.urandom(12)
    key = _key(password, salt)
    aad = MAGIC + kind.encode("utf-8")
    ciphertext = AESGCM(key).encrypt(nonce, payload, aad)
    envelope = {
        "format": 1,
        "kind": kind,
        "kdf": "PBKDF2-HMAC-SHA256",
        "iterations": PBKDF2_ITERS,
        "cipher": "AES-256-GCM",
        "salt": base64.b64encode(salt).decode(),
        "nonce": base64.b64encode(nonce).decode(),
        "aad": base64.b64encode(aad).decode(),
        "ciphertext": base64.b64encode(ciphertext).decode(),
    }
    return MAGIC + json.dumps(envelope, separators=(",", ":")).encode("utf-8")


def decrypt_payload(bundle: bytes, password: str, *, expected_kind: str | None = None) -> bytes:
    if not bundle.startswith(MAGIC):
        raise ValueError("Invalid Triada encrypted bundle")
    envelope = json.loads(bundle[len(MAGIC):].decode("utf-8"))
    if int(envelope.get("format", 0)) != 1:
        raise ValueError("Unsupported encrypted bundle format")
    kind = str(envelope.get("kind", ""))
    if expected_kind and kind != expected_kind:
        raise ValueError(f"Unexpected bundle kind: {kind}")
    if int(envelope.get("iterations", 0)) < 100_000:
        raise ValueError("Encrypted bundle KDF parameters are too weak")
    salt = base64.b64decode(envelope["salt"])
    nonce = base64.b64decode(envelope["nonce"])
    aad = base64.b64decode(envelope["aad"])
    ciphertext = base64.b64decode(envelope["ciphertext"])
    key = _key(password, salt)
    try:
        return AESGCM(key).decrypt(nonce, ciphertext, aad)
    except Exception as exc:
        raise ValueError("Wrong password or corrupted encrypted bundle") from exc


def build_encrypted_zip(files: dict[str, bytes], password: str, *, kind: str) -> bytes:
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, "w", zipfile.ZIP_DEFLATED) as zf:
        manifest = {"format_version": 1, "kind": kind, "files": []}
        for name, content in files.items():
            clean = Path(name).name
            digest = hashlib.sha256(content).hexdigest()
            manifest["files"].append({"name": clean, "sha256": digest, "size": len(content)})
            zf.writestr(clean, content)
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
    return encrypt_payload(raw.getvalue(), password, kind=kind)


def read_encrypted_zip(bundle: bytes, password: str, *, kind: str) -> dict[str, bytes]:
    raw = decrypt_payload(bundle, password, expected_kind=kind)
    result: dict[str, bytes] = {}
    with zipfile.ZipFile(io.BytesIO(raw), "r") as zf:
        names = zf.namelist()
        if "manifest.json" not in names:
            raise ValueError("Encrypted bundle manifest missing")
        manifest = json.loads(zf.read("manifest.json"))
        expected = {entry["name"]: entry for entry in manifest.get("files", [])}
        for name in names:
            if name == "manifest.json" or name.endswith("/"):
                continue
            clean = Path(name).name
            if clean not in expected:
                raise ValueError("Encrypted bundle contains an unlisted file")
            data = zf.read(name)
            if hashlib.sha256(data).hexdigest() != expected[clean]["sha256"]:
                raise ValueError(f"Checksum mismatch for {clean}")
            result[clean] = data
    return result
