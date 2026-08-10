"""Canonical responsive UI for the POS.

There must be exactly one shell and one POS sale layout.  This patch replaces
only the conflicting shell/POS layout while retaining the existing database,
checkout, kitchen, customer, supplier, product, rider, printer and reporting
workflows.
"""
import tkinter as tk
from tkinter import ttk


NAV = [
    "POS", "Dashboard", "Orders", "Kitchen", "Customers", "Tables / Dine-in",
    "Suppliers", "Purchases", "Products / Menu", "Inventory", "Riders / Delivery",
    "Staff", "Expenses", "Cash / Shifts", "Reports / Analytics", "Printers",
    "Settings", "Users / Permissions",
]


def install(App):
    if getattr(App, "_canonical_ui_installed", False):
        return App

    def build_shell(self):
        # Remove any widgets created by an earlier shell implementation.
        for child in list(self.winfo_children()):
            child.destroy()

        self.configure(bg="#eef1f5")
        self.side = tk.Frame(self, bg="#111827", width=235)
        self.side.pack(side="left", fill="y")
        self.side.pack_propagate(False)

        tk.Label(
            self.side, text="MK PIZZA\n& ICE BAR", bg="#111827", fg="white",
            font=("Segoe UI", 17, "bold"), justify="left"
        ).pack(anchor="w", padx=18, pady=(18, 7))
        tk.Label(
            self.side, text=f"{self.user['username']} • {self.user['role']}",
            bg="#111827", fg="#9ca3af", font=("Segoe UI", 9)
        ).pack(anchor="w", padx=18, pady=(0, 9))

        navhost = tk.Frame(self.side, bg="#111827")
        navhost.pack(fill="both", expand=True)
        self.nav_canvas = tk.Canvas(navhost, bg="#111827", highlightthickness=0, bd=0)
        self.nav_scroll = ttk.Scrollbar(navhost, orient="vertical", command=self.nav_canvas.yview)
        self.nav_inner = tk.Frame(self.nav_canvas, bg="#111827")
        self.nav_window = self.nav_canvas.create_window((0, 0), window=self.nav_inner, anchor="nw")
        self.nav_canvas.configure(yscrollcommand=self.nav_scroll.set)
        self.nav_canvas.pack(side="left", fill="both", expand=True)
        self.nav_scroll.pack(side="right", fill="y")

        self.navbuttons = {}
        for name in NAV:
            b = tk.Button(
                self.nav_inner, text=name, anchor="w", relief="flat", bd=0,
                bg="#111827", fg="#f8fafc", activebackground="#2563eb",
                activeforeground="white", font=("Segoe UI", 10, "bold"),
                padx=18, pady=9, cursor="hand2",
                command=lambda n=name: self.show(n)
            )
            b.pack(fill="x", padx=3, pady=1)
            self.navbuttons[name] = b

        footer = tk.Frame(self.side, bg="#111827", height=42)
        footer.pack(side="bottom", fill="x")
        footer.pack_propagate(False)
        tk.Label(
            footer, text="MK Pizza & Ice Bar", bg="#111827", fg="#64748b",
            font=("Segoe UI", 8)
        ).pack(anchor="w", padx=18, pady=10)

        def nav_sync(_=None):
            self.nav_canvas.configure(scrollregion=self.nav_canvas.bbox("all"))
            self.nav_canvas.itemconfigure(self.nav_window, width=max(1, self.nav_canvas.winfo_width()))

        self.nav_inner.bind("<Configure>", nav_sync)
        self.nav_canvas.bind("<Configure>", nav_sync)

        def nav_wheel(event):
            if self.nav_canvas.winfo_exists():
                self.nav_canvas.yview_scroll(-1 * int((event.delta or 0) / 120), "units")

        self.nav_canvas.bind("<MouseWheel>", nav_wheel)
        self.nav_inner.bind("<MouseWheel>", nav_wheel)
        for b in self.navbuttons.values():
            b.bind("<MouseWheel>", nav_wheel)
        self.nav_canvas.bind("<Button-4>", lambda e: self.nav_canvas.yview_scroll(-1, "units"))
        self.nav_canvas.bind("<Button-5>", lambda e: self.nav_canvas.yview_scroll(1, "units"))

        self.bodyhost = tk.Frame(self, bg="#eef1f5")
        self.bodyhost.pack(side="left", fill="both", expand=True)
        self.body = ttk.Frame(self.bodyhost, padding=16)
        self.body.pack(fill="both", expand=True)
        self.bodyinner = self.body

    def page_pos(self):
        self.title("New Sale", "Fast checkout: select products, review the cart, then open checkout for customer, table, delivery and payment details.")

        root = ttk.Frame(self.bodyinner)
        root.pack(fill="both", expand=True)
        root.rowconfigure(1, weight=1)
        root.columnconfigure(0, weight=3)
        root.columnconfigure(1, weight=2)

        toolbar = ttk.Frame(root)
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        toolbar.columnconfigure(0, weight=1)
        self.search = tk.StringVar()
        entry = ttk.Entry(toolbar, textvariable=self.search)
        entry.grid(row=0, column=0, sticky="ew")
        entry.bind("<KeyRelease>", lambda _e: self.load_menu())
        ttk.Button(toolbar, text="SEARCH / FILTER", command=self.load_menu).grid(row=0, column=1, padx=(6, 0))
        ttk.Button(toolbar, text="OPEN ORDERS", command=lambda: self.show("Orders")).grid(row=0, column=2, padx=6)
        ttk.Button(toolbar, text="KITCHEN", command=lambda: self.show("Kitchen")).grid(row=0, column=3)

        left = ttk.LabelFrame(root, text="Menu / Products", padding=8)
        right = ttk.LabelFrame(root, text="Current Order", padding=8)
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 5))
        right.grid(row=1, column=1, sticky="nsew", padx=(5, 0))
        left.rowconfigure(0, weight=1); left.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1); right.columnconfigure(0, weight=1)

        self.menu = self.table(left, ("name", "cat", "price", "stock", "barcode"),
                               {"name": "Product", "cat": "Category", "price": "Price", "stock": "Stock", "barcode": "Barcode"}, 16)
        self.menu.grid(row=0, column=0, sticky="nsew")
        self.menu.bind("<Double-1>", lambda _e: self.add_item())
        ttk.Button(left, text="+ ADD SELECTED TO ORDER", style="Primary.TButton", command=self.add_item).grid(row=1, column=0, sticky="ew", pady=(8, 0))

        self.ct = self.table(right, ("name", "qty", "unit", "total"),
                             {"name": "Item", "qty": "Qty", "unit": "Unit", "total": "Total"}, 12)
        self.ct.grid(row=0, column=0, sticky="nsew")
        controls = ttk.Frame(right)
        controls.grid(row=1, column=0, sticky="ew", pady=7)
        ttk.Button(controls, text="+ Qty", command=lambda: self.qty(1)).pack(side="left")
        ttk.Button(controls, text="- Qty", command=lambda: self.qty(-1)).pack(side="left", padx=4)
        ttk.Button(controls, text="REMOVE", command=self.remove).pack(side="left")
        ttk.Button(controls, text="CLEAR", command=self._canonical_clear_cart).pack(side="right")

        summary = ttk.Frame(right)
        summary.grid(row=2, column=0, sticky="ew", pady=(4, 6))
        summary.columnconfigure(0, weight=1)
        ttk.Label(summary, text="TOTAL", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w")
        self.total = tk.StringVar(value=self.money(0))
        ttk.Label(summary, textvariable=self.total, font=("Segoe UI", 22, "bold")).grid(row=0, column=1, sticky="e")

        quick = ttk.Frame(right)
        quick.grid(row=3, column=0, sticky="ew", pady=(0, 7))
        ttk.Button(quick, text="CUSTOMER / DELIVERY", command=self.checkout).pack(side="left", fill="x", expand=True)
        ttk.Button(quick, text="TABLE / DINE-IN", command=self.checkout).pack(side="left", fill="x", expand=True, padx=5)
        ttk.Button(quick, text="PAYMENT / CHECKOUT", style="Primary.TButton", command=self.checkout).pack(side="left", fill="x", expand=True)

        self.load_menu()
        self.refresh()

    def _canonical_clear_cart(self):
        self.cart.clear()
        self.refresh()

    def show(self, name):
        # The original show implementation handles all page methods.  We only
        # update the navigation highlight after it has built the page.
        original_show(self, name)
        for key, button in self.navbuttons.items():
            button.configure(bg="#2563eb" if key == name else "#111827")

    original_show = App.show
    App.build_shell = build_shell
    App.page_pos = page_pos
    App._canonical_clear_cart = _canonical_clear_cart
    App.show = show
    App._canonical_ui_installed = True
    return App
