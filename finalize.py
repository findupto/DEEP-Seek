import sqlite3, csv
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

def install(db):
    db.c.executescript('''
    CREATE TABLE IF NOT EXISTS sale_payment_splits(id INTEGER PRIMARY KEY AUTOINCREMENT,sale_id INTEGER,method TEXT,amount REAL,reference TEXT,created_at TEXT,user_id INTEGER);
    CREATE TABLE IF NOT EXISTS delivery_addresses(id INTEGER PRIMARY KEY AUTOINCREMENT,customer_id INTEGER,address TEXT,active INTEGER DEFAULT 1);
    ''');db.c.commit()

def patch(Main):
    old=Main.show
    def show(self,name):
        if name=='POS Sale':return sale_page(self)
        if name=='Payment History':return payment_history(self)
        return old(self,name)
    Main.show=show

def sale_page(self):
    self.clear();ttk.Label(self.body,text='POS Sale',style='Title.TLabel').pack(anchor='w');outer=ttk.PanedWindow(self.body,orient='horizontal');outer.pack(fill='both',expand=True,pady=8);left,right=ttk.Frame(outer,padding=8),ttk.Frame(outer,padding=8);outer.add(left,weight=3);outer.add(right,weight=2)
    q=tk.StringVar();ttk.Entry(left,textvariable=q).pack(fill='x',pady=4);tree=self.table(left,('id','name','barcode','category','price','stock'),[],{'id':'ID','name':'Product','barcode':'Barcode','category':'Category','price':'Price','stock':'Stock'});tree.configure(selectmode='browse')
    def load(*_):
        for x in tree.get_children():tree.delete(x)
        z=q.get().lower()
        for r in self.db.rows('products','WHERE active=1 ORDER BY category,name'):
            if z in f"{r['name']} {r['category']} {r['barcode'] or ''} {r['id']}".lower():tree.insert('','end',iid=str(r['id']),values=(r['id'],r['name'],r['barcode'] or '',r['category'],r['price'],r['stock']))
    q.trace_add('write',load);load();cart=[]
    ttk.Button(left,text='Add Selected',style='Accent.TButton',command=lambda:add()).pack(anchor='e',pady=5)
    ttk.Label(right,text='Current Order',font=('Segoe UI',14,'bold')).pack(anchor='w');ct=self.table(right,('id','name','qty','price','total'),[],{'id':'ID','name':'Item','qty':'Qty','price':'Price','total':'Total'});ct.configure(selectmode='browse')
    customer=tk.StringVar();customers=self.db.rows('customers','WHERE active=1 ORDER BY name');cn={f"{r['name']} | {r['phone']}":r['id'] for r in customers};order_type=tk.StringVar(value='Counter');discount=tk.DoubleVar(value=0);notes=tk.StringVar();address=tk.StringVar();paymethod=tk.StringVar(value='Cash');
    f=ttk.Frame(right);f.pack(fill='x',pady=6);ttk.Label(f,text='Customer').grid(row=0,column=0,sticky='w');ttk.Combobox(f,textvariable=customer,values=list(cn),width=25).grid(row=0,column=1,pady=2);ttk.Label(f,text='Order').grid(row=1,column=0);ttk.Combobox(f,textvariable=order_type,values=['Counter','Takeaway','Dine-in','Delivery'],state='readonly',width=25).grid(row=1,column=1);ttk.Label(f,text='Delivery Address').grid(row=2,column=0);ttk.Entry(f,textvariable=address,width=27).grid(row=2,column=1);ttk.Label(f,text='Discount').grid(row=3,column=0);ttk.Entry(f,textvariable=discount,width=27).grid(row=3,column=1);ttk.Label(f,text='Notes').grid(row=4,column=0);ttk.Entry(f,textvariable=notes,width=27).grid(row=4,column=1)
    sub=tk.StringVar(value='0.00');total=tk.StringVar(value='0.00')
    def refresh():
        for x in ct.get_children():ct.delete(x)
        for i,x in enumerate(cart):ct.insert('','end',iid=str(i),values=(x['id'],x['name'],x['qty'],x['price'],x['qty']*x['price']))
        s=sum(x['qty']*x['price'] for x in cart);sub.set(f'{s:,.2f}');total.set(f'{max(0,s-max(0,discount.get())):,.2f}')
    def add():
        sel=tree.selection()
        if not sel:return
        r=self.db.c.execute('SELECT * FROM products WHERE id=?',(int(sel[0]),)).fetchone()
        if not r:return
        for x in cart:
            if x['id']==r['id']:x['qty']+=1;refresh();return
        cart.append({'id':r['id'],'name':r['name'],'price':r['price'],'qty':1});refresh()
    tree.bind('<Double-1>',lambda e:add())
    ttk.Label(right,textvariable=sub).pack(anchor='e');ttk.Label(right,textvariable=total,font=('Segoe UI',18,'bold')).pack(anchor='e')
    def checkout():
        if not cart:return messagebox.showwarning('Order','Add products first',parent=self)
        if order_type.get()=='Delivery' and not address.get().strip():return messagebox.showwarning('Delivery','Enter delivery address',parent=self)
        s=sum(x['qty']*x['price'] for x in cart);d=max(0,discount.get());tot=max(0,s-d);now=datetime.now().isoformat(timespec='seconds');cur=self.db.c
        for x in cart:
            st=cur.execute('SELECT stock FROM products WHERE id=?',(x['id'],)).fetchone()['stock']
            if st<x['qty']:return messagebox.showerror('Stock',f"Insufficient stock: {x['name']}",parent=self)
        cid=cn.get(customer.get());invoice='INV-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        cur.execute('INSERT INTO sales(invoice_no,user_id,customer_id,subtotal,tax,total,payment_method,created_at,status,discount) VALUES(?,?,?,?,?,?,?,?,?,?)',(invoice,self.user['id'],cid,s,0,tot,paymethod.get(),now,'New',d));sid=cur.lastrowid
        for x in cart:
            cur.execute('INSERT INTO sale_items(sale_id,product_id,product_name,quantity,unit_price,line_total) VALUES(?,?,?,?,?,?)',(sid,x['id'],x['name'],x['qty'],x['price'],x['qty']*x['price']));cur.execute('UPDATE products SET stock=stock-? WHERE id=?',(x['qty'],x['id']))
        cur.execute('INSERT OR REPLACE INTO order_meta(sale_id,order_type,delivery_address,notes) VALUES(?,?,?,?)',(sid,order_type.get(),address.get(),notes.get()))
        if order_type.get()=='Delivery':cur.execute('INSERT OR REPLACE INTO deliveries(sale_id,status,assigned_at) VALUES(?,"Pending",NULL)',(sid,))
        if paymethod.get()=='Credit' and cid:cur.execute('UPDATE customers SET balance=balance+? WHERE id=?',(tot,cid));cur.execute('INSERT INTO party_transactions(party_type,party_id,txn_type,amount,note,created_at,user_id) VALUES(?,?,?,?,?,?,?)',('Customer',cid,'Credit',tot,invoice,now,self.user['id']))
        cur.execute('INSERT INTO payments(sale_id,method,amount,created_at,user_id) VALUES(?,?,?,?,?)',(sid,paymethod.get(),tot,now,self.user['id']))
        cur.execute('UPDATE sales SET status="New" WHERE id=?',(sid,));cur.commit();
        try:
            from production import audit;audit(self.db,self.user,'Create Sale','sale',sid,invoice)
        except Exception:pass
        messagebox.showinfo('Sale Completed',f'{invoice}\nTotal: Rs. {tot:,.2f}',parent=self);self.show('POS Sale')
    ttk.Button(right,text='CHECKOUT',style='Accent.TButton',command=checkout).pack(fill='x',pady=10);ttk.Button(right,text='Split Payment / Pay',command=lambda:split_payment_dialog(self,cart,cn.get(customer.get()),order_type.get(),address.get(),notes.get(),discount.get())).pack(fill='x')

