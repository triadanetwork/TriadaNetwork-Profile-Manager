# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Triada Network desktop application."""
import os
from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

datas = [(os.path.join(ROOT, "src", "camoufox_pm", "webui"), "camoufox_pm/webui")]
binaries = []
hiddenimports = collect_submodules("uvicorn") + collect_submodules("triada_desktop")
for _pkg in ("camoufox", "browserforge", "apify_fingerprint_datapoints", "language_tags", "ua_parser", "pywebview", "pystray", "PIL"):
    try:
        _d, _b, _h = collect_all(_pkg)
        datas += _d
        binaries += _b
        hiddenimports += _h
    except Exception:
        pass

a = Analysis(
    [os.path.join(ROOT, "packaging", "launch.py")],
    pathex=[os.path.join(ROOT, "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TriadaNetwork",
    icon=os.path.join(ROOT, "packaging", "assets", "triada.ico"),
    console=False,
    disable_windowed_traceback=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="TriadaNetwork")
