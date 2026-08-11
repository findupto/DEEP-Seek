"""Ultimate POS completion layer.

Adds missing day-to-day POS controls without replacing the existing business logic:
- held/resume orders
- split/partial payments and payment ledger
- returns/refunds with stock restoration
- cash drawer movements
- end-of-day reconciliation
- keyboard-first POS shortcuts and barcode lookup
- dark premium presentation layer
- operational indexes and integrity constraints
"""
import json
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime


def now():
    return datetime.now().isoformat(timespec="seconds")


def money(v):
    return f"Rs. {float(v or 0):,.2f}"


def install(App, Login=None):
    if getattr(App, "_ultimate_pos_installed", False):
        return App

    _install_schema(App)
    _install_navigation(App)
    _install_pages(App)
    _install_shortcuts(App)
    _install_theme(App, Login)
    App._ultimate_pos_installed = True
    return App


def _install_schema(App):
    old_init = App.__init__
    if getattr(App, "_ultimate_schema_installed", False):
        return

    def init(self, *args, **kwargs):
        old_init(self, *args, **kwargs)
        try:
            self.s.c.executescript("""
            CREATE TABLE IF NOT EXISTS held_orders(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                cart_json TEXT NOT NULL,
                customer_id INTEGER,
                order_type TEXT DEFAULT 'Counter',
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                user_id INTEGER,
                status TEXT DEFAULT 'Held'
            );
            CREATE TABLE IF NOT EXISTS sale_returns(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_id INTEGER NOT NULL,
                invoice_no TEXT NOT NULL,
                amount REAL NOT NULL,
                refund_method TEXT DEFAULT 'Cash',
                reason TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                user_id INTEGER
            );
            CREATE TABLE IF NOT EXISTS sale_return_items(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                return_id INTEGER NOT NULL,
                sale_item_id INTEGER NOT NULL,
                product_id INTEGER,
                product_name TEXT,
                quantity REAL NOT NULL,
                unit_price REAL NOT NULL,
                line_total REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS cash_drawer(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shift_id INTEGER,
                direction TEXT NOT NULL,
                category TEXT NOT NULL,
                amount REAL NOT NULL,
                note TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                user_id INTEGER
            );
            CREATE TABLE IF NOT EXISTS payment_allocations(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_id INTEGER NOT NULL,
                method TEXT NOT NULL,
                amount REAL NOT NULL,
                reference TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                user_id INTEGER
            );
            CREATE INDEX IF NOT EXISTS idx_held_status ON held_orders(status,created_at);
            CREATE INDEX IF NOT EXISTS idx_returns_sale ON sale_returns(sale_id,created_at);
            CREATE INDEX IF NOT EXISTS idx_cash_drawer_shift ON cash_drawer(shift_id,created_at);
            CREATE INDEX IF NOT EXISTS idx_payment_allocations_sale ON payment_allocations(sale_id,created_at);
            """)
            self.s.c.commit()
        except sqlite3.Error:
            pass

    App.__init__ = init
    App._ultimate_schema_installed = True


def _install_navigation(App):
    nav = list(getattr(App, "NAV", []))
    additions = [
        "Held Orders", "Payments / Receipts", "Returns / Refunds",
        "Cash Drawer", "End of Day"
    ]
    for item in additions:
        if item not in nav:
            # Keep operational pages together before Settings.
            try:
                nav.insert(nav.index("Settings"), item)
            except ValueError:
                nav.append(item)
    App.NAV = nav


def _tree(parent, cols, heads, height=15):
    f = ttk.Frame(parent)
    f.pack(fill="both", expand=True)
    t = ttk.Treeview(f, columns=cols, show="headings", height=height)
    for c in cols:
        t.heading(c, text=heads.get(c, c.replace("_", " ").title()))
        t.column(c, width=125, minwidth=70, anchor="w")
    sy = ttk.Scrollbar(f, orient="vertical", command=t.yview)
    sx = ttk.Scrollbar(f, orient="horizontal", command=t.xview)
    t.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
    t.grid(row=0, column=0, sticky="nsew")
    sy.grid(row=0, column=1, sticky="ns")
    sx.grid(row=1, column=0, sticky="ew")
    f.rowconfigure(0, weight=1)
    f.columnconfigure(0, weight=1)
    return t


