from pathlib import Path

import triada_desktop.runtime_manager as runtime


def test_runtime_parser_accepts_version_lines():
    parsed = runtime._parse_installed("Installed versions\n135.0\n136.1\n")
    assert [x.version for x in parsed] == ["135.0", "136.1"]


def test_runtime_status_is_dataclass():
    status = runtime.RuntimeStatus(False, None, "unavailable")
    assert status.available is False
    assert status.installed_versions == ()
