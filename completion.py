import csv, os, sqlite3, shutil
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


def install(db):
    db.c.executescript('''
    CREATE TABLE IF NOT EXISTS product_options(id INTEGER PRIMARY KEY AUTOINCREMENT,product_id INTEGER NOT NULL,name TEXT NOT NULL,price REAL DEFAULT 0,active INTEGER DEFAULT 1);
    CREATE TABLE IF NOT EXISTS sale_option_items(id INTEGER PRIMARY KEY AUTOINCREMENT,sale_item_id INTEGER,option_id INTEGER,name TEXT,price REAL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS combos(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE,price REAL NOT NULL,active INTEGER DEFAULT 1);
    CREATE TABLE IF NOT EXISTS combo_items(id INTEGER PRIMARY KEY AUTOINCREMENT,combo_id INTEGER,product_id INTEGER,quantity REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS deliveries(id INTEGER PRIMARY KEY AUTOINCREMENT,sale_id INTEGER UNIQUE,rider_id INTEGER,status TEXT DEFAULT 'Pending',assigned_at TEXT,dispatched_at TEXT,delivered_at TEXT,note TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS staff_shifts(id INTEGER PRIMARY KEY AUTOINCREMENT,staff_id INTEGER,user_id INTEGER,started_at TEXT,ended_at TEXT,opening_cash REAL DEFAULT 0,closing_cash REAL,notes TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS payroll(id INTEGER PRIMARY KEY AUTOINCREMENT,staff_id INTEGER,period_start TEXT,period_end TEXT,amount REAL,paid_at TEXT,payment_method TEXT,note TEXT DEFAULT '',user_id INTEGER);
    CREATE TABLE IF NOT EXISTS purchase_returns(id INTEGER PRIMARY KEY AUTOINCREMENT,purchase_id INTEGER,amount REAL,reason TEXT,created_at TEXT,user_id INTEGER);
    CREATE TABLE IF NOT EXISTS purchase_return_items(id INTEGER PRIMARY KEY AUTOINCREMENT,return_id INTEGER,purchase_item_id INTEGER,quantity REAL,amount REAL);
    CREATE TABLE IF NOT EXISTS ledger(id INTEGER PRIMARY KEY AUTOINCREMENT,account TEXT NOT NULL,entry_type TEXT NOT NULL,amount REAL NOT NULL,reference TEXT,note TEXT,created_at TEXT,user_id INTEGER);
    CREATE TABLE IF NOT EXISTS barcode_aliases(id INTEGER PRIMARY KEY AUTOINCREMENT,product_id INTEGER,barcode TEXT UNIQUE);
    CREATE TABLE IF NOT EXISTS report_exports(id INTEGER PRIMARY KEY AUTOINCREMENT,report_name TEXT,path TEXT,created_at TEXT,user_id INTEGER);
    CREATE TABLE IF NOT EXISTS scheduled_backups(id INTEGER PRIMARY KEY CHECK(id=1),enabled INTEGER DEFAULT 0,path TEXT,interval_hours REAL DEFAULT 24,last_run TEXT);
    ''')
    cols=[r[1] for r in db.c.execute('PRAGMA table_info(products)').fetchall()]
    if 'barcode' not in cols: db.c.execute('ALTER TABLE products ADD COLUMN barcode TEXT DEFAULT ""')
    db.c.commit()


def audit(db,user,action,entity='',eid=None,details=''):
    try:
        db.c.execute('INSERT INTO audit_log(user_id,action,entity,entity_id,details,created_at) VALUES(?,?,?,?,?,?)',(user['id'],action,entity,eid,details,datetime.now().isoformat(timespec='seconds'))); db.c.commit()
    except Exception: pass


