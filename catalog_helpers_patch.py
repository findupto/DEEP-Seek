"""Expose and harden catalog category/modifier handlers for the final catalog page."""
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog


def install(App):
    if getattr(App, "_catalog_helpers_patch", False):
        return App

    def init_catalog_helpers(self):
        self.s.c.executescript(
            """
            CREATE TABLE IF NOT EXISTS product_categories(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                active INTEGER DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS product_modifiers(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                active INTEGER DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS product_modifier_items(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                modifier_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                price_delta REAL DEFAULT 0,
                active INTEGER DEFAULT 1
            );
            """
        )
        self.s.c.commit()

    def categories(self):
        init_catalog_helpers(self)
        w = self.dialog("Menu Categories", 560, 460)
        f = ttk.Frame(w, padding=14)
        f.pack(fill="both", expand=True)

        t = self.table(
            f,
            ("id", "name", "status"),
            {"id": "ID", "name": "Category", "status": "Status"},
            14,
        )

        def reload_():
            t.delete(*t.get_children())
            for r in self.s.rows(
                "SELECT id,name,active FROM product_categories ORDER BY active DESC,name"
            ):
                t.insert(
                    "",
                    "end",
                    iid=str(r["id"]),
                    values=(
                        r["id"],
                        r["name"],
                        "Active" if r["active"] else "Archived",
                    ),
                )

        def add_():
            n = simpledialog.askstring(
                "Category",
                "Category name:",
                parent=w,
            )
            if not n or not n.strip():
                return
            try:
                self.s.q(
                    "INSERT INTO product_categories(name,active) VALUES(?,1)",
                    (n.strip(),),
                )
                self.s.c.commit()
                self.s.audit(
                    self.user,
                    "CREATE",
                    "category",
                    None,
                    n.strip(),
                )
                reload_()
            except sqlite3.IntegrityError:
                # If it was archived, restore it instead of creating a duplicate.
                row = self.s.q(
                    "SELECT id FROM product_categories WHERE name=?",
                    (n.strip(),),
                ).fetchone()
                if row:
                    self.s.q(
                        "UPDATE product_categories SET active=1 WHERE id=?",
                        (row["id"],),
                    )
                    self.s.c.commit()
                    reload_()
                else:
                    messagebox.showerror(
                        "Category",
                        "Category already exists.",
                        parent=w,
                    )

        def archive_():
            sel = t.selection()
            if not sel:
                messagebox.showwarning(
                    "Category",
                    "Select a category first.",
                    parent=w,
                )
                return
            row = self.s.q(
                "SELECT * FROM product_categories WHERE id=?",
                (int(sel[0]),),
            ).fetchone()
            if not row:
                return
            if not messagebox.askyesno(
                "Category",
                f"Archive '{row['name']}'? Existing products remain unchanged.",
                parent=w,
            ):
                return
            self.s.q(
                "UPDATE product_categories SET active=0 WHERE id=?",
                (row["id"],),
            )
            self.s.c.commit()
            reload_()

        def restore_():
            sel = t.selection()
            if not sel:
                return
            self.s.q(
                "UPDATE product_categories SET active=1 WHERE id=?",
                (int(sel[0]),),
            )
            self.s.c.commit()
            reload_()

        b = ttk.Frame(f)
        b.pack(fill="x", pady=8)
        ttk.Button(
            b, text="ADD CATEGORY", style="Primary.TButton", command=add_
        ).pack(side="left")
        ttk.Button(b, text="ARCHIVE", command=archive_).pack(side="left", padx=5)
        ttk.Button(b, text="RESTORE", command=restore_).pack(side="left", padx=5)
        reload_()

    def modifiers(self):
        init_catalog_helpers(self)
        w = self.dialog("Product Modifiers / Add-ons", 800, 560)
        f = ttk.Frame(w, padding=14)
        f.pack(fill="both", expand=True)

        t = self.table(
            f,
            ("id", "modifier", "item", "delta"),
            {
                "id": "ID",
                "modifier": "Modifier Group",
                "item": "Option",
                "delta": "Price +/-",
            },
            14,
        )

        def reload_():
            t.delete(*t.get_children())
            rows = self.s.rows(
                """
                SELECT i.id,m.name modifier,i.name item,i.price_delta
                FROM product_modifier_items i
                JOIN product_modifiers m ON m.id=i.modifier_id
                WHERE i.active=1 AND m.active=1
                ORDER BY m.name,i.name
                """
            )
            for r in rows:
                t.insert(
                    "",
                    "end",
                    iid=str(r["id"]),
                    values=(
                        r["id"],
                        r["modifier"],
                        r["item"],
                        f"{float(r['price_delta']):+.2f}",
                    ),
                )

        def add_():
            d = self.dialog("Add Modifier Option", 460, 360)
            q = ttk.Frame(d, padding=16)
            q.pack(fill="both", expand=True)

            group = tk.StringVar()
            item = tk.StringVar()
            delta = tk.StringVar(value="0")

            for label, var in (
                ("Modifier Group", group),
                ("Option", item),
                ("Price Adjustment", delta),
            ):
                ttk.Label(q, text=label).pack(anchor="w", pady=(6, 2))
                ttk.Entry(q, textvariable=var).pack(fill="x")

            def save():
                if not group.get().strip() or not item.get().strip():
                    messagebox.showerror(
                        "Modifier",
                        "Group and option are required.",
                        parent=d,
                    )
                    return
                try:
                    amount = float(delta.get() or 0)
                    self.s.q(
                        "INSERT OR IGNORE INTO product_modifiers(name,active) VALUES(?,1)",
                        (group.get().strip(),),
                    )
                    mid = self.s.q(
                        "SELECT id FROM product_modifiers WHERE name=?",
                        (group.get().strip(),),
                    ).fetchone()["id"]
                    self.s.q(
                        "INSERT INTO product_modifier_items(modifier_id,name,price_delta,active) VALUES(?,?,?,1)",
                        (mid, item.get().strip(), amount),
                    )
                    self.s.c.commit()
                    d.destroy()
                    reload_()
                except Exception as e:
                    messagebox.showerror("Modifier", str(e), parent=d)

            ttk.Button(
                q,
                text="SAVE MODIFIER",
                style="Primary.TButton",
                command=save,
            ).pack(fill="x", pady=18)

        def archive_():
            sel = t.selection()
            if not sel:
                return
            self.s.q(
                "UPDATE product_modifier_items SET active=0 WHERE id=?",
                (int(sel[0]),),
            )
            self.s.c.commit()
            reload_()

        b = ttk.Frame(f)
        b.pack(fill="x", pady=8)
        ttk.Button(
            b,
            text="ADD MODIFIER OPTION",
            style="Primary.TButton",
            command=add_,
        ).pack(side="left")
        ttk.Button(b, text="REMOVE OPTION", command=archive_).pack(
            side="left", padx=5
        )
        reload_()

    App.init_catalog_helpers = init_catalog_helpers
    App.categories = categories
    App.modifiers = modifiers
    App._catalog_helpers_patch = True
    return App
