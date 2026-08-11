# PyInstaller one-file Windows build for MK Pizza & Ice Bar POS.
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = [
    "win32print",
    "win32api",
    "serial",
    "serial.tools.list_ports",
    "PIL",
    "PIL.Image",
    "PIL.ImageTk",
    "bleak.backends.winrt",
]
# Bleak discovers platform backends dynamically.
try:
    hiddenimports += collect_submodules("bleak.backends")
except Exception:
    pass

a = Analysis(
    ["app.py"],
    pathex=["."],
    binaries=[],
    datas=[("assets", "assets")],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="MK_Pizza_Ice_Bar_POS",
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
    icon="assets/mk_pizza.ico",
)
