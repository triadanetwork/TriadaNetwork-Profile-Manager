from pathlib import Path

from triada_desktop import migrations


def test_migration_plan_from_fresh_state(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(migrations, "app_data_dir", lambda: tmp_path)
    plan = migrations.plan()
    assert plan["current"] == 1
    assert plan["target"] == migrations.CURRENT_SCHEMA
    assert plan["pending"] == [2]


def test_migration_apply_creates_required_directories(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(migrations, "app_data_dir", lambda: tmp_path)
    state = migrations.apply()
    assert state.version == migrations.CURRENT_SCHEMA
    for name in ("logs", "data", "backups", "cache", "config", "temp", "runtime", "quarantine", "updates"):
        assert (tmp_path / name).is_dir()