def _install_pages(App):
    def page_held_orders(self):
        self.title("Held Orders", "Pause a live basket and resume it later without losing the order.")
        top = ttk.Frame(self.bodyinner)
        top.pack(fill="x", pady=(0, 10))
        ttk.Button(top, text="HOLD CURRENT CART", style="Primary.TButton", command=lambda: _hold_current(self)).pack(side="left")
        ttk.Button(top, text="REFRESH", command=lambda: self.show("Held Orders")).pack(side="left", padx=6)
        t = _tree(self.bodyinner, ("id", "name", "type", "customer", "items", "total", "created"),
                  {"id":"ID","name":"Hold Name","type":"Order Type","customer":"Customer","items":"Items","total":"Total","created":"Created"}, 15)
        rows = self.s.rows("""SELECT h.*,COALESCE(c.name,'Walk-in') customer
                              FROM held_orders h LEFT JOIN customers c ON c.id=h.customer_id
                              WHERE h.status='Held' ORDER BY h.id DESC""")
        for r in rows:
            try:
                items = json.loads(r["cart_json"])
                total = sum(float(x.get("qty", 0))*float(x.get("price", 0)) for x in items.values())
                count = sum(float(x.get("qty", 0)) for x in items.values())
            except Exception:
                total, count = 0, 0
            t.insert("", "end", iid=str(r["id"]), values=(r["id"], r["name"], r["order_type"], r["customer"], count, money(total), r["created_at"]))
        def resume(_=None):
            sel = t.selection()
            if sel: _resume_hold(self, int(sel[0]))
        t.bind("<Double-1>", resume)
        ttk.Button(self.bodyinner, text="RESUME SELECTED", style="Success.TButton", command=resume).pack(fill="x", pady=8)

    def page_payments_receipts(self):
        self.title("Payments / Receipts", "Split payments, partial payments, balances and receipt reprints in one ledger.")
        t = _tree(self.bodyinner, ("id","invoice","customer","total","paid","due","status","date"),
                  {"id":"ID","invoice":"Invoice","customer":"Customer","total":"Total","paid":"Paid","due":"Due","status":"Status","date":"Date"}, 16)
        rows = self.s.rows("""SELECT s.id,s.invoice_no,COALESCE(c.name,'Walk-in') customer,s.total,s.created_at,
                              COALESCE((SELECT SUM(amount) FROM payments p WHERE p.sale_id=s.id),0) paid
                              FROM sales s LEFT JOIN customers c ON c.id=s.customer_id ORDER BY s.id DESC LIMIT 500""")
        for r in rows:
            paid = float(r["paid"] or 0); due = max(0, float(r["total"] or 0)-paid)
            status = "Paid" if due <= 0.009 else ("Partial" if paid > 0 else "Unpaid")
            t.insert("", "end", iid=str(r["id"]), values=(r["id"],r["invoice"],r["customer"],money(r["total"]),money(paid),money(due),status,r["created_at"]))
        def manage(_=None):
            sel=t.selection()
            if sel: _payment_dialog(self,int(sel[0]))
        t.bind("<Double-1>",manage)
        ttk.Button(self.bodyinner,text="ADD PAYMENT / SPLIT PAYMENT",style="Primary.TButton",command=manage).pack(fill="x",pady=8)

    def page_returns_refunds(self):
        self.title("Returns / Refunds", "Return sold items safely, restore stock, and record the refund method.")
        top=ttk.Frame(self.bodyinner);top.pack(fill="x",pady=(0,10))
        ttk.Button(top,text="CREATE RETURN",style="Primary.TButton",command=lambda:_return_dialog(self)).pack(side="left")
        t=_tree(self.bodyinner,("id","invoice","amount","method","reason","date"),
                {"id":"ID","invoice":"Invoice","amount":"Refund","method":"Method","reason":"Reason","date":"Date"},15)
        for r in self.s.rows("SELECT * FROM sale_returns ORDER BY id DESC LIMIT 500"):
            t.insert("","end",values=(r["id"],r["invoice_no"],money(r["amount"]),r["refund_method"],r["reason"],r["created_at"]))

    def page_cash_drawer(self):
        self.title("Cash Drawer", "Record paid-in / paid-out movements and reconcile the physical drawer.")
        top=ttk.Frame(self.bodyinner);top.pack(fill="x",pady=(0,10))
        ttk.Button(top,text="CASH IN",style="Primary.TButton",command=lambda:_cash_move(self,"IN")).pack(side="left")
        ttk.Button(top,text="CASH OUT",style="Danger.TButton",command=lambda:_cash_move(self,"OUT")).pack(side="left",padx=6)
        summary=self.s.q("SELECT COALESCE(SUM(CASE WHEN direction='IN' THEN amount ELSE -amount END),0) balance FROM cash_drawer").fetchone()
        box=ttk.LabelFrame(self.bodyinner,text="DRAWER MOVEMENT BALANCE",padding=14);box.pack(fill="x",pady=(0,10))
        ttk.Label(box,text=money(summary["balance"]),font=("Segoe UI",22,"bold")).pack(anchor="w")
        t=_tree(self.bodyinner,("date","direction","category","amount","note"),
                {"date":"Date","direction":"Direction","category":"Category","amount":"Amount","note":"Note"},14)
        for r in self.s.rows("SELECT created_at,direction,category,amount,note FROM cash_drawer ORDER BY id DESC LIMIT 500"):
            t.insert("","end",values=(r["created_at"],r["direction"],r["category"],money(r["amount"]),r["note"]))

    def page_end_of_day(self):
        self.title("End of Day", "Close the shift with a calculated sales, refund, expense and cash reconciliation.")
        today=datetime.now().strftime("%Y-%m-%d")
        sales=self.s.q("SELECT COUNT(*) n,COALESCE(SUM(total),0) total FROM sales WHERE date(created_at)=date('now','localtime')").fetchone()
        paid=self.s.q("SELECT COALESCE(SUM(amount),0) total FROM payments WHERE date(created_at)=date('now','localtime')").fetchone()
        refunds=self.s.q("SELECT COALESCE(SUM(amount),0) total FROM sale_returns WHERE date(created_at)=date('now','localtime')").fetchone()
        expenses=self.s.q("SELECT COALESCE(SUM(amount),0) total FROM expenses WHERE date(created_at)=date('now','localtime')").fetchone()
        drawer=self.s.q("SELECT COALESCE(SUM(CASE WHEN direction='IN' THEN amount ELSE -amount END),0) total FROM cash_drawer WHERE date(created_at)=date('now','localtime')").fetchone()
        grid=ttk.Frame(self.bodyinner);grid.pack(fill="x",pady=10)
        for label,val in (("Orders",sales["n"]),("Gross Sales",money(sales["total"])),("Payments",money(paid["total"])),("Refunds",money(refunds["total"])),("Expenses",money(expenses["total"])),("Drawer Movement",money(drawer["total"]))):
            b=ttk.LabelFrame(grid,text=label,padding=14);b.pack(side="left",fill="both",expand=True,padx=3);ttk.Label(b,text=str(val),font=("Segoe UI",16,"bold")).pack(anchor="w")
        note=ttk.LabelFrame(self.bodyinner,text="RECONCILIATION",padding=14);note.pack(fill="x",pady=10)
        ttk.Label(note,text=f"Business date: {today}\nExpected movement = payments - refunds - expenses + manual drawer movements.\nUse Cash / Shifts for physical count and shift closure.",foreground="#64748b").pack(anchor="w")
        ttk.Button(self.bodyinner,text="BACKUP DATABASE",style="Primary.TButton",command=self.backup).pack(fill="x",pady=8)

    App.page_held_orders=page_held_orders
    App.page_payments_receipts=page_payments_receipts
    App.page_returns_refunds=page_returns_refunds
    App.page_cash_drawer=page_cash_drawer
    App.page_end_of_day=page_end_of_day


