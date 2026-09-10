from pathlib import Path
import zipfile

from triada_desktop.backup import inspect_backup


def test_inspect_backup_rejects_missing_manifest(tmp_path: Path):
    archive = tmp_path / "bad.tnb"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("profiles.db", b"not a database")
    try:
        inspect_backup(archive)
    except ValueError as exc:
        assert "required files" in str(exc)
    else:
        raise AssertionError("invalid backup must be rejected")
