import csv, hashlib, sqlite3
from datetime import datetime
from tkinter import filedialog, messagebox
import tkinter as tk
from tkinter import ttk

DB_FILE='pos.db'
BUSINESS={'name':'MK Pizza & Ice Bar','address':'Collage Road Abbas Chowk, Bhakkar, Pakistan','phone':'0316 9700025','currency':'Rs.','tax':0.0}

def hp(v): return hashlib.sha256(v.encode()).hexdigest()

class DB:
    def __init__(self,path=DB_FILE):
        self.conn=sqlite3.connect(path); self.conn.row_factory=sqlite3.Row; self.init()
    def cols(self,t): return {r[1] for r in self.conn.execute(f'PRAGMA table_info({t})')}
    def addcol(self,t,c,d):
        if c not in self.cols(t): self.conn.execute(f'ALTER TABLE {t} ADD COLUMN {c} {d}')
    def init(self):
        self.conn.executescript('''
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,username TEXT UNIQUE,role TEXT,password_hash TEXT,active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,price REAL NOT NULL,category TEXT DEFAULT 'General',stock REAL DEFAULT 0,active INTEGER DEFAULT 1,barcode TEXT DEFAULT '',cost REAL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS customers(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,phone TEXT DEFAULT '',address TEXT DEFAULT '',balance REAL DEFAULT 0,active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS suppliers(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,phone TEXT DEFAULT '',address TEXT DEFAULT '',balance REAL DEFAULT 0,active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS party_transactions(id INTEGER PRIMARY KEY AUTOINCREMENT,party_type TEXT,party_id INTEGER,txn_type TEXT,amount REAL,note TEXT,created_at TEXT,user_id INTEGER);
        CREATE TABLE IF NOT EXISTS sales(id INTEGER PRIMARY KEY AUTOINCREMENT,invoice_no TEXT UNIQUE,user_id INTEGER,customer_id INTEGER,subtotal REAL,tax REAL,total REAL,payment_method TEXT,created_at TEXT,status TEXT DEFAULT 'New',discount REAL DEFAULT 0,order_type TEXT DEFAULT 'Counter',notes TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS sale_items(id INTEGER PRIMARY KEY AUTOINCREMENT,sale_id INTEGER,product_id INTEGER,product_name TEXT,quantity REAL,unit_price REAL,line_total REAL);
        CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY AUTOINCREMENT,sale_id INTEGER,method TEXT,amount REAL,reference TEXT DEFAULT '',created_at TEXT,user_id INTEGER);
        CREATE TABLE IF NOT EXISTS stock_movements(id INTEGER PRIMARY KEY AUTOINCREMENT,product_id INTEGER,qty REAL,movement_type TEXT,note TEXT,created_at TEXT,user_id INTEGER);
        CREATE TABLE IF NOT EXISTS expenses(id INTEGER PRIMARY KEY AUTOINCREMENT,category TEXT,amount REAL,note TEXT,created_at TEXT,user_id INTEGER);
        CREATE TABLE IF NOT EXISTS staff(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,phone TEXT,role TEXT DEFAULT 'Staff',salary REAL DEFAULT 0,active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS audit_log(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,action TEXT,entity TEXT,entity_id INTEGER,details TEXT,created_at TEXT);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT);
        ''')
        self.addcol('products','stock','REAL DEFAULT 0'); self.addcol('products','barcode',"TEXT DEFAULT ''"); self.addcol('products','cost','REAL DEFAULT 0')
        for c,d in [('customer_id','INTEGER'),('status',"TEXT DEFAULT 'New'"),('discount','REAL DEFAULT 0'),('order_type',"TEXT DEFAULT 'Counter'"),('notes',"TEXT DEFAULT ''")]: self.addcol('sales',c,d)
        for u,r in [('admin','Admin'),('owner','Owner'),('cashier','Cashier'),('accountant','Accountant')]: self.conn.execute('INSERT OR IGNORE INTO users(username,role,password_hash) VALUES(?,?,?)',(u,r,hp('0099')))
        self.conn.commit()
    def q(self,s,a=()): return self.conn.execute(s,a)
    def rows(self,s,a=()): return self.q(s,a).fetchall()
    def login(self,u,p): return self.q('SELECT * FROM users WHERE username=? AND password_hash=? AND active=1',(u.strip(),hp(p))).fetchone()
    def audit(self,user,action,entity='',eid=None,details=''):
        self.q('INSERT INTO audit_log(user_id,action,entity,entity_id,details,created_at) VALUES(?,?,?,?,?,?)',(user['id'],action,entity,eid,details,datetime.now().isoformat(timespec='seconds'))); self.conn.commit()

