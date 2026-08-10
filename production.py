import os, shutil, sqlite3
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

STATUS = ['New','Preparing','Ready','Out for Delivery','Completed','Cancelled']

def install(db):
    db.c.executescript('''
    CREATE TABLE IF NOT EXISTS cash_sessions(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,opened_at TEXT,closed_at TEXT,opening_cash REAL DEFAULT 0,closing_cash REAL,expected_cash REAL,variance REAL,status TEXT DEFAULT 'Open',note TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS expenses(id INTEGER PRIMARY KEY AUTOINCREMENT,category TEXT,amount REAL,note TEXT,created_at TEXT,user_id INTEGER);
    CREATE TABLE IF NOT EXISTS stock_movements(id INTEGER PRIMARY KEY AUTOINCREMENT,product_id INTEGER,qty REAL,movement_type TEXT,note TEXT,created_at TEXT,user_id INTEGER);
    CREATE TABLE IF NOT EXISTS audit_log(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,action TEXT,entity TEXT,entity_id INTEGER,details TEXT,created_at TEXT);
    ''')
    cols=[r[1] for r in db.c.execute('PRAGMA table_info(sales)').fetchall()]
    if 'status' not in cols: db.c.execute("ALTER TABLE sales ADD COLUMN status TEXT DEFAULT 'New'")
    if 'discount' not in cols: db.c.execute("ALTER TABLE sales ADD COLUMN discount REAL DEFAULT 0")
    db.c.commit()

def audit(db,user,action,entity='',eid=None,details=''):
    db.c.execute('INSERT INTO audit_log(user_id,action,entity,entity_id,details,created_at) VALUES(?,?,?,?,?,?)',(user['id'],action,entity,eid,details,datetime.now().isoformat(timespec='seconds'))); db.c.commit()

def backup(db,parent):
    target=filedialog.asksaveasfilename(parent=parent,title='Backup POS Database',defaultextension='.db',filetypes=[('SQLite database','*.db')])
    if not target:return
    try:
        db.c.commit(); shutil.copy2(db.c.database if hasattr(db.c,'database') else 'pos.db',target)
    except Exception:
        db.c.execute('VACUUM INTO ?', (target,))
    messagebox.showinfo('Backup','Database backup created successfully.',parent=parent)

def add_nav(original_build):
    def build(self):
        original_build(self)
        try:
            inner=self.body.master.winfo_children()[1].winfo_children()[0]
        except Exception:return
    return build

def page_cash(self):
    self.clear(); ttk.Label(self.body,text='Cash Control',style='Title.TLabel').pack(anchor='w'); bar=ttk.Frame(self.body); bar.pack(fill='x',pady=10)
    ttk.Button(bar,text='Open Cash Session',style='Accent.TButton',command=lambda:cash_open(self)).pack(side='left'); ttk.Button(bar,text='Close Selected Session',command=lambda:cash_close(self,t.selection())).pack(side='left',padx=6)
    rows=[(r['id'],r['status'],r['opening_cash'],r['expected_cash'] or 0,r['closing_cash'] or 0,r['variance'] or 0,r['opened_at'],r['closed_at'] or '') for r in self.db.rows('cash_sessions','ORDER BY id DESC')]
    self.table(self.body,('id','status','opening','expected','closing','variance','opened','closed'),rows,{'id':'ID','status':'Status','opening':'Opening','expected':'Expected','closing':'Closing','variance':'Variance','opened':'Opened','closed':'Closed'})

def cash_open(self):
    if self.db.c.execute("SELECT 1 FROM cash_sessions WHERE status='Open'").fetchone(): return messagebox.showwarning('Cash','A cash session is already open.',parent=self)
    w=tk.Toplevel(self); w.title('Open Cash Session'); v=tk.DoubleVar(); ttk.Label(w,text='Opening cash').pack(pady=8); ttk.Entry(w,textvariable=v).pack(pady=4); ttk.Button(w,text='Open',command=lambda:(self.db.c.execute("INSERT INTO cash_sessions(user_id,opened_at,opening_cash) VALUES(?,?,?)",(self.user['id'],datetime.now().isoformat(timespec='seconds'),v.get())),self.db.c.commit(),audit(self.db,self.user,'Open Cash Session'),w.destroy(),self.show('Cash Control'))).pack(pady=10)

