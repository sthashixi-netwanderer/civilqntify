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

# ──_datas: bundle resource files alongside the app ──────────────────
# The styles module resolves paths relative to its own __file__, so we
# add the resources folder at the same relative location (app/resources).
datas = [
    (os.path.join(ROOT, "app", "resources"), os.path.join("app", "resources")),
]

# ──hiddenimports: ensure all local packages are found ───────────────
hiddenimports = [
    "concrete_mix",
    "concrete_mix.codes",
    "concrete_mix.codes.aci211",
    "concrete_mix.codes.is10262",
    "concrete_mix.codes.doe",
    "concrete_mix.codes.base",
    "concrete_mix.engine",
    "concrete_mix.estimators",
    "concrete_mix.export",
    "concrete_mix.models",
    "concrete_mix.utils",
    "concrete_mix.validation",
    "material_quantify",
    "material_quantify.engine",
    "material_quantify.models",
    "history",
    "history.db",
    "history.serializers",
    "app",
    "app.main",
    "app.styles",
    "app.unit_preferences",
    "app.widgets",
    "app.widgets.concrete_tab",
    "app.widgets.material_quantify_tab",
    "app.widgets.cost_estimation_tab",
    "app.widgets.history_tab",
    "app.widgets.history_detail_dialog",
    "app.widgets.report_preview_dialog",
    "app.widgets.settings_dialog",
    "app.widgets.info_button",
    "app.widgets.result_panel",
    "app.widgets.quant_result_panel",
    "app.widgets.cost_result_panel",
    "app.workers",
    "app.workers.mix_design_worker",
    "app.workers.quantification_worker",
    "app.pricing",
    "app.pricing.price_sheet_service",
    "app.pricing.price_sheet_worker",
    # Optional live-pricing dependency (only needed if configured in Settings):
    "gspread",
]

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

