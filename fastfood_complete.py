import sqlite3
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox


def install(db):
    db.c.executescript('''
    CREATE TABLE IF NOT EXISTS categories(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE,active INTEGER DEFAULT 1);
    CREATE TABLE IF NOT EXISTS product_modifiers(id INTEGER PRIMARY KEY AUTOINCREMENT,product_id INTEGER,name TEXT,price REAL DEFAULT 0,active INTEGER DEFAULT 1);
    CREATE TABLE IF NOT EXISTS recipes(id INTEGER PRIMARY KEY AUTOINCREMENT,product_id INTEGER,ingredient_product_id INTEGER,qty REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS purchases(id INTEGER PRIMARY KEY AUTOINCREMENT,supplier_id INTEGER,invoice_no TEXT,subtotal REAL,total REAL,payment_method TEXT,status TEXT DEFAULT 'Received',created_at TEXT,user_id INTEGER);
    CREATE TABLE IF NOT EXISTS purchase_items(id INTEGER PRIMARY KEY AUTOINCREMENT,purchase_id INTEGER,product_id INTEGER,quantity REAL,unit_cost REAL,total REAL);
    CREATE TABLE IF NOT EXISTS sale_returns(id INTEGER PRIMARY KEY AUTOINCREMENT,sale_id INTEGER,amount REAL,reason TEXT,created_at TEXT,user_id INTEGER);
    CREATE TABLE IF NOT EXISTS sale_return_items(id INTEGER PRIMARY KEY AUTOINCREMENT,return_id INTEGER,sale_item_id INTEGER,quantity REAL,amount REAL);
    CREATE TABLE IF NOT EXISTS order_meta(sale_id INTEGER PRIMARY KEY,order_type TEXT DEFAULT 'Counter',table_no TEXT DEFAULT '',rider_id INTEGER,delivery_address TEXT DEFAULT '',delivery_fee REAL DEFAULT 0,notes TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY AUTOINCREMENT,sale_id INTEGER,method TEXT,amount REAL,reference TEXT,created_at TEXT,user_id INTEGER);
    ''')
    db.c.commit()


def patch(Main, db_class):
    old_nav, old_show = Main.build_nav, Main.show
    def nav(self):
        old_nav(self)
        try:
            canvas=self.body.master.winfo_children()[1]
            inner=canvas.winfo_children()[0]
            ttk.Button(inner,text='POS Sale',style='Accent.TButton',command=lambda:self.show('POS Sale')).pack(side='left',padx=3,pady=3)
            ttk.Button(inner,text='Purchases',command=lambda:self.show('Purchases')).pack(side='left',padx=3,pady=3)
            ttk.Button(inner,text='Returns',command=lambda:self.show('Returns')).pack(side='left',padx=3,pady=3)
            ttk.Button(inner,text='Recipes',command=lambda:self.show('Recipes')).pack(side='left',padx=3,pady=3)
        except Exception: pass
    def show(self,name):
        if name=='POS Sale': return pos_page(self)
        if name=='Purchases': return purchases_page(self)
        if name=='Returns': return returns_page(self)
        if name=='Recipes': return recipes_page(self)
        return old_show(self,name)
    Main.build_nav=nav; Main.show=show


