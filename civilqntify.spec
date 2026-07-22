# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for CivilQntify.

Build with:  pyinstaller civilqntify.spec
"""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# ── Paths ────────────────────────────────────────────────────────────
ROOT = os.path.abspath(SPECPATH)

# ── datas: bundle resource files & library data alongside the app ───
datas = (
    [
        (os.path.join(ROOT, "app", "resources"), os.path.join("app", "resources")),
    ]
    + collect_data_files("matplotlib", includes=["*.json", "*.png", "*.svg", "*.ttf"])
    + collect_data_files("reportlab", includes=["*.png", "*.jpg", "*.ttf", "*.pfb"])
)

# ── hiddenimports: dynamically collect all local & library submodules 
hiddenimports = (
    collect_submodules("app")
    + collect_submodules("concrete_mix")
    + collect_submodules("material_quantify")
    + collect_submodules("history")
    + collect_submodules("PyQt6")
    + [
        "matplotlib",
        "matplotlib.backends.backend_qtagg",
        "matplotlib.backends.backend_qt5agg",
        "reportlab",
        "reportlab.lib",
        "reportlab.platypus",
        "reportlab.pdfgen",
        "requests",
        "gspread",
        "sqlite3",
        "json",
        "csv",
    ]
)

a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tests",
        "pytest",
        "_pytest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ── Standalone Executable (.exe) ─────────────────────────────────────
exe_standalone = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="CivilQntify-Standalone",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # windowed mode (no console window)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# ── Directory Bundle (for Linux .deb/.rpm packaging) ────────────────
exe_dir = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CivilQntify",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe_dir,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="CivilQntify",
)
