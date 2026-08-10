import sqlite3, tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime

BUSINESS={'name':'MK Pizza & Ice Bar','address':'Collage Road Abbas Chowk, Bhakkar, Pakistan','phone':'0316 9700025','currency':'Rs.'}

def now(): return datetime.now().isoformat(timespec='seconds')

def money(v): return f"Rs. {float(v or 0):,.2f}"

def install(App):
    """Install the real interactive operational pages onto the canonical App class."""
    original_show=App.show
    def show(self,n):
        aliases={'Tables / Dine-in':'Tables / Dine-in','Dine-in':'Tables / Dine-in'}
        target=aliases.get(n,n)
        if target=='Tables / Dine-in':
            self.clear(); self.page_tables_dine_in(); return
        return original_show(self,n)
    App.show=show
    _migrate(App)
    App.page_tables_dine_in=page_tables_dine_in
    App.page_riders=page_riders
    App.page_orders=page_orders
    App.page_customers=page_customers
    App.page_products=page_products
    App.page_suppliers=page_suppliers
    App.checkout=checkout
    return App

def _migrate(App):
    # Only schema objects are created. No business/demo records are inserted.
    try:
        c=App.__dict__.get('_advanced_schema_connection')
    except Exception: c=None
    # Migration is performed per Store connection when App is constructed.
    old_init=App.__init__
    if getattr(App,'_advanced_init_installed',False): return
    def init(self,*a,**kw):
        old_init(self,*a,**kw)
        db=self.s
        db.c.executescript('''
        CREATE TABLE IF NOT EXISTS rider_rates(id INTEGER PRIMARY KEY AUTOINCREMENT,rider_id INTEGER UNIQUE,base_fee REAL DEFAULT 0,per_km REAL DEFAULT 0,minimum_fee REAL DEFAULT 0,updated_at TEXT);
        CREATE TABLE IF NOT EXISTS delivery_tracking(id INTEGER PRIMARY KEY AUTOINCREMENT,sale_id INTEGER NOT NULL,status TEXT NOT NULL,latitude TEXT DEFAULT '',longitude TEXT DEFAULT '',note TEXT DEFAULT '',rider_id INTEGER,created_at TEXT NOT NULL,user_id INTEGER);
        CREATE TABLE IF NOT EXISTS table_sessions(id INTEGER PRIMARY KEY AUTOINCREMENT,table_id INTEGER NOT NULL,customer_id INTEGER,opened_at TEXT NOT NULL,closed_at TEXT,status TEXT DEFAULT 'Open',sale_id INTEGER,guest_count INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS order_events(id INTEGER PRIMARY KEY AUTOINCREMENT,sale_id INTEGER NOT NULL,status TEXT NOT NULL,note TEXT DEFAULT '',created_at TEXT NOT NULL,user_id INTEGER);
        CREATE INDEX IF NOT EXISTS idx_delivery_tracking_sale ON delivery_tracking(sale_id,created_at);
        CREATE INDEX IF NOT EXISTS idx_order_events_sale ON order_events(sale_id,created_at);
        ''')
        for col,typ in [('rider_base_fee','REAL DEFAULT 0'),('rider_per_km','REAL DEFAULT 0'),('delivery_distance_km','REAL DEFAULT 0'),('delivery_fee','REAL DEFAULT 0'),('tracking_status','TEXT DEFAULT \'Pending\'')]:
            try: db.q(f'ALTER TABLE sales ADD COLUMN {col} {typ}')
            except sqlite3.OperationalError: pass
        db.c.commit()
    App.__init__=init
    App._advanced_init_installed=True

def _tree(parent,cols,heads,height=15):
    f=ttk.Frame(parent); f.pack(fill='both',expand=True)
    t=ttk.Treeview(f,columns=cols,show='headings',height=height)
    for c in cols:
        t.heading(c,text=heads.get(c,c.title())); t.column(c,width=130,anchor='w')
    sy=ttk.Scrollbar(f,orient='vertical',command=t.yview); sx=ttk.Scrollbar(f,orient='horizontal',command=t.xview)
    t.configure(yscrollcommand=sy.set,xscrollcommand=sx.set); t.grid(row=0,column=0,sticky='nsew'); sy.grid(row=0,column=1,sticky='ns'); sx.grid(row=1,column=0,sticky='ew'); f.rowconfigure(0,weight=1); f.columnconfigure(0,weight=1)
    return t

def _dialog(self,title,w=650,h=650): return self.dialog(title,w,h)

