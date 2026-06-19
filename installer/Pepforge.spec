# -*- mode: python ; coding: utf-8 -*-
# Pepforge PyInstaller build spec.
# Build from the repository root with:
#   pyinstaller --clean --noconfirm installer/Pepforge.spec

from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).parent.parent
hiddenimports = []
hiddenimports += collect_submodules('suite_gui')
hiddenimports += collect_submodules('peptiforg_core')
hiddenimports += collect_submodules('apps.spps_planner_app')
hiddenimports += collect_submodules('apps.hotspot_finder.sequence_hotspot_finder')

a = Analysis(
    [str(ROOT / 'main_launcher.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / 'assets'), 'assets'),
        (str(ROOT / 'apps'), 'apps'),
        (str(ROOT / 'peptiforg_core'), 'peptiforg_core'),
        (str(ROOT / 'suite_gui'), 'suite_gui'),
        (str(ROOT / 'docs'), 'docs'),
        (str(ROOT / 'examples'), 'examples'),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pytest', 'setuptools.tests'],
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