def nav_patch(Main):
    old_nav,old_show=Main.build_nav,Main.show
    names=['Modifiers','Combos','KDS','Delivery','Barcode','Shifts','Payroll','Purchase Returns','Accounting','Reports','Backup Schedule']
    def nav(self):
        old_nav(self)
        try:
            inner=self.body.master.winfo_children()[1].winfo_children()[0]
            for n in names: ttk.Button(inner,text=n,command=lambda x=n:self.show(x)).pack(side='left',padx=3,pady=3)
        except Exception: pass
    def show(self,name):
        fn={'Modifiers':modifiers_page,'Combos':combos_page,'KDS':kds_page,'Delivery':delivery_page,'Barcode':barcode_page,'Shifts':shifts_page,'Payroll':payroll_page,'Purchase Returns':purchase_returns_page,'Accounting':accounting_page,'Reports':reports_page,'Backup Schedule':backup_page}.get(name)
        if fn:return fn(self)
        return old_show(self,name)
    Main.build_nav=nav;Main.show=show


def modifiers_page(self):
    self.clear(); ttk.Label(self.body,text='Product Modifiers / Add-ons',style='Title.TLabel').pack(anchor='w')
    products=self.db.rows('products','WHERE active=1 ORDER BY name'); names={r['name']:r['id'] for r in products}; f=ttk.Frame(self.body);f.pack(fill='x',pady=8)
    p=tk.StringVar();n=tk.StringVar();price=tk.DoubleVar();ttk.Combobox(f,textvariable=p,values=list(names),state='readonly',width=30).pack(side='left',padx=3);ttk.Entry(f,textvariable=n,width=25).pack(side='left',padx=3);ttk.Entry(f,textvariable=price,width=12).pack(side='left',padx=3)
    def add():
        if not p.get() or not n.get():return
        self.db.c.execute('INSERT INTO product_options(product_id,name,price) VALUES(?,?,?)',(names[p.get()],n.get(),price.get()));self.db.c.commit();audit(self.db,self.user,'Add Modifier','product',names[p.get()],n.get());self.show('Modifiers')
    ttk.Button(f,text='Add Modifier',style='Accent.TButton',command=add).pack(side='left')
    rows=[(r['id'],self.db.c.execute('SELECT name FROM products WHERE id=?',(r['product_id'],)).fetchone()['name'],r['name'],r['price']) for r in self.db.rows('product_options','WHERE active=1 ORDER BY id DESC')];self.table(self.body,('id','product','name','price'),rows,{'id':'ID','product':'Product','name':'Option','price':'Price'})


def combos_page(self):
    self.clear();ttk.Label(self.body,text='Combo Meals',style='Title.TLabel').pack(anchor='w');ttk.Button(self.body,text='New Combo',style='Accent.TButton',command=lambda:combo_dialog(self)).pack(anchor='w',pady=8)
    rows=self.db.rows('combos','WHERE active=1 ORDER BY name');self.table(self.body,('id','name','price'),[(r['id'],r['name'],r['price']) for r in rows],{'id':'ID','name':'Combo','price':'Price'})

def combo_dialog(self):
    w=tk.Toplevel(self);w.title('Create Combo');w.geometry('650x520');name=tk.StringVar();price=tk.DoubleVar();ttk.Label(w,text='Combo Name').pack(pady=5);ttk.Entry(w,textvariable=name,width=45).pack();ttk.Label(w,text='Selling Price').pack(pady=5);ttk.Entry(w,textvariable=price).pack();products=self.db.rows('products','WHERE active=1 ORDER BY name');names={r['name']:r['id'] for r in products};selected=[];pv=tk.StringVar();q=tk.DoubleVar(value=1);ttk.Combobox(w,textvariable=pv,values=list(names),state='readonly').pack(pady=5);ttk.Entry(w,textvariable=q).pack();t=ttk.Treeview(w,columns=('product','qty'),show='headings');t.heading('product',text='Product');t.heading('qty',text='Qty');t.pack(fill='both',expand=True,pady=8)
    def add():
        if pv.get():selected.append((names[pv.get()],q.get()));t.insert('','end',values=(pv.get(),q.get()))
    ttk.Button(w,text='Add Item',command=add).pack()
    def save():
        if not name.get() or not selected:return
        self.db.c.execute('INSERT INTO combos(name,price) VALUES(?,?)',(name.get(),price.get()));cid=self.db.c.lastrowid
        self.db.c.executemany('INSERT INTO combo_items(combo_id,product_id,quantity) VALUES(?,?,?)',[(cid,p,q) for p,q in selected]);self.db.c.commit();audit(self.db,self.user,'Create Combo','combo',cid,name.get());w.destroy();self.show('Combos')
    ttk.Button(w,text='Save Combo',style='Accent.TButton',command=save).pack(pady=8)


