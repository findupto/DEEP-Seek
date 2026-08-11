# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# PyInstaller may evaluate a spec from a temporary working directory.  The
# build script always starts in the repository root, so use cwd as the stable
# project root instead of SPECPATH-relative traversal.
ROOT = Path.cwd().resolve()
ENTRY = ROOT / 'run_pos.py'
if not ENTRY.exists():
    raise SystemExit(f'ERROR: POS launcher not found: {ENTRY}')

hiddenimports = collect_submodules('PIL') + collect_submodules('reportlab')

datas = []
for pkg in ('PIL', 'reportlab'):
    try:
        datas += collect_data_files(pkg)
    except Exception:
        pass

for folder in ('assets', 'templates', 'pwa'):
    p = ROOT / folder
    if p.exists():
        datas.append((str(p), folder))

a = Analysis(
    [str(ENTRY)],
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
