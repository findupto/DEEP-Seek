"""Compatibility hook for printer persistence.

PrinterManager now owns COM, Windows spooler and BLE-GATT transport logic.
This module only normalizes the configuration path and migrates an older
working-directory config when one exists. It intentionally does not monkey-
patch PrinterManager a second time.
"""
import json
import shutil
from pathlib import Path


def install_printer(printer_manager_module):
    app_dir = Path(__file__).resolve().parent
    config_path = app_dir / "printer_config.json"
    old_cwd_path = Path.cwd() / "printer_config.json"
    if not config_path.exists() and old_cwd_path.exists() and old_cwd_path != config_path:
        try:
            shutil.copy2(old_cwd_path, config_path)
        except Exception:
            pass
    printer_manager_module.CONFIG_PATH = config_path
    return printer_manager_module


def install_ui(App):
    # Canonical UI is installed by canonical_ui_patch.py.
    return App
