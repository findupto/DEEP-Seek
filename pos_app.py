import csv, hashlib, os, shutil, sqlite3, tkinter as tk
from datetime import datetime
from tkinter import ttk, messagebox, filedialog, simpledialog
from printer_manager import PrinterManager, PrinterSettings

DB='pos.db'
BUSINESS={'name':'MK Pizza & Ice Bar','address':'Collage Road Abbas Chowk, Bhakkar, Pakistan','phone':'0316 9700025','currency':'Rs.','tax':0.0}

def now(): return datetime.now().isoformat(timespec='seconds')
def hp(v): return hashlib.sha256(v.encode()).hexdigest()

class Store:
    def __init__(self,path=DB):
        self.c=sqlite3.connect(path); self.c.row_factory=sqlite3.Row; self.init()
    def init(self):
        self.c.executescript('''
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,username TEXT UNIQUE,role TEXT,password_hash TEXT,active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,price REAL NOT NULL,category TEXT DEFAULT 'General',stock REAL DEFAULT 0,barcode TEXT DEFAULT '',cost REAL DEFAULT 0,active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS customers(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,phone TEXT DEFAULT '',address TEXT DEFAULT '',balance REAL DEFAULT 0,active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS suppliers(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,phone TEXT DEFAULT '',address TEXT DEFAULT '',balance REAL DEFAULT 0,active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS staff(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,phone TEXT DEFAULT '',role TEXT DEFAULT 'Staff',salary REAL DEFAULT 0,active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS riders(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,phone TEXT DEFAULT '',vehicle TEXT DEFAULT '',active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS tables(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE NOT NULL,seats INTEGER DEFAULT 2,status TEXT DEFAULT 'Available');
        CREATE TABLE IF NOT EXISTS sales(id INTEGER PRIMARY KEY AUTOINCREMENT,invoice_no TEXT UNIQUE,user_id INTEGER,customer_id INTEGER,rider_id INTEGER,subtotal REAL,tax REAL,total REAL,payment_method TEXT,payment_status TEXT DEFAULT 'Unpaid',created_at TEXT,status TEXT DEFAULT 'New',discount REAL DEFAULT 0,order_type TEXT DEFAULT 'Counter',table_no TEXT DEFAULT '',guest_count INTEGER DEFAULT 1,notes TEXT DEFAULT '',delivery_address TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS sale_items(id INTEGER PRIMARY KEY AUTOINCREMENT,sale_id INTEGER,product_id INTEGER,product_name TEXT,quantity REAL,unit_price REAL,line_total REAL);
        CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY AUTOINCREMENT,sale_id INTEGER,method TEXT,amount REAL,reference TEXT DEFAULT '',created_at TEXT,user_id INTEGER);
        CREATE TABLE IF NOT EXISTS party_transactions(id INTEGER PRIMARY KEY AUTOINCREMENT,party_type TEXT,party_id INTEGER,txn_type TEXT,amount REAL,note TEXT,created_at TEXT,user_id INTEGER);
        CREATE TABLE IF NOT EXISTS stock_movements(id INTEGER PRIMARY KEY AUTOINCREMENT,product_id INTEGER,qty REAL,movement_type TEXT,note TEXT,created_at TEXT,user_id INTEGER);
        CREATE TABLE IF NOT EXISTS expenses(id INTEGER PRIMARY KEY AUTOINCREMENT,category TEXT,amount REAL,note TEXT,created_at TEXT,user_id INTEGER);
        CREATE TABLE IF NOT EXISTS audit_log(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,action TEXT,entity TEXT,entity_id INTEGER,details TEXT,created_at TEXT);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT);
        ''')
        for u,r in [('admin','Admin'),('owner','Owner'),('cashier','Cashier'),('accountant','Accountant')]: self.c.execute('INSERT OR IGNORE INTO users(username,role,password_hash) VALUES(?,?,?)',(u,r,hp('0099')))
        self.c.commit()
    def q(self,s,a=()): return self.c.execute(s,a)
    def rows(self,s,a=()): return self.q(s,a).fetchall()
    def audit(self,user,action,entity='',eid=None,details=''): self.q('INSERT INTO audit_log(user_id,action,entity,entity_id,details,created_at) VALUES(?,?,?,?,?,?)',(user['id'],action,entity,eid,details,now())); self.c.commit()
    def login(self,u,p): return self.q('SELECT * FROM users WHERE username=? AND password_hash=? AND active=1',(u.strip(),hp(p))).fetchone()

class Login(tk.Tk):
    def __init__(self,s):
        super().__init__(); self.s=s; self.title(BUSINESS['name']+' - Login'); self.geometry('430x330'); self.resizable(False,False)
        f=ttk.Frame(self,padding=35); f.pack(fill='both',expand=True); ttk.Label(f,text=BUSINESS['name'],font=('Segoe UI',20,'bold')).pack(pady=8); ttk.Label(f,text='FASTFOOD POS').pack(pady=(0,22)); self.u=tk.StringVar(value='admin'); self.p=tk.StringVar(value='0099')
        ttk.Label(f,text='Username').pack(anchor='w'); ttk.Entry(f,textvariable=self.u).pack(fill='x',pady=5); ttk.Label(f,text='Password').pack(anchor='w'); ttk.Entry(f,textvariable=self.p,show='*').pack(fill='x',pady=5); ttk.Button(f,text='LOGIN',command=self.go).pack(fill='x',pady=18); self.bind('<Return>',lambda e:self.go())
    def go(self):
        u=self.s.login(self.u.get(),self.p.get())
        if not u:return messagebox.showerror('Login failed','Invalid username or password.',parent=self)
        self.destroy(); App(self.s,u).mainloop()