def cash_close(self,sel):
    if not sel:return
    sid=int(sel[0]); row=self.db.c.execute('SELECT * FROM cash_sessions WHERE id=?',(sid,)).fetchone();
    if not row or row['status']!='Open':return messagebox.showwarning('Cash','Only an open session can be closed.',parent=self)
    sales=self.db.c.execute("SELECT COALESCE(SUM(total),0) FROM sales WHERE created_at>=? AND payment_method='Cash'",(row['opened_at'],)).fetchone()[0]
    exp=self.db.c.execute("SELECT COALESCE(SUM(amount),0) FROM expenses WHERE created_at>=?",(row['opened_at'],)).fetchone()[0]
    expected=row['opening_cash']+sales-exp
    w=tk.Toplevel(self); w.title('Close Cash Session'); v=tk.DoubleVar(value=expected); ttk.Label(w,text=f'Expected cash: {expected:,.2f}').pack(pady=8); ttk.Label(w,text='Actual closing cash').pack(); ttk.Entry(w,textvariable=v).pack(pady=5)
    def close():
        actual=v.get(); self.db.c.execute("UPDATE cash_sessions SET closed_at=?,closing_cash=?,expected_cash=?,variance=?,status='Closed' WHERE id=?",(datetime.now().isoformat(timespec='seconds'),actual,expected,actual-expected,sid)); self.db.c.commit(); audit(self.db,self.user,'Close Cash Session','cash_session',sid,f'variance={actual-expected}'); w.destroy(); self.show('Cash Control')
    ttk.Button(w,text='Close Session',command=close).pack(pady=10)

def page_expenses(self):
    self.clear(); ttk.Label(self.body,text='Expenses',style='Title.TLabel').pack(anchor='w'); bar=ttk.Frame(self.body); bar.pack(fill='x',pady=10); ttk.Button(bar,text='Add Expense',style='Accent.TButton',command=lambda:expense_add(self)).pack(side='left')
    rows=[(r['id'],r['category'],r['amount'],r['note'],r['created_at']) for r in self.db.rows('expenses','ORDER BY id DESC')]; self.table(self.body,('id','category','amount','note','date'),rows,{'id':'ID','category':'Category','amount':'Amount','note':'Note','date':'Date'})

def expense_add(self):
    w=tk.Toplevel(self); w.title('Add Expense'); vals={}
    for i,k in enumerate(['category','amount','note']): ttk.Label(w,text=k.title()).grid(row=i,column=0,padx=10,pady=6,sticky='w'); v=tk.StringVar(); ttk.Entry(w,textvariable=v,width=35).grid(row=i,column=1,padx=10); vals[k]=v
    def save():
        self.db.c.execute('INSERT INTO expenses(category,amount,note,created_at,user_id) VALUES(?,?,?,?,?)',(vals['category'].get(),float(vals['amount'].get() or 0),vals['note'].get(),datetime.now().isoformat(timespec='seconds'),self.user['id'])); self.db.c.commit(); audit(self.db,self.user,'Add Expense','expense'); w.destroy(); self.show('Expenses')
    ttk.Button(w,text='Save',command=save).grid(row=3,column=1,pady=10,sticky='e')

def page_stock(self):
    self.clear(); ttk.Label(self.body,text='Stock Control',style='Title.TLabel').pack(anchor='w'); bar=ttk.Frame(self.body); bar.pack(fill='x',pady=10); ttk.Button(bar,text='Stock Adjustment',style='Accent.TButton',command=lambda:stock_adjust(self)).pack(side='left')
    rows=[(r['id'],r['name'],r['category'],r['stock']) for r in self.db.rows('products','WHERE active=1 ORDER BY name')]; self.table(self.body,('id','name','category','stock'),rows,{'id':'ID','name':'Product','category':'Category','stock':'Current Stock'})