def kds_page(self):
    self.clear();ttk.Label(self.body,text='Kitchen Display System',style='Title.TLabel').pack(anchor='w');ttk.Button(self.body,text='Refresh',command=lambda:self.show('KDS')).pack(anchor='e');
    rows=self.db.c.execute("SELECT s.id,s.invoice_no,s.status,s.created_at,COALESCE(m.order_type,'Counter') type FROM sales s LEFT JOIN order_meta m ON m.sale_id=s.id WHERE s.status IN ('New','Preparing','Ready') ORDER BY s.id").fetchall();t=self.table(self.body,('id','invoice','status','type','date'),[(r['id'],r['invoice_no'],r['status'],r['type'],r['created_at']) for r in rows],{'id':'ID','invoice':'Order','status':'Status','type':'Type','date':'Time'});t.bind('<Double-1>',lambda e:kds_status(self,t.selection()))

def kds_status(self,sel):
    if not sel:return
    sid=int(sel[0]);r=self.db.c.execute('SELECT status FROM sales WHERE id=?',(sid,)).fetchone();nexts={'New':'Preparing','Preparing':'Ready','Ready':'Completed'};new=nexts.get(r['status'],'Completed');self.db.c.execute('UPDATE sales SET status=? WHERE id=?',(new,sid));self.db.c.commit();audit(self.db,self.user,'KDS Status','sale',sid,new);self.show('KDS')


def delivery_page(self):
    self.clear();ttk.Label(self.body,text='Delivery Dispatch',style='Title.TLabel').pack(anchor='w');
    riders=self.db.rows('staff','WHERE active=1 AND role="Rider" ORDER BY name');rn={r['name']:r['id'] for r in riders};f=ttk.Frame(self.body);f.pack(fill='x',pady=8);rid=tk.StringVar();ttk.Label(f,text='Rider').pack(side='left');ttk.Combobox(f,textvariable=rid,values=list(rn),state='readonly',width=25).pack(side='left',padx=5)
    rows=self.db.c.execute("SELECT d.id,d.sale_id,s.invoice_no,d.status,d.rider_id,d.assigned_at,d.dispatched_at,d.delivered_at,COALESCE(m.delivery_address,'') address FROM deliveries d JOIN sales s ON s.id=d.sale_id LEFT JOIN order_meta m ON m.sale_id=s.id ORDER BY d.id DESC").fetchall();t=self.table(self.body,('id','sale','invoice','status','rider','assigned','dispatch','delivered','address'),[(r['id'],r['sale_id'],r['invoice_no'],r['status'],r['rider_id'] or '',r['assigned_at'] or '',r['dispatched_at'] or '',r['delivered_at'] or '',r['address']) for r in rows],{'id':'ID','sale':'Sale','invoice':'Invoice','status':'Status','rider':'Rider','assigned':'Assigned','dispatch':'Dispatched','delivered':'Delivered','address':'Address'})
    def assign():
        if not t.selection() or not rid.get():return
        did=int(t.selection()[0]);now=datetime.now().isoformat(timespec='seconds');self.db.c.execute('UPDATE deliveries SET rider_id=?,status="Assigned",assigned_at=? WHERE id=?',(rn[rid.get()],now,did));self.db.commit();audit(self.db,self.user,'Assign Rider','delivery',did,rid.get());self.show('Delivery')
    def advance():
        if not t.selection():return
        did=int(t.selection()[0]);r=self.db.c.execute('SELECT status FROM deliveries WHERE id=?',(did,)).fetchone();n={'Pending':'Assigned','Assigned':'Out for Delivery','Out for Delivery':'Delivered'}.get(r['status'],'Delivered');col='dispatched_at' if n=='Out for Delivery' else ('delivered_at' if n=='Delivered' else 'assigned_at');self.db.c.execute(f'UPDATE deliveries SET status=?,{col}=? WHERE id=?',(n,datetime.now().isoformat(timespec='seconds'),did));self.db.commit();self.show('Delivery')
    ttk.Button(f,text='Assign',command=assign).pack(side='left',padx=5);ttk.Button(f,text='Advance Status',command=advance).pack(side='left')


