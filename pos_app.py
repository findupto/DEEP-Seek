import csv, hashlib, sqlite3, tkinter as tk
from datetime import datetime
from tkinter import ttk, messagebox, filedialog
from printer_manager import PrinterManager, PrinterSettings

DB='pos.db'
BUSINESS={'name':'MK Pizza & Ice Bar','address':'Collage Road Abbas Chowk, Bhakkar, Pakistan','phone':'0316 9700025','currency':'Rs.','tax':0}

class Store:
    def __init__(self,path=DB):
        self.c=sqlite3.connect(path); self.c.row_factory=sqlite3.Row; self.init()
    def init(self):
        self.c.executescript('''
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT UNIQUE,role TEXT,password_hash TEXT,active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,price REAL NOT NULL,category TEXT DEFAULT 'General',stock REAL DEFAULT 0,barcode TEXT DEFAULT '',cost REAL DEFAULT 0,active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS customers(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,phone TEXT DEFAULT '',address TEXT DEFAULT '',balance REAL DEFAULT 0,active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS sales(id INTEGER PRIMARY KEY AUTOINCREMENT,invoice_no TEXT UNIQUE,user_id INTEGER,customer_id INTEGER,subtotal REAL,tax REAL,total REAL,payment_method TEXT,payment_status TEXT DEFAULT 'Unpaid',created_at TEXT,status TEXT DEFAULT 'New',discount REAL DEFAULT 0,order_type TEXT DEFAULT 'Counter',table_no TEXT DEFAULT '',guest_count INTEGER DEFAULT 0,notes TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS sale_items(id INTEGER PRIMARY KEY AUTOINCREMENT,sale_id INTEGER,product_id INTEGER,product_name TEXT,quantity REAL,unit_price REAL,line_total REAL);
        CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY AUTOINCREMENT,sale_id INTEGER,method TEXT,amount REAL,reference TEXT DEFAULT '',created_at TEXT,user_id INTEGER);
        CREATE TABLE IF NOT EXISTS party_transactions(id INTEGER PRIMARY KEY AUTOINCREMENT,party_type TEXT,party_id INTEGER,txn_type TEXT,amount REAL,note TEXT,created_at TEXT,user_id INTEGER);
        CREATE TABLE IF NOT EXISTS stock_movements(id INTEGER PRIMARY KEY AUTOINCREMENT,product_id INTEGER,qty REAL,movement_type TEXT,note TEXT,created_at TEXT,user_id INTEGER);
        CREATE TABLE IF NOT EXISTS audit_log(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,action TEXT,entity TEXT,entity_id INTEGER,details TEXT,created_at TEXT);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT);
        ''')
        for c,d in [('payment_status',"TEXT DEFAULT 'Unpaid'"),('table_no',"TEXT DEFAULT ''"),('guest_count','INTEGER DEFAULT 0')]:
            if c not in {r[1] for r in self.c.execute('PRAGMA table_info(sales)')}: self.c.execute('ALTER TABLE sales ADD COLUMN '+c+' '+d)
        for u,r in [('admin','Admin'),('owner','Owner'),('cashier','Cashier'),('accountant','Accountant')]: self.c.execute('INSERT OR IGNORE INTO users(username,role,password_hash) VALUES(?,?,?)',(u,r,hashlib.sha256(b'0099').hexdigest()))
        self.c.commit()
    def q(self,s,a=()): return self.c.execute(s,a)
    def rows(self,s,a=()): return self.q(s,a).fetchall()
    def audit(self,u,a,e='',eid=None,d=''): self.q('INSERT INTO audit_log(user_id,action,entity,entity_id,details,created_at) VALUES(?,?,?,?,?,?)',(u['id'],a,e,eid,d,datetime.now().isoformat(timespec='seconds')));self.c.commit()
    def login(self,u,p): return self.q('SELECT * FROM users WHERE username=? AND password_hash=? AND active=1',(u.strip(),hashlib.sha256(p.encode()).hexdigest())).fetchone()

