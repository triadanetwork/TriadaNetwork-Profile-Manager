from pathlib import Path

from triada_desktop import integrity


def test_integrity_reports_missing_database(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(integrity, "app_data_dir", lambda: tmp_path)
    result = integrity.check_data_integrity()
    assert result["ok"] is False
    assert result["database"]["exists"] is False
