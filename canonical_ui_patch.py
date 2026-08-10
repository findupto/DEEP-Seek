"""Canonical responsive UI for the POS.

This is the single final UI layer. It keeps the existing functional modules,
but provides a real scrollable sidebar/body and a POS layout that never mixes
Tk geometry managers in the same container.
"""
import tkinter as tk
from tkinter import ttk

NAV = [
    "POS", "Dashboard", "Orders", "Kitchen", "Customers", "Tables / Dine-in",
    "Suppliers", "Purchases", "Products / Menu", "Inventory", "Riders / Delivery",
    "Staff", "Expenses", "Cash / Shifts", "Reports / Analytics", "Printers",
    "Settings", "Users / Permissions",
]


def _scrollable_frame(parent, bg="#eef1f5", pad=0):
    host = tk.Frame(parent, bg=bg)
    host.grid_rowconfigure(0, weight=1)
    host.grid_columnconfigure(0, weight=1)
    canvas = tk.Canvas(host, bg=bg, highlightthickness=0, bd=0)
    ybar = ttk.Scrollbar(host, orient="vertical", command=canvas.yview)
    xbar = ttk.Scrollbar(host, orient="horizontal", command=canvas.xview)
    inner = ttk.Frame(canvas, padding=pad)
    window = canvas.create_window((0, 0), window=inner, anchor="nw")
    canvas.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
    canvas.grid(row=0, column=0, sticky="nsew")
    ybar.grid(row=0, column=1, sticky="ns")
    xbar.grid(row=1, column=0, sticky="ew")

    def sync(_=None):
        canvas.configure(scrollregion=canvas.bbox("all"))
        # Keep the normal case fluid; horizontal scrolling remains available
        # when a page deliberately needs more width.
        canvas.itemconfigure(window, width=max(canvas.winfo_width(), inner.winfo_reqwidth()))

    inner.bind("<Configure>", sync)
    canvas.bind("<Configure>", sync)

    def wheel(event):
        if event.delta:
            canvas.yview_scroll(-int(event.delta / 120), "units")
        return "break"

    canvas.bind("<MouseWheel>", wheel)
    inner.bind("<MouseWheel>", wheel)
    canvas.bind("<Button-4>", lambda _e: canvas.yview_scroll(-1, "units"))
    canvas.bind("<Button-5>", lambda _e: canvas.yview_scroll(1, "units"))
    inner.bind("<Button-4>", lambda _e: canvas.yview_scroll(-1, "units"))
    inner.bind("<Button-5>", lambda _e: canvas.yview_scroll(1, "units"))
    return host, inner, canvas, ybar, xbar


def _grid_table(parent, cols, heads, height=14):
    """Treeview whose complete container is managed by grid.

    The base App.table() intentionally uses pack(), so it must not be gridded
    into the same parent. This helper is used only by the grid-based POS page.
    """
    frame = ttk.Frame(parent)
    frame.grid_rowconfigure(0, weight=1)
    frame.grid_columnconfigure(0, weight=1)
    tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse", height=height)
    for c in cols:
        tree.heading(c, text=heads.get(c, c.title()))
        tree.column(c, width=120, minwidth=70, anchor="w", stretch=True)
    ybar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    xbar = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
    tree.grid(row=0, column=0, sticky="nsew")
    ybar.grid(row=0, column=1, sticky="ns")
    xbar.grid(row=1, column=0, sticky="ew")
    return frame, tree


