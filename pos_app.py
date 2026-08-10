import csv, hashlib, os, shutil, sqlite3, tkinter as tk
from datetime import datetime
from tkinter import ttk, messagebox, filedialog, simpledialog
from printer_manager import PrinterManager, PrinterSettings

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "pos.db")
BUSINESS = {"name":"MK Pizza & Ice Bar","address":"Collage Road Abbas Chowk, Bhakkar, Pakistan","phone":"0316 9700025","currency":"Rs.","tax":0.0}

def now(): return datetime.now().isoformat(timespec="seconds")
def hp(v): return hashlib.sha256(str(v).encode()).hexdigest()

class Store:
    def __init__(self, path=DB):
        self.c=sqlite3.connect(path); self.c.row_factory=sqlite3.Row; self.init()
    def q(self,s,a=()): return self.c.execute(s,a)
    def rows(self,s,a=()): return self.q(s,a).fetchall()
    def init(self):
        self.c.executescript("""
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,username TEXT UNIQUE,role TEXT,password_hash TEXT,active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,price REAL NOT NULL,category TEXT DEFAULT 'General',stock REAL DEFAULT 0,barcode TEXT DEFAULT '',cost REAL DEFAULT 0,active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS customers(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,phone TEXT DEFAULT '',address TEXT DEFAULT '',balance REAL DEFAULT 0,active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS suppliers(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,phone TEXT DEFAULT '',address TEXT DEFAULT '',balance REAL DEFAULT 0,active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS staff(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,phone TEXT DEFAULT '',role TEXT DEFAULT 'Staff',salary REAL DEFAULT 0,active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS riders(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,phone TEXT DEFAULT '',vehicle TEXT DEFAULT '',per_km REAL DEFAULT 0,base_fee REAL DEFAULT 0,active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS tables(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE NOT NULL,seats INTEGER DEFAULT 2,status TEXT DEFAULT 'Available');
        CREATE TABLE IF NOT EXISTS sales(id INTEGER PRIMARY KEY AUTOINCREMENT,invoice_no TEXT UNIQUE,user_id INTEGER,customer_id INTEGER,rider_id INTEGER,subtotal REAL,tax REAL,total REAL,payment_method TEXT,payment_status TEXT DEFAULT 'Unpaid',created_at TEXT,status TEXT DEFAULT 'New',discount REAL DEFAULT 0,order_type TEXT DEFAULT 'Counter',table_no TEXT DEFAULT '',guest_count INTEGER DEFAULT 1,notes TEXT DEFAULT '',delivery_address TEXT DEFAULT '',delivery_km REAL DEFAULT 0,delivery_fee REAL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS sale_items(id INTEGER PRIMARY KEY AUTOINCREMENT,sale_id INTEGER,product_id INTEGER,product_name TEXT,quantity REAL,unit_price REAL,line_total REAL);
        CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY AUTOINCREMENT,sale_id INTEGER,method TEXT,amount REAL,reference TEXT DEFAULT '',created_at TEXT,user_id INTEGER);
        CREATE TABLE IF NOT EXISTS party_transactions(id INTEGER PRIMARY KEY AUTOINCREMENT,party_type TEXT,party_id INTEGER,txn_type TEXT,amount REAL,note TEXT,created_at TEXT,user_id INTEGER);
        CREATE TABLE IF NOT EXISTS stock_movements(id INTEGER PRIMARY KEY AUTOINCREMENT,product_id INTEGER,qty REAL,movement_type TEXT,note TEXT,created_at TEXT,user_id INTEGER);
        CREATE TABLE IF NOT EXISTS expenses(id INTEGER PRIMARY KEY AUTOINCREMENT,category TEXT,amount REAL,note TEXT,created_at TEXT,user_id INTEGER);
        CREATE TABLE IF NOT EXISTS audit_log(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,action TEXT,entity TEXT,entity_id INTEGER,details TEXT,created_at TEXT);
        CREATE TABLE IF NOT EXISTS order_events(id INTEGER PRIMARY KEY AUTOINCREMENT,sale_id INTEGER,status TEXT,note TEXT,created_at TEXT,user_id INTEGER);
        CREATE TABLE IF NOT EXISTS delivery_events(id INTEGER PRIMARY KEY AUTOINCREMENT,sale_id INTEGER,status TEXT,note TEXT,latitude TEXT,longitude TEXT,created_at TEXT,user_id INTEGER);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT);
        CREATE TABLE IF NOT EXISTS shifts(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,opened_at TEXT,closed_at TEXT,opening_cash REAL DEFAULT 0,closing_cash REAL,notes TEXT DEFAULT '');
        """)
        for col, typ in [("per_km","REAL DEFAULT 0"),("base_fee","REAL DEFAULT 0")]:
            try: self.q(f"ALTER TABLE riders ADD COLUMN {col} {typ}")
            except sqlite3.OperationalError: pass
        for col, typ in [("delivery_km","REAL DEFAULT 0"),("delivery_fee","REAL DEFAULT 0")]:
            try: self.q(f"ALTER TABLE sales ADD COLUMN {col} {typ}")
            except sqlite3.OperationalError: pass
        for u,r in [("admin","Admin"),("owner","Owner"),("cashier","Cashier"),("accountant","Accountant")]: self.q("INSERT OR IGNORE INTO users(username,role,password_hash) VALUES(?,?,?)",(u,r,hp("0099")))
        self.c.commit()
    def audit(self,user,action,entity="",eid=None,details=""):
        uid=user["id"] if user else None; self.q("INSERT INTO audit_log(user_id,action,entity,entity_id,details,created_at) VALUES(?,?,?,?,?,?)",(uid,action,entity,eid,details,now())); self.c.commit()
    def login(self,u,p): return self.q("SELECT * FROM users WHERE username=? AND password_hash=? AND active=1",(u.strip(),hp(p))).fetchone()

class Login(tk.Tk):
    def __init__(self,s):
        super().__init__(); self.s=s; self.title(BUSINESS["name"]+" - Login"); self.geometry("430x330"); self.resizable(False,False)
        f=ttk.Frame(self,padding=35); f.pack(fill="both",expand=True); ttk.Label(f,text=BUSINESS["name"],font=("Segoe UI",20,"bold")).pack(pady=8); ttk.Label(f,text="FASTFOOD POS").pack(pady=(0,22)); self.u=tk.StringVar(value="admin"); self.p=tk.StringVar(value="0099")
        ttk.Label(f,text="Username").pack(anchor="w"); ttk.Entry(f,textvariable=self.u).pack(fill="x",pady=5); ttk.Label(f,text="Password").pack(anchor="w"); ttk.Entry(f,textvariable=self.p,show="*").pack(fill="x",pady=5); ttk.Button(f,text="LOGIN",command=self.go).pack(fill="x",pady=18); self.bind("<Return>",lambda e:self.go())
    def go(self):
        u=self.s.login(self.u.get(),self.p.get())
        if not u:return messagebox.showerror("Login failed","Invalid username or password.",parent=self)
        self.destroy(); App(self.s,u).mainloop()

class ScrollFrame(ttk.Frame):
    def __init__(self,parent,**kw):
        super().__init__(parent,**kw); self.canvas=tk.Canvas(self,highlightthickness=0); self.v=ttk.Scrollbar(self,orient="vertical",command=self.canvas.yview); self.inner=ttk.Frame(self.canvas); self.win=self.canvas.create_window((0,0),window=self.inner,anchor="nw"); self.canvas.configure(yscrollcommand=self.v.set); self.canvas.pack(side="left",fill="both",expand=True); self.v.pack(side="right",fill="y"); self.inner.bind("<Configure>",lambda e:self.canvas.configure(scrollregion=self.canvas.bbox("all"))); self.canvas.bind("<Configure>",self._resize); self.canvas.bind_all("<MouseWheel>",self._wheel)
    def _resize(self,e): self.canvas.itemconfigure(self.win,width=e.width)
    def _wheel(self,e):
        try:
            if self.winfo_ismapped(): self.canvas.yview_scroll(int(-e.delta/120),"units")
        except Exception: pass

