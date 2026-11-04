# -*- mode: python ; coding: utf-8 -*-
"""Empacotamento Windows one-file do CryptoVault Desktop."""

from pathlib import Path

ROOT = Path(SPECPATH).resolve()
ICON = ROOT / "cryptovault" / "resources" / "logo.ico"
RESOURCES = ROOT / "cryptovault" / "resources"

a = Analysis(
    [str(ROOT / "cryptovault" / "__main__.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[(str(RESOURCES), "cryptovault/resources")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "unittest", "pydoc", "doctest"],
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
    name="CryptoVault",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON),
    version=str(ROOT / "installer" / "version_info.txt"),
)