def stock_adjust(self):
    w=tk.Toplevel(self); w.title('Stock Adjustment'); products=self.db.rows('products','WHERE active=1 ORDER BY name'); names={r['name']:r['id'] for r in products}; n=tk.StringVar(); q=tk.DoubleVar(); kind=tk.StringVar(value='Add'); note=tk.StringVar();
    ttk.Label(w,text='Product').pack(pady=5); ttk.Combobox(w,textvariable=n,values=list(names),state='readonly',width=35).pack(); ttk.Label(w,text='Quantity').pack(pady=5); ttk.Entry(w,textvariable=q).pack(); ttk.Combobox(w,textvariable=kind,values=['Add','Remove','Set'],state='readonly').pack(pady=5); ttk.Entry(w,textvariable=note,width=35).pack()
    def save():
        pid=names[n.get()]; old=self.db.c.execute('SELECT stock FROM products WHERE id=?',(pid,)).fetchone()[0]; qty=q.get(); new=qty if kind.get()=='Set' else old+(qty if kind.get()=='Add' else -qty); self.db.c.execute('UPDATE products SET stock=? WHERE id=?',(max(0,new),pid)); self.db.c.execute('INSERT INTO stock_movements(product_id,qty,movement_type,note,created_at,user_id) VALUES(?,?,?,?,?,?)',(pid,qty,kind.get(),note.get(),datetime.now().isoformat(timespec='seconds'),self.user['id'])); self.db.c.commit(); audit(self.db,self.user,'Stock Adjustment','product',pid,f'{kind.get()} {qty}'); w.destroy(); self.show('Stock Control')
    ttk.Button(w,text='Save',command=save).pack(pady=10)

def page_orders(self):
    self.clear(); ttk.Label(self.body,text='Order Board',style='Title.TLabel').pack(anchor='w'); ttk.Label(self.body,text='Track order lifecycle for counter, kitchen and delivery.',style='Subtitle.TLabel').pack(anchor='w')
    rows=[(r['id'],r['invoice_no'],r['status'] or 'New',r['total'],r['payment_method'],r['created_at']) for r in self.db.rows('sales','ORDER BY id DESC LIMIT 200')]; t=self.table(self.body,('id','invoice','status','total','payment','date'),rows,{'id':'ID','invoice':'Invoice','status':'Status','total':'Total','payment':'Payment','date':'Date'}); t.bind('<Double-1>',lambda e:order_status(self,t.selection()))

def order_status(self,sel):
    if not sel:return
    sid=int(sel[0]); row=self.db.c.execute('SELECT status FROM sales WHERE id=?',(sid,)).fetchone(); w=tk.Toplevel(self); w.title('Update Order Status'); v=tk.StringVar(value=row['status'] or 'New'); ttk.Combobox(w,textvariable=v,values=STATUS,state='readonly').pack(padx=20,pady=15); ttk.Button(w,text='Save',command=lambda:(self.db.c.execute('UPDATE sales SET status=? WHERE id=?',(v.get(),sid)),self.db.c.commit(),audit(self.db,self.user,'Update Order Status','sale',sid,v.get()),w.destroy(),self.show('Order Board'))).pack(pady=10)

def page_audit(self):
    self.clear(); ttk.Label(self.body,text='Audit Log',style='Title.TLabel').pack(anchor='w'); rows=[(r['id'],r['user_id'],r['action'],r['entity'],r['entity_id'] or '',r['details'],r['created_at']) for r in self.db.rows('audit_log','ORDER BY id DESC LIMIT 500')]; self.table(self.body,('id','user','action','entity','entity_id','details','date'),rows,{'id':'ID','user':'User','action':'Action','entity':'Entity','entity_id':'Entity ID','details':'Details','date':'Date'})

def page_backup(self):
    self.clear(); ttk.Label(self.body,text='Backup & Recovery',style='Title.TLabel').pack(anchor='w'); ttk.Label(self.body,text='Create a safe copy before upgrades, imports or major configuration changes.',style='Subtitle.TLabel').pack(anchor='w',pady=(0,15)); ttk.Button(self.body,text='Create Database Backup',style='Accent.TButton',command=lambda:backup(self.db,self)).pack(anchor='w')

def patch(Main):
    old_show=Main.show; old_init=Main.__init__; old_nav=Main.build_nav
    extra=['Order Board','Cash Control','Expenses','Stock Control','Audit Log','Backup & Recovery']
    def nav(self):
        old_nav(self)
        try:
            canvas=self.body.master.winfo_children()[1]; inner=canvas.winfo_children()[0]
            for n in extra: ttk.Button(inner,text=n,command=lambda x=n:self.show(x)).pack(side='left',padx=3,pady=3)
        except Exception: pass
    def show(self,name):
        if name=='Order Board': return page_orders(self)
        if name=='Cash Control': return page_cash(self)
        if name=='Expenses': return page_expenses(self)
        if name=='Stock Control': return page_stock(self)
        if name=='Audit Log': return page_audit(self)
        if name=='Backup & Recovery': return page_backup(self)
        return old_show(self,name)
    Main.build_nav=nav; Main.show=show
    return Main