def install(App):
    if getattr(App, "_canonical_ui_installed", False):
        return App

    def build_shell(self):
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
        ).pack(anchor="w", padx=18, pady=(0, 8))

        navhost = tk.Frame(self.side, bg="#111827")
        navhost.pack(fill="both", expand=True, padx=(7, 0), pady=(0, 4))
        navhost.grid_rowconfigure(0, weight=1)
        navhost.grid_columnconfigure(0, weight=1)
        self.nav_canvas = tk.Canvas(navhost, bg="#111827", highlightthickness=0, bd=0)
        self.nav_scroll = tk.Scrollbar(
            navhost, orient="vertical", command=self.nav_canvas.yview,
            bg="#334155", troughcolor="#0b1220", activebackground="#64748b",
            width=14, highlightthickness=0, bd=0
        )
        self.navbar = tk.Frame(self.nav_canvas, bg="#111827")
        self.navwin = self.nav_canvas.create_window((0, 0), window=self.navbar, anchor="nw")
        self.nav_canvas.configure(yscrollcommand=self.nav_scroll.set)
        self.nav_canvas.grid(row=0, column=0, sticky="nsew")
        self.nav_scroll.grid(row=0, column=1, sticky="ns")

        self.navbuttons = {}
        for name in NAV:
            b = tk.Button(
                self.navbar, text=name, anchor="w", relief="flat", bd=0,
                bg="#111827", fg="#f8fafc", activebackground="#2563eb",
                activeforeground="white", font=("Segoe UI", 10, "bold"),
                padx=16, pady=9, cursor="hand2",
                command=lambda n=name: self.show(n)
            )
            b.pack(fill="x", padx=2, pady=1)
            self.navbuttons[name] = b

        def nav_sync(_=None):
            self.nav_canvas.configure(scrollregion=self.nav_canvas.bbox("all"))
            self.nav_canvas.itemconfigure(self.navwin, width=max(1, self.nav_canvas.winfo_width()))

        self.navbar.bind("<Configure>", nav_sync)
        self.nav_canvas.bind("<Configure>", nav_sync)

        def nav_wheel(event):
            if event.delta:
                self.nav_canvas.yview_scroll(-int(event.delta / 120), "units")
            return "break"

        for widget in (self.nav_canvas, self.navbar, *self.navbuttons.values()):
            widget.bind("<MouseWheel>", nav_wheel)
            widget.bind("<Button-4>", lambda _e: self.nav_canvas.yview_scroll(-1, "units"))
            widget.bind("<Button-5>", lambda _e: self.nav_canvas.yview_scroll(1, "units"))

        footer = tk.Frame(self.side, bg="#111827", height=38)
        footer.pack(side="bottom", fill="x")
        footer.pack_propagate(False)
        tk.Label(
            footer, text="MK Pizza & Ice Bar", bg="#111827", fg="#64748b",
            font=("Segoe UI", 8)
        ).pack(anchor="w", padx=18, pady=9)

        # Keep the existing page API: every module writes into self.body.
        bodyhost = tk.Frame(self, bg="#eef1f5")
        bodyhost.pack(side="left", fill="both", expand=True)
        bodyhost.grid_rowconfigure(0, weight=1)
        bodyhost.grid_columnconfigure(0, weight=1)
        body_canvas = tk.Canvas(bodyhost, bg="#eef1f5", highlightthickness=0, bd=0)
        body_y = ttk.Scrollbar(bodyhost, orient="vertical", command=body_canvas.yview)
        body_x = ttk.Scrollbar(bodyhost, orient="horizontal", command=body_canvas.xview)
        body = ttk.Frame(body_canvas, padding=16)
        body_window = body_canvas.create_window((0, 0), window=body, anchor="nw")
        body_canvas.configure(yscrollcommand=body_y.set, xscrollcommand=body_x.set)
        body_canvas.grid(row=0, column=0, sticky="nsew")
        body_y.grid(row=0, column=1, sticky="ns")
        body_x.grid(row=1, column=0, sticky="ew")

        def body_sync(_=None):
            body_canvas.configure(scrollregion=body_canvas.bbox("all"))
            body_canvas.itemconfigure(body_window, width=max(body_canvas.winfo_width(), body.winfo_reqwidth()))

        body.bind("<Configure>", body_sync)
        body_canvas.bind("<Configure>", body_sync)

        def body_wheel(event):
            if event.delta:
                body_canvas.yview_scroll(-int(event.delta / 120), "units")
            return "break"

        body_canvas.bind("<MouseWheel>", body_wheel)
        body.bind("<MouseWheel>", body_wheel)
        body_canvas.bind("<Button-4>", lambda _e: body_canvas.yview_scroll(-1, "units"))
        body_canvas.bind("<Button-5>", lambda _e: body_canvas.yview_scroll(1, "units"))

        self.bodyhost = bodyhost
        self.body = body
        self.bodyinner = body
        self._body_canvas = body_canvas

    def page_pos(self):
        self.title(
            "New Sale",
            "Fast checkout: select products, review the cart, then open checkout for customer, table, delivery and payment details."
        )

        root = ttk.Frame(self.bodyinner)
        root.pack(fill="both", expand=True)
        root.grid_rowconfigure(1, weight=1)
        root.grid_columnconfigure(0, weight=3, uniform="pos")
        root.grid_columnconfigure(1, weight=2, uniform="pos")

        toolbar = ttk.Frame(root)
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        toolbar.grid_columnconfigure(0, weight=1)
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
        left.grid_rowconfigure(0, weight=1); left.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(0, weight=1); right.grid_columnconfigure(0, weight=1)

        menu_frame, self.menu = _grid_table(
            left,
            ("name", "cat", "price", "stock", "barcode"),
            {"name": "Product", "cat": "Category", "price": "Price", "stock": "Stock", "barcode": "Barcode"},
            16,
        )
        menu_frame.grid(row=0, column=0, sticky="nsew")
        self.menu.bind("<Double-1>", lambda _e: self.add_item())
        ttk.Button(left, text="+ ADD SELECTED TO ORDER", style="Primary.TButton", command=self.add_item).grid(row=1, column=0, sticky="ew", pady=(8, 0))

        order_frame, self.ct = _grid_table(
            right,
            ("name", "qty", "unit", "total"),
            {"name": "Item", "qty": "Qty", "unit": "Unit", "total": "Total"},
            12,
        )
        order_frame.grid(row=0, column=0, sticky="nsew")

        controls = ttk.Frame(right)
        controls.grid(row=1, column=0, sticky="ew", pady=7)
        ttk.Button(controls, text="+ Qty", command=lambda: self.qty(1)).pack(side="left")
        ttk.Button(controls, text="- Qty", command=lambda: self.qty(-1)).pack(side="left", padx=4)
        ttk.Button(controls, text="REMOVE", command=self.remove).pack(side="left")
        ttk.Button(controls, text="CLEAR", command=self._canonical_clear_cart).pack(side="right")

        summary = ttk.Frame(right)
        summary.grid(row=2, column=0, sticky="ew", pady=(4, 6))
        summary.grid_columnconfigure(0, weight=1)
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

    original_show = App.show

    def show(self, name):
        original_show(self, name)
        if hasattr(self, "navbuttons"):
            for key, button in self.navbuttons.items():
                button.configure(bg="#2563eb" if key == name else "#111827")

    App.build_shell = build_shell
    App.page_pos = page_pos
    App._canonical_clear_cart = _canonical_clear_cart
    App.show = show
    App._canonical_ui_installed = True
    return App