def _hold_current(app):
    if not getattr(app,"cart",None):
        messagebox.showwarning("Hold Order","The current cart is empty.",parent=app);return
    name=simpledialog.askstring("Hold Order","Reference name for this order:",parent=app)
    if not name:return
    try:
        payload={str(k):dict(v) for k,v in app.cart.items()}
        app.s.q("INSERT INTO held_orders(name,cart_json,created_at,user_id) VALUES(?,?,?,?)",
                (name.strip(),json.dumps(payload),now(),app.user["id"]))
        app.s.c.commit();app.cart.clear()
        if hasattr(app,"refresh"):app.refresh()
        messagebox.showinfo("Order Held",f"{name.strip()} is safely stored.",parent=app)
    except Exception as e:messagebox.showerror("Hold Order",str(e),parent=app)


def _resume_hold(app,hid):
    r=app.s.q("SELECT * FROM held_orders WHERE id=? AND status='Held'",(hid,)).fetchone()
    if not r:return
    try:
        app.cart={int(k):v for k,v in json.loads(r["cart_json"]).items()}
        app.s.q("UPDATE held_orders SET status='Resumed' WHERE id=?",(hid,));app.s.c.commit()
        if hasattr(app,"refresh"):app.refresh()
        app.show("POS")
    except Exception as e:messagebox.showerror("Resume Order",str(e),parent=app)


