"""Enterprise first-run installation safety.

A fresh installation must never inherit a development/test database. Existing
installations are never silently reset; destructive reset remains an explicit
authenticated administrator operation.
"""
from __future__ import annotations
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

APP_NAME = "MK Pizza & Ice Bar"
MARKER_KEY = "installation_initialized"

def _utc():
    return datetime.now(timezone.utc).isoformat()

def _data_dir():
    root = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    path = Path(root) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path

def _marker_path():
    return _data_dir() / "installation.marker"

def is_initialized(db_path: str) -> bool:
    if _marker_path().exists():
        return True
    try:
        c = sqlite3.connect(db_path)
        row = c.execute("SELECT value FROM settings WHERE key=?", (MARKER_KEY,)).fetchone()
        c.close()
        return bool(row and row[0] == "1")
    except Exception:
        return False

def mark_initialized(db_path: str):
    c = sqlite3.connect(db_path)
    c.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT)")
    c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (MARKER_KEY, "1"))
    c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", ("initialized_at", _utc()))
    c.commit()
    c.close()
    _marker_path().write_text(_utc(), encoding="utf-8")

def needs_first_run(db_path: str) -> bool:
    return not is_initialized(db_path)

def reset_for_new_installation(db_path: str):
    """Only remove an uninitialized database; refuse to destroy live data."""
    if is_initialized(db_path):
        raise RuntimeError("Installation already initialized; use authenticated Admin Factory Reset.")
    for suffix in ("", "-wal", "-shm", "-journal"):
        path = Path(str(db_path) + suffix)
        if path.exists():
            path.unlink()
