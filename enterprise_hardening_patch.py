"""Enterprise UX/data-safety layer for MK Pizza & Ice Bar POS.

Installed last so it stabilizes the existing feature layers without replacing the
business database or deleting existing records.  It focuses on responsive
Windows sizing, customer CRUD, reliable quick-customer creation, DPI handling,
and operator-friendly shortcuts.
"""
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox

APP_NAME = "MK Pizza & Ice Bar"


def _enable_windows_dpi():
    if os.name != "nt":
        return
    try:
        import ctypes
        # Per-monitor DPI awareness when available (Windows 8.1+).
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _screen_size(window):
    try:
        return max(800, int(window.winfo_screenwidth())), max(600, int(window.winfo_screenheight()))
    except Exception:
        return 1366, 768


def _fit_geometry(window, width, height, minimum=(720, 500)):
    sw, sh = _screen_size(window)
    min_w, min_h = minimum
    width = min(max(int(width), min_w), max(min_w, int(sw * 0.92)))
    height = min(max(int(height), min_h), max(min_h, int(sh * 0.90)))
    x = max(0, (sw - width) // 2)
    y = max(0, (sh - height) // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")
    return width, height


def _safe_exists(widget):
    try:
        return bool(widget.winfo_exists())
    except Exception:
        return False


def install(App, Login=None):
    if getattr(App, "_enterprise_hardening_installed", False):
        return App

    _enable_windows_dpi()

    # ------------------------------------------------------------------
    # Responsive dialogs: every existing dialog gets capped to the current
    # display and centered. This fixes fixed 900x760/1000x650 windows on
    # 768p and smaller POS displays without changing callers.
    # ------------------------------------------------------------------
    old_dialog = getattr(App, "dialog", None)
    if old_dialog and not getattr(App, "_responsive_dialog_installed", False):
        def dialog(self, title, w=650, h=650):
            win = old_dialog(self, title, w, h)
            try:
                _fit_geometry(win, w, h)
                win.resizable(True, True)
                win.minsize(min(520, max(420, int(w * 0.72))), min(420, max(320, int(h * 0.72))))
                win.bind("<Escape>", lambda _e: win.destroy())
            except Exception:
                pass
            return win
        App.dialog = dialog
        App._responsive_dialog_installed = True

    # ------------------------------------------------------------------
    # Main window sizing and useful keyboard navigation.
    # ------------------------------------------------------------------
    old_app_init = App.__init__
    if not getattr(App, "_enterprise_init_installed", False):
        def app_init(self, *args, **kwargs):
            old_app_init(self, *args, **kwargs)
            try:
                sw, sh = _screen_size(self)
                width = min(1440, max(1050, int(sw * 0.94)))
                height = min(900, max(650, int(sh * 0.90)))
                _fit_geometry(self, width, height, minimum=(900, 600))
                self.minsize(min(900, max(760, int(sw * 0.78))), min(600, max(540, int(sh * 0.72))))
                self.bind("<Control-f>", lambda _e: self._focus_pos_search())
                self.bind("<F5>", lambda _e: self._refresh_current_page())
                self.bind("<Escape>", lambda _e: self._close_top_dialog())
            except Exception:
                pass
        App.__init__ = app_init
        App._enterprise_init_installed = True

    def _focus_pos_search(self):
        entry = getattr(self, "search", None)
        if entry is not None and hasattr(entry, "focus_set"):
            entry.focus_set()
            try:
                entry.selection_range(0, "end")
            except Exception:
                pass

    def _refresh_current_page(self):
        try:
            current = getattr(self, "_enterprise_current_page", None)
            if current:
                self.show(current)
        except Exception:
            pass

    def _close_top_dialog(self):
        try:
            for child in reversed(self.winfo_children()):
                if isinstance(child, tk.Toplevel) and _safe_exists(child):
                    child.destroy()
                    return "break"
        except Exception:
            pass
        return "break"

    App._focus_pos_search = _focus_pos_search
    App._refresh_current_page = _refresh_current_page
    App._close_top_dialog = _close_top_dialog

    # Preserve the logical page name for F5 even when the existing show()
    # implementation translates aliases such as Products / Menu.
    old_show = App.show
    if not getattr(App, "_enterprise_show_installed", False):
        def show(self, name):
            self._enterprise_current_page = name
            return old_show(self, name)
        App.show = show
        App._enterprise_show_installed = True

    # ------------------------------------------------------------------
    # Robust customer selector/creator used by Checkout. This fixes the
    # legacy dialog validation issue where a visible Entry value could be
    # reported as empty.
    # ------------------------------------------------------------------
    def quick_customer(self, variable, combo=None, cmap=None):
        w = self.dialog("New Customer", 560, 500)
        f = ttk.Frame(w, padding=20)
        f.pack(fill="both", expand=True)
        f.columnconfigure(0, weight=1)

        name = tk.StringVar()
        phone = tk.StringVar()
        address = tk.StringVar()

        ttk.Label(f, text="New Customer", font=("Segoe UI", 17, "bold")).pack(anchor="w", pady=(0, 14))
        for label, var in (("Name", name), ("Phone", phone), ("Delivery / Home Address", address)):
            ttk.Label(f, text=label).pack(anchor="w", pady=(7, 3))
            ttk.Entry(f, textvariable=var).pack(fill="x")

        def save():
            # Read directly from the StringVars and normalize whitespace.
            customer_name = str(name.get() or "").strip()
            customer_phone = str(phone.get() or "").strip()
            customer_address = str(address.get() or "").strip()
            if not customer_name:
                messagebox.showerror("Customer", "Name is required.", parent=w)
                return
            try:
                cur = self.s.q(
                    "INSERT INTO customers(name,phone,address,balance,active) VALUES(?,?,?,?,1)",
                    (customer_name, customer_phone, customer_address, 0),
                )
                cid = cur.lastrowid
                self.s.c.commit()
                self.s.audit(self.user, "CREATE", "customer", cid, customer_name)
                label = f"{customer_name} | {customer_phone}"
                if isinstance(cmap, dict):
                    cmap[label] = cid
                if combo is not None and _safe_exists(combo):
                    values = list(combo.cget("values") or ())
                    if label not in values:
                        values.append(label)
                        values.sort(key=str.lower)
                        combo.configure(values=values)
                    variable.set(label)
                else:
                    variable.set(label)
                w.destroy()
            except Exception as exc:
                messagebox.showerror("Customer", str(exc), parent=w)

        ttk.Button(f, text="SAVE CUSTOMER", style="Primary.TButton", command=save).pack(fill="x", pady=20)
        w.after(80, lambda: self._focus_first_entry(w))
        return w

    def _focus_first_entry(self, parent):
        try:
            for child in parent.winfo_children():
                if isinstance(child, ttk.Entry):
                    child.focus_set()
                    return
                nested = getattr(child, "winfo_children", lambda: ())()
                for sub in nested:
                    if isinstance(sub, ttk.Entry):
                        sub.focus_set()
                        return
        except Exception:
            pass

    App.quick_customer = quick_customer
    App._focus_first_entry = _focus_first_entry

    # ------------------------------------------------------------------
    # Full customer management page: search, add, edit, archive/restore,
    # and history. Existing orders remain untouched.
    # ------------------------------------------------------------------
    def page_customers(self):
        self.title("Customers", "Customer directory, contact details, balances and complete order history.")

        toolbar = ttk.Frame(self.bodyinner)
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Button(toolbar, text="ADD CUSTOMER", style="Primary.TButton", command=lambda: self.customer_edit(False)).pack(side="left")
        ttk.Button(toolbar, text="EDIT SELECTED", command=lambda: self.customer_edit(True)).pack(side="left", padx=5)
        ttk.Button(toolbar, text="VIEW HISTORY", command=self.customer_history).pack(side="left", padx=5)
        ttk.Button(toolbar, text="ARCHIVE", style="Danger.TButton", command=self.customer_archive).pack(side="left", padx=5)
        ttk.Button(toolbar, text="RESTORE", command=self.customer_restore).pack(side="left", padx=5)

        filterbar = ttk.Frame(self.bodyinner)
        filterbar.pack(fill="x", pady=(0, 8))
        self.customer_show_archived = tk.BooleanVar(value=False)
        self.customer_search = tk.StringVar()
        ttk.Checkbutton(filterbar, text="Show archived", variable=self.customer_show_archived, command=self._customer_reload).pack(side="left")
        ttk.Label(filterbar, text="Search").pack(side="left", padx=(15, 4))
        entry = ttk.Entry(filterbar, textvariable=self.customer_search)
        entry.pack(side="left", fill="x", expand=True)
        entry.bind("<KeyRelease>", lambda _e: self._customer_reload())
        ttk.Button(filterbar, text="REFRESH", style="Soft.TButton", command=self._customer_reload).pack(side="left", padx=5)

        self.customer_tree = self.table(
            self.bodyinner,
            ("id", "name", "phone", "address", "balance", "status"),
            {"id": "ID", "name": "Customer", "phone": "Phone", "address": "Address", "balance": "Balance / Due", "status": "Status"},
            18,
        )
        self.customer_tree.bind("<Double-1>", lambda _e: self.customer_history())
        self._customer_reload()

    def _customer_reload(self):
        tree = getattr(self, "customer_tree", None)
        if tree is None or not _safe_exists(tree):
            return
        tree.delete(*tree.get_children())
        archived = bool(getattr(self, "customer_show_archived", tk.BooleanVar(value=False)).get())
        search_var = getattr(self, "customer_search", None)
        query = search_var.get().strip().lower() if search_var else ""
        sql = "SELECT * FROM customers WHERE active=?"
        args = [0 if archived else 1]
        if query:
            sql += " AND lower(COALESCE(name,'') || ' ' || COALESCE(phone,'') || ' ' || COALESCE(address,'')) LIKE ?"
            args.append("%" + query + "%")
        sql += " ORDER BY name"
        for row in self.s.rows(sql, tuple(args)):
            tree.insert("", "end", iid=str(row["id"]), values=(
                row["id"], row["name"], row["phone"], row["address"],
                self.money(row["balance"]), "Active" if row["active"] else "Archived",
            ))

    def _customer_selected(self):
        tree = getattr(self, "customer_tree", None)
        sel = tree.selection() if tree else ()
        if not sel:
            messagebox.showwarning("Customer", "Select a customer first.", parent=self)
            return None
        return self.s.q("SELECT * FROM customers WHERE id=?", (int(sel[0]),)).fetchone()

    def customer_edit(self, editing=False):
        old = self._customer_selected() if editing else None
        if editing and not old:
            return
        w = self.dialog("Edit Customer" if old else "Add Customer", 560, 500)
        f = ttk.Frame(w, padding=20)
        f.pack(fill="both", expand=True)
        vals = {
            "name": tk.StringVar(value=str(old["name"] or "") if old else ""),
            "phone": tk.StringVar(value=str(old["phone"] or "") if old else ""),
            "address": tk.StringVar(value=str(old["address"] or "") if old else ""),
        }
        ttk.Label(f, text="Edit Customer" if old else "New Customer", font=("Segoe UI", 17, "bold")).pack(anchor="w", pady=(0, 12))
        for key, label in (("name", "Name"), ("phone", "Phone"), ("address", "Delivery / Home Address")):
            ttk.Label(f, text=label).pack(anchor="w", pady=(7, 3))
            ttk.Entry(f, textvariable=vals[key]).pack(fill="x")
        if old:
            ttk.Label(f, text=f"Current balance: {self.money(old['balance'])}", foreground="#64748b").pack(anchor="w", pady=12)

        def save():
            name = vals["name"].get().strip()
            if not name:
                messagebox.showerror("Customer", "Name is required.", parent=w)
                return
            try:
                phone = vals["phone"].get().strip()
                address = vals["address"].get().strip()
                if old:
                    self.s.q("UPDATE customers SET name=?,phone=?,address=? WHERE id=?", (name, phone, address, old["id"]))
                    cid, action = old["id"], "UPDATE"
                else:
                    cur = self.s.q("INSERT INTO customers(name,phone,address,balance,active) VALUES(?,?,?,?,1)", (name, phone, address, 0))
                    cid, action = cur.lastrowid, "CREATE"
                self.s.c.commit()
                self.s.audit(self.user, action, "customer", cid, name)
                w.destroy()
                self._customer_reload()
            except Exception as exc:
                messagebox.showerror("Customer", str(exc), parent=w)
        ttk.Button(f, text="SAVE CUSTOMER", style="Primary.TButton", command=save).pack(fill="x", pady=18)
        w.after(80, lambda: self._focus_first_entry(w))

    def customer_archive(self):
        row = self._customer_selected()
        if not row:
            return
        if not messagebox.askyesno("Archive Customer", f"Archive '{row['name']}'? Existing orders and payments will remain intact.", parent=self):
            return
        self.s.q("UPDATE customers SET active=0 WHERE id=?", (row["id"],))
        self.s.c.commit()
        self.s.audit(self.user, "ARCHIVE", "customer", row["id"], row["name"])
        self._customer_reload()

    def customer_restore(self):
        row = self._customer_selected()
        if not row:
            return
        if row["active"]:
            messagebox.showinfo("Customer", "This customer is already active.", parent=self)
            return
        self.s.q("UPDATE customers SET active=1 WHERE id=?", (row["id"],))
        self.s.c.commit()
        self.s.audit(self.user, "RESTORE", "customer", row["id"], row["name"])
        self._customer_reload()

    def customer_history(self):
        row = self._customer_selected()
        if not row:
            return
        w = self.dialog("Customer History — " + row["name"], 980, 650)
        f = ttk.Frame(w, padding=15)
        f.pack(fill="both", expand=True)
        ttk.Label(f, text=row["name"], font=("Segoe UI", 17, "bold")).pack(anchor="w")
        ttk.Label(f, text=f"Phone: {row['phone'] or '-'}    |    Balance / Due: {self.money(row['balance'])}", foreground="#64748b").pack(anchor="w", pady=(3, 10))
        tree = self.table(f, ("invoice", "date", "type", "status", "total", "payment"),
                          {"invoice": "Invoice", "date": "Date", "type": "Order Type", "status": "Status", "total": "Total", "payment": "Payment"}, 18)
        for r in self.s.rows("SELECT invoice_no,created_at,order_type,status,total,payment_status FROM sales WHERE customer_id=? ORDER BY id DESC", (row["id"],)):
            tree.insert("", "end", values=(r["invoice_no"], r["created_at"], r["order_type"], r["status"], self.money(r["total"]), r["payment_status"]))
        ttk.Button(f, text="CLOSE", command=w.destroy).pack(fill="x", pady=(10, 0))

    App.page_customers = page_customers
    App._customer_reload = _customer_reload
    App._customer_selected = _customer_selected
    App.customer_edit = customer_edit
    App.customer_archive = customer_archive
    App.customer_restore = customer_restore
    App.customer_history = customer_history

    # Make login responsive as well. Do this after all previous login patches.
    if Login is not None and not getattr(Login, "_enterprise_login_installed", False):
        old_login_init = Login.__init__
        def login_init(self, *args, **kwargs):
            old_login_init(self, *args, **kwargs)
            try:
                sw, sh = _screen_size(self)
                _fit_geometry(self, min(470, int(sw * 0.80)), min(380, int(sh * 0.70)), minimum=(380, 300))
                self.resizable(False, False)
            except Exception:
                pass
        Login.__init__ = login_init
        Login._enterprise_login_installed = True

    App._enterprise_hardening_installed = True
    return App