def _payment_dialog(app,sid):
    s=app.s.q("SELECT * FROM sales WHERE id=?",(sid,)).fetchone()
    if not s:return
    paid=float(app.s.q("SELECT COALESCE(SUM(amount),0) x FROM payments WHERE sale_id=?",(sid,)).fetchone()["x"] or 0)
    due=max(0,float(s["total"])-paid)
    w=app.dialog(f"Payment — {s['invoice_no']}",520,460);f=ttk.Frame(w,padding=18);f.pack(fill="both",expand=True)
    ttk.Label(f,text=f"{s['invoice_no']}  •  Total {money(s['total'])}",font=("Segoe UI",15,"bold")).pack(anchor="w")
    ttk.Label(f,text=f"Paid {money(paid)}   •   Remaining {money(due)}",foreground="#64748b").pack(anchor="w",pady=(3,15))
    method=tk.StringVar(value="Cash");amount=tk.StringVar(value=f"{due:.2f}");ref=tk.StringVar()
    ttk.Label(f,text="Payment Method").pack(anchor="w");ttk.Combobox(f,textvariable=method,values=["Cash","Card","Bank","JazzCash","EasyPaisa","Other"],state="readonly").pack(fill="x",pady=4)
    ttk.Label(f,text="Amount").pack(anchor="w",pady=(8,2));ttk.Entry(f,textvariable=amount).pack(fill="x")
    ttk.Label(f,text="Reference (optional)").pack(anchor="w",pady=(8,2));ttk.Entry(f,textvariable=ref).pack(fill="x")
    def save():
        try:
            a=float(amount.get() or 0)
            if a<=0:raise ValueError("Payment amount must be greater than zero.")
            if a>due+0.009:raise ValueError("Payment exceeds the remaining balance.")
            app.s.q("INSERT INTO payments(sale_id,method,amount,reference,created_at,user_id) VALUES(?,?,?,?,?,?)",(sid,method.get(),a,ref.get().strip(),now(),app.user["id"]))
            new_paid=paid+a; status="Paid" if new_paid>=float(s["total"])-0.009 else "Unpaid"
            app.s.q("UPDATE sales SET payment_status=? WHERE id=?",(status,sid))
            app.s.q("INSERT INTO payment_allocations(sale_id,method,amount,reference,created_at,user_id) VALUES(?,?,?,?,?,?)",(sid,method.get(),a,ref.get().strip(),now(),app.user["id"]))
            app.s.c.commit();w.destroy();app.show("Payments / Receipts")
        except Exception as e:messagebox.showerror("Payment",str(e),parent=w)
    ttk.Button(f,text="RECORD PAYMENT",style="Primary.TButton",command=save).pack(fill="x",pady=18)