def _history_window(self,title,cols,rows):
    w=_dialog(self,title,1000,650); f=ttk.Frame(w,padding=15); f.pack(fill='both',expand=True)
    t=_tree(f,cols,{c:c.replace('_',' ').title() for c in cols},18)
    for r in rows: t.insert('','end',values=tuple(r[c] for c in cols))
    return w,t

def page_riders(self):
    self.title('Riders','Set base/per-KM delivery charges, availability and live delivery tracking.')
    top=ttk.Frame(self.body); top.pack(fill='x',pady=(0,10)); ttk.Button(top,text='+ ADD RIDER',style='Primary.TButton',command=lambda:_rider_editor(self)).pack(side='left'); ttk.Button(top,text='Refresh',command=lambda:self.show('Riders')).pack(side='left',padx=6)
    t=_tree(self.body,('id','name','phone','vehicle','base','per_km','minimum','active'),{'id':'ID','name':'Rider','phone':'Phone','vehicle':'Vehicle','base':'Base Fee','per_km':'Per KM','minimum':'Minimum','active':'Available'},14)
    for r in self.s.rows('SELECT r.*,COALESCE(rr.base_fee,0) base,COALESCE(rr.per_km,0) per_km,COALESCE(rr.minimum_fee,0) minimum FROM riders r LEFT JOIN rider_rates rr ON rr.rider_id=r.id ORDER BY r.name'):
        t.insert('','end',iid=str(r['id']),values=(r['id'],r['name'],r['phone'],r['vehicle'],money(r['base']),money(r['per_km']),money(r['minimum']),'Yes' if r['active'] else 'No'))
    def edit(_=None):
        sel=t.selection()
        if sel:_rider_editor(self,int(sel[0]))
    t.bind('<Double-1>',edit); ttk.Button(self.body,text='EDIT SELECTED / RATE',command=edit).pack(fill='x',pady=8)

def _rider_editor(self,rid=None):
    old=self.s.q('SELECT r.*,COALESCE(rr.base_fee,0) base,COALESCE(rr.per_km,0) per_km,COALESCE(rr.minimum_fee,0) minimum FROM riders r LEFT JOIN rider_rates rr ON rr.rider_id=r.id WHERE r.id=?',(rid,)).fetchone() if rid else None
    w=_dialog(self,'Rider & Delivery Rate',480,620); f=ttk.Frame(w,padding=18); f.pack(fill='both',expand=True)
    vals={}
    fields=[('name','Name'),('phone','Phone'),('vehicle','Vehicle'),('base','Base Fee'),('per_km','Per KM'),('minimum','Minimum Delivery Fee')]
    for k,label in fields:
        ttk.Label(f,text=label).pack(anchor='w',pady=(8,2)); v=tk.StringVar(value=str(old[k] if old else '0' if k in ('base','per_km','minimum') else '')); vals[k]=v; ttk.Entry(f,textvariable=v).pack(fill='x')
    av=tk.BooleanVar(value=bool(old['active']) if old else True); ttk.Checkbutton(f,text='Available for assignment',variable=av).pack(anchor='w',pady=12)
    def save():
        try:
            if not vals['name'].get().strip(): raise ValueError('Rider name is required')
            nums=[float(vals[k].get() or 0) for k in ('base','per_km','minimum')]
            if rid:self.s.q('UPDATE riders SET name=?,phone=?,vehicle=?,active=? WHERE id=?',(vals['name'].get().strip(),vals['phone'].get().strip(),vals['vehicle'].get().strip(),int(av.get()),rid)); rid2=rid
            else:
                cur=self.s.q('INSERT INTO riders(name,phone,vehicle,active) VALUES(?,?,?,?)',(vals['name'].get().strip(),vals['phone'].get().strip(),vals['vehicle'].get().strip(),int(av.get()))); rid2=cur.lastrowid
            self.s.q('INSERT INTO rider_rates(rider_id,base_fee,per_km,minimum_fee,updated_at) VALUES(?,?,?,?,?) ON CONFLICT(rider_id) DO UPDATE SET base_fee=excluded.base_fee,per_km=excluded.per_km,minimum_fee=excluded.minimum_fee,updated_at=excluded.updated_at',(rid2,*nums,now())); self.s.c.commit(); w.destroy(); self.show('Riders')
        except Exception as e: messagebox.showerror('Rider',str(e),parent=w)
    ttk.Button(f,text='SAVE RIDER & RATE',style='Primary.TButton',command=save).pack(fill='x',pady=15)

