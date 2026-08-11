"""Admin-only database reset tools.

The reset intentionally preserves the database schema and recreates an empty
POS dataset. A timestamped backup is created before destructive work, and the
current admin password is required as a second confirmation factor.
"""
import os
import shutil
import sqlite3
from datetime import datetime
import tkinter as tk
from tkinter import messagebox, simpledialog


def install(App):
    if getattr(App, "_database_reset_installed", False):
        return

    def _is_admin(self):
        role = str(self.user.get("role", "")).strip().lower()
        return role in {"admin", "owner"}

    def _reset_old_database(self):
        if not _is_admin(self):
            messagebox.showerror("Permission denied", "Only Admin or Owner can reset old POS data.", parent=self)
            return

        if not messagebox.askyesno(
            "Reset Old Database",
            "This will permanently remove old sales, purchases, customers, suppliers, inventory movements, payments, expenses, shifts and operational history.\n\nA backup will be created first. Continue?",
            icon="warning", parent=self,
        ):
            return

        username = str(self.user.get("username", ""))
        password = simpledialog.askstring(
            "Confirm Administrator",
            f"Enter the current password for '{username}' to continue:",
            show="*", parent=self,
        )
        if password is None:
            return
        try:
            verified = self.s.login(username, password)
        except Exception:
            verified = None
        if not verified:
            messagebox.showerror("Reset cancelled", "Administrator password is incorrect.", parent=self)
            return

        db_path = getattr(self.s, "path", None) or getattr(self.s, "db_path", None)
        if not db_path:
            db_path = getattr(__import__("pos_app"), "DB", "pos.db")
        db_path = os.path.abspath(db_path)
        backup_dir = os.path.join(os.path.dirname(db_path), "backups")
        os.makedirs(backup_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"pos_before_reset_{stamp}.db")

        try:
            self.s.c.commit()
            shutil.copy2(db_path, backup_path)

            # Keep the schema and system/configuration data, but remove all
            # business transactions and operational history. Products/users/
            # settings are retained so the POS remains immediately usable.
            preserve = {
                "users", "products", "settings", "tables", "staff", "riders",
            }
            rows = self.s.rows("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            self.s.c.execute("PRAGMA foreign_keys=OFF")
            for row in rows:
                table = row["name"]
                if table not in preserve:
                    self.s.q(f'DELETE FROM "{table.replace(chr(34), chr(34)*2)}"')
            self.s.q("DELETE FROM sqlite_sequence")
            self.s.c.commit()
            self.s.q("PRAGMA foreign_keys=ON")
            self.s.c.commit()

            # Record the reset after the destructive operation so there is an
            # audit marker in the fresh dataset.
            self.s.audit(self.user, "DATABASE_RESET", "database", None, f"Pre-reset backup: {backup_path}")
            messagebox.showinfo(
                "Database Reset Complete",
                "Old transactional data has been reset successfully.\n\n"
                f"Backup created at:\n{backup_path}\n\n"
                "Products, users, settings and master data were preserved.",
                parent=self,
            )
            self.show("Dashboard")
        except Exception as exc:
            try:
                self.s.c.rollback()
            except Exception:
                pass
            messagebox.showerror(
                "Reset failed",
                "The database reset could not be completed. The pre-reset backup was preserved.\n\n"
                f"Details: {exc}", parent=self,
            )

    def _database_reset_page(self):
        if not _is_admin(self):
            self.title("Database Reset", "Administrator access required.")
            tk.Label(self.bodyinner, text="Only Admin or Owner can access this function.", fg="#b91c1c").pack(anchor="w", pady=20)
            return
        self.title("Database Reset", "Reset old transactional data while preserving master data and configuration.")
        box = tk.LabelFrame(self.bodyinner, text="Danger Zone", padx=18, pady=18)
        box.pack(fill="x", pady=15)
        tk.Label(box, text="Reset old POS data", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        tk.Label(box, text=(
            "Creates a timestamped backup first, then removes historical sales, "
            "payments, purchases, stock movements, expenses, audit history and "
            "other operational transactions. Users, products, settings, tables, "
            "staff and riders are preserved."
        ), justify="left", wraplength=850).pack(anchor="w", pady=8)
        tk.Button(box, text="RESET OLD DATABASE", bg="#b91c1c", fg="white", activebackground="#991b1b", activeforeground="white", relief="flat", padx=18, pady=10, command=lambda: _reset_old_database(self)).pack(anchor="w", pady=(8, 0))
        tk.Label(self.bodyinner, text="A backup is mandatory and the current Admin/Owner password is required.", fg="#64748b").pack(anchor="w")

    App._reset_old_database = _reset_old_database
    App.page_database_reset = _database_reset_page
    if "Database Reset" not in App.NAV:
        App.NAV = list(App.NAV) + ["Database Reset"]
    App._database_reset_installed = True