def _return_dialog(app):
    inv=simpledialog.askstring("Return / Refund","Enter the invoice number:",parent=app)
    if not inv:return
    sale=app.s.q("SELECT * FROM sales WHERE invoice_no=?",(inv.strip(),)).fetchone()
    if not sale:messagebox.showerror("Return","Invoice not found.",parent=app);return
    items=app.s.rows("SELECT * FROM sale_items WHERE sale_id=? ORDER BY id",(sale["id"],))
    if not items:messagebox.showwarning("Return","This invoice has no items.",parent=app);return
    w=app.dialog(f"Return — {inv}",760,650);f=ttk.Frame(w,padding=14);f.pack(fill="both",expand=True)
    ttk.Label(f,text=f"{inv}  •  Original total {money(sale['total'])}",font=("Segoe UI",15,"bold")).pack(anchor="w",pady=(0,8))
    vars_={}
    for it in items:
        row=ttk.Frame(f);row.pack(fill="x",pady=3)
        ttk.Label(row,text=f"{it['product_name']}  ({it['quantity']} × {money(it['unit_price'])})").pack(side="left",fill="x",expand=True)
        v=tk.StringVar(value="0");vars_[it["id"]]=v;ttk.Entry(row,textvariable=v,width=8).pack(side="right")
    method=tk.StringVar(value="Cash");reason=tk.StringVar()
    ttk.Label(f,text="Refund Method").pack(anchor="w",pady=(12,2));ttk.Combobox(f,textvariable=method,values=["Cash","Card","Bank","JazzCash","EasyPaisa","Credit"],state="readonly").pack(fill="x")
    ttk.Label(f,text="Reason").pack(anchor="w",pady=(8,2));ttk.Entry(f,textvariable=reason).pack(fill="x")
    def save():
        try:
            selected=[];total=0
            for it in items:
                q=float(vars_[it["id"]].get() or 0)
                if q<0 or q>float(it["quantity"]):raise ValueError(f"Invalid return quantity for {it['product_name']}.")
                if q:
                    total+=q*float(it["unit_price"]);selected.append((it,q))
            if not selected:raise ValueError("Select at least one item to return.")
            existing=app.s.q("SELECT COALESCE(SUM(amount),0) x FROM sale_returns WHERE sale_id=?",(sale["id"],)).fetchone()["x"]
            if total>float(sale["total"])-float(existing or 0)+0.009:raise ValueError("Return exceeds the remaining refundable amount.")
            cur=app.s.q("INSERT INTO sale_returns(sale_id,invoice_no,amount,refund_method,reason,created_at,user_id) VALUES(?,?,?,?,?,?,?)",(sale["id"],inv,total,method.get(),reason.get().strip(),now(),app.user["id"]))
            rid=cur.lastrowid
            for it,q in selected:
                line=q*float(it["unit_price"])
                app.s.q("INSERT INTO sale_return_items(return_id,sale_item_id,product_id,product_name,quantity,unit_price,line_total) VALUES(?,?,?,?,?,?,?)",(rid,it["id"],it["product_id"],it["product_name"],q,it["unit_price"],line))
                app.s.q("UPDATE products SET stock=stock+? WHERE id=?",(q,it["product_id"]))
                app.s.q("INSERT INTO stock_movements(product_id,qty,movement_type,note,created_at,user_id) VALUES(?,?,?,?,?,?)",(it["product_id"],q,"RETURN",inv,now(),app.user["id"]))
            if method.get()=="Credit" and sale["customer_id"]:
                app.s.q("UPDATE customers SET balance=MAX(0,COALESCE(balance,0)-?) WHERE id=?",(total,sale["customer_id"]))
            app.s.q("INSERT INTO payments(sale_id,method,amount,reference,created_at,user_id) VALUES(?,?,?,?,?,?)",(sale["id"],"Refund - "+method.get(),-total,reason.get().strip(),now(),app.user["id"]))
            app.s.c.commit();w.destroy();messagebox.showinfo("Return Complete",f"Refund recorded: {money(total)}",parent=app);app.show("Returns / Refunds")
        except Exception as e:messagebox.showerror("Return",str(e),parent=w)
    ttk.Button(f,text="PROCESS RETURN / REFUND",style="Primary.TButton",command=save).pack(fill="x",pady=18)


def _cash_move(app,direction):
    w=app.dialog("Cash In" if direction=="IN" else "Cash Out",440,330);f=ttk.Frame(w,padding=18);f.pack(fill="both",expand=True)
    cat=tk.StringVar(value="Cash Sale" if direction=="IN" else "Expense");amount=tk.StringVar();note=tk.StringVar()
    ttk.Label(f,text="Category").pack(anchor="w");ttk.Entry(f,textvariable=cat).pack(fill="x",pady=4)
    ttk.Label(f,text="Amount").pack(anchor="w",pady=(8,2));ttk.Entry(f,textvariable=amount).pack(fill="x")
    ttk.Label(f,text="Note").pack(anchor="w",pady=(8,2));ttk.Entry(f,textvariable=note).pack(fill="x")
    def save():
        try:
            a=float(amount.get() or 0)
            if a<=0:raise ValueError("Amount must be greater than zero.")
            app.s.q("INSERT INTO cash_drawer(direction,category,amount,note,created_at,user_id) VALUES(?,?,?,?,?,?)",(direction,cat.get().strip() or "Manual",a,note.get().strip(),now(),app.user["id"]))
            app.s.c.commit();w.destroy();app.show("Cash Drawer")
        except Exception as e:messagebox.showerror("Cash Drawer",str(e),parent=w)
    ttk.Button(f,text="SAVE MOVEMENT",style="Primary.TButton",command=save).pack(fill="x",pady=18)


def _install_shortcuts(App):
    old_init=App.__init__
    if getattr(App,"_ultimate_shortcuts_installed",False):return
    def init(self,*args,**kwargs):
        old_init(self,*args,**kwargs)
        self.bind_all("<Control-h>",lambda _e:_hold_current(self))
        self.bind_all("<Control-r>",lambda _e:self.show("Returns / Refunds"))
        self.bind_all("<F2>",lambda _e:_focus_search(self))
        self.bind_all("<F4>",lambda _e:_safe_checkout(self))
        self.bind_all("<Escape>",lambda _e:self.show("POS"))
        # Barcode scanners behave like keyboards and normally terminate with Enter.
        self.bind_all("<Return>",lambda _e:_barcode_enter(self))
    App.__init__=init;App._ultimate_shortcuts_installed=True


