from __future__ import annotations
import os
from pathlib import Path
APP_NAME = "Triada Network"
def app_data_dir() -> Path:
    if os.name == "nt":
        root = os.getenv("LOCALAPPDATA")
        if root: return Path(root) / APP_NAME
    if os.name == "posix" and os.getenv("XDG_DATA_HOME"): return Path(os.environ["XDG_DATA_HOME"]) / "triada-network"
    if os.name == "posix" and os.getenv("HOME"): return Path(os.environ["HOME"]) / "Library" / "Application Support" / APP_NAME
    return Path.cwd() / ".triada"
def ensure_app_dirs() -> Path:
    root=app_data_dir()
    for name in ("logs","data","backups","cache","config","temp","runtime"): (root/name).mkdir(parents=True,exist_ok=True)
    return root
def _dir(name):
    p=app_data_dir()/name; p.mkdir(parents=True,exist_ok=True); return p
def logs_dir(): return _dir("logs")
def data_dir(): return _dir("data")
def backup_dir(): return _dir("backups")
def cache_dir(): return _dir("cache")
def config_dir(): return _dir("config")
def temp_dir(): return _dir("temp")
def runtime_dir(): return _dir("runtime")