def pos_page(self):
    self.clear(); ttk.Label(self.body,text='POS Sale',style='Title.TLabel').pack(anchor='w')
    outer=ttk.PanedWindow(self.body,orient='horizontal'); outer.pack(fill='both',expand=True,pady=8)
    left,right=ttk.Frame(outer,padding=8),ttk.Frame(outer,padding=8); outer.add(left,weight=3); outer.add(right,weight=2)
    search=tk.StringVar(); ttk.Label(left,text='Search menu / product').pack(anchor='w'); ttk.Entry(left,textvariable=search).pack(fill='x',pady=4)
    cols=('id','name','category','price','stock'); tree=self.table(left,cols,[],{'id':'ID','name':'Product','category':'Category','price':'Price','stock':'Stock'}); tree.configure(selectmode='browse')
    def reload(*_):
        for x in tree.get_children(): tree.delete(x)
        q=search.get().lower()
        for r in self.db.rows('products','WHERE active=1 ORDER BY category,name'):
            if q in f"{r['name']} {r['category']}".lower(): tree.insert('','end',iid=str(r['id']),values=(r['id'],r['name'],r['category'],f"{r['price']:,.2f}",r['stock']))
    search.trace_add('write',reload); reload()
    cart=[]
    ttk.Label(right,text='Current Order',font=('Segoe UI',14,'bold')).pack(anchor='w'); ct=self.table(right,('id','name','qty','price','total'),[],{'id':'ID','name':'Item','qty':'Qty','price':'Price','total':'Total'}); ct.configure(selectmode='browse')
    def refresh_cart():
        for x in ct.get_children():ct.delete(x)
        for i,x in enumerate(cart):ct.insert('','end',iid=str(i),values=(x['id'],x['name'],x['qty'],f"{x['price']:,.2f}",f"{x['qty']*x['price']:,.2f}"))
        sub=sum(x['qty']*x['price'] for x in cart); subvar.set(f"{sub:,.2f}"); totalvar.set(f"{max(0,sub-discvar.get()):,.2f}")
    def add(_=None):
        sel=tree.selection()
        if not sel:return
        r=self.db.c.execute('SELECT * FROM products WHERE id=?',(int(sel[0]),)).fetchone()
        if not r:return
        for x in cart:
            if x['id']==r['id']: x['qty']+=1; refresh_cart(); return
        cart.append({'id':r['id'],'name':r['name'],'price':r['price'],'qty':1}); refresh_cart()
    tree.bind('<Double-1>',add)
    ttk.Button(left,text='Add Selected',style='Accent.TButton',command=add).pack(anchor='e',pady=6)
    controls=ttk.Frame(right);controls.pack(fill='x',pady=6)
    order_type=tk.StringVar(value='Counter'); payment=tk.StringVar(value='Cash'); discvar=tk.DoubleVar(value=0); subvar=tk.StringVar(value='0.00'); totalvar=tk.StringVar(value='0.00');
    ttk.Label(controls,text='Order Type').grid(row=0,column=0,sticky='w'); ttk.Combobox(controls,textvariable=order_type,values=['Counter','Takeaway','Delivery','Dine-in'],state='readonly',width=14).grid(row=0,column=1,padx=4,pady=3)
    ttk.Label(controls,text='Payment').grid(row=1,column=0,sticky='w'); ttk.Combobox(controls,textvariable=payment,values=['Cash','Card','Other','Credit'],state='readonly',width=14).grid(row=1,column=1,padx=4,pady=3)
    ttk.Label(controls,text='Discount').grid(row=2,column=0,sticky='w'); ttk.Entry(controls,textvariable=discvar,width=16).grid(row=2,column=1,padx=4,pady=3)
    ttk.Label(right,text='Subtotal: Rs.').pack(anchor='e'); ttk.Label(right,textvariable=subvar,font=('Segoe UI',12,'bold')).pack(anchor='e'); ttk.Label(right,text='Total: Rs.').pack(anchor='e'); ttk.Label(right,textvariable=totalvar,font=('Segoe UI',18,'bold')).pack(anchor='e')
    def complete():
        if not cart:return messagebox.showwarning('Order','Add at least one product.',parent=self)
        sub=sum(x['qty']*x['price'] for x in cart); discount=max(0,discvar.get()); total=max(0,sub-discount)
        for x in cart:
            stock=self.db.c.execute('SELECT stock FROM products WHERE id=?',(x['id'],)).fetchone()[0]
            if stock < x['qty']: return messagebox.showerror('Stock',f"Insufficient stock for {x['name']}",parent=self)
        invoice='INV-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        now=datetime.now().isoformat(timespec='seconds')
        cur=self.db.c
        cur.execute('INSERT INTO sales(invoice_no,user_id,subtotal,tax,total,payment_method,created_at,status,discount) VALUES(?,?,?,?,?,?,?,?,?)',(invoice,self.user['id'],sub,0,total,payment.get(),now,'New',discount)); sid=cur.lastrowid
        for x in cart:
            line=x['qty']*x['price']; cur.execute('INSERT INTO sale_items(sale_id,product_id,product_name,quantity,unit_price,line_total) VALUES(?,?,?,?,?,?)',(sid,x['id'],x['name'],x['qty'],x['price'],line)); cur.execute('UPDATE products SET stock=stock-? WHERE id=?',(x['qty'],x['id']))
            try: cur.execute('INSERT INTO stock_movements(product_id,qty,movement_type,note,created_at,user_id) VALUES(?,?,?,?,?,?)',(x['id'],-x['qty'],'Sale',invoice,now,self.user['id']))
            except sqlite3.OperationalError: pass
        cur.execute('INSERT INTO order_meta(sale_id,order_type) VALUES(?,?)',(sid,order_type.get()))
        cur.execute('INSERT INTO payments(sale_id,method,amount,created_at,user_id) VALUES(?,?,?,?,?)',(sid,payment.get(),total,now,self.user['id']))
        cur.execute('UPDATE customers SET balance=balance+? WHERE id=(SELECT customer_id FROM sales WHERE id=?) AND ?="Credit"',(total,sid,payment.get()))
        cur.execute('UPDATE sales SET status="Preparing" WHERE id=?',(sid,))
        cur.connection.commit()
        try:
            from production import audit; audit(self.db,self.user,'Create Sale','sale',sid,invoice)
        except Exception: pass
        messagebox.showinfo('Sale Completed',f'{invoice}\nTotal: Rs. {total:,.2f}',parent=self); cart.clear();refresh_cart();reload()
    ttk.Button(right,text='COMPLETE SALE',style='Accent.TButton',command=complete).pack(fill='x',pady=12)
    ttk.Button(right,text='Clear Order',command=lambda:(cart.clear(),refresh_cart())).pack(fill='x')


