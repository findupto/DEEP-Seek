# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

ROOT = Path(SPECPATH).resolve().parents[2]

hiddenimports = collect_submodules('PIL') + collect_submodules('reportlab')

datas = []
for pkg in ('PIL', 'reportlab'):
    try:
        datas += collect_data_files(pkg)
    except Exception:
        pass

# Keep application assets/config templates available to the frozen app.
for folder in ('assets', 'templates', 'pwa'):
    p = ROOT / folder
    if p.exists():
        datas.append((str(p), folder))

# The launcher is the canonical entry point because it installs the additive
# enterprise/refund/database-reset/provider layers before starting the UI.
a = Analysis(
    [str(ROOT / 'run_pos.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pytest', 'jupyter', 'notebook'],
    noarchive=False,
)

pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='DEEP-Seek POS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
