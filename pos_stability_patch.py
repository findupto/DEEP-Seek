"""Final stability, data-safety and Windows UX layer for MK Pizza & Ice Bar POS.

This patch is intentionally additive: it does not replace the existing pages or
rewrite business data. It hardens the SQLite connection, application shutdown,
backup, unexpected callback errors and the login/main-window icon.
"""
import os
import sqlite3
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, filedialog

APP_NAME = "MK Pizza & Ice Bar"


def _data_dir():
    root = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    path = Path(root) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def _icon_path():
    import sys
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "assets", "mk_pizza.ico")


def install(App, Store=None, Login=None):
    if getattr(App, "_pos_stability_patch", False):
        return App

    # SQLite connection hardening. No schema/data is removed or reset.
    if Store is not None and not getattr(Store, "_stability_store_patch", False):
        old_store_init = Store.__init__

        def store_init(self, path=None):
            old_store_init(self, path)
            try:
                self.c.execute("PRAGMA busy_timeout=5000")
                self.c.execute("PRAGMA foreign_keys=ON")
                self.c.commit()
            except Exception:
                pass

        Store.__init__ = store_init
        Store._stability_store_patch = True

    # Safe, SQLite-native backup. Copying a live DB file can miss journal data.
    old_backup = getattr(App, "backup", None)
    if old_backup and not getattr(App, "_safe_backup_patch", False):
        def backup(self):
            path = filedialog.asksaveasfilename(
                defaultextension=".db",
                initialfile="pos-backup.db",
                filetypes=[("SQLite database", "*.db")],
                parent=self,
                title="Backup POS Database",
            )
            if not path:
                return
            try:
                dest = sqlite3.connect(path)
                try:
                    self.s.c.commit()
                    self.s.c.backup(dest)
                finally:
                    dest.close()
                messagebox.showinfo("Backup", "Database backup created successfully.", parent=self)
            except Exception as exc:
                messagebox.showerror("Backup failed", str(exc), parent=self)

        App.backup = backup
        App._safe_backup_patch = True

    # Keep financial data internally consistent: payments against a credit sale
    # reduce the customer's outstanding balance exactly once.
    old_init = App.__init__
    if not getattr(App, "_credit_payment_trigger_patch", False):
        def init(self, *args, **kwargs):
            old_init(self, *args, **kwargs)
            try:
                self.s.c.executescript("""
                CREATE TRIGGER IF NOT EXISTS trg_credit_payment_customer_balance
                AFTER INSERT ON payments
                WHEN (SELECT payment_method FROM sales WHERE id=NEW.sale_id)='Credit'
                  AND (SELECT customer_id FROM sales WHERE id=NEW.sale_id) IS NOT NULL
                BEGIN
                    UPDATE customers
                    SET balance=MAX(0, COALESCE(balance,0)-NEW.amount)
                    WHERE id=(SELECT customer_id FROM sales WHERE id=NEW.sale_id);
                END;

                CREATE TRIGGER IF NOT EXISTS trg_prevent_negative_stock
                BEFORE UPDATE OF stock ON products
                WHEN NEW.stock < -0.000001
                BEGIN
                    SELECT RAISE(ABORT, 'Insufficient stock.');
                END;
                """)
                self.s.c.commit()
            except Exception:
                # Existing installations may contain legacy schema differences;
                # the application remains usable even if a safety trigger cannot
                # be installed.
                pass

        App.__init__ = init
        App._credit_payment_trigger_patch = True

    # Main-window cleanup prevents printer sockets/BLE clients from surviving
    # after the Tk root is closed.
    if not getattr(App, "_safe_close_patch", False):
        def close(self):
            try:
                pm = getattr(self, "pm", None)
                if pm is not None:
                    pm.disconnect()
            except Exception:
                pass
            try:
                db = getattr(self, "s", None)
                if db is not None:
                    db.c.commit()
                    db.c.close()
            except Exception:
                pass
            try:
                self.destroy()
            except Exception:
                pass

        App._pos_close = close
        App._safe_close_patch = True

    # Unexpected Tk callback errors are logged instead of disappearing, while
    # the operator gets a concise message rather than a raw Tcl traceback.
    if not getattr(App, "_callback_error_patch", False):
        def report_callback_exception(self, exc, val, tb):
            text = "".join(traceback.format_exception(exc, val, tb))
            try:
                log = _data_dir() / "pos_errors.log"
                with log.open("a", encoding="utf-8") as fh:
                    fh.write("\n" + "=" * 80 + "\n" + text)
            except Exception:
                pass
            try:
                if self.winfo_exists():
                    messagebox.showerror(
                        "POS Error",
                        "The action could not be completed.\n\n"
                        "Details were saved to the POS error log.\n\n"
                        + str(val),
                        parent=self,
                    )
            except Exception:
                pass

        App.report_callback_exception = report_callback_exception
        App._callback_error_patch = True

    # Install the MK icon on both login and main windows. PyInstaller's
    # _MEIPASS path is supported by _icon_path().
    def apply_icon(window):
        path = _icon_path()
        if os.path.exists(path):
            try:
                window.iconbitmap(path)
                window._mk_icon_path = path
            except tk.TclError:
                pass

    if Login is not None and not getattr(Login, "_mk_icon_login_patch", False):
        old_login_init = Login.__init__
        def login_init(self, *args, **kwargs):
            old_login_init(self, *args, **kwargs)
            apply_icon(self)
        Login.__init__ = login_init
        Login._mk_icon_login_patch = True

    old_app_init = App.__init__
    if not getattr(App, "_mk_icon_stability_patch", False):
        def app_init(self, *args, **kwargs):
            old_app_init(self, *args, **kwargs)
            apply_icon(self)
            self.protocol("WM_DELETE_WINDOW", self._pos_close)
        App.__init__ = app_init
        App._mk_icon_stability_patch = True

    App._pos_stability_patch = True
    return App
