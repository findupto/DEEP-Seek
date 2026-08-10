"""Supplier CRUD/archive controls missing from the legacy party page."""
import tkinter as tk
from tkinter import ttk, messagebox


def install(App):
    if getattr(App, "_supplier_management_patch", False):
        return App

    def page_suppliers(self):
        self.title(
            "Suppliers",
            "Manage suppliers, balances, purchases and supplier transaction history.",
        )
        bar = ttk.Frame(self.bodyinner)
        bar.pack(fill="x", pady=8)
        ttk.Button(bar, text="ADD SUPPLIER", style="Primary.TButton", command=lambda: self.supplier_edit()).pack(side="left")
        ttk.Button(bar, text="EDIT SELECTED", command=lambda: self.supplier_edit(True)).pack(side="left", padx=4)
        ttk.Button(bar, text="VIEW HISTORY", command=self.supplier_history).pack(side="left", padx=4)
        ttk.Button(bar, text="REMOVE / ARCHIVE", command=self.supplier_archive).pack(side="left", padx=4)
        ttk.Button(bar, text="RESTORE ARCHIVED", command=self.supplier_restore).pack(side="left", padx=4)
        ttk.Button(bar, text="REFRESH", command=self.page_suppliers).pack(side="left", padx=4)

        filterbar = ttk.Frame(self.bodyinner)
        filterbar.pack(fill="x", pady=(0, 8))
        self.supplier_show_archived = tk.BooleanVar(value=False)
        self.supplier_search = tk.StringVar()
        ttk.Checkbutton(filterbar, text="Show archived", variable=self.supplier_show_archived, command=self._supplier_reload).pack(side="left")
        ttk.Label(filterbar, text="Search").pack(side="left", padx=(15, 4))
        e = ttk.Entry(filterbar, textvariable=self.supplier_search)
        e.pack(side="left", fill="x", expand=True)
        e.bind("<KeyRelease>", lambda _e: self._supplier_reload())

        self.supplier_tree = self.table(
            self.bodyinner,
            ("id", "name", "phone", "address", "balance", "status"),
            {"id": "ID", "name": "Supplier", "phone": "Phone", "address": "Address", "balance": "Balance", "status": "Status"},
            18,
        )
        self.supplier_tree.bind("<Double-1>", lambda _e: self.supplier_history())
        self._supplier_reload()

    def _supplier_reload(self):
        tree = getattr(self, "supplier_tree", None)
        if not tree or not tree.winfo_exists():
            return
        tree.delete(*tree.get_children())
        archived = bool(self.supplier_show_archived.get())
        search = self.supplier_search.get().strip().lower()
        sql = "SELECT * FROM suppliers WHERE active=?"
        args = [0 if archived else 1]
        if search:
            sql += " AND lower(COALESCE(name,'') || ' ' || COALESCE(phone,'') || ' ' || COALESCE(address,'')) LIKE ?"
            args.append("%" + search + "%")
        sql += " ORDER BY name"
        for r in self.s.rows(sql, tuple(args)):
            tree.insert("", "end", iid=str(r["id"]), values=(r["id"], r["name"], r["phone"], r["address"], self.money(r["balance"]), "Archived" if not r["active"] else "Active"))

    def _supplier_selected(self):
        tree = getattr(self, "supplier_tree", None)
        sel = tree.selection() if tree else ()
        if not sel:
            messagebox.showwarning("Supplier", "Select a supplier first.", parent=self)
            return None
        return self.s.q("SELECT * FROM suppliers WHERE id=?", (int(sel[0]),)).fetchone()

    def supplier_edit(self, editing=False):
        old = self._supplier_selected() if editing else None
        if editing and not old:
            return
        w = self.dialog("Edit Supplier" if old else "Add Supplier", 520, 440)
        f = ttk.Frame(w, padding=18)
        f.pack(fill="both", expand=True)
        vars_ = {}
        fields = [("name", "Supplier Name", old["name"] if old else ""), ("phone", "Phone", old["phone"] if old else ""), ("address", "Address", old["address"] if old else "")]
        for key, label, value in fields:
            ttk.Label(f, text=label).pack(anchor="w", pady=(7, 2))
            vars_[key] = tk.StringVar(value=str(value or ""))
            ttk.Entry(f, textvariable=vars_[key]).pack(fill="x")
        if old:
            ttk.Label(f, text=f"Current balance: {self.money(old['balance'])}", foreground="#64748b").pack(anchor="w", pady=12)

        def save():
            name = vars_["name"].get().strip()
            if not name:
                messagebox.showerror("Supplier", "Supplier name is required.", parent=w)
                return
            if old:
                self.s.q("UPDATE suppliers SET name=?, phone=?, address=? WHERE id=?", (name, vars_["phone"].get().strip(), vars_["address"].get().strip(), old["id"]))
                action, sid = "UPDATE", old["id"]
            else:
                cur = self.s.q("INSERT INTO suppliers(name,phone,address,active) VALUES(?,?,?,1)", (name, vars_["phone"].get().strip(), vars_["address"].get().strip()))
                action, sid = "CREATE", cur.lastrowid
            self.s.c.commit()
            self.s.audit(self.user, action, "supplier", sid, name)
            w.destroy()
            self._supplier_reload()

        ttk.Button(f, text="SAVE SUPPLIER", style="Primary.TButton", command=save).pack(fill="x", pady=18)

    def supplier_archive(self):
        p = self._supplier_selected()
        if not p:
            return
        if not messagebox.askyesno("Remove Supplier", f"Remove '{p['name']}' from the active supplier list?\n\nPurchase and payment history will be preserved.", parent=self):
            return
        self.s.q("UPDATE suppliers SET active=0 WHERE id=?", (p["id"],))
        self.s.c.commit()
        self.s.audit(self.user, "ARCHIVE", "supplier", p["id"], p["name"])
        self._supplier_reload()

    def supplier_restore(self):
        p = self._supplier_selected()
        if not p:
            return
        if p["active"]:
            messagebox.showinfo("Supplier", "This supplier is already active.", parent=self)
            return
        self.s.q("UPDATE suppliers SET active=1 WHERE id=?", (p["id"],))
        self.s.c.commit()
        self.s.audit(self.user, "RESTORE", "supplier", p["id"], p["name"])
        self._supplier_reload()

    def supplier_history(self):
        p = self._supplier_selected()
        if not p:
            return
        # The existing party_txn implementation uses party_tree. Point it at
        # the supplier tree for this page, then reuse its real history dialog.
        self.party_tree = self.supplier_tree
        self.party_txn("suppliers")

    App.page_suppliers = page_suppliers
    App._supplier_reload = _supplier_reload
    App.supplier_edit = supplier_edit
    App.supplier_archive = supplier_archive
    App.supplier_restore = supplier_restore
    App.supplier_history = supplier_history
    App._supplier_management_patch = True
    return App