def barcode_page(self):
    self.clear();ttk.Label(self.body,text='Barcode / Scanner',style='Title.TLabel').pack(anchor='w');ttk.Label(self.body,text='Use a USB/Bluetooth scanner in keyboard mode: scan into the field and press Enter.').pack(anchor='w',pady=5);v=tk.StringVar();e=ttk.Entry(self.body,textvariable=v,font=('Segoe UI',16));e.pack(fill='x',pady=10);result=ttk.Label(self.body,text='');result.pack(anchor='w')
    def find(_=None):
        r=self.db.c.execute('SELECT * FROM products WHERE active=1 AND (barcode=? OR id IN (SELECT product_id FROM barcode_aliases WHERE barcode=?))',(v.get().strip(),v.get().strip())).fetchone();result.config(text=(f"{r['name']} | {r['price']:,.2f} | Stock {r['stock']}" if r else 'Barcode not found'));v.set('')
    e.bind('<Return>',find);e.focus()
    ttk.Label(self.body,text='Assign barcode').pack(anchor='w',pady=(20,3));p=tk.StringVar();b=tk.StringVar();names={r['name']:r['id'] for r in self.db.rows('products','WHERE active=1 ORDER BY name')};ttk.Combobox(self.body,textvariable=p,values=list(names),state='readonly').pack(anchor='w');ttk.Entry(self.body,textvariable=b).pack(anchor='w',pady=4);ttk.Button(self.body,text='Save Barcode',command=lambda:(self.db.c.execute('UPDATE products SET barcode=? WHERE id=?',(b.get().strip(),names[p.get()])),self.db.commit(),audit(self.db,self.user,'Set Barcode','product',names[p.get()]),self.show('Barcode'))).pack(anchor='w')


def shifts_page(self):
    self.clear();ttk.Label(self.body,text='Staff Shifts',style='Title.TLabel').pack(anchor='w');staff=self.db.rows('staff','WHERE active=1 ORDER BY name');names={r['name']:r['id'] for r in staff};f=ttk.Frame(self.body);f.pack(fill='x',pady=8);sv=tk.StringVar();ttk.Combobox(f,textvariable=sv,values=list(names),state='readonly').pack(side='left');ttk.Button(f,text='Start Shift',command=lambda:start_shift(self,names.get(sv.get()))).pack(side='left',padx=5);ttk.Button(f,text='End Selected',command=lambda:end_shift(self,t.selection())).pack(side='left')
    rows=self.db.rows('staff_shifts','ORDER BY id DESC');self.table(self.body,('id','staff','start','end','opening','closing','notes'),[(r['id'],r['staff_id'],r['started_at'],r['ended_at'] or '',r['opening_cash'],r['closing_cash'] or '',r['notes']) for r in rows],{'id':'ID','staff':'Staff','start':'Started','end':'Ended','opening':'Opening','closing':'Closing','notes':'Notes'});t=self.body.winfo_children()[-1]

