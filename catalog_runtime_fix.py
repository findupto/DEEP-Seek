import tkinter as tk
from tkinter import ttk, messagebox


def install(App):
    """Final Products/Menu page wiring.

    Keeps the existing catalog CRUD/history/media functionality intact while
    making the bulk-menu operations explicit and reachable from the page.
    Bulk import/export/template handlers are provided by catalog_features.
    """
    if getattr(App, "_catalog_runtime_fix", False):
        return App

    def host(self):
        return getattr(self, "bodyinner", getattr(self, "body", self))

    def selected(self):
        tree = getattr(self, "pr", None)
        sel = tree.selection() if tree else ()
        if not sel:
            messagebox.showwarning("Product", "Select a product first.", parent=self)
            return None
        return self.s.q(
            "SELECT * FROM products WHERE id=?",
            (int(sel[0]),),
        ).fetchone()

    def reload(self, all_rows=False):
        tree = getattr(self, "pr", None)
        if not tree:
            return

        tree.delete(*tree.get_children())

        sql = "SELECT * FROM products WHERE 1=1"
        args = []

        if not all_rows:
            sql += " AND active=1"

        query_var = getattr(self, "prod_filter", None)
        category_var = getattr(self, "cat_filter", None)

        query = query_var.get().strip().lower() if query_var else ""
        category = category_var.get() if category_var else "All"

        if query:
            sql += (
                " AND lower(COALESCE(name,'') || ' ' || "
                "COALESCE(category,'') || ' ' || COALESCE(barcode,'')) LIKE ?"
            )
            args.append("%" + query + "%")

        if category and category != "All":
            sql += " AND category=?"
            args.append(category)

        sql += " ORDER BY active DESC, category, name"

        for row in self.s.rows(sql, tuple(args)):
            tree.insert(
                "",
                "end",
                iid=str(row["id"]),
                values=(
                    row["id"],
                    row["name"],
                    row["category"],
                    f"{float(row['price']):.2f}",
                    f"{float(row['cost']):.2f}",
                    row["stock"],
                    row["barcode"],
                    "Yes" if row["active"] else "Archived",
                ),
            )

    def delete(self):
        product = selected(self)
        if not product:
            return

        if not messagebox.askyesno(
            "Archive Product",
            f"Archive '{product['name']}' from the POS menu?\n\n"
            "Sales/history are preserved.",
            parent=self,
        ):
            return

        self.s.q(
            "UPDATE products SET active=0 WHERE id=?",
            (product["id"],),
        )
        self.s.c.commit()
        self.s.audit(
            self.user,
            "ARCHIVE",
            "product",
            product["id"],
            product["name"],
        )
        reload(self)

    def delete_all(self):
        count = int(
            self.s.q(
                "SELECT COUNT(*) n FROM products WHERE active=1"
            ).fetchone()["n"]
        )

        if not count:
            messagebox.showinfo(
                "Menu",
                "No active products.",
                parent=self,
            )
            return

        if messagebox.askyesno(
            "DELETE ALL MENU",
            f"Archive ALL {count} active products?\n\n"
            "Historical orders remain intact.",
            parent=self,
        ):
            self.s.q(
                "UPDATE products SET active=0 WHERE active=1"
            )
            self.s.c.commit()
            self.s.audit(
                self.user,
                "ARCHIVE_ALL",
                "product",
                None,
                f"{count} products archived",
            )
            reload(self)

    def bulk_center(self):
        """Small real bulk-menu action center using the existing handlers."""
        required = (
            "product_import",
            "product_export",
            "product_template",
        )
        missing = [name for name in required if not hasattr(self, name)]
        if missing:
            messagebox.showerror(
                "Bulk Menu",
                "Bulk menu handlers are not installed: " + ", ".join(missing),
                parent=self,
            )
            return

        w = self.dialog("Bulk Menu Operations", 560, 390)
        f = ttk.Frame(w, padding=18)
        f.pack(fill="both", expand=True)

        ttk.Label(
            f,
            text="Bulk Menu Operations",
            font=("Segoe UI", 18, "bold"),
        ).pack(anchor="w")

        ttk.Label(
            f,
            text=(
                "Import or export the complete menu using CSV files. "
                "Existing products are matched by barcode/SKU first, then name."
            ),
            foreground="#64748b",
            wraplength=500,
            justify="left",
        ).pack(anchor="w", pady=(5, 16))

        ttk.Button(
            f,
            text="UPLOAD / IMPORT MENU CSV",
            style="Primary.TButton",
            command=lambda: self.product_import(),
        ).pack(fill="x", pady=5)

        ttk.Button(
            f,
            text="DOWNLOAD / EXPORT MENU CSV",
            command=lambda: self.product_export(),
        ).pack(fill="x", pady=5)

        ttk.Button(
            f,
            text="DOWNLOAD EMPTY CSV TEMPLATE",
            command=lambda: self.product_template(),
        ).pack(fill="x", pady=5)

        ttk.Label(
            f,
            text=(
                "CSV fields: name, category, price, cost, stock, "
                "barcode, active"
            ),
            foreground="#64748b",
        ).pack(anchor="w", pady=(12, 0))

        ttk.Button(
            f,
            text="CLOSE",
            command=w.destroy,
        ).pack(fill="x", pady=(18, 0))

    def page(self):
        if hasattr(self, "init_catalog"):
            self.init_catalog()

        self.title(
            "Products & Menu",
            "Manage products, media, history and bulk menu files.",
        )

        root = host(self)

        bar = ttk.Frame(root)
        bar.pack(fill="x", pady=8)

        buttons = [
            ("ADD PRODUCT", lambda: self.catalog_edit()),
            ("EDIT SELECTED", lambda: self.catalog_edit()),
            ("VIEW HISTORY", self.catalog_history),
            ("DELETE / ARCHIVE", self.product_delete),
            ("DELETE ALL MENU", self.product_delete_all),
            ("IMAGE / ICON / EMOJI / GIFT", self.product_media),
        ]

        for index, (text, command) in enumerate(buttons):
            ttk.Button(
                bar,
                text=text,
                style="Primary.TButton" if index == 0 else "TButton",
                command=command,
            ).pack(side="left", padx=(0, 4))

        bulk = ttk.LabelFrame(
            root,
            text="BULK MENU — CSV IMPORT / EXPORT",
            padding=8,
        )
        bulk.pack(fill="x", pady=(0, 8))

        ttk.Button(
            bulk,
            text="UPLOAD / IMPORT MENU CSV",
            style="Primary.TButton",
            command=self.product_import,
        ).pack(side="left", padx=(0, 5))

        ttk.Button(
            bulk,
            text="DOWNLOAD / EXPORT MENU CSV",
            command=self.product_export,
        ).pack(side="left", padx=5)

        ttk.Button(
            bulk,
            text="DOWNLOAD CSV TEMPLATE",
            command=self.product_template,
        ).pack(side="left", padx=5)

        ttk.Button(
            bulk,
            text="BULK MENU CENTER",
            command=self.bulk_center,
        ).pack(side="left", padx=5)

        ttk.Label(
            bulk,
            text="name, category, price, cost, stock, barcode, active",
            foreground="#64748b",
        ).pack(side="left", padx=(10, 0))

        tools = ttk.Frame(root)
        tools.pack(fill="x", pady=(0, 8))

        ttk.Button(
            tools,
            text="CATEGORIES",
            command=self.categories,
        ).pack(side="left", padx=(0, 5))

        ttk.Button(
            tools,
            text="MODIFIERS / ADD-ONS",
            command=self.modifiers,
        ).pack(side="left", padx=5)

        filters = ttk.Frame(root)
        filters.pack(fill="x", pady=(0, 8))

        self.cat_filter = tk.StringVar(value="All")
        self.prod_filter = tk.StringVar()

        categories = ["All"] + [
            row["name"]
            for row in self.s.rows(
                "SELECT name FROM product_categories "
                "WHERE active=1 ORDER BY name"
            )
        ]

        combo = ttk.Combobox(
            filters,
            textvariable=self.cat_filter,
            values=categories,
            state="readonly",
            width=18,
        )
        combo.pack(side="left")
        combo.bind(
            "<<ComboboxSelected>>",
            lambda _event: reload(self),
        )

        ttk.Label(
            filters,
            text="Search",
        ).pack(side="left", padx=(12, 3))

        search = ttk.Entry(
            filters,
            textvariable=self.prod_filter,
        )
        search.pack(side="left", fill="x", expand=True)
        search.bind(
            "<KeyRelease>",
            lambda _event: reload(self),
        )

        ttk.Button(
            filters,
            text="SHOW ALL / ARCHIVED",
            command=lambda: reload(self, True),
        ).pack(side="left", padx=5)

        self.pr = self.table(
            root,
            (
                "id",
                "name",
                "category",
                "price",
                "cost",
                "stock",
                "barcode",
                "active",
            ),
            {
                "id": "ID",
                "name": "Product / Menu Item",
                "category": "Category",
                "price": "Sale Price",
                "cost": "Cost",
                "stock": "Stock",
                "barcode": "Barcode / SKU",
                "active": "POS Menu",
            },
            18,
        )

        self.pr.bind(
            "<Double-1>",
            lambda _event: self.catalog_history(),
        )
        self.pr.bind(
            "<Return>",
            lambda _event: self.catalog_history(),
        )

        reload(self)

    App.product_delete = delete
    App.product_delete_all = delete_all
    # The page historically called self.bulk_center; expose that exact name.
    App.bulk_center = bulk_center
    # Keep the previous alias for compatibility with any older callers.
    App.bulk_menu_center = bulk_center
    App._selected_product = selected
    App.load_products = lambda self: reload(self)
    App.load_products_all = lambda self: reload(self, True)
    App.page_products = page
    App.page_products_menu = page
    App._catalog_runtime_fix = True
    return App
