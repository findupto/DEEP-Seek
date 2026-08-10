import csv
import hashlib
import sqlite3
import tkinter as tk
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

DB = "pos.db"
BUSINESS = {"name": "MK Pizza & Ice Bar", "address": "Collage Road Abbas Chowk, Bhakkar, Pakistan", "phone": "0316 9700025", "currency": "Rs.", "tax": 0.0}


def hp(value):
    return hashlib.sha256(value.encode()).hexdigest()


class DB:
    def __init__(self, path=DB):
        self.c = sqlite3.connect(path)
        self.c.row_factory = sqlite3.Row
        self.init()

    def init(self):
        self.c.executescript('''
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, role TEXT, password_hash TEXT, active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, price REAL NOT NULL, category TEXT DEFAULT 'General', stock REAL DEFAULT 0, active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS customers(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, phone TEXT DEFAULT '', address TEXT DEFAULT '', balance REAL DEFAULT 0, active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS suppliers(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, phone TEXT DEFAULT '', address TEXT DEFAULT '', balance REAL DEFAULT 0, active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS party_transactions(id INTEGER PRIMARY KEY AUTOINCREMENT, party_type TEXT NOT NULL, party_id INTEGER NOT NULL, txn_type TEXT NOT NULL, amount REAL NOT NULL, note TEXT DEFAULT '', created_at TEXT NOT NULL, user_id INTEGER);
        CREATE TABLE IF NOT EXISTS sales(id INTEGER PRIMARY KEY AUTOINCREMENT, invoice_no TEXT UNIQUE, user_id INTEGER, customer_id INTEGER, subtotal REAL, tax REAL, total REAL, payment_method TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS sale_items(id INTEGER PRIMARY KEY AUTOINCREMENT, sale_id INTEGER, product_id INTEGER, product_name TEXT, quantity REAL, unit_price REAL, line_total REAL);
        CREATE TABLE IF NOT EXISTS staff(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, phone TEXT DEFAULT '', role TEXT DEFAULT 'Staff', salary REAL DEFAULT 0, active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        ''')
        for u, r in [('admin','Admin'),('owner','Owner'),('cashier','Cashier'),('accountant','Accountant')]:
            self.c.execute('INSERT OR IGNORE INTO users(username,role,password_hash) VALUES(?,?,?)',(u,r,hp('0099')))
        defaults=[('Zinger Burger',350,'Burgers'),('Chicken Burger',300,'Burgers'),('Small Pizza',550,'Pizza'),('Medium Pizza',900,'Pizza'),('Large Pizza',1250,'Pizza'),('Fries',180,'Sides'),('Chicken Shawarma',250,'Shawarma'),('Cold Drink',100,'Drinks')]
        if self.c.execute('SELECT COUNT(*) FROM products').fetchone()[0] == 0:
            self.c.executemany('INSERT INTO products(name,price,category) VALUES(?,?,?)',defaults)
        self.c.commit()

    def login(self,u,p):
        return self.c.execute('SELECT * FROM users WHERE username=? AND password_hash=? AND active=1',(u.strip(),hp(p))).fetchone()

    def rows(self, table, where='', args=()):
        return self.c.execute(f'SELECT * FROM {table} {where}',args).fetchall()

    def party(self, typ):
        return self.rows('customers' if typ=='Customer' else 'suppliers','WHERE active=1 ORDER BY name')

    def party_txns(self, typ, pid):
        return self.rows('party_transactions','WHERE party_type=? AND party_id=? ORDER BY id DESC',(typ,pid))

    def add_txn(self, typ, pid, kind, amount, note, uid):
        table='customers' if typ=='Customer' else 'suppliers'
        sign = 1 if kind in ('Due','Credit') else -1
        self.c.execute(f'UPDATE {table} SET balance=balance+? WHERE id=?',(sign*amount,pid))
        self.c.execute('INSERT INTO party_transactions(party_type,party_id,txn_type,amount,note,created_at,user_id) VALUES(?,?,?,?,?,?,?)',(typ,pid,kind,amount,note,datetime.now().isoformat(timespec='seconds'),uid))
        self.c.commit()

    def save_party(self, typ, name, phone, address, pid=None):
        table='customers' if typ=='Customer' else 'suppliers'
        if pid: self.c.execute(f'UPDATE {table} SET name=?,phone=?,address=? WHERE id=?',(name,phone,address,pid))
        else: self.c.execute(f'INSERT INTO {table}(name,phone,address) VALUES(?,?,?)',(name,phone,address))
        self.c.commit()

    def save_product(self, name, price, category, stock, pid=None):
        if pid: self.c.execute('UPDATE products SET name=?,price=?,category=?,stock=? WHERE id=?',(name,price,category,stock,pid))
        else: self.c.execute('INSERT INTO products(name,price,category,stock) VALUES(?,?,?,?)',(name,price,category,stock))
        self.c.commit()

    def delete_products(self, ids):
        self.c.executemany('UPDATE products SET active=0 WHERE id=?',[(x,) for x in ids]); self.c.commit()

    def export_products(self, path):
        rows=self.rows('products','WHERE active=1 ORDER BY id')
        with open(path,'w',newline='',encoding='utf-8-sig') as f:
            w=csv.writer(f); w.writerow(['id','name','price','category','stock'])
            for r in rows: w.writerow([r['id'],r['name'],r['price'],r['category'],r['stock']])

    def import_products(self,path):
        with open(path,newline='',encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                if not r.get('name'): continue
                self.save_product(r['name'],float(r.get('price') or 0),r.get('category') or 'General',float(r.get('stock') or 0))

    def stats(self):
        sales=self.c.execute("SELECT COUNT(*) n,COALESCE(SUM(total),0) total FROM sales WHERE date(created_at)=date('now','localtime')").fetchone()
        customers=self.c.execute('SELECT COUNT(*) n,COALESCE(SUM(balance),0) b FROM customers WHERE active=1').fetchone()
        suppliers=self.c.execute('SELECT COUNT(*) n,COALESCE(SUM(balance),0) b FROM suppliers WHERE active=1').fetchone()
        products=self.c.execute('SELECT COUNT(*) n,COALESCE(SUM(stock),0) stock FROM products WHERE active=1').fetchone()
        return sales,customers,suppliers,products


class Login(tk.Tk):
    def __init__(self, db):
        super().__init__(); self.db=db; self.title('MK Pizza & Ice Bar - Login'); self.geometry('420x300'); self.resizable(False,False)
        ttk.Label(self,text=BUSINESS['name'],font=('Segoe UI',20,'bold')).pack(pady=(35,4)); ttk.Label(self,text='POS Management System').pack(pady=(0,20))
        f=ttk.Frame(self); f.pack(fill='x',padx=45); ttk.Label(f,text='Username').grid(row=0,column=0,pady=7,sticky='w'); self.u=ttk.Entry(f); self.u.grid(row=0,column=1,sticky='ew'); ttk.Label(f,text='Password').grid(row=1,column=0,pady=7,sticky='w'); self.p=ttk.Entry(f,show='*'); self.p.grid(row=1,column=1,sticky='ew'); f.columnconfigure(1,weight=1)
        ttk.Button(self,text='Login',command=self.go).pack(pady=20); self.p.bind('<Return>',lambda e:self.go()); self.u.focus()
    def go(self):
        user=self.db.login(self.u.get(),self.p.get())
        if not user: messagebox.showerror('Login failed','Invalid username or password'); return
        self.destroy(); Main(self.db,user).mainloop()


class Main(tk.Tk):
    def __init__(self,db,user):
        super().__init__(); self.db=db; self.user=user; self.title(BUSINESS['name']+' - POS'); self.geometry('1280x760'); self.minsize(1050,650)
        self.build_nav(); self.show('Dashboard')

    def build_nav(self):
        top=ttk.Frame(self,padding=10); top.pack(fill='x'); ttk.Label(top,text=BUSINESS['name'],font=('Segoe UI',18,'bold')).pack(side='left'); ttk.Label(top,text=f"{self.user['role']} | {self.user['username']}").pack(side='right')
        nav=ttk.Frame(self,padding=(10,0,10,8)); nav.pack(fill='x')
        names=['Dashboard','Customers','Suppliers','Products','Analytics','Stats','Staff','Counter Persons','Riders','Kitchen','Settings']
        for n in names: ttk.Button(nav,text=n,command=lambda x=n:self.show(x)).pack(side='left',padx=2)
        self.body=ttk.Frame(self,padding=10); self.body.pack(fill='both',expand=True)

    def clear(self):
        for w in self.body.winfo_children(): w.destroy()

    def show(self,name):
        self.clear(); getattr(self,'page_'+name.lower().replace(' ','_'))()

    def table(self,parent,cols,rows,head=None):
        t=ttk.Treeview(parent,columns=cols,show='headings',selectmode='extended')
        for c in cols: t.heading(c,text=(head or {}).get(c,c.title())); t.column(c,width=140)
        for r in rows: t.insert('', 'end', iid=str(r[0]), values=r[1:])
        t.pack(fill='both',expand=True); return t

    def filters(self,parent,callback,fields=('Search',)):
        f=ttk.Frame(parent); f.pack(fill='x',pady=(0,8)); vars=[]
        for label in fields:
            ttk.Label(f,text=label).pack(side='left'); v=tk.StringVar(); e=ttk.Entry(f,textvariable=v,width=20); e.pack(side='left',padx=5); e.bind('<KeyRelease>',lambda e:callback()); vars.append(v)
        return vars

    def page_dashboard(self):
        ttk.Label(self.body,text='Dashboard',font=('Segoe UI',22,'bold')).pack(anchor='w'); s=self.db.stats(); cards=[('Today Sales',f"{s[0]['n']} / {BUSINESS['currency']} {s[0]['total']:,.0f}"),('Customer Balance',f"{BUSINESS['currency']} {s[1]['b']:,.0f}"),('Supplier Balance',f"{BUSINESS['currency']} {s[2]['b']:,.0f}"),('Products / Stock',f"{s[3]['n']} / {s[3]['stock']:,.0f}")]
        row=ttk.Frame(self.body); row.pack(fill='x',pady=20)
        for title,val in cards: b=ttk.LabelFrame(row,text=title,padding=20); b.pack(side='left',fill='x',expand=True,padx=5); ttk.Label(b,text=val,font=('Segoe UI',16,'bold')).pack()
        ttk.Label(self.body,text='Modules: Customers, Suppliers, Products, Analytics, Stats, Staff, Counter Persons, Riders, Kitchen and Settings.').pack(anchor='w',pady=15)

    def party_page(self,typ):
        ttk.Label(self.body,text=typ+'s',font=('Segoe UI',20,'bold')).pack(anchor='w'); search=self.filters(self.body,lambda:self.load_party(t,search[0].get(),typ),('Search',)); bar=ttk.Frame(self.body); bar.pack(fill='x',pady=4)
        ttk.Button(bar,text='Add',command=lambda:self.edit_party(typ)).pack(side='left'); ttk.Button(bar,text='Edit',command=lambda:self.edit_party(typ,t.selection())).pack(side='left',padx=5); ttk.Button(bar,text='Transaction',command=lambda:self.party_transaction(typ,t.selection())).pack(side='left')
        ttk.Label(bar,text='Double-click a party for full transaction history').pack(side='right'); t=self.table(self.body,('id','name','phone','balance'),[],{'id':'ID','name':'Name','phone':'Phone','balance':'Balance'}); t.bind('<Double-1>',lambda e:self.history_party(typ,t.selection())); self.load_party(t,'',typ)
    def load_party(self,t,q,typ):
        for x in t.get_children(): t.delete(x)
        for r in self.db.party(typ):
            if q.lower() in f"{r['name']} {r['phone']} {r['address']}".lower(): t.insert('','end',iid=str(r['id']),values=(r['id'],r['name'],r['phone'],f"{BUSINESS['currency']} {r['balance']:,.2f}"))
    def page_customers(self): self.party_page('Customer')
    def page_suppliers(self): self.party_page('Supplier')
    def edit_party(self,typ,sel=()):
        pid=int(sel[0]) if sel else None; old=next((r for r in self.db.party(typ) if r['id']==pid),None); w=tk.Toplevel(self); w.title('Edit '+typ); w.transient(self)
        vals=[]
        for lab,key in [('Name','name'),('Phone','phone'),('Address','address')]: ttk.Label(w,text=lab).pack(anchor='w',padx=15,pady=(10,2)); v=tk.StringVar(value=old[key] if old else ''); ttk.Entry(w,textvariable=v,width=45).pack(padx=15); vals.append(v)
        ttk.Button(w,text='Save',command=lambda:(self.db.save_party(typ,*[v.get() for v in vals],pid),w.destroy(),self.show(typ+'s'))).pack(pady=15)
    def party_transaction(self,typ,sel):
        if not sel:return
        pid=int(sel[0]); w=tk.Toplevel(self); w.title(typ+' Transaction'); ttk.Label(w,text='Due/Credit increases balance; Advance/Payment reduces it').pack(pady=8); kind=tk.StringVar(value='Payment'); ttk.Combobox(w,textvariable=kind,values=['Due','Credit','Advance','Payment'],state='readonly').pack(); a=tk.DoubleVar(); ttk.Entry(w,textvariable=a).pack(pady=5); note=tk.StringVar(); ttk.Entry(w,textvariable=note,width=40).pack(pady=5); ttk.Button(w,text='Save',command=lambda:(self.db.add_txn(typ,pid,kind.get(),a.get(),note.get(),self.user['id']),w.destroy(),self.show(typ+'s'))).pack(pady=8)
    def history_party(self,typ,sel):
        if not sel:return
        pid=int(sel[0]); p=next(r for r in self.db.party(typ) if r['id']==pid); w=tk.Toplevel(self); w.title(f"{p['name']} - Transaction History"); w.geometry('800x500'); ttk.Label(w,text=f"{p['name']} | Balance: {BUSINESS['currency']} {p['balance']:,.2f}",font=('Segoe UI',14,'bold')).pack(pady=8); t=self.table(w,('id','type','amount','note','date'),[(r['id'],r['txn_type'],f"{BUSINESS['currency']} {r['amount']:,.2f}",r['note'],r['created_at']) for r in self.db.party_txns(typ,pid)],{'id':'ID','type':'Type','amount':'Amount','note':'Note','date':'Date'})

    def page_products(self):
        ttk.Label(self.body,text='Products',font=('Segoe UI',20,'bold')).pack(anchor='w'); sv=self.filters(self.body,lambda:self.load_products(t,sv[0].get()),('Search',)); bar=ttk.Frame(self.body); bar.pack(fill='x',pady=4); ttk.Button(bar,text='Add',command=lambda:self.edit_product()).pack(side='left'); ttk.Button(bar,text='Edit',command=lambda:self.edit_product(t.selection())).pack(side='left',padx=5); ttk.Button(bar,text='Delete Selected',command=lambda:self.delete_products(t.selection())).pack(side='left'); ttk.Button(bar,text='Upload CSV',command=self.import_products).pack(side='left',padx=5); ttk.Button(bar,text='Download CSV',command=self.export_products).pack(side='left'); t=self.table(self.body,('id','name','category','price','stock'),[],{'id':'ID','name':'Name','category':'Category','price':'Price','stock':'Stock'}); t.bind('<Double-1>',lambda e:self.edit_product(t.selection())); self.load_products(t,'')
    def load_products(self,t,q):
        for x in t.get_children():t.delete(x)
        for r in self.db.rows('products','WHERE active=1 ORDER BY category,name'):
            if q.lower() in f"{r['name']} {r['category']}".lower():t.insert('','end',iid=str(r['id']),values=(r['id'],r['name'],r['category'],f"{BUSINESS['currency']} {r['price']:,.2f}",r['stock']))
    def edit_product(self,sel=()):
        pid=int(sel[0]) if sel else None; old=next((r for r in self.db.rows('products','WHERE id=?',(pid,)),None),None); w=tk.Toplevel(self); w.title('Product'); vs=[]
        for lab,key in [('Name','name'),('Price','price'),('Category','category'),('Stock','stock')]: ttk.Label(w,text=lab).pack(anchor='w',padx=15,pady=(8,2));v=tk.StringVar(value=str(old[key]) if old else '');ttk.Entry(w,textvariable=v,width=40).pack(padx=15);vs.append(v)
        def save():
            try:self.db.save_product(vs[0].get(),float(vs[1].get()),vs[2].get() or 'General',float(vs[3].get() or 0),pid);w.destroy();self.show('Products')
            except ValueError:messagebox.showerror('Invalid','Price and stock must be numbers',parent=w)
        ttk.Button(w,text='Save',command=save).pack(pady=15)
    def delete_products(self,sel):
        if sel and messagebox.askyesno('Confirm','Delete selected products?'):self.db.delete_products([int(x) for x in sel]);self.show('Products')
    def import_products(self):
        p=filedialog.askopenfilename(filetypes=[('CSV','*.csv')]);
        if p:self.db.import_products(p);self.show('Products')
    def export_products(self):
        p=filedialog.asksaveasfilename(defaultextension='.csv',filetypes=[('CSV','*.csv')]);
        if p:self.db.export_products(p);messagebox.showinfo('Exported','Products exported successfully')

    def page_analytics(self):
        ttk.Label(self.body,text='Analytics',font=('Segoe UI',20,'bold')).pack(anchor='w'); s=self.db.c.execute("SELECT date(created_at) d,COUNT(*) n,COALESCE(SUM(total),0) total FROM sales GROUP BY date(created_at) ORDER BY d DESC LIMIT 30").fetchall(); self.table(self.body,('date','orders','sales'),[(r['d'],r['n'],f"{BUSINESS['currency']} {r['total']:,.2f}") for r in s],{'date':'Date','orders':'Orders','sales':'Sales'})
    def page_stats(self):
        ttk.Label(self.body,text='Stats',font=('Segoe UI',20,'bold')).pack(anchor='w'); s=self.db.stats(); lines=[('Today Orders',s[0]['n']),('Today Sales',s[0]['total']),('Customer Accounts',s[1]['n']),('Customer Balance',s[1]['b']),('Supplier Accounts',s[2]['n']),('Supplier Balance',s[2]['b']),('Active Products',s[3]['n']),('Stock Units',s[3]['stock'])]; self.table(self.body,('metric','value'),lines,{'metric':'Metric','value':'Value'})
    def simple_staff(self,role):
        ttk.Label(self.body,text=role,font=('Segoe UI',20,'bold')).pack(anchor='w'); q=self.filters(self.body,lambda:self.load_staff(t,q[0].get(),role),('Search',)); ttk.Button(self.body,text='Add',command=lambda:self.edit_staff(role)).pack(anchor='w',pady=5); t=self.table(self.body,('id','name','phone','role','salary'),[],{'id':'ID','name':'Name','phone':'Phone','role':'Role','salary':'Salary'});self.load_staff(t,'',role)
    def load_staff(self,t,q,role):
        for x in t.get_children():t.delete(x)
        for r in self.db.rows('staff','WHERE active=1 AND role=? ORDER BY name',(role,)):
            if q.lower() in f"{r['name']} {r['phone']}".lower():t.insert('','end',iid=str(r['id']),values=(r['id'],r['name'],r['phone'],r['role'],f"{BUSINESS['currency']} {r['salary']:,.2f}"))
    def edit_staff(self,role):
        w=tk.Toplevel(self);w.title('Add '+role);vs=[]
        for lab in ['Name','Phone','Salary']:
            ttk.Label(w,text=lab).pack(anchor='w',padx=15,pady=(8,2));v=tk.StringVar();ttk.Entry(w,textvariable=v,width=40).pack(padx=15);vs.append(v)
        ttk.Button(w,text='Save',command=lambda:(self.db.c.execute('INSERT INTO staff(name,phone,role,salary) VALUES(?,?,?,?)',(vs[0].get(),vs[1].get(),role,float(vs[2].get() or 0))),self.db.c.commit(),w.destroy(),self.show(role))).pack(pady=15)
    def page_staff(self):self.simple_staff('Staff')
    def page_counter_persons(self):self.simple_staff('Counter Person')
    def page_riders(self):self.simple_staff('Rider')
    def page_kitchen(self):
        ttk.Label(self.body,text='Kitchen',font=('Segoe UI',20,'bold')).pack(anchor='w'); ttk.Label(self.body,text='Kitchen order workflow is ready for POS order integration.').pack(anchor='w',pady=10); self.table(self.body,('status','action'),[('Pending','Orders will appear here from POS'),('Preparing','Kitchen preparation queue'),('Ready','Ready for counter/rider')],{'status':'Status','action':'Workflow'})
    def page_settings(self):
        ttk.Label(self.body,text='Settings',font=('Segoe UI',20,'bold')).pack(anchor='w'); f=ttk.Frame(self.body);f.pack(anchor='w',pady=20)
        for k,v in BUSINESS.items(): ttk.Label(f,text=k.title()).grid(row=list(BUSINESS).index(k),column=0,sticky='w',pady=5); ttk.Entry(f,width=55).grid(row=list(BUSINESS).index(k),column=1,padx=10)
        ttk.Label(self.body,text='Business defaults are currently stored in the application configuration.').pack(anchor='w')


if __name__ == '__main__':
    Login(DB()).mainloop()