def split_payment_dialog(self,cart,customer_id,order_type,address,notes,discount):
    if not cart:return
    total=max(0,sum(x['qty']*x['price'] for x in cart)-max(0,discount));w=tk.Toplevel(self);w.title('Split Payment');ttk.Label(w,text=f'Total: Rs. {total:,.2f}',font=('Segoe UI',14,'bold')).pack(pady=8);rows=[];f=ttk.Frame(w);f.pack(fill='x');method=tk.StringVar(value='Cash');amt=tk.DoubleVar();ref=tk.StringVar();ttk.Combobox(f,textvariable=method,values=['Cash','Card','Bank','Other'],state='readonly').grid(row=0,column=0);ttk.Entry(f,textvariable=amt).grid(row=0,column=1);ttk.Entry(f,textvariable=ref,width=20).grid(row=0,column=2);t=ttk.Treeview(w,columns=('method','amount','ref'),show='headings');[t.heading(c,text=c.title()) for c in ('method','amount','ref')];t.pack(fill='both',expand=True,pady=8)
    def add():
        a=amt.get();used=sum(x[1] for x in rows)
        if a<=0 or used+a>total+0.001:return
        rows.append((method.get(),a,ref.get()));t.insert('','end',values=(method.get(),a,ref.get()));amt.set(0)
    ttk.Button(w,text='Add Payment',command=add).pack()
    def save():
        if abs(sum(x[1] for x in rows)-total)>0.01:return messagebox.showwarning('Payment',f'Remaining: Rs. {total-sum(x[1] for x in rows):,.2f}',parent=w)
        now=datetime.now().isoformat(timespec='seconds');cur=self.db.c;invoice='INV-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f');cid=customer_id
        cur.execute('INSERT INTO sales(invoice_no,user_id,customer_id,subtotal,tax,total,payment_method,created_at,status,discount) VALUES(?,?,?,?,?,?,?,?,?,?)',(invoice,self.user['id'],cid,total+discount,0,total,'Split',now,'New',discount));sid=cur.lastrowid
        for x in cart:cur.execute('INSERT INTO sale_items(sale_id,product_id,product_name,quantity,unit_price,line_total) VALUES(?,?,?,?,?,?)',(sid,x['id'],x['name'],x['qty'],x['price'],x['qty']*x['price']));cur.execute('UPDATE products SET stock=stock-? WHERE id=?',(x['qty'],x['id']))
        cur.execute('INSERT INTO order_meta(sale_id,order_type,delivery_address,notes) VALUES(?,?,?,?)',(sid,order_type,address,notes));
        if order_type=='Delivery':cur.execute('INSERT INTO deliveries(sale_id,status) VALUES(?,"Pending")',(sid,))
        for m,a,r in rows:cur.execute('INSERT INTO sale_payment_splits(sale_id,method,amount,reference,created_at,user_id) VALUES(?,?,?,?,?,?)',(sid,m,a,r,now,self.user['id']));cur.execute('INSERT INTO payments(sale_id,method,amount,reference,created_at,user_id) VALUES(?,?,?,?,?,?)',(sid,m,a,r,now,self.user['id']))
        if cid and any(m=='Credit' for m,_,_ in rows):cur.execute('UPDATE customers SET balance=balance+? WHERE id=?',(sum(a for m,a,_ in rows if m=='Credit'),cid))
        cur.commit();w.destroy();self.show('POS Sale')
    ttk.Button(w,text='Complete Split Payment',style='Accent.TButton',command=save).pack(pady=8)

def payment_history(self):
    self.clear();ttk.Label(self.body,text='Payment History',style='Title.TLabel').pack(anchor='w');rows=self.db.rows('payments','ORDER BY id DESC');self.table(self.body,('id','sale','method','amount','reference','date'),[(r['id'],r['sale_id'],r['method'],r['amount'],r['reference'] or '',r['created_at']) for r in rows],{'id':'ID','sale':'Sale','method':'Method','amount':'Amount','reference':'Reference','date':'Date'})