def purchases_page(self):
    self.clear(); ttk.Label(self.body,text='Purchases / Stock Receiving',style='Title.TLabel').pack(anchor='w'); ttk.Button(self.body,text='New Purchase',style='Accent.TButton',command=lambda:purchase_dialog(self)).pack(anchor='w',pady=8)
    rows=[(r['id'],r['invoice_no'] or '',r['supplier_id'] or '',r['total'] or 0,r['payment_method'] or '',r['status'],r['created_at']) for r in self.db.rows('purchases','ORDER BY id DESC')]; self.table(self.body,('id','invoice','supplier','total','payment','status','date'),rows,{'id':'ID','invoice':'Invoice','supplier':'Supplier','total':'Total','payment':'Payment','status':'Status','date':'Date'})


def purchase_dialog(self):
    w=tk.Toplevel(self);w.title('New Purchase');w.geometry('620x500'); products=self.db.rows('products','WHERE active=1 ORDER BY name'); names=[r['name'] for r in products]; ids={r['name']:r['id'] for r in products}; costs={r['name']:r['price'] for r in products}; cart=[]; n=tk.StringVar();q=tk.DoubleVar(value=1);cost=tk.DoubleVar();
    ttk.Label(w,text='Product').pack(pady=4);ttk.Combobox(w,textvariable=n,values=names,state='readonly').pack();ttk.Label(w,text='Quantity').pack();ttk.Entry(w,textvariable=q).pack();ttk.Label(w,text='Unit Cost').pack();ttk.Entry(w,textvariable=cost).pack();t=ttk.Treeview(w,columns=('name','qty','cost'),show='headings');[t.heading(c,text=c.title()) for c in ('name','qty','cost')];t.pack(fill='both',expand=True,pady=8)
    def add():
        if n.get():cart.append((ids[n.get()],n.get(),q.get(),cost.get() or costs[n.get()]));t.insert('','end',values=(n.get(),q.get(),cost.get() or costs[n.get()]))
    ttk.Button(w,text='Add Item',command=add).pack();
    def save():
        if not cart:return
        total=sum(q*c for _,_,q,c in cart);now=datetime.now().isoformat(timespec='seconds');self.db.c.execute('INSERT INTO purchases(invoice_no,total,subtotal,payment_method,created_at,user_id) VALUES(?,?,?,?,?,?)',('PUR-'+datetime.now().strftime('%Y%m%d%H%M%S'),total,total,'Cash',now,self.user['id']));pid=self.db.c.lastrowid
        for prod,_,qty,c in cart:self.db.c.execute('INSERT INTO purchase_items(purchase_id,product_id,quantity,unit_cost,total) VALUES(?,?,?,?,?)',(pid,prod,qty,c,qty*c));self.db.c.execute('UPDATE products SET stock=stock+? WHERE id=?',(qty,prod))
        self.db.c.commit();w.destroy();self.show('Purchases')
    ttk.Button(w,text='Save Purchase',style='Accent.TButton',command=save).pack(pady=8)


