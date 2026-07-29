# -*- mode: python ; coding: utf-8 -*-
# ruff: noqa: UP009, F821

import platform

from PyInstaller.utils.hooks import collect_all, collect_submodules

if platform.system() == "Windows":
    hiddenimports = ["winloop"]
else:
    hiddenimports = ["uvloop"]

datas = [("assets", "assets")]
binaries = []
hiddenimports += collect_submodules("proxhy")
tmp_ret = collect_all("numba")
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]


a = Analysis(
    ["launcher.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="proxhy",
    debug=False,
    bootloader_ignore_signals=True,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