def start_shift(self,staff_id):
    if not staff_id:return
    self.db.c.execute('INSERT INTO staff_shifts(staff_id,user_id,started_at) VALUES(?,?,?)',(staff_id,self.user['id'],datetime.now().isoformat(timespec='seconds')));self.db.commit();audit(self.db,self.user,'Start Shift','staff',staff_id);self.show('Shifts')

def end_shift(self,sel):
    if not sel:return
    self.db.c.execute('UPDATE staff_shifts SET ended_at=? WHERE id=? AND ended_at IS NULL',(datetime.now().isoformat(timespec='seconds'),int(sel[0])));self.db.commit();self.show('Shifts')


def payroll_page(self):
    self.clear();ttk.Label(self.body,text='Payroll',style='Title.TLabel').pack(anchor='w');ttk.Button(self.body,text='Record Payment',style='Accent.TButton',command=lambda:payroll_dialog(self)).pack(anchor='w',pady=8);rows=self.db.rows('payroll','ORDER BY id DESC');self.table(self.body,('id','staff','from','to','amount','paid','method','note'),[(r['id'],r['staff_id'],r['period_start'],r['period_end'],r['amount'],r['paid_at'],r['payment_method'],r['note']) for r in rows],{'id':'ID','staff':'Staff','from':'From','to':'To','amount':'Amount','paid':'Paid At','method':'Method','note':'Note'})

def payroll_dialog(self):
    w=tk.Toplevel(self);w.title('Record Payroll');staff=self.db.rows('staff','WHERE active=1 ORDER BY name');names={r['name']:r['id'] for r in staff};v=[tk.StringVar() for _ in range(6)];labs=['Staff','Period Start','Period End','Amount','Payment Method','Note']
    for i,l in enumerate(labs):ttk.Label(w,text=l).grid(row=i,column=0,padx=10,pady=5,sticky='w');(ttk.Combobox(w,textvariable=v[i],values=list(names),state='readonly') if i==0 else ttk.Entry(w,textvariable=v[i],width=32)).grid(row=i,column=1,padx=10,pady=5)
    ttk.Combobox(w,textvariable=v[4],values=['Cash','Bank','Other'],state='readonly').grid(row=4,column=1,padx=10,pady=5)
    def save():
        now=datetime.now().isoformat(timespec='seconds');self.db.c.execute('INSERT INTO payroll(staff_id,period_start,period_end,amount,paid_at,payment_method,note,user_id) VALUES(?,?,?,?,?,?,?,?)',(names[v[0].get()],v[1].get(),v[2].get(),float(v[3].get() or 0),now,v[4].get(),v[5].get(),self.user['id']));self.db.c.execute('INSERT INTO ledger(account,entry_type,amount,reference,note,created_at,user_id) VALUES(?,?,?,?,?,?,?)',('Payroll','Expense',float(v[3].get() or 0),'PAYROLL',v[5].get(),now,self.user['id']));self.db.commit();w.destroy();self.show('Payroll')
    ttk.Button(w,text='Save',style='Accent.TButton',command=save).grid(row=6,column=1,pady=10,sticky='e')


def purchase_returns_page(self):
    self.clear();ttk.Label(self.body,text='Purchase Returns',style='Title.TLabel').pack(anchor='w');rows=self.db.rows('purchases','ORDER BY id DESC LIMIT 200');t=self.table(self.body,('id','invoice','total','status','date'),[(r['id'],r['invoice_no'],r['total'],r['status'],r['created_at']) for r in rows],{'id':'ID','invoice':'Invoice','total':'Total','status':'Status','date':'Date'});t.bind('<Double-1>',lambda e:purchase_return_dialog(self,t.selection()))

