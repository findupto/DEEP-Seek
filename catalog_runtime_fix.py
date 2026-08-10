import tkinter as tk
from tkinter import ttk, messagebox


def install(App):
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
        return self.s.q("SELECT * FROM products WHERE id=?", (int(sel[0]),)).fetchone()

    def reload(self, all_rows=False):
        tree = getattr(self, "pr", None)
        if not tree:
            return
        tree.delete(*tree.get_children())
        sql = "SELECT * FROM products WHERE 1=1"
        args = []
        if not all_rows:
            sql += " AND active=1"
        query = getattr(self, "prod_filter", tk.StringVar()).get().strip().lower()
        category = getattr(self, "cat_filter", tk.StringVar(value="All")).get()
        if query:
            sql += " AND lower(COALESCE(name,'')||' '||COALESCE(category,'')||' '||COALESCE(barcode,'')) LIKE ?"
            args.append("%" + query + "%")
        if category and category != "All":
            sql += " AND category=?"
            args.append(category)
        for row in self.s.rows(sql + " ORDER BY active DESC, category, name", tuple(args)):
            tree.insert(
                "", "end", iid=str(row["id"]),
                values=(row["id"], row["name"], row["category"],
                        f"{float(row['price']):.2f}", f"{float(row['cost']):.2f}",
                        row["stock"], row["barcode"],
                        "Yes" if row["active"] else "Archived")
            )

    def delete(self):
        product = selected(self)
        if not product:
            return
        if not messagebox.askyesno(
            "Archive Product",
            f"Archive '{product['name']}' from the POS menu?\n\nSales/history are preserved.",
            parent=self,
        ):
            return
        self.s.q("UPDATE products SET active=0 WHERE id=?", (product["id"],))
        self.s.c.commit()
        self.s.audit(self.user, "ARCHIVE", "product", product["id"], product["name"])
        reload(self)

    def delete_all(self):
        count = int(self.s.q("SELECT COUNT(*) n FROM products WHERE active=1").fetchone()["n"])
        if not count:
            messagebox.showinfo("Menu", "No active products.", parent=self)
            return
        if messagebox.askyesno(
            "DELETE ALL MENU",
            f"Archive ALL {count} active products?\n\nHistorical orders remain intact.",
            parent=self,
        ):
            self.s.q("UPDATE products SET active=0 WHERE active=1")
            self.s.c.commit()
            self.s.audit(self.user, "ARCHIVE_ALL", "product", None, f"{count} products archived")
            reload(self)

    def page(self):
        if hasattr(self, "init_catalog"):
            self.init_catalog()
        self.title("Products & Menu", "Manage products, media, history and bulk menu files.")
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
                bar, text=text,
                style="Primary.TButton" if index == 0 else "TButton",
                command=command,
            ).pack(side="left", padx=(0, 4))

        bulk = ttk.Frame(root)
        bulk.pack(fill="x", pady=(0, 8))
        for text, command in (
            ("UPLOAD MENU CSV", self.product_import),
            ("DOWNLOAD MENU CSV", self.product_export),
            ("DOWNLOAD CSV TEMPLATE", self.product_template),
            ("CATEGORIES", self.categories),
            ("MODIFIERS / ADD-ONS", self.modifiers),
        ):
            ttk.Button(bulk, text=text, command=command).pack(side="left", padx=(0, 4))

        filters = ttk.Frame(root)
        filters.pack(fill="x", pady=(0, 8))
        self.cat_filter = tk.StringVar(value="All")
        self.prod_filter = tk.StringVar()
        categories = ["All"] + [
            row["name"] for row in self.s.rows(
                "SELECT name FROM product_categories WHERE active=1 ORDER BY name"
            )
        ]
        combo = ttk.Combobox(
            filters, textvariable=self.cat_filter, values=categories,
            state="readonly", width=18
        )
        combo.pack(side="left")
        combo.bind("<<ComboboxSelected>>", lambda _event: reload(self))
        ttk.Label(filters, text="Search").pack(side="left", padx=(12, 3))
        search = ttk.Entry(filters, textvariable=self.prod_filter)
        search.pack(side="left", fill="x", expand=True)
        search.bind("<KeyRelease>", lambda _event: reload(self))
        ttk.Button(
            filters, text="SHOW ALL / ARCHIVED",
            command=lambda: reload(self, True)
        ).pack(side="left", padx=5)

        self.pr = self.table(
            root,
            ("id", "name", "category", "price", "cost", "stock", "barcode", "active"),
            {
                "id": "ID", "name": "Product / Menu Item", "category": "Category",
                "price": "Sale Price", "cost": "Cost", "stock": "Stock",
                "barcode": "Barcode / SKU", "active": "POS Menu",
            },
            18,
        )
        self.pr.bind("<Double-1>", lambda _event: self.catalog_history())
        self.pr.bind("<Return>", lambda _event: self.catalog_history())
        reload(self)

    App.product_delete = delete
    App.product_delete_all = delete_all
    App._selected_product = selected
    App.load_products = lambda self: reload(self)
    App.load_products_all = lambda self: reload(self, True)
    App.page_products = page
    App.page_products_menu = page
    App._catalog_runtime_fix = True
    return App