def page_tables_dine_in(self):
    self.title('Tables / Dine-in','Create tables, see occupancy, open orders and close tables. No tables are planted automatically.')
    top=ttk.Frame(self.body); top.pack(fill='x',pady=(0,10)); ttk.Button(top,text='+ ADD TABLE',style='Primary.TButton',command=lambda:_table_editor(self)).pack(side='left'); ttk.Button(top,text='Refresh',command=lambda:self.show('Tables / Dine-in')).pack(side='left',padx=6)
    t=_tree(self.body,('id','name','seats','status','open_sale','opened_at'),{'id':'ID','name':'Table','seats':'Seats','status':'Status','open_sale':'Open Order','opened_at':'Opened'},14)
    for r in self.s.rows('SELECT t.id,t.name,t.seats,t.status,COALESCE(CAST(ts.sale_id AS TEXT),\'\') open_sale,COALESCE(ts.opened_at,\'\') opened_at FROM tables t LEFT JOIN table_sessions ts ON ts.table_id=t.id AND ts.status=\'Open\' ORDER BY t.name'):
        t.insert('','end',iid=str(r['id']),values=(r['id'],r['name'],r['seats'],r['status'],r['open_sale'],r['opened_at']))
    def open_table():
        sel=t.selection()
        if not sel:return
        _open_table(self,int(sel[0]))
    def history(_=None):
        sel=t.selection()
        if not sel:return
        r=self.s.q('SELECT * FROM tables WHERE id=?',(int(sel[0]),)).fetchone(); rows=self.s.rows('SELECT s.invoice_no,s.created_at,s.status,s.total,s.payment_status,c.name customer FROM sales s LEFT JOIN customers c ON c.id=s.customer_id WHERE s.table_no=? ORDER BY s.id DESC',(r['name'],)); _history_window(self,f"{r['name']} — Order History",('invoice_no','created_at','status','total','payment_status','customer'),rows)
    t.bind('<Double-1>',history); ttk.Button(self.body,text='OPEN / MANAGE SELECTED TABLE',style='Primary.TButton',command=open_table).pack(fill='x',pady=8); ttk.Label(self.body,text='Double-click a table to view every order previously served there.',foreground='#64748b').pack(anchor='w')

def _table_editor(self):
    w=_dialog(self,'Add Table',420,300); f=ttk.Frame(w,padding=18); f.pack(fill='both',expand=True); nv=tk.StringVar(); sv=tk.IntVar(value=2); ttk.Label(f,text='Table Name').pack(anchor='w'); ttk.Entry(f,textvariable=nv).pack(fill='x'); ttk.Label(f,text='Seats').pack(anchor='w',pady=(10,2)); ttk.Spinbox(f,from_=1,to=100,textvariable=sv).pack(fill='x')
    def save():
        try:self.s.q('INSERT INTO tables(name,seats) VALUES(?,?)',(nv.get().strip(),sv.get()));self.s.c.commit();w.destroy();self.show('Tables / Dine-in')
        except Exception as e:messagebox.showerror('Table',str(e),parent=w)
    ttk.Button(f,text='SAVE TABLE',style='Primary.TButton',command=save).pack(fill='x',pady=15)

def _open_table(self,tid):
    r=self.s.q('SELECT * FROM tables WHERE id=?',(tid,)).fetchone(); existing=self.s.q('SELECT * FROM table_sessions WHERE table_id=? AND status=\'Open\'',(tid,)).fetchone()
    if existing:
        messagebox.showinfo('Table',f"{r['name']} is open on order #{existing['sale_id'] or 'pending'}. Use Orders to manage the order.",parent=self); return
    w=_dialog(self,f"Open {r['name']}",440,360); f=ttk.Frame(w,padding=18);f.pack(fill='both',expand=True); gv=tk.IntVar(value=1); cv=tk.StringVar(); cust=self.s.rows('SELECT id,name,phone FROM customers WHERE active=1 ORDER BY name'); cmap={f"{x['name']} | {x['phone']}":x['id'] for x in cust}; ttk.Label(f,text='Guests').pack(anchor='w');ttk.Spinbox(f,from_=1,to=r['seats'] or 99,textvariable=gv).pack(fill='x');ttk.Label(f,text='Customer (optional)').pack(anchor='w',pady=(10,2));ttk.Combobox(f,textvariable=cv,values=list(cmap),state='readonly').pack(fill='x')
    def save():
        cid=cmap.get(cv.get());self.s.q('INSERT INTO table_sessions(table_id,customer_id,opened_at,status,guest_count) VALUES(?,?,?,?,?)',(tid,cid,now(),'Open',gv.get()));self.s.q('UPDATE tables SET status=\'Occupied\' WHERE id=?',(tid,));self.s.c.commit();w.destroy();self.show('Tables / Dine-in')
    ttk.Button(f,text='OPEN TABLE',style='Primary.TButton',command=save).pack(fill='x',pady=18)

