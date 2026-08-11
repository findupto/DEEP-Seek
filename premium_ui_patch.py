"""Final visual/UX layer for MK Pizza & Ice Bar POS.
Keeps existing business/data logic intact and makes the UI consistent.
"""
import tkinter as tk
from tkinter import ttk


def install(App, Login=None):
    if getattr(App, "_premium_ui_installed", False):
        return App

    st = ttk.Style()
    try:
        st.theme_use("clam")
    except tk.TclError:
        pass
    st.configure("TFrame", background="#f4f7fb")
    st.configure("TLabel", background="#f4f7fb", foreground="#172033", font=("Segoe UI", 10))
    st.configure("Title.TLabel", background="#f4f7fb", foreground="#0f172a", font=("Segoe UI", 25, "bold"))
    st.configure("TButton", font=("Segoe UI", 9, "bold"), padding=(12, 8), background="#ffffff", foreground="#1e293b")
    st.map("TButton", background=[("active", "#e8eef8")])
    st.configure("Primary.TButton", font=("Segoe UI", 9, "bold"), padding=(13, 9), background="#2563eb", foreground="#ffffff")
    st.map("Primary.TButton", background=[("active", "#1d4ed8")])
    st.configure("Success.TButton", font=("Segoe UI", 9, "bold"), padding=(12, 9), background="#16a34a", foreground="#ffffff")
    st.map("Success.TButton", background=[("active", "#15803d")])
    st.configure("Danger.TButton", font=("Segoe UI", 9, "bold"), padding=(12, 8), background="#dc2626", foreground="#ffffff")
    st.map("Danger.TButton", background=[("active", "#b91c1c")])
    st.configure("Soft.TButton", font=("Segoe UI", 9, "bold"), padding=(11, 8), background="#eaf0f8", foreground="#1e3a5f")
    st.map("Soft.TButton", background=[("active", "#dbe7f6")])
    st.configure("TLabelframe", background="#ffffff", relief="solid", borderwidth=1)
    st.configure("TLabelframe.Label", background="#ffffff", foreground="#334155", font=("Segoe UI", 10, "bold"))
    st.configure("Treeview", background="#ffffff", fieldbackground="#ffffff", foreground="#172033", rowheight=34, font=("Segoe UI", 10), borderwidth=0)
    st.configure("Treeview.Heading", background="#e9eef5", foreground="#172033", font=("Segoe UI", 9, "bold"), padding=(8, 8))
    st.map("Treeview", background=[("selected", "#dbeafe")], foreground=[("selected", "#0f172a")])
    st.configure("TEntry", padding=7, fieldbackground="#ffffff")
    st.configure("TCombobox", padding=6, fieldbackground="#ffffff")

    def polish(root):
        for w in root.winfo_children():
            try:
                if isinstance(w, ttk.Button):
                    text = str(w.cget("text") or "").upper()
                    current = str(w.cget("style") or "")
                    if current in ("", "TButton"):
                        if any(x in text for x in ("DELETE", "REMOVE", "ARCHIVE", "CANCEL")):
                            w.configure(style="Danger.TButton")
                        elif any(x in text for x in ("ADD", "SAVE", "CHECKOUT", "PAYMENT", "CONNECT", "IMPORT", "CREATE", "OPEN SHIFT")):
                            w.configure(style="Primary.TButton")
                        elif any(x in text for x in ("REFRESH", "FILTER", "HISTORY", "VIEW", "BACKUP", "EXPORT", "DOWNLOAD")):
                            w.configure(style="Soft.TButton")
            except Exception:
                pass
            try:
                polish(w)
            except Exception:
                pass

    old_build = App.build_shell
    def build_shell(self):
        old_build(self)
        try:
            self.configure(bg="#f4f7fb")
            self.minsize(1050, 650)
            self.geometry("1440x880")
            self.side.configure(width=248, bg="#0f172a")
            for b in getattr(self, "navbuttons", {}).values():
                b.configure(bg="#0f172a", fg="#f8fafc", activebackground="#2563eb", activeforeground="white",
                            font=("Segoe UI", 10, "bold"), padx=18, pady=10, relief="flat", bd=0, cursor="hand2")
                b.bind("<Enter>", lambda _e, x=b: x.configure(bg="#1e3a8a"))
                b.bind("<Leave>", lambda _e, x=b: x.configure(bg="#2563eb" if getattr(self, "_premium_active", "") == x.cget("text") else "#0f172a"))
        except Exception:
            pass

    def modern_pos(self):
        self.title("New Sale", "Fast checkout workspace — search the menu, build the order, then checkout in one clean flow.")
        root = ttk.Frame(self.bodyinner)
        root.pack(fill="both", expand=True, pady=(2, 8))
        root.grid_rowconfigure(1, weight=1)
        root.grid_columnconfigure(0, weight=3, uniform="pos")
        root.grid_columnconfigure(1, weight=2, uniform="pos")

        tools = ttk.LabelFrame(root, text="QUICK SALE TOOLS", padding=9)
        tools.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 9))
        tools.grid_columnconfigure(0, weight=1)
        self.search = tk.StringVar()
        e = ttk.Entry(tools, textvariable=self.search)
        e.grid(row=0, column=0, sticky="ew")
        e.bind("<KeyRelease>", lambda _e: self.load_menu())
        ttk.Button(tools, text="SEARCH / FILTER", style="Soft.TButton", command=self.load_menu).grid(row=0, column=1, padx=5)
        ttk.Button(tools, text="ORDERS", command=lambda: self.show("Orders")).grid(row=0, column=2, padx=3)
        ttk.Button(tools, text="KITCHEN", command=lambda: self.show("Kitchen")).grid(row=0, column=3, padx=3)
        ttk.Button(tools, text="PRODUCTS", command=lambda: self.show("Products / Menu")).grid(row=0, column=4, padx=3)

        left = ttk.LabelFrame(root, text="MENU / PRODUCTS", padding=9)
        right = ttk.LabelFrame(root, text="CURRENT ORDER", padding=9)
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 6))
        right.grid(row=1, column=1, sticky="nsew", padx=(6, 0))
        left.grid_rowconfigure(0, weight=1); left.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(0, weight=1); right.grid_columnconfigure(0, weight=1)

        mf = ttk.Frame(left); mf.grid(row=0, column=0, sticky="nsew"); mf.grid_rowconfigure(0, weight=1); mf.grid_columnconfigure(0, weight=1)
        self.menu = ttk.Treeview(mf, columns=("name", "cat", "price", "stock", "barcode"), show="headings")
        for c, h, width in (("name","Product",270),("cat","Category",150),("price","Price",120),("stock","Stock",110),("barcode","Barcode",150)):
            self.menu.heading(c, text=h); self.menu.column(c, width=width, minwidth=80, stretch=True)
        my = ttk.Scrollbar(mf, orient="vertical", command=self.menu.yview); mx = ttk.Scrollbar(mf, orient="horizontal", command=self.menu.xview)
        self.menu.configure(yscrollcommand=my.set, xscrollcommand=mx.set)
        self.menu.grid(row=0, column=0, sticky="nsew"); my.grid(row=0, column=1, sticky="ns"); mx.grid(row=1, column=0, sticky="ew")
        self.menu.bind("<Double-1>", lambda _e: self.add_item())
        ttk.Button(left, text="+ ADD SELECTED TO ORDER", style="Primary.TButton", command=self.add_item).grid(row=1, column=0, sticky="ew", pady=(9, 0))

        cf = ttk.Frame(right); cf.grid(row=0, column=0, sticky="nsew"); cf.grid_rowconfigure(0, weight=1); cf.grid_columnconfigure(0, weight=1)
        self.ct = ttk.Treeview(cf, columns=("name", "qty", "unit", "total"), show="headings")
        for c, h, width in (("name","Item",230),("qty","Qty",70),("unit","Unit",100),("total","Total",120)):
            self.ct.heading(c, text=h); self.ct.column(c, width=width, minwidth=60, stretch=True)
        cy = ttk.Scrollbar(cf, orient="vertical", command=self.ct.yview); cx = ttk.Scrollbar(cf, orient="horizontal", command=self.ct.xview)
        self.ct.configure(yscrollcommand=cy.set, xscrollcommand=cx.set)
        self.ct.grid(row=0, column=0, sticky="nsew"); cy.grid(row=0, column=1, sticky="ns"); cx.grid(row=1, column=0, sticky="ew")
        controls = ttk.Frame(right); controls.grid(row=1, column=0, sticky="ew", pady=8)
        ttk.Button(controls, text="+ QTY", command=lambda: self.qty(1)).pack(side="left")
        ttk.Button(controls, text="- QTY", command=lambda: self.qty(-1)).pack(side="left", padx=4)
        ttk.Button(controls, text="REMOVE", style="Danger.TButton", command=self.remove).pack(side="left")
        ttk.Button(controls, text="CLEAR", style="Soft.TButton", command=lambda: (self.cart.clear(), self.refresh())).pack(side="right")
        summary = ttk.Frame(right); summary.grid(row=2, column=0, sticky="ew", pady=(4, 8)); summary.grid_columnconfigure(0, weight=1)
        ttk.Label(summary, text="ORDER TOTAL", foreground="#64748b", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w")
        self.total = tk.StringVar(value=self.money(0)); ttk.Label(summary, textvariable=self.total, foreground="#0f172a", font=("Segoe UI", 24, "bold")).grid(row=1, column=0, sticky="w")
        quick = ttk.Frame(right); quick.grid(row=3, column=0, sticky="ew")
        ttk.Button(quick, text="CUSTOMER / DELIVERY", command=self.checkout).pack(side="left", fill="x", expand=True)
        ttk.Button(quick, text="TABLE / DINE-IN", command=self.checkout).pack(side="left", fill="x", expand=True, padx=5)
        ttk.Button(quick, text="CHECKOUT / SEND KITCHEN", style="Success.TButton", command=self.checkout).pack(side="left", fill="x", expand=True)
        self.load_menu(); self.refresh()

    old_show = App.show
    def show(self, name):
        self._premium_active = name
        result = old_show(self, name)
        try:
            polish(self.bodyinner)
            self.update_idletasks()
        except Exception:
            pass
        return result

    App.build_shell = build_shell
    App.page_pos = modern_pos
    App.show = show
    App._premium_ui_installed = True

    if Login is not None and not getattr(Login, "_premium_login_installed", False):
        old_login = Login.__init__
        def login_init(self, *a, **kw):
            old_login(self, *a, **kw)
            try:
                self.configure(bg="#0f172a")
                self.geometry("470x380")
            except Exception:
                pass
        Login.__init__ = login_init
        Login._premium_login_installed = True
    return App