class App(tk.Tk):
    def __init__(self,s,user):
        super().__init__(); self.s=s; self.user=user; self.cart={}; self.pm=PrinterManager(); self.title(BUSINESS['name']+' — POS'); self.geometry('1400x850'); self.minsize(1100,700)
        st=ttk.Style(self); st.theme_use('clam'); st.configure('TButton',padding=(10,8)); st.configure('Primary.TButton',background='#2563eb',foreground='white',font=('Segoe UI',10,'bold'),padding=(12,10)); st.configure('Title.TLabel',font=('Segoe UI',22,'bold')); st.configure('Treeview',rowheight=32,font=('Segoe UI',10)); st.configure('Treeview.Heading',font=('Segoe UI',10,'bold'))
        self.build(); self.show('POS'); self.after(800,self.pm.auto_reconnect)
    def build(self):
        side=tk.Frame(self,bg='#111827',width=220); side.pack(side='left',fill='y'); side.pack_propagate(False); tk.Label(side,text='MK PIZZA\n& ICE BAR',bg='#111827',fg='white',font=('Segoe UI',17,'bold'),justify='left').pack(anchor='w',padx=18,pady=20)
        for n in ['POS','Dashboard','Orders','Kitchen','Customers','Tables / Dine-in','Suppliers','Products','Riders','Staff','Reports','Printers','Settings']: ttk.Button(side,text=n,command=lambda x=n:self.show(x)).pack(fill='x',padx=10,pady=2)
        tk.Label(side,text=f"{self.user['username']} • {self.user['role']}",bg='#111827',fg='#9ca3af').pack(side='bottom',anchor='w',padx=18,pady=18); self.body=ttk.Frame(self,padding=22); self.body.pack(side='left',fill='both',expand=True)
    def clear(self):
        for w in self.body.winfo_children(): w.destroy()
    def show(self,n):
        self.clear(); fn=getattr(self,'page_'+n.lower().replace(' / ','_').replace(' ','_'),None)
        if fn: fn()
    def table(self,p,cols,heads,height=14):
        f=ttk.Frame(p); f.pack(fill='both',expand=True); t=ttk.Treeview(f,columns=cols,show='headings',selectmode='browse',height=height)
        for c in cols:t.heading(c,text=heads.get(c,c.title()));t.column(c,width=120)
        y=ttk.Scrollbar(f,orient='vertical',command=t.yview);t.configure(yscrollcommand=y.set);t.pack(side='left',fill='both',expand=True);y.pack(side='right',fill='y');return t
    def title(self,text,sub=''):
        ttk.Label(self.body,text=text,style='Title.TLabel').pack(anchor='w');
        if sub:ttk.Label(self.body,text=sub,foreground='#64748b').pack(anchor='w',pady=(2,10))
    def dialog(self,title,w,h):
        x=tk.Toplevel(self);x.title(title);x.geometry(f'{w}x{h}');x.transient(self);x.grab_set();return x
    def page_dashboard(self):
        self.title('Dashboard','Live store totals; no sample data is created.');a=self.s.q("SELECT COUNT(*) n,COALESCE(SUM(total),0) t FROM sales WHERE date(created_at)=date('now','localtime')").fetchone();u=self.s.q("SELECT COUNT(*) n FROM sales WHERE payment_status!='Paid'").fetchone();k=self.s.q("SELECT COUNT(*) n FROM sales WHERE status IN ('New','Preparing','Ready')").fetchone();row=ttk.Frame(self.body);row.pack(fill='x',pady=15)
        for h,v,d in [('Today Sales',f"Rs. {a['t']:,.2f}",f"{a['n']} orders"),('Unpaid Orders',str(u['n']),'Need collection'),('Kitchen Queue',str(k['n']),'New / preparing / ready')]:
            c=ttk.LabelFrame(row,text=h,padding=16);c.pack(side='left',fill='both',expand=True,padx=5);ttk.Label(c,text=v,font=('Segoe UI',20,'bold')).pack(anchor='w');ttk.Label(c,text=d,foreground='#64748b').pack(anchor='w')
    def page_pos(self):
        self.title('New Sale','Build an order, choose customer/order type, then send it to kitchen.');pane=ttk.PanedWindow(self.body,orient='horizontal');pane.pack(fill='both',expand=True,pady=10);left=ttk.Frame(pane);right=ttk.Frame(pane);pane.add(left,weight=3);pane.add(right,weight=2);bar=ttk.Frame(left);bar.pack(fill='x',pady=(0,8));self.search=tk.StringVar();e=ttk.Entry(bar,textvariable=self.search);e.pack(side='left',fill='x',expand=True);e.bind('<KeyRelease>',lambda _:self.load_menu());ttk.Button(bar,text='Products',command=lambda:self.show('Products')).pack(side='right',padx=5);self.menu=self.table(left,('name','cat','price','stock','barcode'),{'name':'Product','cat':'Category','price':'Price','stock':'Stock','barcode':'Barcode'},16);self.menu.bind('<Double-1>',lambda e:self.add_item());ttk.Button(left,text='+ ADD SELECTED',style='Primary.TButton',command=self.add_item).pack(fill='x',pady=8);box=ttk.LabelFrame(right,text='Current Order',padding=12);box.pack(fill='both',expand=True);self.ct=self.table(box,('name','qty','unit','total'),{'name':'Item','qty':'Qty','unit':'Unit','total':'Total'},10);ctl=ttk.Frame(box);ctl.pack(fill='x',pady=8);ttk.Button(ctl,text='+ Qty',command=lambda:self.qty(1)).pack(side='left');ttk.Button(ctl,text='- Qty',command=lambda:self.qty(-1)).pack(side='left',padx=4);ttk.Button(ctl,text='Remove',command=self.remove).pack(side='left');ttk.Button(ctl,text='Clear',command=lambda:(self.cart.clear(),self.refresh())).pack(side='right');self.total=tk.StringVar(value='Rs. 0.00');ttk.Label(box,textvariable=self.total,font=('Segoe UI',22,'bold')).pack(anchor='e',pady=8);ttk.Button(box,text='CHECKOUT / SEND TO KITCHEN',style='Primary.TButton',command=self.checkout).pack(fill='x');self.load_menu();self.refresh()
    def load_menu(self):
        for x in self.menu.get_children():self.menu.delete(x)
        z=self.search.get().lower().strip()
        for r in self.s.rows('SELECT * FROM products WHERE active=1 ORDER BY category,name'):
            if z and z not in f"{r['name']} {r['category']} {r['barcode']}".lower():continue
            self.menu.insert('','end',iid=str(r['id']),values=(r['name'],r['category'],f"Rs. {r['price']:,.2f}",r['stock'],r['barcode']))
    def add_item(self):
        sel=self.menu.selection();
        if not sel:return
        r=self.s.q('SELECT * FROM products WHERE id=?',(int(sel[0]),)).fetchone();i=self.cart.setdefault(r['id'],{'id':r['id'],'name':r['name'],'price':float(r['price']),'qty':0,'stock':float(r['stock'])})
        if i['qty']<i['stock']:i['qty']+=1
        else:messagebox.showwarning('Stock','Insufficient stock.',parent=self)
        self.refresh()
    def refresh(self):
        if not hasattr(self,'ct'):return
        for x in self.ct.get_children():self.ct.delete(x)
        total=0
        for i in self.cart.values():z=i['qty']*i['price'];total+=z;self.ct.insert('','end',iid=str(i['id']),values=(i['name'],i['qty'],f"{i['price']:,.2f}",f"{z:,.2f}"))
        self.total.set(f'Rs. {total:,.2f}')
    def qty(self,d):
        sel=self.ct.selection();
        if not sel:return
        i=self.cart.get(int(sel[0]));
        if i:i['qty']=max(0,min(i['stock'],i['qty']+d));self.cart.pop(i['id'],None) if i['qty']==0 else None;self.refresh()
    def remove(self):
        for x in self.ct.selection():self.cart.pop(int(x),None)
        self.refresh()
    def quick_customer(self,cv,cb,cmap):
        w=self.dialog('New Customer',420,360);f=ttk.Frame(w,padding=18);f.pack(fill='both',expand=True);v={}
        for k,label in [('name','Name'),('phone','Phone'),('address','Delivery / Home Address')]:ttk.Label(f,text=label).pack(anchor='w',pady=(8,2));v[k]=tk.StringVar();ttk.Entry(f,textvariable=v[k]).pack(fill='x')
        def save():
            if not v['name'].get().strip():return messagebox.showerror('Customer','Name is required.',parent=w)
            cur=self.s.q('INSERT INTO customers(name,phone,address) VALUES(?,?,?)',(v['name'].get().strip(),v['phone'].get().strip(),v['address'].get().strip()));self.s.c.commit();r=self.s.q('SELECT * FROM customers WHERE id=?',(cur.lastrowid,)).fetchone();key=f"{r['name']} | {r['phone']}";cmap[key]=r['id'];cb['values']=list(cmap);cv.set(key);w.destroy()
        ttk.Button(f,text='SAVE CUSTOMER',style='Primary.TButton',command=save).pack(fill='x',pady=18)
    def checkout(self):
        if not self.cart:return messagebox.showwarning('Order','Add products first.',parent=self)
        w=self.dialog('Checkout — Customer / Kitchen / Payment',560,650);f=ttk.Frame(w,padding=20);f.pack(fill='both',expand=True);custs=self.s.rows('SELECT * FROM customers WHERE active=1 ORDER BY name');cmap={f"{r['name']} | {r['phone']}":r['id'] for r in custs};cv=tk.StringVar();row=ttk.Frame(f);row.pack(fill='x');ttk.Label(row,text='Customer').pack(side='left');cb=ttk.Combobox(row,textvariable=cv,values=list(cmap),state='readonly');cb.pack(side='left',fill='x',expand=True,padx=6);ttk.Button(row,text='+ New',command=lambda:self.quick_customer(cv,cb,cmap)).pack(side='right');ov=tk.StringVar(value='Counter');ttk.Label(f,text='Order Type').pack(anchor='w',pady=(12,2));ttk.Combobox(f,textvariable=ov,values=['Counter','Takeaway','Dine-in','Delivery'],state='readonly').pack(fill='x');tv=tk.StringVar();gv=tk.IntVar(value=1);ttk.Label(f,text='Table (Dine-in)').pack(anchor='w',pady=(12,2));ttk.Entry(f,textvariable=tv).pack(fill='x');ttk.Label(f,text='Guests').pack(anchor='w',pady=(8,2));ttk.Spinbox(f,from_=1,to=99,textvariable=gv).pack(fill='x');pay=tk.StringVar(value='Cash');ttk.Label(f,text='Payment').pack(anchor='w',pady=(12,2));ttk.Combobox(f,textvariable=pay,values=['Cash','Card','Other','Credit','Pay when Ready'],state='readonly').pack(fill='x');nv=tk.StringVar();ttk.Label(f,text='Notes').pack(anchor='w',pady=(12,2));ttk.Entry(f,textvariable=nv).pack(fill='x');gross=sum(i['qty']*i['price'] for i in self.cart.values());ttk.Label(f,text=f'Total: Rs. {gross:,.2f}',font=('Segoe UI',16,'bold')).pack(anchor='w',pady=16)
        def save():
            typ=ov.get();cid=cmap.get(cv.get());table=tv.get().strip()
            if typ=='Delivery' and not cid:return messagebox.showerror('Delivery','Select/create a customer with saved address.',parent=w)
            if typ=='Delivery' and cid and not self.s.q('SELECT address FROM customers WHERE id=?',(cid,)).fetchone()['address'].strip():return messagebox.showerror('Delivery','Customer address is empty. Edit the customer first.',parent=w)
            if typ=='Dine-in' and not table:return messagebox.showerror('Dine-in','Enter a table number.',parent=w)
            if pay.get()=='Credit' and not cid:return messagebox.showerror('Credit','Customer account is required.',parent=w)
            inv='INV-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f');t=now();ps='Paid' if pay.get() in ('Cash','Card','Other') else 'Unpaid';cur=self.s.c.cursor();addr=self.s.q('SELECT address FROM customers WHERE id=?',(cid,)).fetchone()['address'] if cid else '';cur.execute('INSERT INTO sales(invoice_no,user_id,customer_id,subtotal,tax,total,payment_method,payment_status,created_at,status,order_type,table_no,guest_count,notes,delivery_address) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(inv,self.user['id'],cid,gross,0,gross,pay.get(),ps,t,'New',typ,table,gv.get(),nv.get(),addr));sid=cur.lastrowid
            for i in self.cart.values():cur.execute('INSERT INTO sale_items(sale_id,product_id,product_name,quantity,unit_price,line_total) VALUES(?,?,?,?,?,?)',(sid,i['id'],i['name'],i['qty'],i['price'],i['qty']*i['price']));cur.execute('UPDATE products SET stock=stock-? WHERE id=?',(i['qty'],i['id']));cur.execute('INSERT INTO stock_movements(product_id,qty,movement_type,note,created_at,user_id) VALUES(?,?,?,?,?,?)',(i['id'],-i['qty'],'Sale',inv,t,self.user['id']))
            if ps=='Paid':cur.execute('INSERT INTO payments(sale_id,method,amount,created_at,user_id) VALUES(?,?,?,?,?)',(sid,pay.get(),gross,t,self.user['id']))
            if pay.get()=='Credit':cur.execute('UPDATE customers SET balance=balance+? WHERE id=?',(gross,cid));cur.execute('INSERT INTO party_transactions(party_type,party_id,txn_type,amount,note,created_at,user_id) VALUES(?,?,?,?,?,?,?)',('customer',cid,'Credit',gross,inv,t,self.user['id']))
            self.s.c.commit();self.s.audit(self.user,'CREATE','sale',sid,inv);self.cart.clear();w.destroy();self.show('Kitchen');
            if ps=='Paid':self.try_print(sid)
        ttk.Button(f,text='SEND ORDER TO KITCHEN',style='Primary.TButton',command=save).pack(fill='x')
    def try_print(self,sid):
        r=self.s.q('SELECT * FROM sales WHERE id=?',(sid,)).fetchone();items=self.s.rows('SELECT product_name name,quantity qty,unit_price price FROM sale_items WHERE sale_id=?',(sid,))
        try:self.pm.print_receipt(BUSINESS,r['invoice_no'],[dict(x) for x in items],r['subtotal'],r['tax'],r['total'],r['payment_method'],self.user['username'])
        except Exception as e:messagebox.showwarning('Printer',str(e),parent=self)
    def page_orders(self):
        self.title('Orders','Filter orders, update lifecycle, assign riders and collect unpaid orders.');bar=ttk.Frame(self.body);bar.pack(fill='x',pady=8);self.of=tk.StringVar(value='All');ttk.Combobox(bar,textvariable=self.of,values=['All','New','Preparing','Ready','Completed','Cancelled'],state='readonly',width=15).pack(side='left');ttk.Button(bar,text='Refresh',command=lambda:self.show('Orders')).pack(side='left',padx=5);ttk.Button(bar,text='Collect Payment',command=self.collect_selected).pack(side='right');ttk.Button(bar,text='Assign Rider',command=self.assign_rider).pack(side='right',padx=5);self.ot=self.table(self.body,('id','invoice','type','customer','total','payment','status','created'),{'id':'ID','invoice':'Invoice','type':'Type','customer':'Customer','total':'Total','payment':'Payment','status':'Status','created':'Created'},18);self.load_orders()
    def load_orders(self):
        for x in self.ot.get_children():self.ot.delete(x)
        q="SELECT s.*,COALESCE(c.name,'Walk-in') customer FROM sales s LEFT JOIN customers c ON c.id=s.customer_id";a=();
        if self.of.get()!='All':q+=' WHERE s.status=?';a=(self.of.get(),)
        q+=' ORDER BY s.id DESC'
        for r in self.s.rows(q,a):self.ot.insert('','end',iid=str(r['id']),values=(r['id'],r['invoice_no'],r['order_type'],r['customer'],f"Rs. {r['total']:,.2f}",r['payment_status'],r['status'],r['created_at']))
    def page_kitchen(self):
        self.title('Kitchen Display','Real lifecycle: New → Preparing → Ready → Completed.');bar=ttk.Frame(self.body);bar.pack(fill='x',pady=8);ttk.Button(bar,text='START / PREPARING',command=lambda:self.kitchen_status('Preparing')).pack(side='left');ttk.Button(bar,text='MARK READY',command=lambda:self.kitchen_status('Ready')).pack(side='left',padx=5);ttk.Button(bar,text='COMPLETE',command=lambda:self.kitchen_status('Completed')).pack(side='left');ttk.Button(bar,text='COLLECT PAYMENT',command=self.collect_selected).pack(side='right');self.kt=self.table(self.body,('id','invoice','type','customer','table','total','payment','status'),{'id':'ID','invoice':'Invoice','type':'Type','customer':'Customer','table':'Table','total':'Total','payment':'Payment','status':'Status'},18);self.load_kitchen()
    def load_kitchen(self):
        for x in self.kt.get_children():self.kt.delete(x)
        for r in self.s.rows("SELECT s.*,COALESCE(c.name,'Walk-in') customer FROM sales s LEFT JOIN customers c ON c.id=s.customer_id WHERE s.status IN ('New','Preparing','Ready') ORDER BY s.id") :self.kt.insert('','end',iid=str(r['id']),values=(r['id'],r['invoice_no'],r['order_type'],r['customer'],r['table_no'],f"Rs. {r['total']:,.2f}",r['payment_status'],r['status']))
    def kitchen_status(self,status):
        t=getattr(self,'kt',None);sel=t.selection() if t else ()
        if not sel:return
        sid=int(sel[0]);self.s.q('UPDATE sales SET status=? WHERE id=?',(status,sid));self.s.c.commit();self.s.audit(self.user,'STATUS','sale',sid,status);self.load_kitchen()
    def collect_selected(self):
        t=getattr(self,'ot',None) or getattr(self,'kt',None);sel=t.selection() if t else ()
        if not sel:return messagebox.showwarning('Payment','Select an order.',parent=self)
        self.collect_payment(int(sel[0]))
    def collect_payment(self,sid):
        r=self.s.q('SELECT * FROM sales WHERE id=?',(sid,)).fetchone();
        if not r:return
        paid=self.s.q('SELECT COALESCE(SUM(amount),0) x FROM payments WHERE sale_id=?',(sid,)).fetchone()['x'];due=max(0,float(r['total'])-float(paid))
        if due<=0:return messagebox.showinfo('Payment','This order is already fully paid.',parent=self)
        w=self.dialog('Collect Payment',400,300);f=ttk.Frame(w,padding=18);f.pack(fill='both',expand=True);ttk.Label(f,text=f"Invoice: {r['invoice_no']}").pack(anchor='w');ttk.Label(f,text=f"Due: Rs. {due:,.2f}",font=('Segoe UI',16,'bold')).pack(anchor='w',pady=12);m=tk.StringVar(value='Cash');ttk.Combobox(f,textvariable=m,values=['Cash','Card','Other'],state='readonly').pack(fill='x');ref=tk.StringVar();ttk.Entry(f,textvariable=ref).pack(fill='x',pady=8)
        def pay():
            t=now();self.s.q('INSERT INTO payments(sale_id,method,amount,reference,created_at,user_id) VALUES(?,?,?,?,?,?)',(sid,m.get(),due,ref.get(),t,self.user['id']));self.s.q('UPDATE sales SET payment_status=?,payment_method=? WHERE id=?',('Paid',m.get(),sid));
            if r['customer_id']:self.s.q('UPDATE customers SET balance=MAX(0,balance-?) WHERE id=?',(due,r['customer_id']));self.s.q('INSERT INTO party_transactions(party_type,party_id,txn_type,amount,note,created_at,user_id) VALUES(?,?,?,?,?,?,?)',('customer',r['customer_id'],'Payment',due,r['invoice_no'],t,self.user['id']))
            self.s.c.commit();self.s.audit(self.user,'PAYMENT','sale',sid,f'{m.get()} {due}');w.destroy();self.try_print(sid);self.show('Orders')
        ttk.Button(f,text='TAKE PAYMENT & PRINT',style='Primary.TButton',command=pay).pack(fill='x',pady=10)
    def assign_rider(self):
        sel=self.ot.selection() if hasattr(self,'ot') else (); 
        if not sel:return
        sid=int(sel[0]);riders=self.s.rows('SELECT * FROM riders WHERE active=1 ORDER BY name');mp={f"{r['name']} | {r['phone']}":r['id'] for r in riders};w=self.dialog('Assign Rider',400,220);f=ttk.Frame(w,padding=18);f.pack(fill='both',expand=True);v=tk.StringVar();ttk.Combobox(f,textvariable=v,values=list(mp),state='readonly').pack(fill='x');
        def save():
            rid=mp.get(v.get());
            if not rid:return
            self.s.q('UPDATE sales SET rider_id=? WHERE id=?',(rid,sid));self.s.c.commit();w.destroy();self.show('Orders')
        ttk.Button(f,text='ASSIGN',style='Primary.TButton',command=save).pack(fill='x',pady=15)
    def page_customers(self):self.party_page('customer')
    def page_suppliers(self):self.party_page('supplier')
    def party_page(self,typ):
        label='Customers' if typ=='customer' else 'Suppliers';self.title(label,'Double-click a record to see every account transaction.');bar=ttk.Frame(self.body);bar.pack(fill='x',pady=8);ttk.Button(bar,text='Add',style='Primary.TButton',command=lambda:self.party_edit(typ)).pack(side='left');ttk.Button(bar,text='Record Payment',command=lambda:self.party_payment(typ)).pack(side='left',padx=5);self.pt=self.table(self.body,('id','name','phone','address','balance'),{'id':'ID','name':'Name','phone':'Phone','address':'Address','balance':'Balance'},18);self.party_type=typ
        for r in self.s.rows('SELECT * FROM '+('customers' if typ=='customer' else 'suppliers')+' WHERE active=1 ORDER BY name'):self.pt.insert('','end',iid=str(r['id']),values=(r['id'],r['name'],r['phone'],r['address'],f"Rs. {r['balance']:,.2f}"))
        self.pt.bind('<Double-1>',lambda e:self.party_history(typ))
    def party_edit(self,typ):
        w=self.dialog('New '+typ.title(),430,350);f=ttk.Frame(w,padding=18);f.pack(fill='both',expand=True);v={}
        for k in ['name','phone','address']:ttk.Label(f,text=k.title()).pack(anchor='w');v[k]=tk.StringVar();ttk.Entry(f,textvariable=v[k]).pack(fill='x',pady=4)
        def save():
            if not v['name'].get().strip():return messagebox.showerror('Error','Name required.',parent=w)
            self.s.q('INSERT INTO '+('customers' if typ=='customer' else 'suppliers')+'(name,phone,address) VALUES(?,?,?)',(v['name'].get().strip(),v['phone'].get().strip(),v['address'].get().strip()));self.s.c.commit();w.destroy();self.show('Customers' if typ=='customer' else 'Suppliers')
        ttk.Button(f,text='SAVE',style='Primary.TButton',command=save).pack(fill='x',pady=15)
    def party_history(self,typ):
        sel=self.pt.selection();
        if not sel:return
        pid=int(sel[0]);rows=self.s.rows('SELECT * FROM party_transactions WHERE party_type=? AND party_id=? ORDER BY id DESC',(typ,pid));w=self.dialog('Transaction History',760,500);f=ttk.Frame(w,padding=12);f.pack(fill='both',expand=True);t=self.table(f,('id','type','amount','note','date'),{'id':'ID','type':'Type','amount':'Amount','note':'Note','date':'Date'},18)
        for r in rows:t.insert('','end',values=(r['id'],r['txn_type'],f"Rs. {r['amount']:,.2f}",r['note'],r['created_at']))
    def party_payment(self,typ):
        sel=self.pt.selection();
        if not sel:return
        pid=int(sel[0]);w=self.dialog('Record Payment',400,280);f=ttk.Frame(w,padding=18);f.pack(fill='both',expand=True);a=tk.DoubleVar();n=tk.StringVar();ttk.Label(f,text='Amount').pack(anchor='w');ttk.Entry(f,textvariable=a).pack(fill='x');ttk.Label(f,text='Note').pack(anchor='w',pady=(8,2));ttk.Entry(f,textvariable=n).pack(fill='x')
        def save():
            if a.get()<=0:return messagebox.showerror('Payment','Enter a positive amount.',parent=w)
            table='customers' if typ=='customer' else 'suppliers';self.s.q(f'UPDATE {table} SET balance=MAX(0,balance-?) WHERE id=?',(a.get(),pid));self.s.q('INSERT INTO party_transactions(party_type,party_id,txn_type,amount,note,created_at,user_id) VALUES(?,?,?,?,?,?,?)',(typ,pid,'Payment',a.get(),n.get(),now(),self.user['id']));self.s.c.commit();w.destroy();self.show('Customers' if typ=='customer' else 'Suppliers')
        ttk.Button(f,text='SAVE PAYMENT',style='Primary.TButton',command=save).pack(fill='x',pady=15)
    def page_tables_dine_in(self):
        self.title('Tables / Dine-in','Manage tables and open their sales history.');bar=ttk.Frame(self.body);bar.pack(fill='x',pady=8);ttk.Button(bar,text='Add Table',style='Primary.TButton',command=self.add_table).pack(side='left');self.tt=self.table(self.body,('id','name','seats','status'),{'id':'ID','name':'Table','seats':'Seats','status':'Status'},18)
        for r in self.s.rows('SELECT * FROM tables ORDER BY id'):self.tt.insert('','end',iid=str(r['id']),values=(r['id'],r['name'],r['seats'],r['status']))
        self.tt.bind('<Double-1>',lambda e:self.table_history())
    def add_table(self):
        w=self.dialog('Add Table',360,250);f=ttk.Frame(w,padding=18);f.pack(fill='both',expand=True);n=tk.StringVar();se=tk.IntVar(value=2);ttk.Label(f,text='Table name/number').pack(anchor='w');ttk.Entry(f,textvariable=n).pack(fill='x');ttk.Label(f,text='Seats').pack(anchor='w',pady=8);ttk.Spinbox(f,from_=1,to=100,textvariable=se).pack(fill='x')
        def save():
            try:self.s.q('INSERT INTO tables(name,seats) VALUES(?,?)',(n.get().strip(),se.get()));self.s.c.commit();w.destroy();self.show('Tables / Dine-in')
            except sqlite3.IntegrityError:messagebox.showerror('Table','Table already exists.',parent=w)
        ttk.Button(f,text='SAVE',command=save).pack(fill='x',pady=15)
    def table_history(self):
        sel=self.tt.selection();
        if not sel:return
        name=self.s.q('SELECT name FROM tables WHERE id=?',(int(sel[0]),)).fetchone()['name'];rows=self.s.rows('SELECT invoice_no,total,payment_status,status,created_at FROM sales WHERE table_no=? ORDER BY id DESC',(name,));w=self.dialog('Table History',700,450);f=ttk.Frame(w,padding=12);f.pack(fill='both',expand=True);t=self.table(f,('invoice','total','payment','status','date'),{'invoice':'Invoice','total':'Total','payment':'Payment','status':'Status','date':'Date'},16)
        for r in rows:t.insert('','end',values=(r['invoice_no'],f"Rs. {r['total']:,.2f}",r['payment_status'],r['status'],r['created_at']))
    def page_products(self):
        self.title('Products','Add/edit/delete individually or import/export CSV. No sample products are created.');bar=ttk.Frame(self.body);bar.pack(fill='x',pady=8);ttk.Button(bar,text='Add',style='Primary.TButton',command=lambda:self.product_edit()).pack(side='left');ttk.Button(bar,text='Edit',command=self.product_edit).pack(side='left',padx=4);ttk.Button(bar,text='Delete Selected',command=self.product_delete).pack(side='left');ttk.Button(bar,text='Import CSV',command=self.product_import).pack(side='right');ttk.Button(bar,text='Export CSV',command=self.product_export).pack(side='right',padx=4);self.pr=self.table(self.body,('id','name','category','price','cost','stock','barcode'),{'id':'ID','name':'Name','category':'Category','price':'Price','cost':'Cost','stock':'Stock','barcode':'Barcode'},18);self.load_products()
    def load_products(self):
        for x in self.pr.get_children():self.pr.delete(x)
        for r in self.s.rows('SELECT * FROM products WHERE active=1 ORDER BY name'):self.pr.insert('','end',iid=str(r['id']),values=(r['id'],r['name'],r['category'],r['price'],r['cost'],r['stock'],r['barcode']))
    def product_edit(self):
        sel=self.pr.selection() if hasattr(self,'pr') else ();old=self.s.q('SELECT * FROM products WHERE id=?',(int(sel[0]),)).fetchone() if sel else None;w=self.dialog('Product',430,430);f=ttk.Frame(w,padding=18);f.pack(fill='both',expand=True);v={}
        for k in ['name','category','price','cost','stock','barcode']:ttk.Label(f,text=k.title()).pack(anchor='w');v[k]=tk.StringVar(value=str(old[k]) if old else '');ttk.Entry(f,textvariable=v[k]).pack(fill='x',pady=3)
        def save():
            try:
                data=(v['name'].get().strip(),v['category'].get().strip() or 'General',float(v['price'].get()),float(v['cost'].get() or 0),float(v['stock'].get() or 0),v['barcode'].get().strip());
                if not data[0] or data[2]<0 or data[4]<0:raise ValueError()
                if old:self.s.q('UPDATE products SET name=?,category=?,price=?,cost=?,stock=?,barcode=? WHERE id=?',data+(old['id'],))
                else:self.s.q('INSERT INTO products(name,category,price,cost,stock,barcode) VALUES(?,?,?,?,?,?)',data)
                self.s.c.commit();w.destroy();self.show('Products')
            except ValueError:messagebox.showerror('Product','Enter valid product values.',parent=w)
        ttk.Button(f,text='SAVE PRODUCT',style='Primary.TButton',command=save).pack(fill='x',pady=15)
    def product_delete(self):
        sel=self.pr.selection();
        if not sel:return
        if messagebox.askyesno('Delete','Deactivate selected product?',parent=self):self.s.q('UPDATE products SET active=0 WHERE id=?',(int(sel[0]),));self.s.c.commit();self.load_products()
    def product_export(self):
        p=filedialog.asksaveasfilename(defaultextension='.csv',filetypes=[('CSV','*.csv')],parent=self)
        if not p:return
        rows=self.s.rows('SELECT id,name,category,price,cost,stock,barcode FROM products WHERE active=1')
        with open(p,'w',newline='',encoding='utf-8-sig') as f:
            w=csv.writer(f);w.writerow(['id','name','category','price','cost','stock','barcode']);[w.writerow(list(r)) for r in rows]
    def product_import(self):
        p=filedialog.askopenfilename(filetypes=[('CSV','*.csv')],parent=self)
        if not p:return
        try:
            with open(p,newline='',encoding='utf-8-sig') as f:
                for r in csv.DictReader(f):self.s.q('INSERT INTO products(name,category,price,cost,stock,barcode) VALUES(?,?,?,?,?,?)',(r['name'].strip(),r.get('category','General'),float(r['price']),float(r.get('cost') or 0),float(r.get('stock') or 0),r.get('barcode','').strip()))
            self.s.c.commit();self.load_products()
        except Exception as e:messagebox.showerror('Import failed',str(e),parent=self)
    def page_riders(self):self.simple_people('riders',['name','phone','vehicle'])
    def page_staff(self):self.simple_people('staff',['name','phone','role','salary'])
    def simple_people(self,table,fields):
        self.title(table.title(),'Manage records used by delivery/staff workflows.');bar=ttk.Frame(self.body);bar.pack(fill='x',pady=8);ttk.Button(bar,text='Add',style='Primary.TButton',command=lambda:self.people_edit(table,fields)).pack(side='left');t=self.table(self.body,tuple(['id']+fields),{x:x.title() for x in ['id']+fields},18)
        for r in self.s.rows(f'SELECT * FROM {table} WHERE active=1 ORDER BY name'):t.insert('','end',iid=str(r['id']),values=tuple(r[x] for x in ['id']+fields))
    def people_edit(self,table,fields):
        w=self.dialog('Add '+table.title(),430,430);f=ttk.Frame(w,padding=18);f.pack(fill='both',expand=True);v={}
        for k in fields:ttk.Label(f,text=k.title()).pack(anchor='w');v[k]=tk.StringVar();ttk.Entry(f,textvariable=v[k]).pack(fill='x',pady=3)
        def save():
            try:
                vals=[float(v[k].get()) if k=='salary' else v[k].get().strip() for k in fields]
                if not vals[0]:raise ValueError('Name required')
                self.s.q(f'INSERT INTO {table}({",".join(fields)}) VALUES({",".join("?" for _ in fields)})',vals);self.s.c.commit();w.destroy();self.show(table.title())
            except Exception as e:messagebox.showerror('Save failed',str(e),parent=w)
        ttk.Button(f,text='SAVE',style='Primary.TButton',command=save).pack(fill='x',pady=15)
    def page_reports(self):
        self.title('Reports & Analytics','Live reports from the database.');t=self.table(self.body,('metric','value'),{'metric':'Metric','value':'Value'},14);queries=[('All Sales',"SELECT COALESCE(SUM(total),0) FROM sales"),('Paid Sales',"SELECT COALESCE(SUM(amount),0) FROM payments"),('Customer Dues',"SELECT COALESCE(SUM(balance),0) FROM customers"),('Supplier Dues',"SELECT COALESCE(SUM(balance),0) FROM suppliers"),('Expenses',"SELECT COALESCE(SUM(amount),0) FROM expenses"),('Low/Zero Stock',"SELECT COUNT(*) FROM products WHERE active=1 AND stock<=0")]
        for n,q in queries:t.insert('','end',values=(n,self.s.q(q).fetchone()[0]))
    def page_printers(self):
        self.title('Printers & Receipt Themes','Configure the real 80mm ESC/POS printer; no fake connection is shown.');p=self.pm.status().get('printer') or {};c=ttk.LabelFrame(self.body,text='Printer',padding=16);c.pack(fill='x',pady=12);ttk.Label(c,text=f"Saved: {p.get('name','None')}").pack(anchor='w');ttk.Label(c,text=f"Status: {'Connected' if self.pm.status().get('connected') else 'Not connected'}").pack(anchor='w',pady=3);ttk.Button(c,text='OPEN PRINTER SETTINGS / DISCOVER DEVICES',style='Primary.TButton',command=lambda:PrinterSettings(self,self.pm,BUSINESS)).pack(anchor='w',pady=8);ttk.Button(c,text='Reconnect Now',command=self.pm.auto_reconnect).pack(anchor='w')
    def page_settings(self):
        self.title('Settings','Business settings and local database backup.');f=ttk.LabelFrame(self.body,text='Business',padding=16);f.pack(fill='x');v={}
        for k in ['name','address','phone','currency']:ttk.Label(f,text=k.title()).pack(anchor='w');v[k]=tk.StringVar(value=BUSINESS[k]);ttk.Entry(f,textvariable=v[k]).pack(fill='x',pady=3)
        def save():
            BUSINESS.update({k:v[k].get() for k in v});[self.s.q('INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)',(k,x)) for k,x in v.items()];self.s.c.commit();messagebox.showinfo('Settings','Saved.',parent=self)
        ttk.Button(f,text='SAVE SETTINGS',style='Primary.TButton',command=save).pack(fill='x',pady=12);b=ttk.LabelFrame(self.body,text='Backup',padding=16);b.pack(fill='x',pady=12);ttk.Button(b,text='Backup Database',command=self.backup).pack(anchor='w')
    def backup(self):
        p=filedialog.asksaveasfilename(defaultextension='.db',initialfile='pos-backup.db',filetypes=[('SQLite','*.db')],parent=self)
        if p:self.s.c.commit();shutil.copy2(DB,p);messagebox.showinfo('Backup','Database backup created.',parent=self)

def main():Login(Store()).mainloop()
if __name__=='__main__':main()