def purchase_return_dialog(self,sel):
    if not sel:return
    pid=int(sel[0]);items=self.db.rows('purchase_items','WHERE purchase_id=?',(pid,));w=tk.Toplevel(self);w.title('Purchase Return');vals=[]
    for r in items:
        maxq=r['quantity'];v=tk.DoubleVar(value=0);ttk.Label(w,text=f"Product {r['product_id']} | Purchased {maxq} @ {r['unit_cost']}").pack(anchor='w',padx=10);ttk.Entry(w,textvariable=v).pack(anchor='w',padx=10);vals.append((r,v))
    reason=tk.StringVar();ttk.Entry(w,textvariable=reason,width=45).pack(padx=10,pady=8)
    def save():
        now=datetime.now().isoformat(timespec='seconds');cur=self.db.c;cur.execute('INSERT INTO purchase_returns(purchase_id,amount,reason,created_at,user_id) VALUES(?,?,?,?,?)',(pid,0,reason.get(),now,self.user['id']));rid=cur.lastrowid;amount=0
        for r,v in vals:
            q=max(0,min(v.get(),r['quantity']));a=q*r['unit_cost']
            if q:amount+=a;cur.execute('INSERT INTO purchase_return_items(return_id,purchase_item_id,quantity,amount) VALUES(?,?,?,?)',(rid,r['id'],q,a));cur.execute('UPDATE products SET stock=MAX(0,stock-?) WHERE id=?',(q,r['product_id']))
        cur.execute('UPDATE purchase_returns SET amount=? WHERE id=?',(amount,rid));cur.commit();audit(self.db,self.user,'Purchase Return','purchase',pid,f'amount={amount}');w.destroy();self.show('Purchase Returns')
    ttk.Button(w,text='Process Return',style='Accent.TButton',command=save).pack(pady=10)


def accounting_page(self):
    self.clear();ttk.Label(self.body,text='Accounting Ledger',style='Title.TLabel').pack(anchor='w');f=ttk.Frame(self.body);f.pack(fill='x',pady=8);ttk.Button(f,text='Add Entry',command=lambda:ledger_dialog(self)).pack(side='left');rows=self.db.rows('ledger','ORDER BY id DESC');self.table(self.body,('id','account','type','amount','reference','note','date'),[(r['id'],r['account'],r['entry_type'],r['amount'],r['reference'],r['note'],r['created_at']) for r in rows],{'id':'ID','account':'Account','type':'Type','amount':'Amount','reference':'Reference','note':'Note','date':'Date'})

def ledger_dialog(self):
    w=tk.Toplevel(self);w.title('Ledger Entry');v=[tk.StringVar() for _ in range(5)];labs=['Account','Type','Amount','Reference','Note']
    for i,l in enumerate(labs):ttk.Label(w,text=l).grid(row=i,column=0,padx=10,pady=5,sticky='w');ttk.Entry(w,textvariable=v[i],width=35).grid(row=i,column=1,padx=10,pady=5)
    ttk.Combobox(w,textvariable=v[1],values=['Income','Expense','Asset','Liability','Equity'],state='readonly').grid(row=1,column=1,padx=10,pady=5)
    ttk.Button(w,text='Save',command=lambda:(self.db.c.execute('INSERT INTO ledger(account,entry_type,amount,reference,note,created_at,user_id) VALUES(?,?,?,?,?,?,?)',(v[0].get(),v[1].get(),float(v[2].get() or 0),v[3].get(),v[4].get(),datetime.now().isoformat(timespec='seconds'),self.user['id'])),self.db.c.commit(),w.destroy(),self.show('Accounting'))).grid(row=5,column=1,pady=10,sticky='e')


def reports_page(self):
    self.clear();ttk.Label(self.body,text='Reports & Export',style='Title.TLabel').pack(anchor='w');names=['Sales','Products','Customers','Suppliers','Expenses','Ledger','Shifts','Payroll','Deliveries'];v=tk.StringVar(value='Sales');ttk.Combobox(self.body,textvariable=v,values=names,state='readonly').pack(anchor='w',pady=8);ttk.Button(self.body,text='Export CSV',style='Accent.TButton',command=lambda:export_report(self,v.get())).pack(anchor='w');ttk.Label(self.body,text='Exports contain live database records only.').pack(anchor='w',pady=8)

