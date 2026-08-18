# -*- mode: python ; coding: utf-8 -*-
"""Pepforge V3.0.0 lightweight PyInstaller spec.

This spec deliberately packages only the desktop runtime. Research/training
stacks (xgboost, scikit-learn training modules, torch/ESM, Streamlit, pytest)
are not collected into the standard Pepforge EXE.
"""
from pathlib import Path

SPEC_DIR = Path(SPECPATH).resolve()
ROOT = SPEC_DIR.parent
PDE = ROOT / 'apps' / 'peptide_design_engine' / 'Python'
SPPS_APP = ROOT / 'apps' / 'spps_planner_app'
HOTSPOT_APP = ROOT / 'apps' / 'hotspot_finder'

# main_launcher imports tool GUIs lazily, so only those entry modules need to be
# declared here. PyInstaller then follows their normal imports recursively.
hiddenimports = [
    'suite_gui.hotspot_gui',
    'suite_gui.spps_tk_gui',
    'spps_v4_gui.spps_tk_gui',
    'spps_v4_gui.release',
    'spps_v4_gui.controller',
    'spps_v4_gui.experimental_workflow',
    'spps_v4_gui.experimental_data',
    'spps_v4_gui.condition_optimizer_v4',
    'spps_v4_gui.ml_advisor_v4',
    'suite_gui.docking_workbench_gui',
    'suite_gui.external_tools_guide',
    'suite_gui.pymol_structure_builder_gui',
    'peptiforg_core.workflow_gui',
    'desktop_gui',
    'peptide_engine',
    'data_manager',
    'ml_trainer',
    'external_parsers',
    'spps_planner.engine',
    'spps_planner.parser',
    'spps_planner.export',
    'sequence_hotspot_finder.engine',
]

# Keep optional research/training dependencies out of the default executable.
# They remain installable separately from the research/ML requirement files.
excludes = [
    'xgboost',
    'sklearn',
    'scikit_learn',
    'torch',
    'torchvision',
    'torchaudio',
    'esm',
    'streamlit',
    'dask',
    'numba',
    'hypothesis',
    'pytest',
    '_pytest',
    'setuptools.tests',
]

a = Analysis(
    [str(ROOT / 'main_launcher.py')],
    pathex=[str(ROOT), str(PDE), str(SPPS_APP), str(HOTSPOT_APP)],
    binaries=[],
    datas=[
        (str(ROOT / 'assets'), 'assets'),
        (str(ROOT / 'apps'), 'apps'),
        (str(ROOT / 'peptiforg_core'), 'peptiforg_core'),
        (str(ROOT / 'suite_gui'), 'suite_gui'),
        (str(ROOT / 'spps_v4_gui'), 'spps_v4_gui'),
        (str(ROOT / 'docs'), 'docs'),
        (str(ROOT / 'examples'), 'examples'),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Pepforge',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(ROOT / 'assets' / 'Pepforge_Icon.ico'),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Pepforge',
)