def page_orders(self):
    self.title('Orders','Every order is clickable. Open an order to see items, status timeline, payment, delivery tracking and print options.')
    top=ttk.Frame(self.body);top.pack(fill='x',pady=(0,8));q=tk.StringVar();ttk.Entry(top,textvariable=q).pack(side='left',fill='x',expand=True);ttk.Button(top,text='Refresh',command=lambda:self.show('Orders')).pack(side='left',padx=5)
    t=_tree(self.body,('id','invoice_no','created_at','order_type','customer','rider','status','total','payment_status'),{'id':'ID','invoice_no':'Invoice','created_at':'Date','order_type':'Type','customer':'Customer','rider':'Rider','status':'Kitchen','total':'Total','payment_status':'Payment'},15)
    rows=self.s.rows('SELECT s.*,COALESCE(c.name,\'Walk-in\') customer,COALESCE(r.name,\'\') rider FROM sales s LEFT JOIN customers c ON c.id=s.customer_id LEFT JOIN riders r ON r.id=s.rider_id ORDER BY s.id DESC')
    for r in rows:
        t.insert('','end',iid=str(r['id']),values=(r['id'],r['invoice_no'],r['created_at'],r['order_type'],r['customer'],r['rider'],r['status'],money(r['total']),r['payment_status']))
    def open_order(_=None):
        sel=t.selection()
        if sel:_order_detail(self,int(sel[0]))
    t.bind('<Double-1>',open_order); ttk.Button(self.body,text='OPEN / EXPAND SELECTED ORDER',style='Primary.TButton',command=open_order).pack(fill='x',pady=8)

def _order_detail(self,sid):
    s=self.s.q('SELECT s.*,COALESCE(c.name,\'Walk-in\') customer,COALESCE(c.phone,\'\') phone,COALESCE(c.address,\'\') address,COALESCE(r.name,\'\') rider FROM sales s LEFT JOIN customers c ON c.id=s.customer_id LEFT JOIN riders r ON r.id=s.rider_id WHERE s.id=?',(sid,)).fetchone()
    if not s:return
    w=_dialog(self,f"Order {s['invoice_no']}",900,760); f=ttk.Frame(w,padding=15);f.pack(fill='both',expand=True)
    info=ttk.LabelFrame(f,text='Order',padding=10);info.pack(fill='x');ttk.Label(info,text=f"{s['invoice_no']}  •  {s['order_type']}  •  {s['created_at']}  •  {s['customer']}").pack(anchor='w');ttk.Label(info,text=f"Status: {s['status']}    Payment: {s['payment_status']}    Total: {money(s['total'])}").pack(anchor='w',pady=3);ttk.Label(info,text=f"Delivery: {s['delivery_address'] or s['address'] or '-'}    Rider: {s['rider'] or '-'}").pack(anchor='w')
    items=_tree(f,('name','qty','unit','total'),{'name':'Product','qty':'Qty','unit':'Unit','total':'Total'},8)
    for x in self.s.rows('SELECT * FROM sale_items WHERE sale_id=?',(sid,)):items.insert('','end',values=(x['product_name'],x['quantity'],money(x['unit_price']),money(x['line_total'])))
    buttons=ttk.Frame(f);buttons.pack(fill='x',pady=8)
    for status in ('New','Preparing','Ready','Completed','Cancelled'):
        ttk.Button(buttons,text=status,command=lambda st=status:_set_order_status(self,sid,st,w)).pack(side='left',padx=2)
    ttk.Button(buttons,text='COLLECT PAYMENT',style='Primary.TButton',command=lambda:_collect_payment(self,sid,w)).pack(side='right',padx=4);ttk.Button(buttons,text='PRINT RECEIPT',command=lambda:_print_order(self,sid)).pack(side='right',padx=4)
    if s['order_type']=='Delivery':
        tr=_tree(f,('status','latitude','longitude','note','created_at'),{'status':'Tracking','latitude':'Latitude','longitude':'Longitude','note':'Note','created_at':'Time'},6)
        for x in self.s.rows('SELECT * FROM delivery_tracking WHERE sale_id=? ORDER BY id DESC',(sid,)):tr.insert('','end',values=(x['status'],x['latitude'],x['longitude'],x['note'],x['created_at']))
        ttk.Button(f,text='ADD DELIVERY TRACKING EVENT',command=lambda:_tracking_event(self,sid,w)).pack(fill='x',pady=5)