def _focus_search(app):
    w=getattr(app,"search",None)
    if isinstance(w,tk.StringVar):
        for child in app.winfo_children():
            try:
                entries=[]
                def walk(x):
                    for c in x.winfo_children():
                        if isinstance(c,ttk.Entry):entries.append(c)
                        walk(c)
                walk(child)
                if entries:
                    entries[0].focus_set();return
            except Exception:pass


def _safe_checkout(app):
    try:
        if hasattr(app,"checkout"):app.checkout()
    except Exception as e:messagebox.showerror("Checkout",str(e),parent=app)


def _barcode_enter(app):
    try:
        focus=app.focus_get()
        if focus is None:return
        text=str(focus.get()) if hasattr(focus,"get") else ""
        if not text or len(text)>80:return
        row=app.s.q("SELECT * FROM products WHERE active=1 AND barcode=? LIMIT 1",(text.strip(),)).fetchone()
        if row and hasattr(app,"add_item"):
            try:
                app.menu.selection_set(str(row["id"]));app.menu.focus(str(row["id"]));app.add_item();focus.delete(0,"end")
            except Exception:pass
    except Exception:pass


def _install_theme(App, Login):
    try:
        style=ttk.Style();style.theme_use("clam")
        bg="#0b1020";panel="#111827";panel2="#172033";fg="#e5e7eb";muted="#94a3b8";accent="#8b5cf6";cyan="#22d3ee"
        style.configure("TFrame",background=bg);style.configure("TLabel",background=bg,foreground=fg,font=("Segoe UI",10))
        style.configure("Title.TLabel",background=bg,foreground="#f8fafc",font=("Segoe UI",25,"bold"))
        style.configure("TLabelframe",background=panel,foreground=fg,borderwidth=1,relief="solid")
        style.configure("TLabelframe.Label",background=panel,foreground=cyan,font=("Segoe UI",10,"bold"))
        style.configure("TButton",background=panel2,foreground=fg,padding=(11,8),font=("Segoe UI",9,"bold"),borderwidth=0)
        style.map("TButton",background=[("active",accent)])
        style.configure("Primary.TButton",background=accent,foreground="white",padding=(12,9),font=("Segoe UI",9,"bold"))
        style.configure("Success.TButton",background="#059669",foreground="white",padding=(12,9),font=("Segoe UI",9,"bold"))
        style.configure("Danger.TButton",background="#b91c1c",foreground="white",padding=(12,9),font=("Segoe UI",9,"bold"))
        style.configure("Soft.TButton",background="#1e293b",foreground=fg,padding=(11,8),font=("Segoe UI",9,"bold"))
        style.configure("TEntry",fieldbackground="#0f172a",foreground=fg,insertcolor=cyan,padding=7)
        style.configure("TCombobox",fieldbackground="#0f172a",foreground=fg,padding=6)
        style.configure("Treeview",background="#0f172a",fieldbackground="#0f172a",foreground=fg,rowheight=32,borderwidth=0)
        style.configure("Treeview.Heading",background="#1e293b",foreground="#cbd5e1",font=("Segoe UI",9,"bold"),padding=8)
        style.map("Treeview",background=[("selected", "#312e81")],foreground=[("selected", "white")])
    except Exception:
        pass

    if Login is not None and not getattr(Login,"_ultimate_login_installed",False):
        old=Login.__init__
        def login_init(self,*args,**kwargs):
            old(self,*args,**kwargs)
            try:self.configure(bg="#0b1020")
            except Exception:pass
        Login.__init__=login_init;Login._ultimate_login_installed=True

    old_build=App.build_shell
    if getattr(App,"_ultimate_shell_installed",False):return
    def build_shell(self):
        old_build(self)
        try:
            self.configure(bg="#0b1020");self.geometry("1440x880");self.minsize(980,620)
            self.side.configure(bg="#090d18")
            for b in getattr(self,"navbuttons",{}).values():
                b.configure(bg="#090d18",fg="#e5e7eb",activebackground="#4c1d95",activeforeground="white",font=("Segoe UI",10,"bold"),cursor="hand2")
        except Exception:pass
    App.build_shell=build_shell;App._ultimate_shell_installed=True