def returns_page(self):
    self.clear();ttk.Label(self.body,text='Sales Returns / Refunds',style='Title.TLabel').pack(anchor='w');
    rows=[(r['id'],r['invoice_no'],r['total'],r['payment_method'],r['created_at']) for r in self.db.rows('sales','ORDER BY id DESC LIMIT 200')];t=self.table(self.body,('id','invoice','total','payment','date'),rows,{'id':'ID','invoice':'Invoice','total':'Total','payment':'Payment','date':'Date'});t.bind('<Double-1>',lambda e:return_dialog(self,t.selection()))


def return_dialog(self,sel):
    if not sel:return
    sid=int(sel[0]); sale=self.db.c.execute('SELECT * FROM sales WHERE id=?',(sid,)).fetchone(); items=self.db.c.execute('SELECT * FROM sale_items WHERE sale_id=?',(sid,)).fetchall();w=tk.Toplevel(self);w.title('Refund / Return');rows=[]
    for r in items:
        v=tk.DoubleVar(value=0);ttk.Label(w,text=f"{r['product_name']} (sold {r['quantity']})").pack(anchor='w',padx=15);ttk.Entry(w,textvariable=v).pack(anchor='w',padx=15);rows.append((r,v))
    reason=tk.StringVar();ttk.Label(w,text='Reason').pack(anchor='w',padx=15);ttk.Entry(w,textvariable=reason).pack(fill='x',padx=15)
    def save():
        now=datetime.now().isoformat(timespec='seconds');amount=0;items_ret=[];cur=self.db.c
        cur.execute('INSERT INTO sale_returns(sale_id,amount,reason,created_at,user_id) VALUES(?,?,?,?,?)',(sid,0,reason.get(),now,self.user['id']));rid=cur.lastrowid
        for r,v in rows:
            qty=max(0,min(v.get(),r['quantity']));amt=qty*r['unit_price'];
            if qty: amount+=amt;items_ret.append((r,qty,amt));cur.execute('INSERT INTO sale_return_items(return_id,sale_item_id,quantity,amount) VALUES(?,?,?,?)',(rid,r['id'],qty,amt));cur.execute('UPDATE products SET stock=stock+? WHERE id=?',(qty,r['product_id']))
        cur.execute('UPDATE sale_returns SET amount=? WHERE id=?',(amount,rid));cur.execute('UPDATE sales SET total=MAX(0,total-?) WHERE id=?',(amount,sid));cur.commit();w.destroy();self.show('Returns')
    ttk.Button(w,text='Process Refund',style='Accent.TButton',command=save).pack(pady=12)


def recipes_page(self):
    self.clear();ttk.Label(self.body,text='Recipes & Food Cost',style='Title.TLabel').pack(anchor='w');ttk.Label(self.body,text='Define ingredient usage per menu item for future automatic ingredient costing.',style='Subtitle.TLabel').pack(anchor='w',pady=6)
    rows=[]
    for r in self.db.rows('recipes','ORDER BY product_id'): rows.append((r['id'],r['product_id'],r['ingredient_product_id'],r['qty']))
    self.table(self.body,('id','product','ingredient','qty'),rows,{'id':'ID','product':'Menu Product','ingredient':'Ingredient Product','qty':'Qty'})