def _set_order_status(self,sid,status,w=None):
    self.s.q('UPDATE sales SET status=? WHERE id=?',(status,sid));self.s.q('INSERT INTO order_events(sale_id,status,note,created_at,user_id) VALUES(?,?,?,?,?)',(sid,status,'',now(),self.user['id']))
    if status=='Completed':
        s=self.s.q('SELECT table_no FROM sales WHERE id=?',(sid,)).fetchone()
        if s and s['table_no']: self.s.q('UPDATE tables SET status=\'Available\' WHERE name=?',(s['table_no'],));self.s.q('UPDATE table_sessions SET status=\'Closed\',closed_at=? WHERE sale_id=?',(now(),sid))
    self.s.c.commit();
    if w:w.destroy()
    self.show('Orders')

def _collect_payment(self,sid,parent=None):
    s=self.s.q('SELECT total,payment_status,customer_id FROM sales WHERE id=?',(sid,)).fetchone(); paid=float(self.s.q('SELECT COALESCE(SUM(amount),0) x FROM payments WHERE sale_id=?',(sid,)).fetchone()['x']); due=max(0,float(s['total'])-paid)
    if due<=0: messagebox.showinfo('Payment','This order is already fully paid.',parent=parent or self);return
    w=_dialog(self,'Collect Payment',440,400);f=ttk.Frame(w,padding=18);f.pack(fill='both',expand=True);ttk.Label(f,text=f'Amount due: {money(due)}',font=('Segoe UI',18,'bold')).pack(anchor='w',pady=8); av=tk.StringVar(value=f'{due:.2f}');mv=tk.StringVar(value='Cash');rv=tk.StringVar();ttk.Label(f,text='Amount').pack(anchor='w');ttk.Entry(f,textvariable=av).pack(fill='x');ttk.Label(f,text='Method').pack(anchor='w',pady=(10,2));ttk.Combobox(f,textvariable=mv,values=['Cash','Card','Other'],state='readonly').pack(fill='x');ttk.Label(f,text='Reference').pack(anchor='w',pady=(10,2));ttk.Entry(f,textvariable=rv).pack(fill='x')
    def save():
        try:
            amount=float(av.get());
            if amount<=0 or amount>due+0.001: raise ValueError('Amount must be positive and not exceed the remaining due.')
            self.s.q('INSERT INTO payments(sale_id,method,amount,reference,created_at,user_id) VALUES(?,?,?,?,?,?)',(sid,mv.get(),amount,rv.get().strip(),now(),self.user['id'])); remain=due-amount;self.s.q('UPDATE sales SET payment_status=? WHERE id=?',('Paid' if remain<=0.001 else 'Partially Paid',sid));
            if remain<=0.001:self.s.q('UPDATE sales SET status=CASE WHEN status=\'Ready\' THEN \'Completed\' ELSE status END WHERE id=?',(sid,))
            self.s.c.commit();w.destroy();
            if parent:parent.destroy()
            self.show('Orders')
        except Exception as e:messagebox.showerror('Payment',str(e),parent=w)
    ttk.Button(f,text='SAVE PAYMENT',style='Primary.TButton',command=save).pack(fill='x',pady=18)

def _tracking_event(self,sid,parent=None):
    w=_dialog(self,'Delivery Tracking',460,480);f=ttk.Frame(w,padding=18);f.pack(fill='both',expand=True);sv=tk.StringVar(value='Assigned');lat=tk.StringVar();lon=tk.StringVar();note=tk.StringVar();ttk.Label(f,text='Status').pack(anchor='w');ttk.Combobox(f,textvariable=sv,values=['Assigned','Picked Up','Out for Delivery','Near Customer','Delivered','Failed','Returned'],state='readonly').pack(fill='x');
    for var,label in ((lat,'Latitude'),(lon,'Longitude'),(note,'Note / Location')):ttk.Label(f,text=label).pack(anchor='w',pady=(10,2));ttk.Entry(f,textvariable=var).pack(fill='x')
    def save():
        rider=self.s.q('SELECT rider_id FROM sales WHERE id=?',(sid,)).fetchone()['rider_id'];self.s.q('INSERT INTO delivery_tracking(sale_id,status,latitude,longitude,note,rider_id,created_at,user_id) VALUES(?,?,?,?,?,?,?,?)',(sid,sv.get(),lat.get(),lon.get(),note.get(),rider,now(),self.user['id']));self.s.q('UPDATE sales SET tracking_status=? WHERE id=?',(sv.get(),sid));self.s.c.commit();w.destroy();_order_detail(self,sid)
    ttk.Button(f,text='SAVE TRACKING EVENT',style='Primary.TButton',command=save).pack(fill='x',pady=18)