class Login(tk.Tk):
    def __init__(self,store):
        super().__init__();self.s=store;self.title(BUSINESS['name']+' - Login');self.geometry('440x330');self.configure(bg='#f4f7fb');f=ttk.Frame(self,padding=35);f.pack(fill='both',expand=True);ttk.Label(f,text=BUSINESS['name'],font=('Segoe UI',20,'bold')).pack(pady=10);ttk.Label(f,text='FASTFOOD POS').pack(pady=(0,25));self.u=tk.StringVar();self.p=tk.StringVar();ttk.Label(f,text='Username').pack(anchor='w');ttk.Entry(f,textvariable=self.u).pack(fill='x',pady=5);ttk.Label(f,text='Password').pack(anchor='w');ttk.Entry(f,textvariable=self.p,show='•').pack(fill='x',pady=5);ttk.Button(f,text='LOGIN',command=self.go).pack(fill='x',pady=18);self.bind('<Return>',lambda e:self.go());self.u.set('admin');self.p.set('0099')
    def go(self):
        u=self.s.login(self.u.get(),self.p.get())
        if not u:return messagebox.showerror('Login failed','Invalid username or password.',parent=self)
        self.destroy();App(self.s,u).mainloop()

class App(tk.Tk):
    def __init__(self,s,user):
        super().__init__();self.s=s;self.user=user;self.cart={};self.pm=PrinterManager();self.title(BUSINESS['name']+' — POS');self.geometry('1400x850');self.minsize(1100,700);self.style=ttk.Style(self);self.style.theme_use('clam');self.style.configure('TButton',padding=(10,8));self.style.configure('Primary.TButton',background='#2563eb',foreground='white',font=('Segoe UI',10,'bold'),padding=(12,10));self.style.map('Primary.TButton',background=[('active','#1d4ed8')]);self.style.configure('Title.TLabel',font=('Segoe UI',22,'bold'));self.style.configure('Treeview',rowheight=34,font=('Segoe UI',10));self.build();self.show('POS');self.after(500,self.pm.auto_reconnect)
    def build(self):
        side=tk.Frame(self,bg='#111827',width=225);side.pack(side='left',fill='y');side.pack_propagate(False);tk.Label(side,text='MK PIZZA\n& ICE BAR',bg='#111827',fg='white',font=('Segoe UI',17,'bold'),justify='left').pack(anchor='w',padx=18,pady=20);tk.Label(side,text='FASTFOOD POS',bg='#111827',fg='#93c5fd').pack(anchor='w',padx=18,pady=(0,15))
        for n in ['POS','Orders','Kitchen','Customers','Tables / Dine-in','Riders','Products','Printers','Reports','Settings']:
            ttk.Button(side,text=n,command=lambda x=n:self.show(x)).pack(fill='x',padx=10,pady=3)
        tk.Label(side,text=f"{self.user['username']} • {self.user['role']}",bg='#111827',fg='#9ca3af').pack(side='bottom',anchor='w',padx=18,pady=18);self.body=ttk.Frame(self,padding=22);self.body.pack(side='left',fill='both',expand=True)
    def clear(self):
        for w in self.body.winfo_children():w.destroy()
    def show(self,n): self.clear();getattr(self,'page_'+n.lower().replace(' / ','_').replace(' ','_'))()
    def table(self,p,cols,heads,height=14):
        f=ttk.Frame(p);f.pack(fill='both',expand=True);t=ttk.Treeview(f,columns=cols,show='headings',selectmode='browse',height=height)
        for c in cols:t.heading(c,text=heads.get(c,c.title()));t.column(c,width=120)
        sy=ttk.Scrollbar(f,orient='vertical',command=t.yview);t.configure(yscrollcommand=sy.set);t.pack(side='left',fill='both',expand=True);sy.pack(side='right',fill='y');return t
    def page_pos(self):
        top=ttk.Frame(self.body);top.pack(fill='x');ttk.Label(top,text='New Sale',style='Title.TLabel').pack(side='left');ttk.Button(top,text='Printer',command=lambda:self.show('Printers')).pack(side='right')
        pane=ttk.PanedWindow(self.body,orient='horizontal');pane.pack(fill='both',expand=True,pady=15);left=ttk.Frame(pane);right=ttk.Frame(pane);pane.add(left,weight=3);pane.add(right,weight=2)
        bar=ttk.Frame(left);bar.pack(fill='x',pady=(0,8));self.search=tk.StringVar();e=ttk.Entry(bar,textvariable=self.search);e.pack(side='left',fill='x',expand=True);e.bind('<KeyRelease>',lambda _:self.load_menu());ttk.Button(bar,text='Manage Products',command=lambda:self.show('Products')).pack(side='right',padx=5);self.menu=self.table(left,('name','cat','price','stock'),{'name':'Product','cat':'Category','price':'Price','stock':'Stock'},16);self.menu.bind('<Double-1>',lambda e:self.add_item());ttk.Button(left,text='+ ADD SELECTED',style='Primary.TButton',command=self.add_item).pack(fill='x',pady=8)
        box=ttk.LabelFrame(right,text='Current Order',padding=12);box.pack(fill='both',expand=True);self.ct=self.table(box,('name','qty','unit','total'),{'name':'Item','qty':'Qty','unit':'Unit','total':'Total'},10);ctl=ttk.Frame(box);ctl.pack(fill='x',pady=8);ttk.Button(ctl,text='+ Qty',command=lambda:self.qty(1)).pack(side='left');ttk.Button(ctl,text='- Qty',command=lambda:self.qty(-1)).pack(side='left',padx=4);ttk.Button(ctl,text='Remove',command=self.remove).pack(side='left');ttk.Button(ctl,text='Clear',command=lambda:(self.cart.clear(),self.refresh())).pack(side='right');self.total=tk.StringVar(value='Rs. 0.00');ttk.Label(box,textvariable=self.total,font=('Segoe UI',22,'bold')).pack(anchor='e',pady=8);ttk.Button(box,text='CHECKOUT / SEND TO KITCHEN',style='Primary.TButton',command=self.checkout).pack(fill='x');self.load_menu();self.refresh()
    def load_menu(self):
        for x in self.menu.get_children():self.menu.delete(x)
        z=self.search.get().lower().strip()
        for r in self.s.rows('SELECT * FROM products WHERE active=1 ORDER BY category,name'):
            if z and z not in f"{r['name']} {r['category']} {r['barcode']}".lower():continue
            self.menu.insert('','end',iid=str(r['id']),values=(r['name'],r['category'],f"Rs. {r['price']:,.2f}",r['stock']))
    def add_item(self):
        sel=self.menu.selection()
        if not sel:return
        r=self.s.q('SELECT * FROM products WHERE id=?',(int(sel[0]),)).fetchone();i=self.cart.setdefault(r['id'],{'id':r['id'],'name':r['name'],'price':float(r['price']),'qty':0,'stock':float(r['stock'])});
        if i['qty']<i['stock']:i['qty']+=1
        else: messagebox.showwarning('Stock','No more stock available.',parent=self)
        self.refresh()
    def refresh(self):
        if not hasattr(self,'ct'):return
        for x in self.ct.get_children():self.ct.delete(x)
        total=0
        for i in self.cart.values():
            z=i['qty']*i['price'];total+=z;self.ct.insert('','end',iid=str(i['id']),values=(i['name'],i['qty'],f"{i['price']:,.2f}",f"{z:,.2f}"))
        self.total.set(f'Rs. {total:,.2f}')
    def qty(self,d):
        sel=self.ct.selection();
        if not sel:return
        i=self.cart.get(int(sel[0]));
        if i:i['qty']=max(0,min(i['stock'],i['qty']+d));self.cart.pop(i['id'],None) if i['qty']==0 else None;self.refresh()
    def remove(self):
        for x in self.ct.selection():self.cart.pop(int(x),None)
        self.refresh()
    def checkout(self):
        if not self.cart:return messagebox.showwarning('Order','Add products first.',parent=self)
        w=tk.Toplevel(self);w.title('Checkout — Customer / Payment / Kitchen');w.geometry('560x700');w.transient(self);w.grab_set();f=ttk.Frame(w,padding=20);f.pack(fill='both',expand=True);ttk.Label(f,text='Order Details',font=('Segoe UI',18,'bold')).pack(anchor='w',pady=(0,12))
        custs=self.s.rows('SELECT * FROM customers WHERE active=1 ORDER BY name'); cmap={f"{r['name']} | {r['phone']}":r['id'] for r in custs};cv=tk.StringVar();row=ttk.Frame(f);row.pack(fill='x');ttk.Label(row,text='Customer').pack(side='left');cb=ttk.Combobox(row,textvariable=cv,values=list(cmap),state='readonly');cb.pack(side='left',fill='x',expand=True,padx=6);ttk.Button(row,text='+ New',command=lambda:self.quick_customer(cv,cb,cmap)).pack(side='right')
        ov=tk.StringVar(value='Counter');ttk.Label(f,text='Order Type').pack(anchor='w',pady=(12,2));ttk.Combobox(f,textvariable=ov,values=['Counter','Takeaway','Dine-in','Delivery'],state='readonly').pack(fill='x')
        tv=tk.StringVar();gv=tk.IntVar(value=1);ttk.Label(f,text='Table Number (for Dine-in)').pack(anchor='w',pady=(12,2));ttk.Entry(f,textvariable=tv).pack(fill='x');ttk.Label(f,text='Guests').pack(anchor='w',pady=(8,2));ttk.Spinbox(f,from_=1,to=99,textvariable=gv).pack(fill='x')
        ttk.Label(f,text='Delivery address is stored on the selected customer record.').pack(anchor='w',pady=(8,0))
        pay=tk.StringVar(value='Cash');ttk.Label(f,text='Payment').pack(anchor='w',pady=(12,2));ttk.Combobox(f,textvariable=pay,values=['Cash','Card','Other','Credit','Pay when Ready'],state='readonly').pack(fill='x')
        nv=tk.StringVar();ttk.Label(f,text='Order Notes').pack(anchor='w',pady=(12,2));ttk.Entry(f,textvariable=nv).pack(fill='x');gross=sum(i['qty']*i['price'] for i in self.cart.values());ttk.Label(f,text=f'Total: Rs. {gross:,.2f}',font=('Segoe UI',15,'bold')).pack(anchor='w',pady=15)
        def save():
            typ=ov.get();cid=cmap.get(cv.get());
            if typ=='Delivery' and not cid:return messagebox.showerror('Delivery customer required','Create/select the customer so name, phone and delivery address are saved.',parent=w)
            if typ=='Dine-in' and not tv.get().strip():return messagebox.showerror('Table required','Enter the table number for dine-in.',parent=w)
            if pay.get()=='Credit' and not cid:return messagebox.showerror('Customer required','Credit sales need a customer account.',parent=w)
            total=gross;now=datetime.now().isoformat(timespec='seconds');inv='INV-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f');status='New';pstatus='Paid' if pay.get() not in ('Pay when Ready','Credit') else ('Unpaid' if pay.get()=='Pay when Ready' else 'Unpaid')
            cur=self.s.c.cursor();cur.execute('INSERT INTO sales(invoice_no,user_id,customer_id,subtotal,tax,total,payment_method,payment_status,created_at,status,order_type,table_no,guest_count,notes) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(inv,self.user['id'],cid,total,0,total,pay.get(),pstatus,now,status,typ,tv.get().strip(),gv.get(),nv.get()));sid=cur.lastrowid
            for i in self.cart.values():
                cur.execute('INSERT INTO sale_items(sale_id,product_id,product_name,quantity,unit_price,line_total) VALUES(?,?,?,?,?,?,?)',(sid,i['id'],i['name'],i['qty'],i['price'],i['qty']*i['price']));cur.execute('UPDATE products SET stock=stock-? WHERE id=?',(i['qty'],i['id']));cur.execute('INSERT INTO stock_movements(product_id,qty,movement_type,note,created_at,user_id) VALUES(?,?,?,?,?,?)',(i['id'],-i['qty'],'Sale',inv,now,self.user['id']))
            if pstatus=='Paid':cur.execute('INSERT INTO payments(sale_id,method,amount,created_at,user_id) VALUES(?,?,?,?,?)',(sid,pay.get(),total,now,self.user['id']))
            if pay.get()=='Credit':cur.execute('UPDATE customers SET balance=balance+? WHERE id=?',(total,cid));cur.execute('INSERT INTO party_transactions(party_type,party_id,txn_type,amount,note,created_at,user_id) VALUES(?,?,?,?,?,?,?)',('Customer',cid,'Due',total,inv,now,self.user['id']))
            self.s.c.commit();self.s.audit(self.user,'Send Order to Kitchen','sale',sid,f'{inv} {typ} {pay.get()}');self.print_kitchen(inv,sid,typ,tv.get(),cid);w.destroy();self.cart.clear();self.load_menu();self.refresh();messagebox.showinfo('Order sent',f'{inv}\nStatus: NEW\nKitchen has received the order.\nPayment: {pstatus}',parent=self)
        ttk.Button(f,text='SEND ORDER TO KITCHEN',style='Primary.TButton',command=save).pack(fill='x',pady=8)
    def quick_customer(self,cv,cb,cmap):
        w=tk.Toplevel(self);w.title('New Customer');w.transient(self);f=ttk.Frame(w,padding=18);f.pack();vs=[]
        for lab in ['Name','Phone','Delivery Address']:ttk.Label(f,text=lab).pack(anchor='w');v=tk.StringVar();ttk.Entry(f,textvariable=v,width=42).pack(pady=4);vs.append(v)
        def save():
            if not vs[0].get().strip():return
            cur=self.s.q('INSERT INTO customers(name,phone,address) VALUES(?,?,?)',(vs[0].get().strip(),vs[1].get().strip(),vs[2].get().strip()));self.s.c.commit();r=self.s.q('SELECT * FROM customers WHERE id=?',(cur.lastrowid,)).fetchone();key=f"{r['name']} | {r['phone']}";cmap[key]=r['id'];cb['values']=list(cmap);cv.set(key);w.destroy()
        ttk.Button(f,text='Save Customer',style='Primary.TButton',command=save).pack(fill='x',pady=8)
    def print_kitchen(self,inv,sid,typ,table,cid):
        try:
            items=[dict(x) for x in self.s.rows('SELECT product_name name,quantity qty,unit_price price FROM sale_items WHERE sale_id=?',(sid,))];self.pm.print_receipt(BUSINESS,inv,items,0,0,0,'KITCHEN',self.user['username'])
        except Exception: pass
    def page_orders(self):
        ttk.Label(self.body,text='Orders',style='Title.TLabel').pack(anchor='w');t=self.table(self.body,('id','invoice','status','type','table','payment','paid','total'),{'id':'ID','invoice':'Invoice','status':'Status','type':'Type','table':'Table','payment':'Payment','paid':'Paid?','total':'Total'},18)
        for r in self.s.rows('SELECT * FROM sales ORDER BY id DESC LIMIT 500'):t.insert('','end',iid=str(r['id']),values=(r['id'],r['invoice_no'],r['status'],r['order_type'],r['table_no'],r['payment_method'],r['payment_status'],f"Rs. {r['total']:,.2f}"))
        bar=ttk.Frame(self.body);bar.pack(fill='x',pady=8);ttk.Button(bar,text='Update Status',style='Primary.TButton',command=lambda:self.change_status(t)).pack(side='left');ttk.Button(bar,text='Collect Payment',command=lambda:self.collect_payment(t)).pack(side='left',padx=6)
    def change_status(self,t):
        sel=t.selection();
        if not sel:return
        sid=int(sel[0]);r=self.s.q('SELECT status FROM sales WHERE id=?',(sid,)).fetchone();cur=r['status'];nexts={'New':'Preparing','Preparing':'Ready','Ready':'Completed','Out for Delivery':'Delivered','Completed':'Completed','Delivered':'Delivered','Cancelled':'Cancelled'};n=nexts.get(cur,cur)
        if cur=='Ready': n='Completed'
        if messagebox.askyesno('Advance order',f'{cur} → {n}?',parent=self):self.s.q('UPDATE sales SET status=? WHERE id=?',(n,sid));self.s.c.commit();self.s.audit(self.user,'Advance Order','sale',sid,n);self.show('Orders')
    def collect_payment(self,t):
        sel=t.selection();
        if not sel:return
        sid=int(sel[0]);r=self.s.q('SELECT * FROM sales WHERE id=?',(sid,)).fetchone()
        if r['payment_status']=='Paid':return messagebox.showinfo('Payment','This order is already paid.',parent=self)
        w=tk.Toplevel(self);w.title('Collect Payment');f=ttk.Frame(w,padding=20);f.pack();ttk.Label(f,text=f"Invoice {r['invoice_no']} — Rs. {r['total']:,.2f}",font=('Segoe UI',14,'bold')).pack(pady=8);m=tk.StringVar(value='Cash');ttk.Combobox(f,textvariable=m,values=['Cash','Card','Other'],state='readonly').pack(fill='x',pady=8);ref=tk.StringVar();ttk.Entry(f,textvariable=ref).pack(fill='x',pady=8)
        def pay():
            now=datetime.now().isoformat(timespec='seconds');self.s.q('INSERT INTO payments(sale_id,method,amount,reference,created_at,user_id) VALUES(?,?,?,?,?,?)',(sid,m.get(),r['total'],ref.get(),now,self.user['id']));self.s.q('UPDATE sales SET payment_status=?,payment_method=? WHERE id=?',('Paid',m.get(),sid));self.s.c.commit();self.s.audit(self.user,'Collect Payment','sale',sid,m.get());self.print_receipt(sid);w.destroy();self.show('Orders')
        ttk.Button(f,text='TAKE PAYMENT & PRINT RECEIPT',style='Primary.TButton',command=pay).pack(fill='x',pady=8)
    def print_receipt(self,sid):
        r=self.s.q('SELECT * FROM sales WHERE id=?',(sid,)).fetchone();items=[dict(x) for x in self.s.rows('SELECT product_name name,quantity qty,unit_price price FROM sale_items WHERE sale_id=?',(sid,))]
        try:self.pm.print_receipt(BUSINESS,r['invoice_no'],items,r['subtotal'],r['tax'],r['total'],r['payment_method'],self.user['username'])
        except Exception as e:messagebox.showwarning('Printer','Payment saved, but receipt could not be printed:\n'+str(e),parent=self)
    def page_kitchen(self):
        ttk.Label(self.body,text='Kitchen Display System',style='Title.TLabel').pack(anchor='w');ttk.Label(self.body,text='New → Preparing → Ready. Payment can be collected when ready.',foreground='#64748b').pack(anchor='w',pady=(0,10));t=self.table(self.body,('id','invoice','type','table','status','paid','time'),{'id':'ID','invoice':'Invoice','type':'Order','table':'Table','status':'Status','paid':'Payment','time':'Created'},18)
        for r in self.s.rows("SELECT id,invoice_no,order_type,table_no,status,payment_status,created_at FROM sales WHERE status IN ('New','Preparing','Ready') ORDER BY id"):t.insert('','end',iid=str(r['id']),values=(r['id'],r['invoice_no'],r['order_type'],r['table_no'],r['status'],r['payment_status'],r['created_at']))
        bar=ttk.Frame(self.body);bar.pack(fill='x',pady=8);ttk.Button(bar,text='START / PREPARING',style='Primary.TButton',command=lambda:self.set_kitchen(t,'Preparing')).pack(side='left');ttk.Button(bar,text='MARK READY',style='Primary.TButton',command=lambda:self.set_kitchen(t,'Ready')).pack(side='left',padx=6);ttk.Button(bar,text='COLLECT PAYMENT',command=lambda:self.collect_payment(t)).pack(side='left');ttk.Button(bar,text='REFRESH',command=lambda:self.show('Kitchen')).pack(side='right')
    def set_kitchen(self,t,status):
        sel=t.selection();
        if not sel:return
        sid=int(sel[0]);self.s.q('UPDATE sales SET status=? WHERE id=?',(status,sid));self.s.c.commit();self.s.audit(self.user,'Kitchen Status','sale',sid,status);self.show('Kitchen')
    def page_customers(self):
        ttk.Label(self.body,text='Customers & History',style='Title.TLabel').pack(anchor='w');bar=ttk.Frame(self.body);bar.pack(fill='x',pady=10);q=tk.StringVar();ttk.Entry(bar,textvariable=q).pack(side='left',fill='x',expand=True);ttk.Button(bar,text='+ Customer',style='Primary.TButton',command=self.new_customer).pack(side='right',padx=5);t=self.table(self.body,('id','name','phone','address','balance'),{'id':'ID','name':'Name','phone':'Phone','address':'Address','balance':'Due / Balance'},18)
        def load(*_):
            for x in t.get_children():t.delete(x)
            z=q.get().lower();
            for r in self.s.rows('SELECT * FROM customers WHERE active=1 ORDER BY name'):
                if not z or z in f"{r['name']} {r['phone']} {r['address']}".lower():t.insert('','end',iid=str(r['id']),values=(r['id'],r['name'],r['phone'],r['address'],f"Rs. {r['balance']:,.2f}"))
        q.trace_add('write',load);load();t.bind('<Double-1>',lambda e:self.customer_history(t))
    def new_customer(self):
        w=tk.Toplevel(self);w.title('Customer');f=ttk.Frame(w,padding=20);f.pack();vs=[]
        for x in ['Name','Phone','Address']:ttk.Label(f,text=x).pack(anchor='w');v=tk.StringVar();ttk.Entry(f,textvariable=v,width=45).pack(pady=4);vs.append(v)
        ttk.Button(f,text='Save',style='Primary.TButton',command=lambda:self.save_customer(w,vs)).pack(fill='x',pady=8)
    def save_customer(self,w,vs):
        if not vs[0].get().strip():return
        self.s.q('INSERT INTO customers(name,phone,address) VALUES(?,?,?)',(vs[0].get().strip(),vs[1].get().strip(),vs[2].get().strip()));self.s.c.commit();w.destroy();self.show('Customers')
    def customer_history(self,t):
        sel=t.selection();
        if not sel:return
        cid=int(sel[0]);c=self.s.q('SELECT * FROM customers WHERE id=?',(cid,)).fetchone();w=tk.Toplevel(self);w.title(c['name']+' — Complete History');w.geometry('950x600');ttk.Label(w,text=f"{c['name']} | {c['phone']} | Due: Rs. {c['balance']:,.2f}",font=('Segoe UI',15,'bold')).pack(anchor='w',padx=18,pady=15);ot=self.table(w,('invoice','type','table','status','payment','total','date'),{'invoice':'Invoice','type':'Order','table':'Table','status':'Status','payment':'Payment','total':'Total','date':'Date'},14)
        for r in self.s.rows('SELECT invoice_no,order_type,table_no,status,payment_method,total,created_at FROM sales WHERE customer_id=? ORDER BY id DESC',(cid,)):ot.insert('','end',values=(r['invoice_no'],r['order_type'],r['table_no'],r['status'],r['payment_method'],f"Rs. {r['total']:,.2f}",r['created_at']))
    def page_tables___dine_in(self): self.page_tables__dine_in()
    def page_tables__dine_in(self):
        ttk.Label(self.body,text='Tables / Dine-in',style='Title.TLabel').pack(anchor='w');ttk.Label(self.body,text='Tables are user-created; no dummy tables are inserted.',foreground='#64748b').pack(anchor='w',pady=(0,10));t=self.table(self.body,('table','orders','customers','sales'),{'table':'Table','orders':'Orders','customers':'Customers','sales':'Sales'},18)
        for r in self.s.rows("SELECT table_no,COUNT(*) orders,COUNT(DISTINCT customer_id) customers,COALESCE(SUM(total),0) sales FROM sales WHERE order_type='Dine-in' AND table_no<>'' GROUP BY table_no ORDER BY table_no"):t.insert('','end',values=(r['table_no'],r['orders'],r['customers'],f"Rs. {r['sales']:,.2f}"))
        ttk.Button(self.body,text='Open New Dine-in Sale',style='Primary.TButton',command=lambda:self.show('POS')).pack(anchor='e',pady=8)
    def page_riders(self):
        ttk.Label(self.body,text='Riders',style='Title.TLabel').pack(anchor='w');t=self.table(self.body,('id','name','phone'),{'id':'ID','name':'Name','phone':'Phone'},15)
        for r in self.s.rows("SELECT id,name,phone FROM users WHERE role='Rider' AND active=1"):t.insert('','end',values=(r['id'],r['name'],r['phone'] if 'phone' in r.keys() else ''))
    def page_products(self):
        ttk.Label(self.body,text='Products',style='Title.TLabel').pack(anchor='w');bar=ttk.Frame(self.body);bar.pack(fill='x',pady=10);ttk.Button(bar,text='+ Product',style='Primary.TButton',command=self.product_dialog).pack(side='right');ttk.Button(bar,text='Import CSV',command=self.import_csv).pack(side='right',padx=5);ttk.Button(bar,text='Export CSV',command=self.export_csv).pack(side='right');t=self.table(self.body,('id','name','category','price','stock','barcode'),{'id':'ID','name':'Product','category':'Category','price':'Price','stock':'Stock','barcode':'Barcode'},18)
        for r in self.s.rows('SELECT * FROM products WHERE active=1 ORDER BY name'):t.insert('','end',iid=str(r['id']),values=(r['id'],r['name'],r['category'],f"Rs. {r['price']:,.2f}",r['stock'],r['barcode']))
        t.bind('<Double-1>',lambda e:self.product_dialog(t.selection()))
    def product_dialog(self,sel=()):
        old=self.s.q('SELECT * FROM products WHERE id=?',(int(sel[0]),)).fetchone() if sel else None;w=tk.Toplevel(self);w.title('Product');f=ttk.Frame(w,padding=20);f.pack();vs=[]
        for lab,key in [('Name','name'),('Price','price'),('Category','category'),('Stock','stock'),('Barcode','barcode'),('Cost','cost')]:ttk.Label(f,text=lab).pack(anchor='w');v=tk.StringVar(value=str(old[key]) if old else '');ttk.Entry(f,textvariable=v,width=45).pack(pady=3);vs.append(v)
        def save():
            try:d=(vs[0].get().strip(),float(vs[1].get()),vs[2].get().strip() or 'General',float(vs[3].get() or 0),vs[4].get().strip(),float(vs[5].get() or 0));
            except: return messagebox.showerror('Invalid','Check product values.',parent=w)
            if old:self.s.q('UPDATE products SET name=?,price=?,category=?,stock=?,barcode=?,cost=? WHERE id=?',d+(old['id'],))
            else:self.s.q('INSERT INTO products(name,price,category,stock,barcode,cost) VALUES(?,?,?,?,?,?)',d)
            self.s.c.commit();w.destroy();self.show('Products')
        ttk.Button(f,text='Save Product',style='Primary.TButton',command=save).pack(fill='x',pady=8)
    def export_csv(self):
        p=filedialog.asksaveasfilename(defaultextension='.csv',filetypes=[('CSV','*.csv')],parent=self)
        if p:
            with open(p,'w',newline='',encoding='utf-8-sig') as f:w=csv.writer(f);w.writerow(['name','price','category','stock','barcode','cost']);[w.writerow([r['name'],r['price'],r['category'],r['stock'],r['barcode'],r['cost']]) for r in self.s.rows('SELECT * FROM products WHERE active=1')]
    def import_csv(self):
        p=filedialog.askopenfilename(filetypes=[('CSV','*.csv')],parent=self)
        if not p:return
        try:
            with open(p,newline='',encoding='utf-8-sig') as f:
                for r in csv.DictReader(f):
                    if r.get('name'):self.s.q('INSERT INTO products(name,price,category,stock,barcode,cost) VALUES(?,?,?,?,?,?)',(r['name'],float(r.get('price') or 0),r.get('category') or 'General',float(r.get('stock') or 0),r.get('barcode') or '',float(r.get('cost') or 0)))
            self.s.c.commit();self.show('Products')
        except Exception as e:messagebox.showerror('Import failed',str(e),parent=self)
    def page_printers(self):
        ttk.Label(self.body,text='Printers & Receipt Themes',style='Title.TLabel').pack(anchor='w');ttk.Label(self.body,text='80mm Bluetooth / ESC-POS printer discovery, connection and automatic reconnect.',foreground='#64748b').pack(anchor='w',pady=8);card=ttk.LabelFrame(self.body,text='Printer',padding=16);card.pack(fill='x',pady=12);p=self.pm.status().get('printer') or {};ttk.Label(card,text=f"Saved: {p.get('name','None')}").pack(anchor='w');ttk.Label(card,text=f"Status: {'Connected' if self.pm.status()['connected'] else 'Not connected'}").pack(anchor='w',pady=3);ttk.Button(card,text='OPEN PRINTER SETTINGS / DISCOVER DEVICES',style='Primary.TButton',command=lambda:PrinterSettings(self,self.pm,BUSINESS)).pack(anchor='w',pady=8);ttk.Button(card,text='Reconnect Now',command=self.pm.auto_reconnect).pack(anchor='w')
    def page_reports(self):
        ttk.Label(self.body,text='Reports',style='Title.TLabel').pack(anchor='w');r=self.s.q("SELECT COUNT(*) n,COALESCE(SUM(total),0) total,COALESCE(SUM(CASE WHEN payment_status='Paid' THEN total ELSE 0 END),0) paid FROM sales WHERE date(created_at)=date('now','localtime')").fetchone();self.card('TODAY ORDERS',str(r['n']),f"Paid Rs. {r['paid']:,.2f}")
    def card(self,title,val,sub):
        f=ttk.LabelFrame(self.body,text=title,padding=20);f.pack(side='left',fill='x',expand=True,padx=8);ttk.Label(f,text=val,font=('Segoe UI',22,'bold')).pack();ttk.Label(f,text=sub).pack()
    def page_settings(self):
        ttk.Label(self.body,text='Settings',style='Title.TLabel').pack(anchor='w');ttk.Label(self.body,text=BUSINESS['name']).pack(anchor='w',pady=10);ttk.Label(self.body,text=BUSINESS['address']).pack(anchor='w');ttk.Label(self.body,text=BUSINESS['phone']).pack(anchor='w')
    def print_kitchen(self,inv,sid,typ,table,cid):
        try:
            items=[dict(x) for x in self.s.rows('SELECT product_name name,quantity qty,unit_price price FROM sale_items WHERE sale_id=?',(sid,))];self.pm.print_receipt(BUSINESS,inv,items,0,0,0,'KITCHEN',self.user['username'])
        except:pass
    def print_receipt(self,sid):
        r=self.s.q('SELECT * FROM sales WHERE id=?',(sid,)).fetchone();items=[dict(x) for x in self.s.rows('SELECT product_name name,quantity qty,unit_price price FROM sale_items WHERE sale_id=?',(sid,))]
        self.pm.print_receipt(BUSINESS,r['invoice_no'],items,r['subtotal'],r['tax'],r['total'],r['payment_method'],self.user['username'])

def main(): Login(Store()).mainloop()