def export_report(self,name):
    tables={'Sales':'sales','Products':'products','Customers':'customers','Suppliers':'suppliers','Expenses':'expenses','Ledger':'ledger','Shifts':'staff_shifts','Payroll':'payroll','Deliveries':'deliveries'};table=tables[name];path=filedialog.asksaveasfilename(defaultextension='.csv',filetypes=[('CSV','*.csv')],initialfile=name.lower()+'.csv');
    if not path:return
    rows=self.db.rows(table);f=open(path,'w',newline='',encoding='utf-8-sig');w=csv.writer(f);w.writerow(rows[0].keys() if rows else []);[w.writerow(list(r)) for r in rows];f.close();self.db.c.execute('INSERT INTO report_exports(report_name,path,created_at,user_id) VALUES(?,?,?,?)',(name,path,datetime.now().isoformat(timespec='seconds'),self.user['id']));self.db.commit();messagebox.showinfo('Report','Report exported successfully.',parent=self)


def backup_page(self):
    self.clear();ttk.Label(self.body,text='Scheduled Backups',style='Title.TLabel').pack(anchor='w');r=self.db.c.execute('SELECT * FROM scheduled_backups WHERE id=1').fetchone();enabled=tk.BooleanVar(value=bool(r['enabled']) if r else False);path=tk.StringVar(value=r['path'] if r else '');hours=tk.DoubleVar(value=r['interval_hours'] if r else 24);ttk.Checkbutton(self.body,text='Enable automatic backups while POS is running',variable=enabled).pack(anchor='w',pady=8);f=ttk.Frame(self.body);f.pack(anchor='w');ttk.Label(f,text='Backup Folder').pack(side='left');ttk.Entry(f,textvariable=path,width=55).pack(side='left',padx=5);ttk.Button(f,text='Browse',command=lambda:path.set(filedialog.askdirectory() or path.get())).pack(side='left');ttk.Label(self.body,text='Interval hours').pack(anchor='w',pady=(10,2));ttk.Entry(self.body,textvariable=hours).pack(anchor='w');
    def save():
        self.db.c.execute('INSERT OR REPLACE INTO scheduled_backups(id,enabled,path,interval_hours,last_run) VALUES(1,?,?,?,COALESCE((SELECT last_run FROM scheduled_backups WHERE id=1),NULL))',(int(enabled.get()),path.get(),hours.get()));self.db.commit();self._backup_schedule();messagebox.showinfo('Backup','Backup schedule saved.',parent=self)
    ttk.Button(self.body,text='Save Schedule',style='Accent.TButton',command=save).pack(anchor='w',pady=12);self._backup_schedule()


def schedule_patch(Main):
    old=Main.__init__
    def init(self,*a,**k):
        old(self,*a,**k);self.after(5000,self._backup_schedule)
    def run(self):
        r=self.db.c.execute('SELECT * FROM scheduled_backups WHERE id=1').fetchone()
        if r and r['enabled'] and r['path']:
            due=not r['last_run'] or datetime.fromisoformat(r['last_run'])+timedelta(hours=r['interval_hours'])<=datetime.now()
            if due:
                try:
                    os.makedirs(r['path'],exist_ok=True);name='pos_backup_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.db';self.db.c.commit();shutil.copy2('pos.db',os.path.join(r['path'],name));self.db.c.execute('UPDATE scheduled_backups SET last_run=? WHERE id=1',(datetime.now().isoformat(timespec='seconds'),));self.db.commit()
                except Exception: pass
        self.after(60000,self._backup_schedule)
    Main.__init__=init;Main._backup_schedule=run
