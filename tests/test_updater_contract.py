import json
from pathlib import Path
import pytest

from triada_desktop.updater import _normalize_channel, check_update, UpdateInfo


def test_channel_validation():
    assert _normalize_channel("stable") == "stable"
    assert _normalize_channel("beta") == "beta"
    with pytest.raises(ValueError):
        _normalize_channel("nightly")


def test_manifest_requires_matching_channel(monkeypatch, tmp_path):
    payload={"version":"9.9.9","channel":"beta","download_url":"https://example.invalid/a.exe","sha256":"0"*64}
    class FakeResponse:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def read(self,*args): return json.dumps(payload).encode()
    monkeypatch.setattr("triada_desktop.updater.urllib.request.urlopen", lambda *a, **k: FakeResponse())
    with pytest.raises(ValueError, match="channel mismatch"):
        check_update("https://example.invalid/manifest.json","1.0.0", channel="stable")


def test_version_parser_handles_v_prefix():
    from triada_desktop.updater import _v
    assert _v("v1.2.3") == (1,2,3)