class App(tk.Tk):
    NAV=["POS","Dashboard","Orders","Kitchen","Customers","Tables / Dine-in","Suppliers","Products / Menu","Inventory","Riders / Delivery","Staff","Expenses","Reports / Analytics","Printers","Settings","Users / Permissions"]
    def __init__(self,s,user):
        super().__init__(); self.s=s; self.user=user; self.cart={}; self.pm=PrinterManager(); self.title(BUSINESS["name"]+" — POS"); self.geometry("1400x850"); self.minsize(900,600); st=ttk.Style(self); st.theme_use("clam"); st.configure("TButton",padding=(9,7)); st.configure("Primary.TButton",background="#2563eb",foreground="white",font=("Segoe UI",10,"bold"),padding=(12,10)); st.configure("Title.TLabel",font=("Segoe UI",22,"bold")); st.configure("Treeview",rowheight=30,font=("Segoe UI",10)); st.configure("Treeview.Heading",font=("Segoe UI",10,"bold")); self.build_shell(); self.show("POS"); self.after(700,self.pm.auto_reconnect)
    def build_shell(self):
        self.side=tk.Frame(self,bg="#111827",width=235); self.side.pack(side="left",fill="y"); self.side.pack_propagate(False); tk.Label(self.side,text="MK PIZZA\n& ICE BAR",bg="#111827",fg="white",font=("Segoe UI",17,"bold"),justify="left").pack(anchor="w",padx=18,pady=(20,8)); tk.Label(self.side,text=f"{self.user['username']} • {self.user['role']}",bg="#111827",fg="#9ca3af").pack(anchor="w",padx=18,pady=(0,10))
        nav=tk.Frame(self.side,bg="#111827"); nav.pack(fill="both",expand=True); self.nav_canvas=tk.Canvas(nav,bg="#111827",highlightthickness=0); self.navbar=tk.Frame(self.nav_canvas,bg="#111827"); self.navscroll=ttk.Scrollbar(nav,orient="vertical",command=self.nav_canvas.yview); self.nav_canvas.configure(yscrollcommand=self.navscroll.set); self.nav_canvas.pack(side="left",fill="both",expand=True); self.navscroll.pack(side="right",fill="y"); self.navwin=self.nav_canvas.create_window((0,0),window=self.navbar,anchor="nw"); self.navbar.bind("<Configure>",lambda e:self.nav_canvas.configure(scrollregion=self.nav_canvas.bbox("all"))); self.nav_canvas.bind("<Configure>",lambda e:self.nav_canvas.itemconfigure(self.navwin,width=e.width)); self.nav_canvas.bind_all("<MouseWheel>",lambda e:self._navwheel(e)); self.navbuttons={}
        for n in self.NAV:
            b=tk.Button(self.navbar,text=n,anchor="w",bg="#111827",fg="white",activebackground="#2563eb",activeforeground="white",relief="flat",bd=0,font=("Segoe UI",10,"bold"),padx=20,pady=9,command=lambda x=n:self.show(x)); b.pack(fill="x"); self.navbuttons[n]=b
        tk.Label(self.side,text=BUSINESS["name"],bg="#111827",fg="#64748b",font=("Segoe UI",8)).pack(side="bottom",anchor="w",padx=18,pady=8); self.bodyhost=ttk.Frame(self); self.bodyhost.pack(side="left",fill="both",expand=True); self.body=ScrollFrame(self.bodyhost); self.body.pack(fill="both",expand=True); self.bodyinner=self.body.inner
    def _navwheel(self,e):
        try:
            if self.nav_canvas.winfo_containing(e.x_root,e.y_root) is not None:self.nav_canvas.yview_scroll(int(-e.delta/120),"units")
        except Exception: pass
    def clear(self):
        for w in self.bodyinner.winfo_children():w.destroy()
    def show(self,n):
        self.clear()
        for k,b in self.navbuttons.items():b.configure(bg="#2563eb" if k==n else "#111827")
        fn=getattr(self,"page_"+n.lower().replace(" / ","_").replace(" ","_"),None)
        if fn:fn()
    def title(self,text,sub=""):
        ttk.Label(self.bodyinner,text=text,style="Title.TLabel").pack(anchor="w")
        if sub:ttk.Label(self.bodyinner,text=sub,foreground="#64748b").pack(anchor="w",pady=(2,10))
    def dialog(self,title,w,h):x=tk.Toplevel(self);x.title(title);x.geometry(f"{w}x{h}");x.transient(self);x.grab_set();return x
    def table(self,p,cols,heads,height=14):
        f=ttk.Frame(p);f.pack(fill="both",expand=True);t=ttk.Treeview(f,columns=cols,show="headings",selectmode="browse",height=height)
        for c in cols:t.heading(c,text=heads.get(c,c.title()));t.column(c,width=120,anchor="w")
        y=ttk.Scrollbar(f,orient="vertical",command=t.yview);x=ttk.Scrollbar(f,orient="horizontal",command=t.xview);t.configure(yscrollcommand=y.set,xscrollcommand=x.set);t.grid(row=0,column=0,sticky="nsew");y.grid(row=0,column=1,sticky="ns");x.grid(row=1,column=0,sticky="ew");f.rowconfigure(0,weight=1);f.columnconfigure(0,weight=1);return t
    def money(self,v):return f"{BUSINESS['currency']} {float(v):,.2f}"

    def page_dashboard(self):
        self.title("Dashboard","Live database totals. Nothing is pre-populated.");a=self.s.q("SELECT COUNT(*) n,COALESCE(SUM(total),0) t FROM sales WHERE date(created_at)=date('now','localtime')").fetchone();unpaid=self.s.q("SELECT COUNT(*) n,COALESCE(SUM(total),0) t FROM sales WHERE payment_status!='Paid'").fetchone();kitchen=self.s.q("SELECT COUNT(*) n FROM sales WHERE status IN ('New','Preparing','Ready')").fetchone();low=self.s.q("SELECT COUNT(*) n FROM products WHERE active=1 AND stock<=0").fetchone();row=ttk.Frame(self.bodyinner);row.pack(fill="x",pady=15)
        for h,v,d in [("Today Sales",self.money(a["t"]),f"{a['n']} orders"),("Unpaid",str(unpaid["n"]),self.money(unpaid["t"])),("Kitchen Queue",str(kitchen["n"]),"New / preparing / ready"),("Out of Stock",str(low["n"]),"Active products")]:
            c=ttk.LabelFrame(row,text=h,padding=16);c.pack(side="left",fill="both",expand=True,padx=4);ttk.Label(c,text=v,font=("Segoe UI",18,"bold")).pack(anchor="w");ttk.Label(c,text=d,foreground="#64748b").pack(anchor="w")
        bar=ttk.Frame(self.bodyinner);bar.pack(fill="x",pady=8);ttk.Button(bar,text="NEW SALE",style="Primary.TButton",command=lambda:self.show("POS")).pack(side="left");ttk.Button(bar,text="OPEN KITCHEN",command=lambda:self.show("Kitchen")).pack(side="left",padx=5);t=self.table(self.bodyinner,("invoice","type","total","payment","status","date"),{"invoice":"Invoice","type":"Type","total":"Total","payment":"Payment","status":"Status","date":"Date"},10)
        for r in self.s.rows("SELECT invoice_no,order_type,total,payment_status,status,created_at FROM sales ORDER BY id DESC LIMIT 20"):t.insert("","end",values=(r["invoice_no"],r["order_type"],self.money(r["total"]),r["payment_status"],r["status"],r["created_at"]))

    def page_pos(self):
        self.title("New Sale","Add products, customer/order type, delivery/table details, then send to kitchen and collect payment.");pane=ttk.PanedWindow(self.bodyinner,orient="horizontal");pane.pack(fill="both",expand=True,pady=10);left=ttk.Frame(pane);right=ttk.Frame(pane);pane.add(left,weight=3);pane.add(right,weight=2);bar=ttk.Frame(left);bar.pack(fill="x",pady=(0,8));self.search=tk.StringVar();e=ttk.Entry(bar,textvariable=self.search);e.pack(side="left",fill="x",expand=True);e.bind("<KeyRelease>",lambda _:self.load_menu());ttk.Button(bar,text="Refresh",command=self.load_menu).pack(side="right",padx=5);self.menu=self.table(left,("name","cat","price","stock","barcode"),{"name":"Product","cat":"Category","price":"Price","stock":"Stock","barcode":"Barcode"},18);self.menu.bind("<Double-1>",lambda e:self.add_item());ttk.Button(left,text="+ ADD SELECTED",style="Primary.TButton",command=self.add_item).pack(fill="x",pady=8);box=ttk.LabelFrame(right,text="Current Order",padding=12);box.pack(fill="both",expand=True);self.ct=self.table(box,("name","qty","unit","total"),{"name":"Item","qty":"Qty","unit":"Unit","total":"Total"},12);ctl=ttk.Frame(box);ctl.pack(fill="x",pady=8);ttk.Button(ctl,text="+ Qty",command=lambda:self.qty(1)).pack(side="left");ttk.Button(ctl,text="- Qty",command=lambda:self.qty(-1)).pack(side="left",padx=4);ttk.Button(ctl,text="Remove",command=self.remove).pack(side="left");ttk.Button(ctl,text="Clear",command=lambda:(self.cart.clear(),self.refresh())).pack(side="right");self.total=tk.StringVar(value=self.money(0));ttk.Label(box,textvariable=self.total,font=("Segoe UI",22,"bold")).pack(anchor="e",pady=8);ttk.Button(box,text="CHECKOUT / SEND TO KITCHEN",style="Primary.TButton",command=self.checkout).pack(fill="x");self.load_menu();self.refresh()
    def load_menu(self):
        if not hasattr(self,"menu"):return
        for x in self.menu.get_children():self.menu.delete(x)
        z=self.search.get().lower().strip()
        for r in self.s.rows("SELECT * FROM products WHERE active=1 ORDER BY category,name"):
            if z and z not in f"{r['name']} {r['category']} {r['barcode']}".lower():continue
            self.menu.insert("","end",iid=str(r["id"]),values=(r["name"],r["category"],self.money(r["price"]),r["stock"],r["barcode"]))
    def add_item(self):
        sel=self.menu.selection()
        if not sel:return
        r=self.s.q("SELECT * FROM products WHERE id=?",(int(sel[0]),)).fetchone();i=self.cart.setdefault(r["id"],{"id":r["id"],"name":r["name"],"price":float(r["price"]),"qty":0,"stock":float(r["stock"])})
        if i["qty"]<i["stock"]:i["qty"]+=1
        else:messagebox.showwarning("Stock","Insufficient stock.",parent=self)
        self.refresh()
    def refresh(self):
        if not hasattr(self,"ct"):return
        for x in self.ct.get_children():self.ct.delete(x)
        total=0
        for i in self.cart.values():z=i["qty"]*i["price"];total+=z;self.ct.insert("","end",iid=str(i["id"]),values=(i["name"],i["qty"],f"{i['price']:,.2f}",f"{z:,.2f}"))
        self.total.set(self.money(total))
    def qty(self,d):
        sel=self.ct.selection()
        if not sel:return
        i=self.cart.get(int(sel[0]))
        if i:i["qty"]=max(0,min(i["stock"],i["qty"]+d));self.cart.pop(i["id"],None) if i["qty"]==0 else None;self.refresh()
    def remove(self):
        for x in self.ct.selection():self.cart.pop(int(x),None)
        self.refresh()
    def quick_customer(self,cv,cb,cmap):
        w=self.dialog("New Customer",450,380);f=ttk.Frame(w,padding=18);f.pack(fill="both",expand=True);v={}
        for k,label in [("name","Name"),("phone","Phone"),("address","Delivery / Home Address")]:ttk.Label(f,text=label).pack(anchor="w",pady=(8,2));v[k]=tk.StringVar();ttk.Entry(f,textvariable=v[k]).pack(fill="x")
        def save():
            if not v["name"].get().strip():return messagebox.showerror("Customer","Name is required.",parent=w)
            cur=self.s.q("INSERT INTO customers(name,phone,address) VALUES(?,?,?)",(v["name"].get().strip(),v["phone"].get().strip(),v["address"].get().strip()));self.s.c.commit();r=self.s.q("SELECT * FROM customers WHERE id=?",(cur.lastrowid,)).fetchone();key=f"{r['name']} | {r['phone']}";cmap[key]=r["id"];cb["values"]=list(cmap);cv.set(key);w.destroy()
        ttk.Button(f,text="SAVE CUSTOMER",style="Primary.TButton",command=save).pack(fill="x",pady=18)
    def checkout(self):
        if not self.cart:return messagebox.showwarning("Order","Add products first.",parent=self)
        w=self.dialog("Checkout",620,720);f=ScrollFrame(w);f.pack(fill="both",expand=True);p=f.inner;custs=self.s.rows("SELECT * FROM customers WHERE active=1 ORDER BY name");cmap={f"{r['name']} | {r['phone']}":r["id"] for r in custs};cv=tk.StringVar();ttk.Label(p,text="Customer").pack(anchor="w");row=ttk.Frame(p);row.pack(fill="x");cb=ttk.Combobox(row,textvariable=cv,values=list(cmap),state="readonly");cb.pack(side="left",fill="x",expand=True);ttk.Button(row,text="+ New",command=lambda:self.quick_customer(cv,cb,cmap)).pack(side="right",padx=5);ov=tk.StringVar(value="Counter");ttk.Label(p,text="Order Type").pack(anchor="w",pady=(12,2));ttk.Combobox(p,textvariable=ov,values=["Counter","Takeaway","Dine-in","Delivery"],state="readonly").pack(fill="x");tv=tk.StringVar();ttk.Label(p,text="Table (Dine-in)").pack(anchor="w",pady=(12,2));ttk.Entry(p,textvariable=tv).pack(fill="x");gv=tk.IntVar(value=1);ttk.Label(p,text="Guests").pack(anchor="w",pady=(8,2));ttk.Spinbox(p,from_=1,to=99,textvariable=gv).pack(fill="x");addr=tk.StringVar();ttk.Label(p,text="Delivery Address").pack(anchor="w",pady=(8,2));ttk.Entry(p,textvariable=addr).pack(fill="x");rider_rows=self.s.rows("SELECT * FROM riders WHERE active=1 ORDER BY name");rider_map={f"{r['name']} | {r['phone']}":r["id"] for r in rider_rows};rv=tk.StringVar();ttk.Label(p,text="Rider").pack(anchor="w",pady=(8,2));rcb=ttk.Combobox(p,textvariable=rv,values=list(rider_map),state="readonly");rcb.pack(fill="x");km=tk.DoubleVar(value=0);ttk.Label(p,text="Delivery Distance (KM)").pack(anchor="w",pady=(8,2));ttk.Spinbox(p,from_=0,to=999,increment=.1,textvariable=km).pack(fill="x");feevar=tk.StringVar(value=self.money(0))
        def calc_fee(*_):
            rid=rider_map.get(rv.get());fee=0
            if rid:rr=self.s.q("SELECT base_fee,per_km FROM riders WHERE id=?",(rid,)).fetchone();fee=float(rr["base_fee"] or 0)+float(rr["per_km"] or 0)*float(km.get() or 0)
            feevar.set(self.money(fee))
        rcb.bind("<<ComboboxSelected>>",calc_fee);km.trace_add("write",calc_fee);ttk.Label(p,text="Delivery Fee").pack(anchor="w",pady=(8,2));ttk.Label(p,textvariable=feevar,font=("Segoe UI",11,"bold")).pack(anchor="w");pay=tk.StringVar(value="Cash");ttk.Label(p,text="Payment").pack(anchor="w",pady=(12,2));ttk.Combobox(p,textvariable=pay,values=["Cash","Card","Other","Credit","Pay when Ready"],state="readonly").pack(fill="x");nv=tk.StringVar();ttk.Label(p,text="Notes").pack(anchor="w",pady=(8,2));ttk.Entry(p,textvariable=nv).pack(fill="x");total=sum(i["qty"]*i["price"] for i in self.cart.values());ttk.Label(p,text=f"Subtotal: {self.money(total)}",font=("Segoe UI",13,"bold")).pack(anchor="w",pady=12)
        def save_order():
            try:
                rid=rider_map.get(rv.get());delivery_fee=0
                if rid:rr=self.s.q("SELECT base_fee,per_km FROM riders WHERE id=?",(rid,)).fetchone();delivery_fee=float(rr["base_fee"] or 0)+float(rr["per_km"] or 0)*float(km.get() or 0)
                subtotal=total+delivery_fee;invoice="INV-"+datetime.now().strftime("%Y%m%d%H%M%S")+f"-{self.s.q('SELECT COALESCE(MAX(id),0)+1 FROM sales').fetchone()[0]}";payment_status="Paid" if pay.get() in ("Cash","Card","Other") else "Unpaid";cur=self.s.q("""INSERT INTO sales(invoice_no,user_id,customer_id,rider_id,subtotal,tax,total,payment_method,payment_status,created_at,status,order_type,table_no,guest_count,notes,delivery_address,delivery_km,delivery_fee) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(invoice,self.user["id"],cmap.get(cv.get()),rid,subtotal,0,subtotal,pay.get(),payment_status,now(),"New",ov.get(),tv.get().strip(),int(gv.get()),nv.get().strip(),addr.get().strip(),float(km.get() or 0),delivery_fee));sid=cur.lastrowid
                for i in self.cart.values():
                    line=i["qty"]*i["price"];self.s.q("INSERT INTO sale_items(sale_id,product_id,product_name,quantity,unit_price,line_total) VALUES(?,?,?,?,?,?)",(sid,i["id"],i["name"],i["qty"],i["price"],line));self.s.q("UPDATE products SET stock=stock-? WHERE id=?",(i["qty"],i["id"]));self.s.q("INSERT INTO stock_movements(product_id,qty,movement_type,note,created_at,user_id) VALUES(?,?,?,?,?,?)",(i["id"],-i["qty"],"SALE",invoice,now(),self.user["id"]))
                self.s.q("INSERT INTO order_events(sale_id,status,note,created_at,user_id) VALUES(?,?,?,?,?)",(sid,"New","Order created and sent to kitchen",now(),self.user["id"]));
                if payment_status=="Paid":self.s.q("INSERT INTO payments(sale_id,method,amount,created_at,user_id) VALUES(?,?,?,?,?)",(sid,pay.get(),subtotal,now(),self.user["id"]))
                if pay.get()=="Credit" and cmap.get(cv.get()):self.s.q("UPDATE customers SET balance=balance+? WHERE id=?",(subtotal,cmap.get(cv.get())))
                self.s.c.commit();self.s.audit(self.user,"CREATE","sale",sid,invoice)
                if ov.get()=="Dine-in" and tv.get().strip():self.s.q("UPDATE tables SET status='Occupied' WHERE name=?",(tv.get().strip(),));self.s.c.commit()
                self.cart.clear();self.refresh();w.destroy();self.show("Kitchen");messagebox.showinfo("Order",f"{invoice} created and sent to kitchen.",parent=self)
            except Exception as e:messagebox.showerror("Checkout failed",str(e),parent=w)
        ttk.Button(p,text="CREATE ORDER + SEND KITCHEN",style="Primary.TButton",command=save_order).pack(fill="x",pady=18)

    def page_orders(self):
        self.title("Orders","Double-click an order for full items, status, payment and delivery history.");bar=ttk.Frame(self.bodyinner);bar.pack(fill="x",pady=8);self.order_filter=tk.StringVar();ttk.Entry(bar,textvariable=self.order_filter).pack(side="left",fill="x",expand=True);ttk.Button(bar,text="Refresh",command=self.load_orders).pack(side="left",padx=5);ttk.Button(bar,text="COLLECT PAYMENT",style="Primary.TButton",command=self.collect_payment).pack(side="right");self.ot=self.table(self.bodyinner,("id","invoice","type","customer","total","payment","status","date"),{"id":"ID","invoice":"Invoice","type":"Type","customer":"Customer","total":"Total","payment":"Payment","status":"Status","date":"Date"},18);self.ot.bind("<Double-1>",lambda e:self.order_detail());self.load_orders()
    def load_orders(self):
        for x in self.ot.get_children():self.ot.delete(x)
        z=self.order_filter.get().lower().strip();rows=self.s.rows("SELECT s.*,COALESCE(c.name,'Walk-in') customer FROM sales s LEFT JOIN customers c ON c.id=s.customer_id ORDER BY s.id DESC")
        for r in rows:
            text=f"{r['invoice_no']} {r['customer']} {r['order_type']} {r['status']} {r['payment_status']}".lower()
            if z and z not in text:continue
            self.ot.insert("","end",iid=str(r["id"]),values=(r["id"],r["invoice_no"],r["order_type"],r["customer"],self.money(r["total"]),r["payment_status"],r["status"],r["created_at"]))
    def selected_sale(self,tree):
        sel=tree.selection();return self.s.q("SELECT * FROM sales WHERE id=?",(int(sel[0]),)).fetchone() if sel else None
    def order_detail(self):
        r=self.selected_sale(self.ot)
        if not r:return
        w=self.dialog("Order "+r["invoice_no"],900,650);p=ScrollFrame(w);p.pack(fill="both",expand=True);f=p.inner;ttk.Label(f,text=f"{r['invoice_no']} — {self.money(r['total'])}",font=("Segoe UI",18,"bold")).pack(anchor="w");ttk.Label(f,text=f"Type: {r['order_type']} | Payment: {r['payment_status']} | Status: {r['status']} | Customer ID: {r['customer_id'] or 'Walk-in'}").pack(anchor="w",pady=6);items=self.table(f,("item","qty","unit","total"),{"item":"Item","qty":"Qty","unit":"Unit","total":"Total"},8)
        for x in self.s.rows("SELECT * FROM sale_items WHERE sale_id=?",(r["id"],)):items.insert("","end",values=(x["product_name"],x["quantity"],self.money(x["unit_price"]),self.money(x["line_total"])))
        ttk.Label(f,text="Order Status Timeline",font=("Segoe UI",12,"bold")).pack(anchor="w",pady=10);ev=self.table(f,("status","note","date"),{"status":"Status","note":"Note","date":"Date"},6)
        for x in self.s.rows("SELECT status,note,created_at FROM order_events WHERE sale_id=? ORDER BY id",(r["id"],)):ev.insert("","end",values=(x["status"],x["note"],x["created_at"]))
        if r["order_type"]=="Delivery":
            ttk.Label(f,text="Delivery Timeline",font=("Segoe UI",12,"bold")).pack(anchor="w",pady=10);de=self.table(f,("status","note","lat","lon","date"),{"status":"Status","note":"Note","lat":"Latitude","lon":"Longitude","date":"Date"},6)
            for x in self.s.rows("SELECT status,note,latitude,longitude,created_at FROM delivery_events WHERE sale_id=? ORDER BY id",(r["id"],)):de.insert("","end",values=tuple(x))
        bar=ttk.Frame(f);bar.pack(fill="x",pady=12);ttk.Button(bar,text="COLLECT PAYMENT",command=lambda:self.collect_payment_for(r["id"],w)).pack(side="left");ttk.Button(bar,text="PRINT RECEIPT",command=lambda:self.print_receipt(r["id"])).pack(side="left",padx=5);ttk.Button(bar,text="STATUS",command=lambda:self.change_order_status(r["id"],w)).pack(side="left")
    def change_order_status(self,sid,parent=None):
        w=self.dialog("Order Status",420,260);f=ttk.Frame(w,padding=18);f.pack(fill="both",expand=True);sv=tk.StringVar(value=self.s.q("SELECT status FROM sales WHERE id=?",(sid,)).fetchone()[0]);note=tk.StringVar();ttk.Label(f,text="Status").pack(anchor="w");ttk.Combobox(f,textvariable=sv,values=["New","Preparing","Ready","Completed","Cancelled"],state="readonly").pack(fill="x");ttk.Label(f,text="Note").pack(anchor="w",pady=(10,2));ttk.Entry(f,textvariable=note).pack(fill="x")
        def save():self.s.q("UPDATE sales SET status=? WHERE id=?",(sv.get(),sid));self.s.q("INSERT INTO order_events(sale_id,status,note,created_at,user_id) VALUES(?,?,?,?,?)",(sid,sv.get(),note.get(),now(),self.user["id"]));self.s.c.commit();w.destroy();self.load_orders()
        ttk.Button(f,text="SAVE STATUS",style="Primary.TButton",command=save).pack(fill="x",pady=15)
    def collect_payment(self):
        r=self.selected_sale(self.ot)
        if r:self.collect_payment_for(r["id"])
    def collect_payment_for(self,sid,parent=None):
        r=self.s.q("SELECT * FROM sales WHERE id=?",(sid,)).fetchone();due=max(0,float(r["total"])-float(self.s.q("SELECT COALESCE(SUM(amount),0) FROM payments WHERE sale_id=?",(sid,)).fetchone()[0] or 0))
        if due<=0:return messagebox.showinfo("Payment","This order is already fully paid.",parent=parent or self)
        w=self.dialog("Collect Payment",420,300);f=ttk.Frame(w,padding=18);f.pack(fill="both",expand=True);av=tk.DoubleVar(value=due);mv=tk.StringVar(value="Cash");ref=tk.StringVar();ttk.Label(f,text=f"Amount due: {self.money(due)}",font=("Segoe UI",13,"bold")).pack(anchor="w",pady=8);ttk.Label(f,text="Amount").pack(anchor="w");ttk.Entry(f,textvariable=av).pack(fill="x");ttk.Label(f,text="Method").pack(anchor="w",pady=(8,2));ttk.Combobox(f,textvariable=mv,values=["Cash","Card","Other"],state="readonly").pack(fill="x");ttk.Label(f,text="Reference").pack(anchor="w",pady=(8,2));ttk.Entry(f,textvariable=ref).pack(fill="x")
        def save():
            try:
                amount=float(av.get())
                if amount<=0 or amount>due+0.001:raise ValueError("Invalid amount")
                self.s.q("INSERT INTO payments(sale_id,method,amount,reference,created_at,user_id) VALUES(?,?,?,?,?,?)",(sid,mv.get(),amount,ref.get().strip(),now(),self.user["id"]));newdue=due-amount;self.s.q("UPDATE sales SET payment_status=? WHERE id=?",("Paid" if newdue<=0.001 else "Partial",sid));self.s.c.commit();w.destroy();self.load_orders()
            except Exception as e:messagebox.showerror("Payment",str(e),parent=w)
        ttk.Button(f,text="SAVE PAYMENT",style="Primary.TButton",command=save).pack(fill="x",pady=15)
    def print_receipt(self,sid):
        try:
            r=self.s.q("SELECT * FROM sales WHERE id=?",(sid,)).fetchone();items=self.s.rows("SELECT * FROM sale_items WHERE sale_id=?",(sid,));lines=[b"\x1b@",b"\x1ba\x01",f"{BUSINESS['name']}\n".encode(),f"{BUSINESS['address']}\n{BUSINESS['phone']}\n".encode(),f"Invoice: {r['invoice_no']}\n".encode()]
            for x in items:lines.append(f"{x['product_name'][:20]:20} {x['quantity']:>4} {x['line_total']:>8.2f}\n".encode())
            lines.append(f"TOTAL {self.money(r['total'])}\nPayment: {r['payment_status']}\n\n".encode());lines.append(b"\x1dV\x00");self.pm.write_raw(b"".join(lines));messagebox.showinfo("Printer","Receipt sent.",parent=self)
        except Exception as e:messagebox.showerror("Print failed",str(e),parent=self)

    def page_kitchen(self):
        self.title("Kitchen Display","Real order workflow: New → Preparing → Ready → Completed.");bar=ttk.Frame(self.bodyinner);bar.pack(fill="x",pady=8);ttk.Button(bar,text="Refresh",command=self.load_kitchen).pack(side="left");ttk.Button(bar,text="PREPARING",style="Primary.TButton",command=lambda:self.kitchen_status("Preparing")).pack(side="left",padx=4);ttk.Button(bar,text="READY",command=lambda:self.kitchen_status("Ready")).pack(side="left");ttk.Button(bar,text="COMPLETED",command=lambda:self.kitchen_status("Completed")).pack(side="left");self.kt=self.table(self.bodyinner,("id","invoice","type","items","status","created"),{"id":"ID","invoice":"Invoice","type":"Type","items":"Items","status":"Status","created":"Created"},16);self.load_kitchen()
    def load_kitchen(self):
        for x in self.kt.get_children():self.kt.delete(x)
        for r in self.s.rows("SELECT * FROM sales WHERE status IN ('New','Preparing','Ready') ORDER BY id"):
            cnt=self.s.q("SELECT COALESCE(SUM(quantity),0) FROM sale_items WHERE sale_id=?",(r["id"],)).fetchone()[0];self.kt.insert("","end",iid=str(r["id"]),values=(r["id"],r["invoice_no"],r["order_type"],cnt,r["status"],r["created_at"]))
    def kitchen_status(self,status):
        sel=self.kt.selection()
        if not sel:return
        sid=int(sel[0]);self.s.q("UPDATE sales SET status=? WHERE id=?",(status,sid));self.s.q("INSERT INTO order_events(sale_id,status,note,created_at,user_id) VALUES(?,?,?,?,?)",(sid,status,"Kitchen status",now(),self.user["id"]));self.s.c.commit();self.load_kitchen()

    def page_customers(self):self.party_page("customers","Customers",["name","phone","address","balance"])
    def page_suppliers(self):self.party_page("suppliers","Suppliers",["name","phone","address","balance"])
    def party_page(self,table,title,fields):
        self.title(title,"Add, edit, view complete transaction/payment history.");bar=ttk.Frame(self.bodyinner);bar.pack(fill="x",pady=8);ttk.Button(bar,text="Add",style="Primary.TButton",command=lambda:self.party_edit(table,fields)).pack(side="left");ttk.Button(bar,text="Edit",command=lambda:self.party_edit(table,fields,True)).pack(side="left",padx=4);ttk.Button(bar,text="TRANSACTION / PAYMENT",command=lambda:self.party_txn(table)).pack(side="left");t=self.table(self.bodyinner,tuple(["id"]+fields),{x:x.title() for x in ["id"]+fields},18);setattr(self,"party_tree",t)
        for r in self.s.rows(f"SELECT * FROM {table} WHERE active=1 ORDER BY name"):t.insert("","end",iid=str(r["id"]),values=tuple(r[x] for x in ["id"]+fields))
        t.bind("<Double-1>",lambda e:self.party_txn(table))
    def party_edit(self,table,fields,editing=False):
        t=getattr(self,"party_tree",None);sel=t.selection() if t else ();old=self.s.q(f"SELECT * FROM {table} WHERE id=?",(int(sel[0]),)).fetchone() if editing and sel else None;w=self.dialog(("Edit " if old else "Add ")+table.title(),480,420);f=ttk.Frame(w,padding=18);f.pack(fill="both",expand=True);v={}
        for k in fields[:3]:ttk.Label(f,text=k.title()).pack(anchor="w");v[k]=tk.StringVar(value=str(old[k]) if old else "");ttk.Entry(f,textvariable=v[k]).pack(fill="x",pady=4)
        def save():
            if not v["name"].get().strip():return messagebox.showerror("Required","Name required.",parent=w)
            if old:self.s.q(f"UPDATE {table} SET name=?,phone=?,address=? WHERE id=?",(v["name"].get().strip(),v["phone"].get().strip(),v["address"].get().strip(),old["id"]))
            else:self.s.q(f"INSERT INTO {table}(name,phone,address) VALUES(?,?,?)",(v["name"].get().strip(),v["phone"].get().strip(),v["address"].get().strip()))
            self.s.c.commit();w.destroy();self.show("Customers" if table=="customers" else "Suppliers")
        ttk.Button(f,text="SAVE",style="Primary.TButton",command=save).pack(fill="x",pady=15)
    def party_txn(self,table):
        t=getattr(self,"party_tree",None);sel=t.selection() if t else ()
        if not sel:return
        pid=int(sel[0]);r=self.s.q(f"SELECT * FROM {table} WHERE id=?",(pid,)).fetchone();ptype="Customer" if table=="customers" else "Supplier";w=self.dialog(f"{ptype} History — {r['name']}",900,600);f=ScrollFrame(w);f.pack(fill="both",expand=True);p=f.inner;ttk.Label(p,text=f"{r['name']} — Balance {self.money(r['balance'])}",font=("Segoe UI",16,"bold")).pack(anchor="w")
        if table=="customers":
            t1=self.table(p,("invoice","total","status","payment","date"),{"invoice":"Invoice","total":"Total","status":"Status","payment":"Payment","date":"Date"},8)
            for x in self.s.rows("SELECT invoice_no,total,status,payment_status,created_at FROM sales WHERE customer_id=? ORDER BY id DESC",(pid,)):t1.insert("","end",values=(x["invoice_no"],self.money(x["total"]),x["status"],x["payment_status"],x["created_at"]))
        t2=self.table(p,("type","amount","note","date"),{"type":"Transaction","amount":"Amount","note":"Note","date":"Date"},8)
        for x in self.s.rows("SELECT txn_type,amount,note,created_at FROM party_transactions WHERE party_type=? AND party_id=? ORDER BY id DESC",(ptype,pid)):t2.insert("","end",values=(x["txn_type"],self.money(x["amount"]),x["note"],x["created_at"]))
        ttk.Button(p,text="ADD PAYMENT / CREDIT / ADVANCE",command=lambda:self.party_payment(table,pid,w)).pack(fill="x",pady=12)
    def party_payment(self,table,pid,parent):
        ptype="Customer" if table=="customers" else "Supplier";w=self.dialog("Party Transaction",450,360);f=ttk.Frame(w,padding=18);f.pack(fill="both",expand=True);tv=tk.StringVar(value="Payment");av=tk.DoubleVar();note=tk.StringVar();ttk.Label(f,text="Transaction").pack(anchor="w");ttk.Combobox(f,textvariable=tv,values=["Payment","Credit","Advance","Adjustment"],state="readonly").pack(fill="x");ttk.Label(f,text="Amount").pack(anchor="w",pady=(10,2));ttk.Entry(f,textvariable=av).pack(fill="x");ttk.Label(f,text="Note").pack(anchor="w",pady=(10,2));ttk.Entry(f,textvariable=note).pack(fill="x")
        def save():
            try:
                a=float(av.get());
                if a<=0:raise ValueError()
                self.s.q("INSERT INTO party_transactions(party_type,party_id,txn_type,amount,note,created_at,user_id) VALUES(?,?,?,?,?,?,?)",(ptype,pid,tv.get(),a,note.get(),now(),self.user["id"]));sign=1 if tv.get()=="Credit" else -1
                if tv.get()=="Adjustment":sign=1
                self.s.q(f"UPDATE {table} SET balance=balance+? WHERE id=?",(sign*a,pid));self.s.c.commit();w.destroy();parent.destroy();self.party_txn(table)
            except Exception:messagebox.showerror("Transaction","Enter a positive amount.",parent=w)
        ttk.Button(f,text="SAVE TRANSACTION",style="Primary.TButton",command=save).pack(fill="x",pady=18)

    def page_tables_dine_in(self):
        self.title("Tables / Dine-in","Manage actual tables. Double-click for table order history.");bar=ttk.Frame(self.bodyinner);bar.pack(fill="x",pady=8);ttk.Button(bar,text="Add Table",style="Primary.TButton",command=self.add_table).pack(side="left");ttk.Button(bar,text="Mark Available",command=lambda:self.table_status("Available")).pack(side="left",padx=4);ttk.Button(bar,text="Mark Occupied",command=lambda:self.table_status("Occupied")).pack(side="left");self.tt=self.table(self.bodyinner,("id","name","seats","status"),{"id":"ID","name":"Table","seats":"Seats","status":"Status"},18)
        for r in self.s.rows("SELECT * FROM tables ORDER BY id"):self.tt.insert("","end",iid=str(r["id"]),values=(r["id"],r["name"],r["seats"],r["status"]))
        self.tt.bind("<Double-1>",lambda e:self.table_history())
    def add_table(self):
        w=self.dialog("Add Table",360,250);f=ttk.Frame(w,padding=18);f.pack(fill="both",expand=True);n=tk.StringVar();se=tk.IntVar(value=2);ttk.Label(f,text="Table name/number").pack(anchor="w");ttk.Entry(f,textvariable=n).pack(fill="x");ttk.Label(f,text="Seats").pack(anchor="w",pady=8);ttk.Spinbox(f,from_=1,to=100,textvariable=se).pack(fill="x")
        def save():
            try:self.s.q("INSERT INTO tables(name,seats) VALUES(?,?)",(n.get().strip(),se.get()));self.s.c.commit();w.destroy();self.show("Tables / Dine-in")
            except sqlite3.IntegrityError:messagebox.showerror("Table","Table already exists.",parent=w)
        ttk.Button(f,text="SAVE",command=save).pack(fill="x",pady=15)
    def table_status(self,status):
        sel=self.tt.selection()
        if sel:self.s.q("UPDATE tables SET status=? WHERE id=?",(status,int(sel[0])));self.s.c.commit();self.show("Tables / Dine-in")
    def table_history(self):
        sel=self.tt.selection()
        if not sel:return
        name=self.s.q("SELECT name FROM tables WHERE id=?",(int(sel[0]),)).fetchone()["name"];rows=self.s.rows("SELECT invoice_no,total,payment_status,status,created_at FROM sales WHERE table_no=? ORDER BY id DESC",(name,));w=self.dialog("Table History",760,500);f=ScrollFrame(w);f.pack(fill="both",expand=True);t=self.table(f.inner,("invoice","total","payment","status","date"),{"invoice":"Invoice","total":"Total","payment":"Payment","status":"Status","date":"Date"},16)
        for r in rows:t.insert("","end",values=(r["invoice_no"],self.money(r["total"]),r["payment_status"],r["status"],r["created_at"]))

    def page_products_menu(self):
        self.title("Products & Menu","Real catalog management: add/edit/deactivate, stock, CSV import/export and history.");bar=ttk.Frame(self.bodyinner);bar.pack(fill="x",pady=8);ttk.Button(bar,text="ADD PRODUCT",style="Primary.TButton",command=self.product_edit).pack(side="left");ttk.Button(bar,text="EDIT",command=self.product_edit).pack(side="left",padx=4);ttk.Button(bar,text="DEACTIVATE",command=self.product_delete).pack(side="left");ttk.Button(bar,text="PRODUCT HISTORY",command=self.product_history).pack(side="left",padx=4);ttk.Button(bar,text="IMPORT CSV",command=self.product_import).pack(side="right");ttk.Button(bar,text="EXPORT CSV",command=self.product_export).pack(side="right",padx=4);self.pr=self.table(self.bodyinner,("id","name","category","price","cost","stock","barcode"),{"id":"ID","name":"Name","category":"Category","price":"Price","cost":"Cost","stock":"Stock","barcode":"Barcode"},18);self.load_products()
    def load_products(self):
        for x in self.pr.get_children():self.pr.delete(x)
        for r in self.s.rows("SELECT * FROM products WHERE active=1 ORDER BY category,name"):self.pr.insert("","end",iid=str(r["id"]),values=(r["id"],r["name"],r["category"],self.money(r["price"]),self.money(r["cost"]),r["stock"],r["barcode"]))
    def product_edit(self):
        sel=self.pr.selection() if hasattr(self,"pr") else ();old=self.s.q("SELECT * FROM products WHERE id=?",(int(sel[0]),)).fetchone() if sel else None;w=self.dialog("Product",460,520);f=ScrollFrame(w);f.pack(fill="both",expand=True);p=f.inner;v={}
        for k in ["name","category","price","cost","stock","barcode"]:ttk.Label(p,text=k.title()).pack(anchor="w");v[k]=tk.StringVar(value=str(old[k]) if old else "");ttk.Entry(p,textvariable=v[k]).pack(fill="x",pady=3)
        def save():
            try:
                data=(v["name"].get().strip(),v["category"].get().strip() or "General",float(v["price"].get()),float(v["cost"].get() or 0),float(v["stock"].get() or 0),v["barcode"].get().strip())
                if not data[0] or data[2]<0 or data[4]<0:raise ValueError()
                if old:self.s.q("UPDATE products SET name=?,category=?,price=?,cost=?,stock=?,barcode=? WHERE id=?",data+(old["id"],))
                else:self.s.q("INSERT INTO products(name,category,price,cost,stock,barcode) VALUES(?,?,?,?,?,?)",data)
                self.s.c.commit();w.destroy();self.show("Products / Menu")
            except Exception:messagebox.showerror("Product","Enter valid values.",parent=w)
        ttk.Button(p,text="SAVE PRODUCT",style="Primary.TButton",command=save).pack(fill="x",pady=15)
    def product_delete(self):
        sel=self.pr.selection()
        if sel and messagebox.askyesno("Deactivate","Deactivate selected product?",parent=self):self.s.q("UPDATE products SET active=0 WHERE id=?",(int(sel[0]),));self.s.c.commit();self.load_products()
    def product_history(self):
        sel=self.pr.selection()
        if not sel:return
        pid=int(sel[0]);r=self.s.q("SELECT * FROM products WHERE id=?",(pid,)).fetchone();w=self.dialog("Product History — "+r["name"],850,550);f=ScrollFrame(w);f.pack(fill="both",expand=True);t=self.table(f.inner,("qty","type","note","date"),{"qty":"Qty","type":"Movement","note":"Note","date":"Date"},16)
        for x in self.s.rows("SELECT qty,movement_type,note,created_at FROM stock_movements WHERE product_id=? ORDER BY id DESC",(pid,)):t.insert("","end",values=(x["qty"],x["movement_type"],x["note"],x["created_at"]))
    def product_export(self):
        p=filedialog.asksaveasfilename(defaultextension=".csv",filetypes=[("CSV","*.csv")],parent=self)
        if not p:return
        rows=self.s.rows("SELECT id,name,category,price,cost,stock,barcode FROM products WHERE active=1")
        with open(p,"w",newline="",encoding="utf-8-sig") as f:w=csv.writer(f);w.writerow(["id","name","category","price","cost","stock","barcode"]);w.writerows([list(r) for r in rows])
    def product_import(self):
        p=filedialog.askopenfilename(filetypes=[("CSV","*.csv")],parent=self)
        if not p:return
        try:
            with open(p,newline="",encoding="utf-8-sig") as f:
                for r in csv.DictReader(f):self.s.q("INSERT INTO products(name,category,price,cost,stock,barcode) VALUES(?,?,?,?,?,?)",(r["name"].strip(),r.get("category","General"),float(r["price"]),float(r.get("cost") or 0),float(r.get("stock") or 0),r.get("barcode","").strip()))
            self.s.c.commit();self.load_products()
        except Exception as e:messagebox.showerror("Import failed",str(e),parent=self)

    def page_inventory(self):
        self.title("Inventory","Real stock adjustments and movement history.");bar=ttk.Frame(self.bodyinner);bar.pack(fill="x",pady=8);ttk.Button(bar,text="ADJUST STOCK",style="Primary.TButton",command=self.adjust_stock).pack(side="left");ttk.Button(bar,text="MOVEMENT HISTORY",command=self.inventory_history).pack(side="left",padx=5);self.it=self.table(self.bodyinner,("id","name","stock","cost","value"),{"id":"ID","name":"Product","stock":"Stock","cost":"Cost","value":"Stock Value"},18)
        for r in self.s.rows("SELECT * FROM products WHERE active=1 ORDER BY name"):self.it.insert("","end",iid=str(r["id"]),values=(r["id"],r["name"],r["stock"],self.money(r["cost"]),self.money(float(r["stock"])*float(r["cost"]))))
    def adjust_stock(self):
        sel=self.it.selection()
        if not sel:return
        pid=int(sel[0]);r=self.s.q("SELECT * FROM products WHERE id=?",(pid,)).fetchone();w=self.dialog("Stock Adjustment",430,330);f=ttk.Frame(w,padding=18);f.pack(fill="both",expand=True);q=tk.DoubleVar();typ=tk.StringVar(value="IN");note=tk.StringVar();ttk.Label(f,text=f"{r['name']} — Current {r['stock']}").pack(anchor="w");ttk.Label(f,text="Adjustment Qty").pack(anchor="w",pady=(10,2));ttk.Entry(f,textvariable=q).pack(fill="x");ttk.Label(f,text="Direction").pack(anchor="w",pady=(8,2));ttk.Combobox(f,textvariable=typ,values=["IN","OUT"],state="readonly").pack(fill="x");ttk.Label(f,text="Note").pack(anchor="w",pady=(8,2));ttk.Entry(f,textvariable=note).pack(fill="x")
        def save():
            try:
                a=float(q.get());delta=a if typ.get()=="IN" else -a
                if a<=0 or float(r["stock"])+delta<0:raise ValueError()
                self.s.q("UPDATE products SET stock=stock+? WHERE id=?",(delta,pid));self.s.q("INSERT INTO stock_movements(product_id,qty,movement_type,note,created_at,user_id) VALUES(?,?,?,?,?,?)",(pid,delta,"ADJUSTMENT",note.get(),now(),self.user["id"]));self.s.c.commit();w.destroy();self.show("Inventory")
            except Exception:messagebox.showerror("Stock","Invalid adjustment.",parent=w)
        ttk.Button(f,text="SAVE ADJUSTMENT",style="Primary.TButton",command=save).pack(fill="x",pady=15)
    def inventory_history(self):
        w=self.dialog("Inventory Movement History",900,600);f=ScrollFrame(w);f.pack(fill="both",expand=True);t=self.table(f.inner,("product","qty","type","note","date"),{"product":"Product","qty":"Qty","type":"Movement","note":"Note","date":"Date"},20)
        for r in self.s.rows("SELECT p.name,m.qty,m.movement_type,m.note,m.created_at FROM stock_movements m JOIN products p ON p.id=m.product_id ORDER BY m.id DESC"):t.insert("","end",values=tuple(r))

    def page_riders_delivery(self):
        self.title("Riders & Delivery","Manage rider rates and delivery lifecycle. Per-KM fee is stored with each order.");bar=ttk.Frame(self.bodyinner);bar.pack(fill="x",pady=8);ttk.Button(bar,text="ADD RIDER",style="Primary.TButton",command=self.rider_edit).pack(side="left");ttk.Button(bar,text="EDIT",command=self.rider_edit).pack(side="left",padx=4);ttk.Button(bar,text="DELIVERY TRACKING",command=self.delivery_tracking).pack(side="left");self.rt=self.table(self.bodyinner,("id","name","phone","vehicle","base","km","active"),{"id":"ID","name":"Name","phone":"Phone","vehicle":"Vehicle","base":"Base Fee","km":"Per KM","active":"Active"},15)
        for r in self.s.rows("SELECT * FROM riders ORDER BY name"):self.rt.insert("","end",iid=str(r["id"]),values=(r["id"],r["name"],r["phone"],r["vehicle"],self.money(r["base_fee"]),self.money(r["per_km"]),r["active"]))
    def rider_edit(self):
        sel=self.rt.selection() if hasattr(self,"rt") else ();old=self.s.q("SELECT * FROM riders WHERE id=?",(int(sel[0]),)).fetchone() if sel else None;w=self.dialog("Rider",450,480);f=ScrollFrame(w);f.pack(fill="both",expand=True);p=f.inner;v={}
        for k in ["name","phone","vehicle","base_fee","per_km"]:ttk.Label(p,text=k.replace("_"," ").title()).pack(anchor="w");v[k]=tk.StringVar(value=str(old[k]) if old else "");ttk.Entry(p,textvariable=v[k]).pack(fill="x",pady=4)
        def save():
            try:
                vals=(v["name"].get().strip(),v["phone"].get().strip(),v["vehicle"].get().strip(),float(v["base_fee"].get() or 0),float(v["per_km"].get() or 0))
                if not vals[0] or vals[3]<0 or vals[4]<0:raise ValueError()
                if old:self.s.q("UPDATE riders SET name=?,phone=?,vehicle=?,base_fee=?,per_km=? WHERE id=?",vals+(old["id"],))
                else:self.s.q("INSERT INTO riders(name,phone,vehicle,base_fee,per_km) VALUES(?,?,?,?,?)",vals)
                self.s.c.commit();w.destroy();self.show("Riders / Delivery")
            except Exception:messagebox.showerror("Rider","Invalid rider data.",parent=w)
        ttk.Button(p,text="SAVE RIDER",style="Primary.TButton",command=save).pack(fill="x",pady=15)
    def delivery_tracking(self):
        w=self.dialog("Delivery Tracking",1050,650);f=ScrollFrame(w);f.pack(fill="both",expand=True);p=f.inner;t=self.table(p,("id","invoice","customer","rider","status","km","fee","order"),{"id":"ID","invoice":"Invoice","customer":"Customer","rider":"Rider","status":"Delivery Status","km":"KM","fee":"Fee","order":"Order Status"},16);rows=self.s.rows("SELECT s.*,COALESCE(c.name,'Walk-in') customer,COALESCE(r.name,'Unassigned') rider FROM sales s LEFT JOIN customers c ON c.id=s.customer_id LEFT JOIN riders r ON r.id=s.rider_id WHERE s.order_type='Delivery' ORDER BY s.id DESC")
        for r in rows:t.insert("","end",iid=str(r["id"]),values=(r["id"],r["invoice_no"],r["customer"],r["rider"],self.delivery_status(r["id"]),r["delivery_km"],self.money(r["delivery_fee"]),r["status"]))
        ttk.Button(p,text="UPDATE SELECTED DELIVERY",style="Primary.TButton",command=lambda:self.update_delivery(t,w)).pack(fill="x",pady=10)
    def delivery_status(self,sid):
        r=self.s.q("SELECT status FROM delivery_events WHERE sale_id=? ORDER BY id DESC LIMIT 1",(sid,)).fetchone();return r["status"] if r else "Assigned"
    def update_delivery(self,t,parent):
        sel=t.selection()
        if not sel:return
        sid=int(sel[0]);w=self.dialog("Delivery Event",480,430);f=ttk.Frame(w,padding=18);f.pack(fill="both",expand=True);sv=tk.StringVar(value=self.delivery_status(sid));note=tk.StringVar();lat=tk.StringVar();lon=tk.StringVar();ttk.Label(f,text="Status").pack(anchor="w");ttk.Combobox(f,textvariable=sv,values=["Assigned","Picked Up","Out for Delivery","Near Customer","Delivered","Failed","Returned"],state="readonly").pack(fill="x")
        for var,label in [(note,"Note"),(lat,"Latitude"),(lon,"Longitude")]:ttk.Label(f,text=label).pack(anchor="w",pady=(10,2));ttk.Entry(f,textvariable=var).pack(fill="x")
        def save():
            self.s.q("INSERT INTO delivery_events(sale_id,status,note,latitude,longitude,created_at,user_id) VALUES(?,?,?,?,?,?,?)",(sid,sv.get(),note.get(),lat.get(),lon.get(),now(),self.user["id"]));
            if sv.get()=="Delivered":self.s.q("UPDATE sales SET status='Completed' WHERE id=?",(sid,))
            self.s.c.commit();w.destroy();parent.destroy();self.delivery_tracking()
        ttk.Button(f,text="SAVE DELIVERY EVENT",style="Primary.TButton",command=save).pack(fill="x",pady=15)

    def page_staff(self):self.simple_people("staff",["name","phone","role","salary"],"Staff")
    def simple_people(self,table,fields,title):
        self.title(title,"Actual staff records; no sample staff is created.");bar=ttk.Frame(self.bodyinner);bar.pack(fill="x",pady=8);ttk.Button(bar,text="ADD",style="Primary.TButton",command=lambda:self.people_edit(table,fields)).pack(side="left");t=self.table(self.bodyinner,tuple(["id"]+fields),{x:x.title() for x in ["id"]+fields},18)
        for r in self.s.rows(f"SELECT * FROM {table} WHERE active=1 ORDER BY name"):t.insert("","end",iid=str(r["id"]),values=tuple(r[x] for x in ["id"]+fields))
    def people_edit(self,table,fields):
        w=self.dialog("Add "+table.title(),430,440);f=ScrollFrame(w);f.pack(fill="both",expand=True);p=f.inner;v={}
        for k in fields:ttk.Label(p,text=k.title()).pack(anchor="w");v[k]=tk.StringVar();ttk.Entry(p,textvariable=v[k]).pack(fill="x",pady=3)
        def save():
            try:
                vals=[float(v[k].get()) if k=="salary" else v[k].get().strip() for k in fields]
                if not vals[0]:raise ValueError("Name required")
                self.s.q(f"INSERT INTO {table}({','.join(fields)}) VALUES({','.join('?' for _ in fields)})",vals);self.s.c.commit();w.destroy();self.show("Staff")
            except Exception as e:messagebox.showerror("Save failed",str(e),parent=w)
        ttk.Button(p,text="SAVE",style="Primary.TButton",command=save).pack(fill="x",pady=15)

    def page_expenses(self):
        self.title("Expenses","Record actual store expenses and inspect history.");bar=ttk.Frame(self.bodyinner);bar.pack(fill="x",pady=8);ttk.Button(bar,text="ADD EXPENSE",style="Primary.TButton",command=self.add_expense).pack(side="left");t=self.table(self.bodyinner,("id","category","amount","note","date"),{"id":"ID","category":"Category","amount":"Amount","note":"Note","date":"Date"},18)
        for r in self.s.rows("SELECT * FROM expenses ORDER BY id DESC"):t.insert("","end",values=(r["id"],r["category"],self.money(r["amount"]),r["note"],r["created_at"]))
    def add_expense(self):
        w=self.dialog("Expense",430,360);f=ttk.Frame(w,padding=18);f.pack(fill="both",expand=True);c=tk.StringVar();a=tk.DoubleVar();n=tk.StringVar()
        for var,label in [(c,"Category"),(a,"Amount"),(n,"Note")]:ttk.Label(f,text=label).pack(anchor="w",pady=(8,2));ttk.Entry(f,textvariable=var).pack(fill="x")
        def save():
            try:
                if float(a.get())<=0:raise ValueError()
                self.s.q("INSERT INTO expenses(category,amount,note,created_at,user_id) VALUES(?,?,?,?,?)",(c.get(),float(a.get()),n.get(),now(),self.user["id"]));self.s.c.commit();w.destroy();self.show("Expenses")
            except Exception:messagebox.showerror("Expense","Enter a positive amount.",parent=w)
        ttk.Button(f,text="SAVE EXPENSE",style="Primary.TButton",command=save).pack(fill="x",pady=15)

    def page_reports_analytics(self):
        self.title("Reports & Analytics","Live financial, sales, inventory and payment metrics.");t=self.table(self.bodyinner,("metric","value"),{"metric":"Metric","value":"Value"},16);q=[("Gross Sales","SELECT COALESCE(SUM(total),0) FROM sales WHERE status!='Cancelled'"),("Paid","SELECT COALESCE(SUM(amount),0) FROM payments"),("Customer Balances","SELECT COALESCE(SUM(balance),0) FROM customers"),("Supplier Balances","SELECT COALESCE(SUM(balance),0) FROM suppliers"),("Expenses","SELECT COALESCE(SUM(amount),0) FROM expenses"),("Products","SELECT COUNT(*) FROM products WHERE active=1"),("Orders","SELECT COUNT(*) FROM sales"),("Delivery Orders","SELECT COUNT(*) FROM sales WHERE order_type='Delivery'")]
        for n,sql in q:t.insert("","end",values=(n,self.s.q(sql).fetchone()[0]))
        ttk.Button(self.bodyinner,text="SALES BY PAYMENT / TYPE",command=self.analytics_breakdown).pack(fill="x",pady=8)
    def analytics_breakdown(self):
        w=self.dialog("Analytics Breakdown",800,520);f=ScrollFrame(w);f.pack(fill="both",expand=True);p=f.inner;t=self.table(p,("group","count","total"),{"group":"Group","count":"Orders","total":"Sales"},18)
        for r in self.s.rows("SELECT payment_method g,COUNT(*) c,COALESCE(SUM(total),0) t FROM sales GROUP BY payment_method ORDER BY t DESC"):t.insert("","end",values=(r["g"],r["c"],self.money(r["t"])))
        for r in self.s.rows("SELECT order_type g,COUNT(*) c,COALESCE(SUM(total),0) t FROM sales GROUP BY order_type ORDER BY t DESC"):t.insert("","end",values=(r["g"],r["c"],self.money(r["t"])))

    def page_printers(self):
        self.title("Printers & Receipt Themes","Real 80mm ESC/POS printer connection, saved identity, reconnect and test print.");p=self.pm.status().get("printer") or {};st=self.pm.status();c=ttk.LabelFrame(self.bodyinner,text="Printer",padding=16);c.pack(fill="x",pady=12);ttk.Label(c,text=f"Saved: {p.get('name','None')}").pack(anchor="w");ttk.Label(c,text=f"Transport: {p.get('transport','-')}").pack(anchor="w");ttk.Label(c,text=f"Status: {'Connected' if st.get('connected') else 'Not connected'}").pack(anchor="w",pady=3);b=ttk.Frame(c);b.pack(fill="x",pady=8);ttk.Button(b,text="OPEN DISCOVERY / SETTINGS",style="Primary.TButton",command=lambda:PrinterSettings(self,self.pm,BUSINESS)).pack(side="left");ttk.Button(b,text="RECONNECT SAVED",command=self.pm.auto_reconnect).pack(side="left",padx=5);ttk.Button(b,text="TEST PRINT",command=self.print_test).pack(side="left");th=ttk.LabelFrame(self.bodyinner,text="Receipt Theme",padding=16);th.pack(fill="x",pady=8);theme=tk.StringVar(value=st.get("theme","Classic"));cb=ttk.Combobox(th,textvariable=theme,values=["Classic","Compact","Modern"],state="readonly");cb.pack(side="left");ttk.Button(th,text="SAVE THEME",command=lambda:self.save_theme(theme.get())).pack(side="left",padx=5)
    def print_test(self):
        try:self.pm.test_print();messagebox.showinfo("Printer","Test print sent.",parent=self)
        except Exception as e:messagebox.showerror("Printer",str(e),parent=self)
    def save_theme(self,theme):self.pm.config["theme"]=theme;self.pm.save();messagebox.showinfo("Receipt","Theme saved.",parent=self)

    def page_settings(self):
        self.title("Settings","Business configuration, database backup and local preferences.");f=ttk.LabelFrame(self.bodyinner,text="Business",padding=16);f.pack(fill="x");v={}
        for k in ["name","address","phone","currency"]:ttk.Label(f,text=k.title()).pack(anchor="w");v[k]=tk.StringVar(value=BUSINESS[k]);ttk.Entry(f,textvariable=v[k]).pack(fill="x",pady=3)
        def save():BUSINESS.update({k:v[k].get() for k in v});[self.s.q("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",(k,x)) for k,x in v.items()];self.s.c.commit();messagebox.showinfo("Settings","Saved.",parent=self)
        ttk.Button(f,text="SAVE SETTINGS",style="Primary.TButton",command=save).pack(fill="x",pady=12);b=ttk.LabelFrame(self.bodyinner,text="Backup",padding=16);b.pack(fill="x",pady=12);ttk.Button(b,text="BACKUP DATABASE",command=self.backup).pack(anchor="w")
    def backup(self):
        p=filedialog.asksaveasfilename(defaultextension=".db",initialfile="pos-backup.db",filetypes=[("SQLite","*.db")],parent=self)
        if p:self.s.c.commit();shutil.copy2(DB,p);messagebox.showinfo("Backup","Database backup created.",parent=self)

    def page_users_permissions(self):
        self.title("Users & Permissions","Manage login users. Passwords are stored as SHA-256 hashes.");bar=ttk.Frame(self.bodyinner);bar.pack(fill="x",pady=8);ttk.Button(bar,text="ADD USER",style="Primary.TButton",command=self.user_edit).pack(side="left");ttk.Button(bar,text="CHANGE PASSWORD",command=self.change_password).pack(side="left",padx=5);ttk.Button(bar,text="ENABLE / DISABLE",command=self.toggle_user).pack(side="left");self.ut=self.table(self.bodyinner,("id","username","role","active"),{"id":"ID","username":"Username","role":"Role","active":"Active"},15)
        for r in self.s.rows("SELECT id,username,role,active FROM users ORDER BY username"):self.ut.insert("","end",iid=str(r["id"]),values=tuple(r))
    def user_edit(self):
        w=self.dialog("Add User",430,330);f=ttk.Frame(w,padding=18);f.pack(fill="both",expand=True);u=tk.StringVar();r=tk.StringVar(value="Cashier");p=tk.StringVar();ttk.Label(f,text="Username").pack(anchor="w",pady=(8,2));ttk.Entry(f,textvariable=u).pack(fill="x");ttk.Label(f,text="Role").pack(anchor="w",pady=(8,2));ttk.Combobox(f,textvariable=r,values=["Admin","Owner","Cashier","Accountant"],state="readonly").pack(fill="x");ttk.Label(f,text="Password").pack(anchor="w",pady=(8,2));ttk.Entry(f,textvariable=p,show="*").pack(fill="x")
        def save():
            try:self.s.q("INSERT INTO users(username,role,password_hash) VALUES(?,?,?)",(u.get().strip(),r.get(),hp(p.get())));self.s.c.commit();w.destroy();self.show("Users / Permissions")
            except Exception as e:messagebox.showerror("User",str(e),parent=w)
        ttk.Button(f,text="SAVE USER",style="Primary.TButton",command=save).pack(fill="x",pady=15)
    def change_password(self):
        sel=self.ut.selection()
        if not sel:return
        p=simpledialog.askstring("Password","New password:",show="*",parent=self)
        if p:self.s.q("UPDATE users SET password_hash=? WHERE id=?",(hp(p),int(sel[0])));self.s.c.commit()
    def toggle_user(self):
        sel=self.ut.selection()
        if sel:self.s.q("UPDATE users SET active=1-active WHERE id=?",(int(sel[0]),));self.s.c.commit();self.show("Users / Permissions")

def main():Login(Store()).mainloop()
if __name__=="__main__":main()