class App(tk.Tk):
    def __init__(self,db,user):
        super().__init__(); self.db=db; self.user=user; self.cart={}; self.dark=False
        self.title(BUSINESS['name']+' — POS'); self.geometry('1360x820'); self.minsize(1050,700); self.configure(bg='#f5f7fb'); self.protocol('WM_DELETE_WINDOW',self.destroy)
        s=ttk.Style(self); s.theme_use('clam'); s.configure('App.TFrame',background='#f5f7fb'); s.configure('Side.TFrame',background='#111827'); s.configure('Top.TFrame',background='#ffffff'); s.configure('Title.TLabel',background='#f5f7fb',font=('Segoe UI',22,'bold')); s.configure('Sub.TLabel',background='#f5f7fb',foreground='#64748b'); s.configure('Side.TButton',background='#111827',foreground='#e5e7eb',borderwidth=0,padding=(16,11),font=('Segoe UI',10,'bold')); s.map('Side.TButton',background=[('active','#1f2937')]); s.configure('Primary.TButton',background='#2563eb',foreground='white',padding=(14,10),font=('Segoe UI',10,'bold')); s.map('Primary.TButton',background=[('active','#1d4ed8')]); s.configure('Card.TLabelframe',background='white',borderwidth=1); s.configure('Card.TLabelframe.Label',background='white',font=('Segoe UI',11,'bold')); s.configure('TEntry',padding=7); s.configure('TCombobox',padding=6); s.configure('Treeview',rowheight=34,font=('Segoe UI',10)); s.configure('Treeview.Heading',font=('Segoe UI',10,'bold'),padding=8)
        self.build(); self.show('POS')
    def build(self):
        self.side=ttk.Frame(self,style='Side.TFrame',width=220); self.side.pack(side='left',fill='y'); self.side.pack_propagate(False)
        tk.Label(self.side,text='MK PIZZA\n& ICE BAR',bg='#111827',fg='white',font=('Segoe UI',17,'bold'),justify='left').pack(anchor='w',padx=18,pady=(22,4)); tk.Label(self.side,text='FASTFOOD POS',bg='#111827',fg='#93c5fd',font=('Segoe UI',9,'bold')).pack(anchor='w',padx=18,pady=(0,20))
        for n,i in [('POS','▣'),('Dashboard','⌂'),('Orders','☷'),('Customers','♙'),('Suppliers','▤'),('Products','□'),('Kitchen','♨'),('Riders','➜'),('Staff','♟'),('Reports','▥'),('Settings','⚙')]: ttk.Button(self.side,text=f'{i}  {n}',style='Side.TButton',command=lambda x=n:self.show(x)).pack(fill='x',padx=10,pady=2)
        tk.Label(self.side,text=f"{self.user['username']}  •  {self.user['role']}",bg='#111827',fg='#9ca3af',font=('Segoe UI',9)).pack(side='bottom',anchor='w',padx=18,pady=18)
        self.main=ttk.Frame(self,style='App.TFrame'); self.main.pack(side='left',fill='both',expand=True); top=ttk.Frame(self.main,style='Top.TFrame',padding=(22,13)); top.pack(fill='x'); self.crumb=tk.Label(top,text='Point of Sale',bg='white',fg='#0f172a',font=('Segoe UI',14,'bold')); self.crumb.pack(side='left'); tk.Label(top,text='●  Ready',bg='white',fg='#16a34a',font=('Segoe UI',9,'bold')).pack(side='right',padx=14); ttk.Button(top,text='Display',command=self.display).pack(side='right'); self.content=ttk.Frame(self.main,style='App.TFrame',padding=22); self.content.pack(fill='both',expand=True)
    def clear(self):
        for w in self.content.winfo_children(): w.destroy()
    def show(self,name):
        self.clear(); self.crumb.config(text=name); fn=getattr(self,'page_'+name.lower(),None); fn() if fn else self.page_dashboard()
    def table(self,p,cols,heads,height=12):
        f=ttk.Frame(p); f.pack(fill='both',expand=True); t=ttk.Treeview(f,columns=cols,show='headings',height=height,selectmode='extended');
        for c in cols:t.heading(c,text=heads.get(c,c.title()));t.column(c,width=120)
        y=ttk.Scrollbar(f,orient='vertical',command=t.yview);t.configure(yscrollcommand=y.set);t.pack(side='left',fill='both',expand=True);y.pack(side='right',fill='y');return t
    def card(self,p,title,val,sub):
        f=ttk.LabelFrame(p,text=title,style='Card.TLabelframe',padding=16);f.pack(side='left',fill='both',expand=True,padx=(0,12));ttk.Label(f,text=val,font=('Segoe UI',20,'bold')).pack(anchor='w');ttk.Label(f,text=sub,style='Sub.TLabel').pack(anchor='w',pady=(4,0))
    def page_dashboard(self):
        ttk.Label(self.content,text='Good day 👋',style='Title.TLabel').pack(anchor='w');ttk.Label(self.content,text=BUSINESS['address'],style='Sub.TLabel').pack(anchor='w');row=ttk.Frame(self.content,style='App.TFrame');row.pack(fill='x',pady=22);a=self.db.q("SELECT COUNT(*) n,COALESCE(SUM(total),0) total FROM sales WHERE date(created_at)=date('now','localtime')").fetchone();c=self.db.q('SELECT COUNT(*) n,COALESCE(SUM(balance),0) b FROM customers WHERE active=1').fetchone();p=self.db.q('SELECT COUNT(*) n,COALESCE(SUM(stock),0) s FROM products WHERE active=1').fetchone();self.card(row,'TODAY SALES',f"Rs. {a['total']:,.0f}",f"{a['n']} orders");self.card(row,'CUSTOMER BALANCE',f"Rs. {c['b']:,.0f}",f"{c['n']} accounts");self.card(row,'ACTIVE PRODUCTS',str(p['n']),f"{p['s']:,.0f} stock units");box=ttk.LabelFrame(self.content,text='Quick actions',style='Card.TLabelframe',padding=18);box.pack(fill='x');ttk.Button(box,text='New Sale',style='Primary.TButton',command=lambda:self.show('POS')).pack(side='left',padx=5);ttk.Button(box,text='Products',command=lambda:self.show('Products')).pack(side='left',padx=5);ttk.Button(box,text='Customers',command=lambda:self.show('Customers')).pack(side='left',padx=5);ttk.Button(box,text='Kitchen',command=lambda:self.show('Kitchen')).pack(side='left',padx=5)
    def page_pos(self):
        pane=ttk.PanedWindow(self.content,orient='horizontal');pane.pack(fill='both',expand=True);left=ttk.Frame(pane,style='App.TFrame');right=ttk.Frame(pane,style='App.TFrame');pane.add(left,weight=3);pane.add(right,weight=2);bar=ttk.Frame(left,style='App.TFrame');bar.pack(fill='x',pady=(0,10));self.search=tk.StringVar();e=ttk.Entry(bar,textvariable=self.search);e.pack(side='left',fill='x',expand=True);e.bind('<KeyRelease>',lambda _:self.load_menu());ttk.Button(bar,text='Manage Products',command=lambda:self.show('Products')).pack(side='right',padx=(8,0));self.menu=ttk.Treeview(left,columns=('name','cat','price','stock'),show='headings');
        for c,h,w in [('name','Product',260),('cat','Category',130),('price','Price',100),('stock','Stock',90)]:self.menu.heading(c,text=h);self.menu.column(c,width=w)
        self.menu.pack(fill='both',expand=True);self.menu.bind('<Double-1>',lambda _:self.add_selected());ttk.Button(left,text='+ Add Selected to Order',style='Primary.TButton',command=self.add_selected).pack(fill='x',pady=10);box=ttk.LabelFrame(right,text='Current Order',style='Card.TLabelframe',padding=12);box.pack(fill='both',expand=True);self.cart_tree=self.table(box,('name','qty','price','total'),{'name':'Item','qty':'Qty','price':'Unit','total':'Total'},9);ctl=ttk.Frame(box);ctl.pack(fill='x',pady=8);ttk.Button(ctl,text='+ Qty',command=lambda:self.change_qty(1)).pack(side='left');ttk.Button(ctl,text='− Qty',command=lambda:self.change_qty(-1)).pack(side='left',padx=5);ttk.Button(ctl,text='Remove',command=self.remove_cart).pack(side='left');ttk.Button(ctl,text='Clear',command=self.clear_cart).pack(side='right');self.total_var=tk.StringVar(value='Rs. 0.00');f=ttk.Frame(box);f.pack(fill='x',pady=8);ttk.Label(f,text='TOTAL',font=('Segoe UI',10,'bold')).pack(side='left');ttk.Label(f,textvariable=self.total_var,font=('Segoe UI',22,'bold')).pack(side='right');ttk.Button(box,text='CHARGE / CHECKOUT',style='Primary.TButton',command=self.checkout).pack(fill='x');self.load_menu();self.refresh_cart()
    def load_menu(self):
        if not hasattr(self,'menu'):return
        for x in self.menu.get_children():self.menu.delete(x)
        q=self.search.get().lower().strip()
        for r in self.db.rows('SELECT * FROM products WHERE active=1 ORDER BY category,name'):
            if q and q not in f"{r['name']} {r['category']} {r['barcode']}".lower():continue
            self.menu.insert('','end',iid=str(r['id']),values=(r['name'],r['category'],f"Rs. {r['price']:,.2f}",r['stock']))
    def add_selected(self):
        s=self.menu.selection();
        if not s:return
        r=self.db.q('SELECT * FROM products WHERE id=?',(int(s[0]),)).fetchone();
        if not r:return
        i=self.cart.setdefault(r['id'],{'id':r['id'],'name':r['name'],'price':float(r['price']),'qty':0,'stock':float(r['stock'])});i['qty']+=1;self.refresh_cart()
    def refresh_cart(self):
        if not hasattr(self,'cart_tree'):return
        for x in self.cart_tree.get_children():self.cart_tree.delete(x)
        total=0
        for i in self.cart.values():line=i['qty']*i['price'];total+=line;self.cart_tree.insert('','end',iid=str(i['id']),values=(i['name'],i['qty'],f"{i['price']:,.2f}",f"{line:,.2f}"))
        self.total_var.set(f"Rs. {total:,.2f}")
    def change_qty(self,d):
        s=self.cart_tree.selection();
        if not s:return
        i=self.cart.get(int(s[0]));
        if i:i['qty']=max(0,i['qty']+d);self.cart.pop(i['id'],None) if i and i['qty']==0 else None;self.refresh_cart()
    def remove_cart(self):
        for s in self.cart_tree.selection():self.cart.pop(int(s),None)
        self.refresh_cart()
    def clear_cart(self):self.cart.clear();self.refresh_cart()
    def checkout(self):
        if not self.cart:return messagebox.showwarning('Order','Add products first.',parent=self)
        w=tk.Toplevel(self);w.title('Checkout');w.geometry('460x520');w.transient(self);w.grab_set();f=ttk.Frame(w,padding=20);f.pack(fill='both',expand=True);ttk.Label(f,text='Complete Sale',font=('Segoe UI',18,'bold')).pack(anchor='w',pady=(0,15));custs=self.db.rows('SELECT * FROM customers WHERE active=1 ORDER BY name');cmap={f"{r['name']} | {r['phone']}":r['id'] for r in custs};cv=tk.StringVar();ttk.Label(f,text='Customer').pack(anchor='w');ttk.Combobox(f,textvariable=cv,values=list(cmap),state='readonly').pack(fill='x',pady=5);ov=tk.StringVar(value='Counter');ttk.Label(f,text='Order Type').pack(anchor='w');ttk.Combobox(f,textvariable=ov,values=['Counter','Takeaway','Dine-in','Delivery'],state='readonly').pack(fill='x',pady=5);pv=tk.StringVar(value='Cash');ttk.Label(f,text='Payment').pack(anchor='w');ttk.Combobox(f,textvariable=pv,values=['Cash','Card','Other','Credit'],state='readonly').pack(fill='x',pady=5);dv=tk.DoubleVar(value=0);ttk.Label(f,text='Discount (Rs.)').pack(anchor='w');ttk.Entry(f,textvariable=dv).pack(fill='x',pady=5);nv=tk.StringVar();ttk.Label(f,text='Notes').pack(anchor='w');ttk.Entry(f,textvariable=nv).pack(fill='x',pady=5);gross=sum(i['qty']*i['price'] for i in self.cart.values());ttk.Label(f,text=f'Payable: Rs. {gross:,.2f}',font=('Segoe UI',14,'bold')).pack(anchor='w',pady=10)
        def save():
            discount=max(0,float(dv.get() or 0));total=max(0,gross-discount);cid=cmap.get(cv.get());pay=pv.get();
            if pay=='Credit' and not cid:return messagebox.showerror('Customer required','Select a customer for a credit sale.',parent=w)
            for i in self.cart.values():
                st=self.db.q('SELECT stock FROM products WHERE id=?',(i['id'],)).fetchone()['stock'];
                if st < i['qty']:return messagebox.showerror('Stock',f"Insufficient stock: {i['name']}",parent=w)
            now=datetime.now().isoformat(timespec='seconds');inv='INV-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f');cur=self.db.conn.cursor();cur.execute('INSERT INTO sales(invoice_no,user_id,customer_id,subtotal,tax,total,payment_method,created_at,status,discount,order_type,notes) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(inv,self.user['id'],cid,gross,0,total,pay,now,'New',discount,ov.get(),nv.get()));sid=cur.lastrowid
            for i in self.cart.values():cur.execute('INSERT INTO sale_items(sale_id,product_id,product_name,quantity,unit_price,line_total) VALUES(?,?,?,?,?,?)',(sid,i['id'],i['name'],i['qty'],i['price'],i['qty']*i['price']));cur.execute('UPDATE products SET stock=stock-? WHERE id=?',(i['qty'],i['id']));cur.execute('INSERT INTO stock_movements(product_id,qty,movement_type,note,created_at,user_id) VALUES(?,?,?,?,?,?)',(i['id'],-i['qty'],'Sale',inv,now,self.user['id']))
            cur.execute('INSERT INTO payments(sale_id,method,amount,created_at,user_id) VALUES(?,?,?,?,?)',(sid,pay,total,now,self.user['id']))
            if pay=='Credit':cur.execute('UPDATE customers SET balance=balance+? WHERE id=?',(total,cid));cur.execute('INSERT INTO party_transactions(party_type,party_id,txn_type,amount,note,created_at,user_id) VALUES(?,?,?,?,?,?,?)',('Customer',cid,'Due',total,inv,now,self.user['id']))
            self.db.conn.commit();self.db.audit(self.user,'Create Sale','sale',sid,inv);w.destroy();self.clear_cart();self.load_menu();messagebox.showinfo('Sale completed',f'{inv}\nRs. {total:,.2f}',parent=self)
        ttk.Button(f,text='COMPLETE SALE',style='Primary.TButton',command=save).pack(fill='x',pady=8)
    def page_orders(self):
        ttk.Label(self.content,text='Orders',style='Title.TLabel').pack(anchor='w');t=self.table(self.content,('id','invoice','status','type','total','payment','date'),{'id':'ID','invoice':'Invoice','status':'Status','type':'Type','total':'Total','payment':'Payment','date':'Created'},15)
        for r in self.db.rows('SELECT id,invoice_no,status,order_type,total,payment_method,created_at FROM sales ORDER BY id DESC LIMIT 500'):t.insert('','end',iid=str(r['id']),values=(r['id'],r['invoice_no'],r['status'],r['order_type'],f"Rs. {r['total']:,.2f}",r['payment_method'],r['created_at']))
        ttk.Button(self.content,text='Update Status',style='Primary.TButton',command=lambda:self.order_status(t)).pack(anchor='e',pady=8)
    def order_status(self,t):
        s=t.selection();
        if not s:return
        sid=int(s[0]);w=tk.Toplevel(self);w.title('Order status');v=tk.StringVar(value=self.db.q('SELECT status FROM sales WHERE id=?',(sid,)).fetchone()['status'] or 'New');ttk.Combobox(w,textvariable=v,values=['New','Preparing','Ready','Out for Delivery','Completed','Cancelled'],state='readonly').pack(padx=20,pady=20);ttk.Button(w,text='Save',command=lambda:(self.db.q('UPDATE sales SET status=? WHERE id=?',(v.get(),sid)),self.db.conn.commit(),self.db.audit(self.user,'Update Order','sale',sid,v.get()),w.destroy(),self.show('Orders'))).pack(pady=(0,20))
    def page_products(self):
        ttk.Label(self.content,text='Products',style='Title.TLabel').pack(anchor='w');bar=ttk.Frame(self.content);bar.pack(fill='x',pady=12);q=tk.StringVar();ttk.Entry(bar,textvariable=q).pack(side='left',fill='x',expand=True);ttk.Button(bar,text='Add Product',style='Primary.TButton',command=self.product_dialog).pack(side='right',padx=6);ttk.Button(bar,text='Import CSV',command=self.import_csv).pack(side='right');ttk.Button(bar,text='Export CSV',command=self.export_csv).pack(side='right',padx=6);t=self.table(self.content,('id','name','category','price','stock','barcode'),{'id':'ID','name':'Product','category':'Category','price':'Price','stock':'Stock','barcode':'Barcode'},15)
        def load(*_):
            for x in t.get_children():t.delete(x)
            z=q.get().lower()
            for r in self.db.rows('SELECT * FROM products WHERE active=1 ORDER BY category,name'):
                if z in f"{r['name']} {r['category']} {r['barcode']}".lower():t.insert('','end',iid=str(r['id']),values=(r['id'],r['name'],r['category'],f"Rs. {r['price']:,.2f}",r['stock'],r['barcode']))
        q.trace_add('write',load);load();t.bind('<Double-1>',lambda _:self.product_dialog(t.selection()))
    def product_dialog(self,sel=()):
        old=self.db.q('SELECT * FROM products WHERE id=?',(int(sel[0]),)).fetchone() if sel else None;w=tk.Toplevel(self);w.title('Product');f=ttk.Frame(w,padding=20);f.pack(fill='both',expand=True);v=[]
        for lab,key in [('Name','name'),('Price','price'),('Category','category'),('Stock','stock'),('Barcode','barcode'),('Cost','cost')]:ttk.Label(f,text=lab).pack(anchor='w');x=tk.StringVar(value=str(old[key]) if old else '');ttk.Entry(f,textvariable=x).pack(fill='x',pady=(2,8));v.append(x)
        def save():
            try:
                data=(v[0].get().strip(),float(v[1].get()),v[2].get().strip() or 'General',float(v[3].get() or 0),v[4].get().strip(),float(v[5].get() or 0));
                if not data[0]:raise ValueError()
                if old:self.db.q('UPDATE products SET name=?,price=?,category=?,stock=?,barcode=?,cost=? WHERE id=?',data+(old['id'],))
                else:self.db.q('INSERT INTO products(name,price,category,stock,barcode,cost) VALUES(?,?,?,?,?,?)',data)
                self.db.conn.commit();self.db.audit(self.user,'Save Product','product',old['id'] if old else None,data[0]);w.destroy();self.show('Products')
            except ValueError:messagebox.showerror('Invalid','Enter a valid name, price and stock.',parent=w)
        ttk.Button(f,text='Save Product',style='Primary.TButton',command=save).pack(fill='x')
    def export_csv(self):
        p=filedialog.asksaveasfilename(defaultextension='.csv',filetypes=[('CSV','*.csv')],parent=self)
        if not p:return
        with open(p,'w',newline='',encoding='utf-8-sig') as f:
            w=csv.writer(f);w.writerow(['id','name','price','category','stock','barcode','cost']);
            for r in self.db.rows('SELECT * FROM products WHERE active=1 ORDER BY id'):w.writerow([r['id'],r['name'],r['price'],r['category'],r['stock'],r['barcode'],r['cost']])
    def import_csv(self):
        p=filedialog.askopenfilename(filetypes=[('CSV','*.csv')],parent=self)
        if not p:return
        try:
            with open(p,newline='',encoding='utf-8-sig') as f:
                for r in csv.DictReader(f):
                    if r.get('name'):self.db.q('INSERT INTO products(name,price,category,stock,barcode,cost) VALUES(?,?,?,?,?,?)',(r['name'],float(r.get('price') or 0),r.get('category') or 'General',float(r.get('stock') or 0),r.get('barcode') or '',float(r.get('cost') or 0)))
            self.db.conn.commit();self.show('Products')
        except Exception as e:messagebox.showerror('Import failed',str(e),parent=self)
    def party_page(self,typ):
        table='customers' if typ=='Customer' else 'suppliers';ttk.Label(self.content,text=typ+'s',style='Title.TLabel').pack(anchor='w');bar=ttk.Frame(self.content);bar.pack(fill='x',pady=12);q=tk.StringVar();ttk.Entry(bar,textvariable=q).pack(side='left',fill='x',expand=True);ttk.Button(bar,text='Add '+typ,style='Primary.TButton',command=lambda:self.party_dialog(typ)).pack(side='right');t=self.table(self.content,('id','name','phone','balance'),{'id':'ID','name':'Name','phone':'Phone','balance':'Balance'},15)
        def load(*_):
            for x in t.get_children():t.delete(x)
            z=q.get().lower()
            for r in self.db.rows(f'SELECT * FROM {table} WHERE active=1 ORDER BY name'):
                if z in f"{r['name']} {r['phone']} {r['address']}".lower():t.insert('','end',iid=str(r['id']),values=(r['id'],r['name'],r['phone'],f"Rs. {r['balance']:,.2f}"))
        q.trace_add('write',load);load();t.bind('<Double-1>',lambda _:self.party_history(typ,t.selection()));ttk.Button(self.content,text='Transaction / Payment',command=lambda:self.party_txn(typ,t.selection())).pack(anchor='e',pady=8)
    def page_customers(self):self.party_page('Customer')
    def page_suppliers(self):self.party_page('Supplier')
    def party_dialog(self,typ):
        table='customers' if typ=='Customer' else 'suppliers';w=tk.Toplevel(self);w.title('Add '+typ);f=ttk.Frame(w,padding=20);f.pack(fill='both',expand=True);v=[]
        for lab in ['Name','Phone','Address']:ttk.Label(f,text=lab).pack(anchor='w');x=tk.StringVar();ttk.Entry(f,textvariable=x).pack(fill='x',pady=3);v.append(x)
        def save():
            if not v[0].get().strip():return
            self.db.q(f'INSERT INTO {table}(name,phone,address) VALUES(?,?,?)',(v[0].get().strip(),v[1].get().strip(),v[2].get().strip()));self.db.conn.commit();self.db.audit(self.user,'Add '+typ,table);w.destroy();self.show(typ+'s')
        ttk.Button(f,text='Save',style='Primary.TButton',command=save).pack(fill='x',pady=8)
    def party_history(self,typ,sel):
        if not sel:return
        pid=int(sel[0]);table='customers' if typ=='Customer' else 'suppliers';p=self.db.q(f'SELECT * FROM {table} WHERE id=?',(pid,)).fetchone();w=tk.Toplevel(self);w.title(p['name']+' — History');w.geometry('850x520');ttk.Label(w,text=f"{p['name']}   Balance: Rs. {p['balance']:,.2f}",font=('Segoe UI',15,'bold')).pack(padx=18,pady=15,anchor='w');t=self.table(w,('id','type','amount','note','date'),{'id':'ID','type':'Transaction','amount':'Amount','note':'Note','date':'Date'},12)
        for r in self.db.rows('SELECT * FROM party_transactions WHERE party_type=? AND party_id=? ORDER BY id DESC',(typ,pid)):t.insert('','end',values=(r['id'],r['txn_type'],f"Rs. {r['amount']:,.2f}",r['note'],r['created_at']))
    def party_txn(self,typ,sel):
        if not sel:return
        pid=int(sel[0]);w=tk.Toplevel(self);w.title(typ+' transaction');f=ttk.Frame(w,padding=20);f.pack();kind=tk.StringVar(value='Payment');ttk.Label(f,text='Type').pack(anchor='w');ttk.Combobox(f,textvariable=kind,values=['Due','Credit','Advance','Payment'],state='readonly').pack(fill='x');a=tk.DoubleVar();ttk.Label(f,text='Amount').pack(anchor='w');ttk.Entry(f,textvariable=a).pack(fill='x');n=tk.StringVar();ttk.Label(f,text='Note').pack(anchor='w');ttk.Entry(f,textvariable=n).pack(fill='x')
        def save():
            amount=float(a.get() or 0);sign=1 if kind.get() in ('Due','Credit') else -1;table='customers' if typ=='Customer' else 'suppliers';now=datetime.now().isoformat(timespec='seconds');self.db.q(f'UPDATE {table} SET balance=balance+? WHERE id=?',(sign*amount,pid));self.db.q('INSERT INTO party_transactions(party_type,party_id,txn_type,amount,note,created_at,user_id) VALUES(?,?,?,?,?,?,?)',(typ,pid,kind.get(),amount,n.get(),now,self.user['id']));self.db.conn.commit();self.db.audit(self.user,'Party Transaction',typ,pid,kind.get());w.destroy();self.show(typ+'s')
        ttk.Button(f,text='Save Transaction',style='Primary.TButton',command=save).pack(fill='x',pady=10)
    def page_kitchen(self):
        ttk.Label(self.content,text='Kitchen Display',style='Title.TLabel').pack(anchor='w');t=self.table(self.content,('id','invoice','type','status','total','time'),{'id':'ID','invoice':'Invoice','type':'Order','status':'Status','total':'Total','time':'Time'},14)
        for r in self.db.rows("SELECT id,invoice_no,order_type,status,total,created_at FROM sales WHERE status IN ('New','Preparing','Ready') ORDER BY id DESC"):t.insert('','end',iid=str(r['id']),values=(r['id'],r['invoice_no'],r['order_type'],r['status'],f"Rs. {r['total']:,.2f}",r['created_at']))
        ttk.Button(self.content,text='Advance Status',style='Primary.TButton',command=lambda:self.order_status(t)).pack(anchor='e',pady=8)
    def page_staff(self):self.staff_page()
    def page_riders(self):self.staff_page('Rider')
    def staff_page(self,role=None):
        ttk.Label(self.content,text=(role+'s' if role else 'Staff'),style='Title.TLabel').pack(anchor='w');t=self.table(self.content,('id','name','phone','role','salary'),{'id':'ID','name':'Name','phone':'Phone','role':'Role','salary':'Salary'},14);sql='SELECT * FROM staff WHERE active=1 ORDER BY name';a=();
        if role:sql='SELECT * FROM staff WHERE active=1 AND role=? ORDER BY name';a=(role,)
        for r in self.db.rows(sql,a):t.insert('','end',iid=str(r['id']),values=(r['id'],r['name'],r['phone'],r['role'],f"Rs. {r['salary']:,.2f}"));ttk.Button(self.content,text='Add Staff',style='Primary.TButton',command=lambda:self.staff_dialog(role)).pack(anchor='e',pady=8)
    def staff_dialog(self,role=None):
        w=tk.Toplevel(self);w.title('Add Staff');f=ttk.Frame(w,padding=20);f.pack();v=[]
        for lab,val in [('Name',''),('Phone',''),('Role',role or 'Staff'),('Salary','')]:ttk.Label(f,text=lab).pack(anchor='w');x=tk.StringVar(value=val);ttk.Entry(f,textvariable=x).pack(fill='x',pady=3);v.append(x)
        ttk.Button(f,text='Save',style='Primary.TButton',command=lambda:(self.db.q('INSERT INTO staff(name,phone,role,salary) VALUES(?,?,?,?)',(v[0].get(),v[1].get(),v[2].get(),float(v[3].get() or 0))),self.db.conn.commit(),w.destroy(),self.show('Riders' if role=='Rider' else 'Staff'))).pack(fill='x',pady=8)
    def page_reports(self):
        ttk.Label(self.content,text='Reports & Analytics',style='Title.TLabel').pack(anchor='w');row=ttk.Frame(self.content);row.pack(fill='x',pady=18);r=self.db.q("SELECT COUNT(*) n,COALESCE(SUM(total),0) total,COALESCE(SUM(discount),0) disc FROM sales").fetchone();self.card(row,'ALL ORDERS',str(r['n']),'Recorded sales');self.card(row,'GROSS SALES',f"Rs. {r['total']:,.2f}",'All recorded sales');self.card(row,'DISCOUNTS',f"Rs. {r['disc']:,.2f}",'Recorded discounts');t=self.table(self.content,('date','orders','sales'),{'date':'Date','orders':'Orders','sales':'Sales'},12)
        for r in self.db.rows("SELECT date(created_at) d,COUNT(*) n,COALESCE(SUM(total),0) total FROM sales GROUP BY date(created_at) ORDER BY d DESC LIMIT 60"):t.insert('','end',values=(r['d'],r['n'],f"Rs. {r['total']:,.2f}"))
    def page_settings(self):
        ttk.Label(self.content,text='Settings',style='Title.TLabel').pack(anchor='w');f=ttk.LabelFrame(self.content,text='Business',style='Card.TLabelframe',padding=18);f.pack(fill='x');v={}
        for k in ['name','address','phone','currency']:ttk.Label(f,text=k.title()).pack(anchor='w');x=tk.StringVar(value=BUSINESS[k]);ttk.Entry(f,textvariable=x).pack(fill='x',pady=(2,8));v[k]=x
        ttk.Button(f,text='Save Business Settings',style='Primary.TButton',command=lambda:BUSINESS.update({k:x.get() for k,x in v.items()})).pack(anchor='e');ttk.Button(self.content,text='Backup Database',command=self.backup).pack(anchor='w',pady=14)
    def backup(self):
        p=filedialog.asksaveasfilename(defaultextension='.db',filetypes=[('SQLite database','*.db')],parent=self)
        if p:self.db.q('VACUUM INTO ?',(p,));messagebox.showinfo('Backup','Backup created successfully.',parent=self)
    def display(self):messagebox.showinfo('Display','The layout is responsive and uses larger controls. Windows display scaling can be used for system-wide scaling.',parent=self)

class Login(tk.Tk):
    def __init__(self,db):
        super().__init__();self.db=db;self.title(BUSINESS['name']+' — Login');self.geometry('470x430');self.configure(bg='#111827');self.resizable(False,False);tk.Label(self,text='MK PIZZA & ICE BAR',bg='#111827',fg='white',font=('Segoe UI',22,'bold')).pack(pady=(55,6));tk.Label(self,text='POINT OF SALE',bg='#111827',fg='#93c5fd',font=('Segoe UI',10,'bold')).pack(pady=(0,28));f=tk.Frame(self,bg='white');f.pack(fill='both',expand=True,padx=30,pady=(0,30));tk.Label(f,text='Sign in',bg='white',fg='#0f172a',font=('Segoe UI',17,'bold')).pack(anchor='w',padx=28,pady=(24,15));self.u=tk.Entry(f,font=('Segoe UI',11),relief='solid',bd=1);self.u.pack(fill='x',padx=28,pady=6);self.u.insert(0,'admin');self.p=tk.Entry(f,font=('Segoe UI',11),show='*',relief='solid',bd=1);self.p.pack(fill='x',padx=28,pady=6);self.p.insert(0,'0099');tk.Button(f,text='LOGIN',bg='#2563eb',fg='white',relief='flat',font=('Segoe UI',10,'bold'),command=self.go).pack(fill='x',padx=28,pady=18,ipady=9);self.p.bind('<Return>',lambda _:self.go())
    def go(self):
        u=self.db.login(self.u.get(),self.p.get())
        if not u:return messagebox.showerror('Login failed','Invalid username or password.',parent=self)
        self.destroy();App(self.db,u).mainloop()

def main():Login(DB()).mainloop()
if __name__=='__main__':main()
