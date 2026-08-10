"""Persist POS database outside the PyInstaller one-file extraction directory."""
import os

APP_NAME = "MK Pizza & Ice Bar"

def install(pos_app):
    if getattr(pos_app, "_persistent_data_installed", False):
        return pos_app
    root = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    data_dir = os.path.join(root, APP_NAME)
    os.makedirs(data_dir, exist_ok=True)
    db_path = os.path.join(data_dir, "pos.db")
    original_db = getattr(pos_app, "DB", "")
    original_init = pos_app.Store.__init__

    def store_init(self, path=None):
        if path is None or path == original_db:
            path = db_path
        return original_init(self, path)

    pos_app.Store.__init__ = store_init
    pos_app.DB = db_path
    pos_app.APP_DATA_DIR = data_dir
    pos_app._persistent_data_installed = True
    return pos_app