def _print_order(self,sid):
    s=self.s.q('SELECT s.*,COALESCE(c.name,\'Walk-in\') customer FROM sales s LEFT JOIN customers c ON c.id=s.customer_id WHERE s.id=?',(sid,)).fetchone();items=self.s.rows('SELECT * FROM sale_items WHERE sale_id=?',(sid,));
    lines=['\x1b@','\x1ba\x01',BUSINESS['name'],BUSINESS['address'],BUSINESS['phone'],'-'*32,s['invoice_no'],f"{s['created_at']}  {s['order_type']}",f"Customer: {s['customer']}",'--------------------------------']
    for x in items: lines.append(f"{x['product_name'][:20]:20} {x['quantity']:>4g} {float(x['line_total']):>8.2f}")
    lines += ['--------------------------------',f"TOTAL: {float(s['total']):.2f}",f"PAYMENT: {s['payment_status']}",'','Thank you!','\x1dV\x00']; data='\n'.join(lines).encode('ascii','replace')
    try:self.pm.write_raw(data);messagebox.showinfo('Printer','Receipt sent to printer.',parent=self)
    except Exception as e:messagebox.showerror('Printer',str(e),parent=self)

def checkout(self):
    if not self.cart:return messagebox.showwarning('Order','Add products first.',parent=self)
    w=_dialog(self,'Checkout — Customer / Delivery / Table / Payment',620,760);f=ttk.Frame(w,padding=20);f.pack(fill='both',expand=True)
    cust=self.s.rows('SELECT * FROM customers WHERE active=1 ORDER BY name');cmap={f"{r['name']} | {r['phone']}":r['id'] for r in cust};cv=tk.StringVar();cb=ttk.Combobox(f,textvariable=cv,values=list(cmap),state='readonly');ttk.Label(f,text='Customer (save even for takeaway/dine-in)');ttk.Label(f,text='Customer').pack(anchor='w');cb.pack(fill='x');
    ttk.Button(f,text='+ New Customer',command=lambda:self.quick_customer(cv,cb,cmap)).pack(anchor='e',pady=4)
    ov=tk.StringVar(value='Counter');ttk.Label(f,text='Order Type').pack(anchor='w',pady=(8,2));ttk.Combobox(f,textvariable=ov,values=['Counter','Takeaway','Dine-in','Delivery'],state='readonly').pack(fill='x')
    tv=tk.StringVar();gv=tk.IntVar(value=1);ttk.Label(f,text='Table (Dine-in)').pack(anchor='w',pady=(8,2));ttk.Entry(f,textvariable=tv).pack(fill='x');ttk.Label(f,text='Guests').pack(anchor='w');ttk.Spinbox(f,from_=1,to=99,textvariable=gv).pack(fill='x')
    riders=self.s.rows('SELECT r.*,COALESCE(rr.base_fee,0) base,COALESCE(rr.per_km,0) per_km,COALESCE(rr.minimum_fee,0) minimum FROM riders r LEFT JOIN rider_rates rr ON rr.rider_id=r.id WHERE r.active=1 ORDER BY r.name');rmap={f"{r['name']} | {r['phone']}":r['id'] for r in riders};rv=tk.StringVar();rd=ttk.Combobox(f,textvariable=rv,values=list(rmap),state='readonly');ttk.Label(f,text='Rider (Delivery)').pack(anchor='w',pady=(8,2));rd.pack(fill='x');
    km=tk.DoubleVar(value=0);ttk.Label(f,text='Distance KM').pack(anchor='w',pady=(8,2));ttk.Spinbox(f,from_=0,to=999,increment=.1,textvariable=km).pack(fill='x');fee=tk.StringVar(value='0.00');ttk.Label(f,text='Delivery Fee (calculated)');ttk.Label(f,textvariable=fee,font=('Segoe UI',11,'bold')).pack(anchor='w')
    def calc(*_):
        rid=rmap.get(rv.get());rr=self.s.q('SELECT * FROM rider_rates WHERE rider_id=?',(rid,)).fetchone() if rid else None;amount=max(float(rr['minimum_fee']),float(rr['base_fee'])+float(rr['per_km'])*float(km.get())) if rr else 0;fee.set(f'{amount:.2f}')
    rd.bind('<<ComboboxSelected>>',calc);km.trace_add('write',calc)
    pay=tk.StringVar(value='Cash');ttk.Label(f,text='Payment').pack(anchor='w',pady=(8,2));ttk.Combobox(f,textvariable=pay,values=['Cash','Card','Other','Credit','Pay when Ready'],state='readonly').pack(fill='x')
    discount=tk.DoubleVar(value=0);ttk.Label(f,text='Discount');ttk.Entry(f,textvariable=discount).pack(fill='x');notes=tk.StringVar();ttk.Label(f,text='Notes').pack(anchor='w');ttk.Entry(f,textvariable=notes).pack(fill='x')
    def save():
        try:
            subtotal=sum(float(i['qty'])*float(i['price']) for i in self.cart.values());disc=max(0,float(discount.get()));delivery=float(fee.get()) if ov.get()=='Delivery' else 0;total=max(0,subtotal-disc+delivery);cid=cmap.get(cv.get());rid=rmap.get(rv.get()) if ov.get()=='Delivery' else None;inv=f"MK-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{self.s.q('SELECT COALESCE(MAX(id),0)+1 x FROM sales').fetchone()['x']}";ps='Paid' if pay.get() in ('Cash','Card','Other') else 'Unpaid';status='New';addr='';
            if ov.get()=='Delivery' and cid:addr=self.s.q('SELECT address FROM customers WHERE id=?',(cid,)).fetchone()['address'] or ''
            cur=self.s.q('INSERT INTO sales(invoice_no,user_id,customer_id,rider_id,subtotal,tax,total,payment_method,payment_status,created_at,status,discount,order_type,table_no,guest_count,notes,delivery_address,rider_base_fee,rider_per_km,delivery_distance_km,delivery_fee,tracking_status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(inv,self.user['id'],cid,rid,subtotal,0,total,pay.get(),ps,now(),status,disc,ov.get(),tv.get().strip(),gv.get(),notes.get().strip(),addr,0,0,float(km.get()) if ov.get()=='Delivery' else 0,delivery,'Assigned' if rid else 'Pending'))
            sid=cur.lastrowid
            for i in self.cart.values():self.s.q('INSERT INTO sale_items(sale_id,product_id,product_name,quantity,unit_price,line_total) VALUES(?,?,?,?,?,?)',(sid,i['id'],i['name'],i['qty'],i['price'],i['qty']*i['price']));self.s.q('UPDATE products SET stock=stock-? WHERE id=?',(i['qty'],i['id']));self.s.q('INSERT INTO stock_movements(product_id,qty,movement_type,note,created_at,user_id) VALUES(?,?,?,?,?,?)',(i['id'],-i['qty'],'SALE',inv,now(),self.user['id']))
            self.s.q('INSERT INTO order_events(sale_id,status,note,created_at,user_id) VALUES(?,?,?,?,?)',(sid,'New','Sent to Kitchen',now(),self.user['id']))
            if ps=='Paid':self.s.q('INSERT INTO payments(sale_id,method,amount,created_at,user_id) VALUES(?,?,?,?,?)',(sid,pay.get(),total,now(),self.user['id']))
            if ov.get()=='Dine-in' and tv.get().strip():self.s.q('UPDATE tables SET status=\'Occupied\' WHERE name=?',(tv.get().strip(),));self.s.q('UPDATE table_sessions SET sale_id=? WHERE table_id=(SELECT id FROM tables WHERE name=?) AND status=\'Open\'',(sid,tv.get().strip()))
            self.s.c.commit();self.cart.clear();w.destroy();self.show('Orders');messagebox.showinfo('Kitchen',f'{inv} sent to Kitchen as New.',parent=self)
        except Exception as e:messagebox.showerror('Checkout failed',str(e),parent=w)
    ttk.Button(f,text='SEND ORDER TO KITCHEN',style='Primary.TButton',command=save).pack(fill='x',pady=18)

def page_customers(self):
    self.title('Customers','Double-click any customer for complete order, payment, due and advance history.')
    t=_tree(self.body,('id','name','phone','address','balance'),{'id':'ID','name':'Customer','phone':'Phone','address':'Address','balance':'Balance'},16)
    for r in self.s.rows('SELECT * FROM customers WHERE active=1 ORDER BY name'):t.insert('','end',iid=str(r['id']),values=(r['id'],r['name'],r['phone'],r['address'],money(r['balance'])))
    def detail(_=None):
        sel=t.selection()
        if not sel:return
        cid=int(sel[0]);r=self.s.q('SELECT * FROM customers WHERE id=?',(cid,)).fetchone();rows=self.s.rows('SELECT invoice_no,created_at,order_type,status,total,payment_status FROM sales WHERE customer_id=? ORDER BY id DESC',(cid,));_history_window(self,f"Customer: {r['name']} — Full Order History",('invoice_no','created_at','order_type','status','total','payment_status'),rows)
    t.bind('<Double-1>',detail);ttk.Button(self.body,text='OPEN FULL HISTORY',command=detail).pack(fill='x',pady=8)

def page_products(self):
    self.title('Products','Double-click a product for sales, stock movement and price history.')
    t=_tree(self.body,('id','name','category','price','cost','stock','barcode'),{'id':'ID','name':'Product','category':'Category','price':'Price','cost':'Cost','stock':'Stock','barcode':'Barcode'},16)
    for r in self.s.rows('SELECT * FROM products WHERE active=1 ORDER BY category,name'):t.insert('','end',iid=str(r['id']),values=(r['id'],r['name'],r['category'],money(r['price']),money(r['cost']),r['stock'],r['barcode']))
    def detail(_=None):
        sel=t.selection()
        if not sel:return
        pid=int(sel[0]);r=self.s.q('SELECT * FROM products WHERE id=?',(pid,)).fetchone();w=_dialog(self,f"Product: {r['name']}",1000,650);f=ttk.Frame(w,padding=15);f.pack(fill='both',expand=True);ttk.Label(f,text=f"{r['name']} • Current stock: {r['stock']} • Price: {money(r['price'])}",font=('Segoe UI',15,'bold')).pack(anchor='w',pady=8);x=_tree(f,('created_at','type','qty','note'),{'created_at':'Date','type':'Movement','qty':'Qty','note':'Reference'},15)
        for m in self.s.rows('SELECT created_at,movement_type type,qty,note FROM stock_movements WHERE product_id=? ORDER BY id DESC',(pid,)):x.insert('','end',values=(m['created_at'],m['type'],m['qty'],m['note']))
        ttk.Button(f,text='PRINT PRODUCT HISTORY',command=lambda:_print_text(self,f"PRODUCT {r['name']}",[(m['created_at'],m['movement_type'],m['qty'],m['note']) for m in self.s.rows('SELECT created_at,movement_type,qty,note FROM stock_movements WHERE product_id=? ORDER BY id DESC',(pid,))])).pack(fill='x',pady=8)
    t.bind('<Double-1>',detail);ttk.Button(self.body,text='OPEN PRODUCT HISTORY',command=detail).pack(fill='x',pady=8)

def page_suppliers(self):
    self.title('Suppliers','Double-click any supplier to inspect purchases, payments and balance history.')
    t=_tree(self.body,('id','name','phone','address','balance'),{'id':'ID','name':'Supplier','phone':'Phone','address':'Address','balance':'Balance'},16)
    for r in self.s.rows('SELECT * FROM suppliers WHERE active=1 ORDER BY name'):t.insert('','end',iid=str(r['id']),values=(r['id'],r['name'],r['phone'],r['address'],money(r['balance'])))
    def detail(_=None):
        sel=t.selection()
        if not sel:return
        sid=int(sel[0]);r=self.s.q('SELECT * FROM suppliers WHERE id=?',(sid,)).fetchone();rows=self.s.rows('SELECT txn_type,amount,note,created_at FROM party_transactions WHERE party_type=\'supplier\' AND party_id=? ORDER BY id DESC',(sid,));_history_window(self,f"Supplier: {r['name']} — Transaction History",('txn_type','amount','note','created_at'),rows)
    t.bind('<Double-1>',detail);ttk.Button(self.body,text='OPEN FULL HISTORY',command=detail).pack(fill='x',pady=8)

def _print_text(self,title,rows):
    try:
        lines=['\x1b@','\x1ba\x01',BUSINESS['name'],title,'-'*32]
        lines += [' | '.join(str(x) for x in r) for r in rows];lines += ['','\x1dV\x00'];self.pm.write_raw('\n'.join(lines).encode('ascii','replace'));messagebox.showinfo('Printer','Sent to printer.',parent=self)
    except Exception as e:messagebox.showerror('Printer',str(e),parent=self)
