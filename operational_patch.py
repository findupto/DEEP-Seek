import sqlite3
from datetime import datetime
from tkinter import ttk, messagebox

def install(App):
    if getattr(App,'_operational_patch_installed',False): return
    old_init=App.__init__
    def init(self,*a,**kw):
        old_init(self,*a,**kw)
        self.s.c.executescript('''
        CREATE TRIGGER IF NOT EXISTS trg_sale_rider_rate AFTER INSERT ON sales
        WHEN NEW.rider_id IS NOT NULL
        BEGIN
          UPDATE sales SET rider_base_fee=COALESCE((SELECT base_fee FROM rider_rates WHERE rider_id=NEW.rider_id),0), rider_per_km=COALESCE((SELECT per_km FROM rider_rates WHERE rider_id=NEW.rider_id),0) WHERE id=NEW.id;
        END;
        ''')
        self.s.c.commit()
    App.__init__=init
    App.page_kitchen=page_kitchen
    App._operational_patch_installed=True

def page_kitchen(self):
    self.title('Kitchen Display','Live kitchen queue. Select an order and move it New → Preparing → Ready → Completed.')
    top=ttk.Frame(self.body);top.pack(fill='x',pady=(0,8));ttk.Button(top,text='REFRESH',command=lambda:self.show('Kitchen')).pack(side='left');ttk.Button(top,text='PREPARING',style='Primary.TButton',command=lambda:_move(self,'Preparing',t)).pack(side='left',padx=5);ttk.Button(top,text='READY',command=lambda:_move(self,'Ready',t)).pack(side='left',padx=5);ttk.Button(top,text='COMPLETED',command=lambda:_move(self,'Completed',t)).pack(side='left',padx=5);ttk.Button(top,text='OPEN ORDER',command=lambda:_open(self,t)).pack(side='right')
    t=ttk.Treeview(self.body,columns=('id','invoice','time','type','customer','items','status','payment'),show='headings',height=18);heads={'id':'ID','invoice':'Invoice','time':'Time','type':'Type','customer':'Customer','items':'Items','status':'Kitchen Status','payment':'Payment'}
    for c in t['columns']:t.heading(c,text=heads[c]);t.column(c,width=130)
    sy=ttk.Scrollbar(self.body,orient='vertical',command=t.yview);t.configure(yscrollcommand=sy.set);t.pack(side='left',fill='both',expand=True);sy.pack(side='right',fill='y')
    rows=self.s.rows("SELECT s.id,s.invoice_no,s.created_at,s.order_type,COALESCE(c.name,'Walk-in') customer,s.status,s.payment_status,COALESCE((SELECT GROUP_CONCAT(si.product_name||' x'||si.quantity, ', ') FROM sale_items si WHERE si.sale_id=s.id),'') items FROM sales s LEFT JOIN customers c ON c.id=s.customer_id WHERE s.status IN ('New','Preparing','Ready') ORDER BY s.id ASC")
    for r in rows:t.insert('','end',iid=str(r['id']),values=(r['id'],r['invoice_no'],r['created_at'],r['order_type'],r['customer'],r['items'],r['status'],r['payment_status']))

def _move(self,status,t):
    sel=t.selection()
    if not sel:return messagebox.showwarning('Kitchen','Select an order first.',parent=self)
    sid=int(sel[0]);self.s.q('UPDATE sales SET status=? WHERE id=?',(status,sid));self.s.q('INSERT INTO order_events(sale_id,status,note,created_at,user_id) VALUES(?,?,?,?,?)',(sid,status,'Kitchen update',datetime.now().isoformat(timespec='seconds'),self.user['id']));self.s.c.commit();self.show('Kitchen')

def _open(self,t):
    sel=t.selection()
    if not sel:return messagebox.showwarning('Kitchen','Select an order first.',parent=self)
    # Use the operational order detail already installed by advanced_features.
    import advanced_features
    advanced_features._order_detail(self,int(sel[0]))
