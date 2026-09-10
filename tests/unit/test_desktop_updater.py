from pathlib import Path

import pytest

from triada_desktop.updater import check_update


def test_update_manifest_requires_https():
    with pytest.raises(ValueError, match="HTTPS"):
        check_update("http://updates.example/manifest.json", "2.1.0")


def test_malformed_update_manifest_is_rejected(monkeypatch):
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self, *args):
            return b'{"version":"2.2.0"}'

    monkeypatch.setattr("triada_desktop.updater.urllib.request.urlopen", lambda *args, **kwargs: Response())
    with pytest.raises(ValueError, match="Invalid update manifest"):
        check_update("https://updates.example/manifest.json", "2.1.0")
