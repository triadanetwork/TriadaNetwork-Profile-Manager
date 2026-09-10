from __future__ import annotations

import base64
import json
import os
import secrets
import ctypes
from pathlib import Path
from ctypes import wintypes

from cryptography.fernet import Fernet

from .paths import config_dir

_STORE = config_dir() / "secrets.bin"


def _dpapi_protect(raw: bytes) -> bytes:
    if os.name != "nt":
        raise RuntimeError("DPAPI is only available on Windows")
    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]
    in_blob = DATA_BLOB(len(raw), ctypes.cast(ctypes.create_string_buffer(raw), ctypes.POINTER(ctypes.c_char)))
    out_blob = DATA_BLOB()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    if not crypt.CryptProtectData(ctypes.byref(in_blob), "Triada Network".encode("utf-16le"), None, None, None, 0, ctypes.byref(out_blob)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        ctypes.WinDLL("kernel32", use_last_error=True).LocalFree(out_blob.pbData)


def _dpapi_unprotect(raw: bytes) -> bytes:
    if os.name != "nt":
        raise RuntimeError("DPAPI is only available on Windows")
    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]
    buf = ctypes.create_string_buffer(raw)
    in_blob = DATA_BLOB(len(raw), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    out_blob = DATA_BLOB()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    if not crypt.CryptUnprotectData(ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        ctypes.WinDLL("kernel32", use_last_error=True).LocalFree(out_blob.pbData)


def _fallback_key() -> bytes:
    config_dir().mkdir(parents=True, exist_ok=True)
    key_file = config_dir() / "local.key"
    if not key_file.exists():
        key_file.write_bytes(Fernet.generate_key())
        try:
            os.chmod(key_file, 0o600)
        except OSError:
            pass
    return key_file.read_bytes()


def _encrypt(raw: bytes) -> bytes:
    if os.name == "nt":
        return b"DPAPI1" + _dpapi_protect(raw)
    return b"FERNET1" + Fernet(_fallback_key()).encrypt(raw)


def _decrypt(raw: bytes) -> bytes:
    if raw.startswith(b"DPAPI1"):
        return _dpapi_unprotect(raw[6:])
    if raw.startswith(b"FERNET1"):
        return Fernet(_fallback_key()).decrypt(raw[7:])
    raise ValueError("Unknown Triada secret-store format")


def _read() -> dict[str, str]:
    if not _STORE.exists():
        return {}
    try:
        return json.loads(_decrypt(_STORE.read_bytes()).decode("utf-8"))
    except Exception:
        return {}


def _write(values: dict[str, str]) -> None:
    payload = _encrypt(json.dumps(values, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    temp = _STORE.with_suffix(".tmp")
    temp.write_bytes(payload)
    temp.replace(_STORE)


def set_secret(name: str, value: str) -> None:
    values = _read()
    values[name] = value
    _write(values)


def get_secret(name: str) -> str | None:
    return _read().get(name)


def delete_secret(name: str) -> None:
    values = _read()
    if name in values:
        values.pop(name)
        _write(values)


def list_secret_names() -> list[str]:
    return sorted(_read())
