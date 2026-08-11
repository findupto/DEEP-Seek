"""Final visual/UX layer for MK Pizza & Ice Bar POS.

Keeps all existing database and business logic intact while providing one
consistent, polished UI layer and a guaranteed modern POS workspace.
"""
import tkinter as tk
from tkinter import ttk


NAV = [
    "POS", "Dashboard", "Orders", "Kitchen", "Customers", "Tables / Dine-in",
    "Suppliers", "Purchases", "Products / Menu", "Inventory", "Riders / Delivery",
    "Staff", "Expenses", "Cash / Shifts", "Reports / Analytics", "Printers",
    "Settings", "Users / Permissions",
]


def install(App, Login=None):
    if getattr(App, "_premium_ui_installed", False):
        return App

    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure("TFrame", background="#f4f7fb")
    style.configure("TLabel", background="#f4f7fb", foreground="#172033", font=("Segoe UI", 10))
    style.configure("Title.TLabel", background="#f4f7fb", foreground="#0f172a", font=("Segoe UI", 25, "bold"))
    style.configure("Subtitle.TLabel", background="#f4f7fb", foreground="#64748b", font=("Segoe UI", 10))
    style.configure("TButton", font=("Segoe UI", 9, "bold"), padding=(12, 8), background="#ffffff", foreground="#1e293b")
    style.map("TButton", background=[("active", "#e8eef8")])
    style.configure("Primary.TButton", font=("Segoe UI", 9, "bold"), padding=(13, 9), background="#2563eb", foreground="#ffffff")
    style.map("Primary.TButton", background=[("active", "#1d4ed8")])
    style.configure("Success.TButton", font=("Segoe UI", 9, "bold"), padding=(12, 8), background="#16a34a", foreground="#ffffff")
    style.map("Success.TButton", background=[("active", "#15803d")])
    style.configure("Danger.TButton", font=("Segoe UI", 9, "bold"), padding=(12, 8), background="#dc2626", foreground="#ffffff")
    style.map("Danger.TButton", background=[("active", "#b91c1c")])
    style.configure("Soft.TButton", font=("Segoe UI", 9, "bold"), padding=(11, 8), background="#eaf0f8", foreground="#1e3a5f")
    style.map("Soft.TButton", background=[("active", "#dbe7f6")])
    style.configure("TLabelframe", background="#ffffff", borderwidth=1, relief="solid")
    style.configure("TLabelframe.Label", background="#ffffff", foreground="#334155", font=("Segoe UI", 10, "bold"))
    style.configure("Treeview", background="#ffffff", fieldbackground="#ffffff", foreground="#172033", rowheight=34, font=("Segoe UI", 10), borderwidth=0)
    style.configure("Treeview.Heading", background="#e9eef5", foreground="#172033", font=("Segoe UI", 9, "bold"), padding=(8, 8))
    style.map("Treeview", background=[("selected", "#dbeafe")], foreground=[("selected", "#0f172a")])
    style.configure("TEntry", padding=7, fieldbackground="#ffffff")
    style.configure("TCombobox", padding=6, fieldbackground="#ffffff")
    style.configure("TNotebook", background="#f4f7fb", borderwidth=0)

    def _style_widget_tree(self, root):
        try:
            root.configure(bg="#f4f7fb")
        except Exception:
            pass
        for w in root.winfo_children():
            try:
                if isinstance(w, ttk.Treeview):
                    w.configure(height=max(8, int(w.cget("height"))))
                elif isinstance(w, ttk.Button):
                    text = str(w.cget("text") or "").upper()
                    current = str(w.cget("style") or "")
                    if current in ("", "TButton"):
                        if any(x in text for x in ("DELETE", "REMOVE", "ARCHIVE", "CANCEL")):
                            w.configure(style="Danger.TButton")
                        elif any(x in text for x in ("ADD", "SAVE", "CHECKOUT", "PAYMENT", "CONNECT", "IMPORT", "OPEN SHIFT", "CREATE")):
                            w.configure(style="Primary.TButton")
                        elif any(x in text for x in ("REFRESH", "FILTER", "HISTORY", "VIEW", "BACKUP", "EXPORT", "DOWNLOAD")):
                            w.configure(style="Soft.TButton")
                elif isinstance(w, tk.Frame):
                    pass
            except Exception:
                pass
            try:
                _style_widget_tree(self, w)
            except Exception:
                pass

    def _hover(button, normal="#111827", active="#2563eb"):
        try:
            button.bind("<Enter>", lambda _e: button.configure(bg=active))
            button.bind("<Leave>", lambda _e: button.configure(bg=normal))
        except Exception:
            pass

    original_build_shell = App.build_shell

    def build_shell(self):
        original_build_shell(self)
        try:
            self.configure(bg="#f4f7fb")
            self.minsize(1050, 650)
            self.geometry("1440x880")
            self.side.configure(width=248, bg="#0f172a")
            self.side.pack_propagate(False)
            for child in self.side.winfo_children():
                try:
                    if isinstance(child, tk.Label):
                        child.configure(bg="#0f172a")
                except Exception:
                    pass
            for name, button in getattr(self, "navbuttons", {}).items():
                try:
                    button.configure(
                        bg="#0f172a", fg="#f8fafc", activebackground="#2563eb",
                        activeforeground="#ffffff", font=("Segoe UI", 10, "bold"),
                        padx=18, pady=10, relief="flat", bd=0, cursor="hand2"
                    )
                    _hover(button)
                except Exception:
                    pass
            self._premium_style_shell_ready = True
        except Exception:
            pass

    def _modern_pos(self):
        self.title("New Sale", "Fast checkout workspace — search the menu, build the order, then checkout in one clean flow.")
        root = ttk.Frame(self.bodyinner)
        root.pack(fill="both", expand=True, pady=(2, 8))
        root.grid_rowconfigure(1, weight=1)
        root.grid_columnconfigure(0, weight=3, uniform="pos")
        root.grid_columnconfigure(1, weight=2, uniform="pos")

        toolbar = ttk.LabelFrame(root, text="QUICK SALE TOOLS", padding=9)
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 9))
        toolbar.grid_columnconfigure(0, weight=1)
        self.search = tk.StringVar()
        search = ttk.Entry(toolbar, textvariable=self.search)
        search.grid(row=0, column=0, sticky="ew")
        search.insert(0, "Search product, category or barcode...")
        search.bind("<FocusIn>", lambda _e: search.delete(0, "end") if search.get() == "Search product, category or barcode..." else None)
        search.bind("<KeyRelease>", lambda _e: self.load_menu())
        ttk.Button(toolbar, text="SEARCH / FILTER", style="Soft.TButton", command=self.load_menu).grid(row=0, column=1, padx=5)
        ttk.Button(toolbar, text="ORDERS", command=lambda: self.show("Orders")).grid(row=0, column=2, padx=3)
        ttk.Button(toolbar, text="KITCHEN", command=lambda: self.show("Kitchen")).grid(row=0, column=3, padx=3)
        ttk.Button(toolbar, text="PRODUCTS", command=lambda: self.show("Products / Menu")).grid(row=0, column=4, padx=(3, 0))

        menu_box = ttk.LabelFrame(root, text="MENU / PRODUCTS", padding=9)
        cart_box = ttk.LabelFrame(root, text="CURRENT ORDER", padding=9)
        menu_box.grid(row=1, column=0, sticky="nsew", padx=(0, 6))
        cart_box.grid(row=1, column=1, sticky="nsew", padx=(6, 0))
        menu_box.grid_rowconfigure(0, weight=1); menu_box.grid_columnconfigure(0, weight=1)
        cart_box.grid_rowconfigure(0, weight=1); cart_box.grid_columnconfigure(0, weight=1)

        mf = ttk.Frame(menu_box)
        mf.grid(row=0, column=0, sticky="nsew")
        mf.grid_rowconfigure(0, weight=1); mf.grid_columnconfigure(0, weight=1)
        self.menu = ttk.Treeview(mf, columns=("name", "cat", "price", "stock", "barcode"), show="headings", selectmode="browse")
        heads = {"name":"Product", "cat":"Category", "price":"Price", "stock":"Stock", "barcode":"Barcode"}
        widths = {"name":260, "cat":150, "price":120, "stock":110, "barcode":150}
        for c in heads:
            self.menu.heading(c, text=heads[c])
            self.menu.column(c, width=widths[c], minwidth=80, anchor="w", stretch=True)
        my = ttk.Scrollbar(mf, orient="vertical", command=self.menu.yview)
        mx = ttk.Scrollbar(mf, orient="horizontal", command=self.menu.xview)
        self.menu.configure(yscrollcommand=my.set, xscrollcommand=mx.set)
        self.menu.grid(row=0, column=0, sticky="nsew"); my.grid(row=0, column=1, sticky="ns"); mx.grid(row=1, column=0, sticky="ew")
        self.menu.bind("<Double-1>", lambda _e: self.add_item())
        ttk.Button(menu_box, text="+ ADD SELECTED TO ORDER", style="Primary.TButton", command=self.add_item).grid(row=1, column=0, sticky="ew", pady=(9, 0))

        cf = ttk.Frame(cart_box)
        cf.grid(row=0, column=0, sticky="nsew")
        cf.grid_rowconfigure(0, weight=1); cf.grid_columnconfigure(0, weight=1)
        self.ct = ttk.Treeview(cf, columns=("name", "qty", "unit", "total"), show="headings", selectmode="browse")
        for c, h, width in (("name","Item",230),("qty","Qty",70),("unit","Unit",100),("total","Total",120)):
            self.ct.heading(c, text=h); self.ct.column(c, width=width, minwidth=60, anchor="w", stretch=True)
        cy = ttk.Scrollbar(cf, orient="vertical", command=self.ct.yview)
        cx = ttk.Scrollbar(cf, orient="horizontal", command=self.ct.xview)
        self.ct.configure(yscrollcommand=cy.set, xscrollcommand=cx.set)
        self.ct.grid(row=0, column=0, sticky="nsew"); cy.grid(row=0, column=1, sticky="ns"); cx.grid(row=1, column=0, sticky="ew")

        controls = ttk.Frame(cart_box)
        controls.grid(row=1, column=0, sticky="ew", pady=8)
        ttk.Button(controls, text="+ QTY", command=lambda: self.qty(1)).pack(side="left")
        ttk.Button(controls, text="- QTY", command=lambda: self.qty(-1)).pack(side="left", padx=4)
        ttk.Button(controls, text="REMOVE", style="Danger.TButton", command=self.remove).pack(side="left")
        ttk.Button(controls, text="CLEAR", style="Soft.TButton", command=lambda: (self.cart.clear(), self.refresh())).pack(side="right")

        summary = ttk.Frame(cart_box)
        summary.grid(row=2, column=0, sticky="ew", pady=(4, 8))
        summary.grid_columnconfigure(0, weight=1)
        ttk.Label(summary, text="ORDER TOTAL", font=("Segoe UI", 10, "bold"), foreground="#64748b").grid(row=0, column=0, sticky="w")
        self.total = tk.StringVar(value=self.money(0))
        ttk.Label(summary, textvariable=self.total, font=("Segoe UI", 24, "bold"), foreground="#0f172a").grid(row=1, column=0, sticky="w")

        quick = ttk.Frame(cart_box)
        quick.grid(row=3, column=0, sticky="ew")
        ttk.Button(quick, text="CUSTOMER / DELIVERY", command=self.checkout).pack(side="left", fill="x", expand=True)
        ttk.Button(quick, text="TABLE / DINE-IN", command=self.checkout).pack(side="left", fill="x", expand=True, padx=5)
        ttk.Button(quick, text="CHECKOUT / SEND KITCHEN", style="Success.TButton", command=self.checkout).pack(side="left", fill="x", expand=True)

        self.load_menu()
        self.refresh()

    def _inject_sparse_actions(self, name):
        if name in {"POS", "Orders", "Kitchen", "Customers", "Suppliers", "Purchases", "Products / Menu", "Inventory", "Riders / Delivery", "Printers", "Users / Permissions"}:
            return
        root = getattr(self, "bodyinner", None)
        if root is None:
            return
        children = list(root.winfo_children())
        if not children:
            return
        if getattr(self, "_premium_action_page", None) == name:
            return
        actions = {
            "Dashboard": [("NEW SALE", lambda: self.show("POS")), ("ORDERS", lambda: self.show("Orders")), ("KITCHEN", lambda: self.show("Kitchen")), ("REPORTS", lambda: self.show("Reports / Analytics"))],
            "Staff": [("ADD STAFF", lambda: self.people_edit("staff", ["name", "phone", "role", "salary"])), ("USERS / PERMISSIONS", lambda: self.show("Users / Permissions"))],
            "Expenses": [("ADD EXPENSE", self.add_expense), ("REPORTS", lambda: self.show("Reports / Analytics"))],
            "Cash / Shifts": [("OPEN SHIFT", self.open_shift), ("REPORTS", lambda: self.show("Reports / Analytics"))],
            "Reports / Analytics": [("NEW SALE", lambda: self.show("POS")), ("EXPENSES", lambda: self.show("Expenses")), ("CASH / SHIFTS", lambda: self.show("Cash / Shifts"))],
            "Settings": [("BACKUP DATABASE", self.backup), ("PRINTERS", lambda: self.show("Printers")), ("USERS", lambda: self.show("Users / Permissions"))],
        }
        items = actions.get(name)
        if not items:
            return
        anchor = children[2] if len(children) > 2 else children[-1]
        bar = ttk.LabelFrame(root, text="QUICK ACTIONS", padding=7)
        bar.pack(fill="x", pady=(0, 9), before=anchor)
        for i, (text, cmd) in enumerate(items):
            ttk.Button(bar, text=text, style="Primary.TButton" if i == 0 else "Soft.TButton", command=cmd).pack(side="left", padx=(0, 5))
        self._premium_action_page = name

    def show(self, name):
        self._premium_action_page = None
        result = self._premium_original_show(name)
        try:
            self._inject_sparse_actions(name)
            _style_widget_tree(self, self.bodyinner)
            self.update_idletasks()
        except Exception:
            pass
        return result

    original_show = App.show
    App._premium_original_show = original_show
    App.build_shell = build_shell
    App.page_pos = _modern_pos
    App.show = show
    App._premium_ui_installed = True

    if Login is not None and not getattr(Login, "_premium_login_installed", False):
        original_login_init = Login.__init__

        def login_init(self, *args, **kwargs):
            original_login_init(self, *args, **kwargs)
            try:
                self.configure(bg="#0f172a")
                self.geometry("470x380")
                for w in self.winfo_children():
                    try:
                        if isinstance(w, ttk.Frame):
                            w.configure(padding=40)
                    except Exception:
                        pass
            except Exception:
                pass

        Login.__init__ = login_init
        Login._premium_login_installed = True

    return App
