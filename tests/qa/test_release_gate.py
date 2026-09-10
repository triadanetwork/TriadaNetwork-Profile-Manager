"""Lightweight repository-level QA tests that do not require Camoufox/network."""
from pathlib import Path
import json
import tomllib

ROOT = Path(__file__).resolve().parents[2]


def test_versions_are_aligned():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = project["project"]["version"]
    desktop = (ROOT / "src/triada_desktop/__init__.py").read_text(encoding="utf-8")
    web = json.loads((ROOT / "web/package.json").read_text(encoding="utf-8"))["version"]
    lock = json.loads((ROOT / "web/package-lock.json").read_text(encoding="utf-8"))
    assert f'APP_VERSION = "{version}"' in desktop
    assert web == version
    assert lock["version"] == version
    assert lock["packages"][""]["version"] == version


def test_no_runtime_build_artifacts_in_source_tree():
    forbidden = {".venv", "node_modules", ".next", "out", "dist", "build", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
    # The repository-level release gate performs the strict filesystem check
    # before tests. This unit test ignores caches pytest itself may create while
    # collecting/running the suite.
    for path in ROOT.rglob("*"):
        if any(part in {".pytest_cache", "__pycache__"} for part in path.parts):
            continue
        assert not any(part in forbidden for part in path.parts), path


def test_desktop_packaging_is_triadanetwork():
    spec = (ROOT / "packaging/triada-network.spec").read_text(encoding="utf-8")
    assert 'name="TriadaNetwork"' in spec
    assert 'icon=os.path.join(ROOT, "packaging", "assets", "triada.ico")' in spec
    assert "console=False" in spec
