from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_source_release_contains_no_user_history_state():
    forbidden_dirs = {".venv", "node_modules", ".next", "out", "dist", "build", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
    forbidden_root_dirs = {"data", "logs", "backups", "cache", "temp", "runtime"}
    forbidden_names = {"profiles.db", "profiles.db-shm", "profiles.db-wal", "history.db", "app.log", "browser.log", "crash.log", "update.log"}
    forbidden_suffixes = {".db", ".sqlite", ".sqlite3", ".log", ".tnb", ".tnbx", ".cookies.json"}
    for path in ROOT.rglob("*"):
        rel = path.relative_to(ROOT)
        if any(part in forbidden_dirs for part in rel.parts) or (rel.parts and rel.parts[0] in forbidden_root_dirs):
            if any(part in {".git", ".github"} for part in rel.parts):
                continue
            if ".pytest_cache" in rel.parts or "__pycache__" in rel.parts:
                continue
            raise AssertionError(f"user/runtime state in source tree: {path}")
        if path.is_file():
            assert path.name not in forbidden_names, path
            assert path.suffix.lower() not in forbidden_suffixes, path


def test_release_is_candidate_version():
    import tomllib
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["version"] == "2.3.0-rc.1"
