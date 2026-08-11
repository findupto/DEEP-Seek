"""Enterprise POS completion layer: offline sync, CRM loyalty/gift cards,
attendance, receipt delivery, employee analytics, and integration queues.
All features are local-first and provider-neutral; external providers are queued
until credentials/connectors are configured.
"""
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import json


def now(): return datetime.now().isoformat(timespec="seconds")
def money(v): return f"Rs. {float(v or 0):,.2f}"

SCHEMA = """
CREATE TABLE IF NOT EXISTS offline_queue(id INTEGER PRIMARY KEY AUTOINCREMENT, operation TEXT NOT NULL, entity TEXT, entity_id INTEGER, payload TEXT NOT NULL, status TEXT DEFAULT 'PENDING', attempts INTEGER DEFAULT 0, last_error TEXT DEFAULT '', created_at TEXT NOT NULL, synced_at TEXT);
CREATE INDEX IF NOT EXISTS idx_offline_queue_status ON offline_queue(status,created_at);
CREATE TABLE IF NOT EXISTS loyalty_accounts(id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER UNIQUE NOT NULL, points REAL DEFAULT 0, tier TEXT DEFAULT 'STANDARD', lifetime_spend REAL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS loyalty_transactions(id INTEGER PRIMARY KEY AUTOINCREMENT, loyalty_id INTEGER NOT NULL, points REAL NOT NULL, transaction_type TEXT NOT NULL, sale_id INTEGER, note TEXT DEFAULT '', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS gift_cards(id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE NOT NULL, initial_value REAL NOT NULL, balance REAL NOT NULL, status TEXT DEFAULT 'ACTIVE', customer_id INTEGER, expires_at TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS gift_card_transactions(id INTEGER PRIMARY KEY AUTOINCREMENT, gift_card_id INTEGER NOT NULL, amount REAL NOT NULL, transaction_type TEXT NOT NULL, sale_id INTEGER, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS attendance(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, store_id INTEGER, clock_in TEXT NOT NULL, clock_out TEXT, note TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS receipt_delivery_queue(id INTEGER PRIMARY KEY AUTOINCREMENT, sale_id INTEGER, channel TEXT NOT NULL, destination TEXT NOT NULL, status TEXT DEFAULT 'PENDING', attempts INTEGER DEFAULT 0, last_error TEXT DEFAULT '', created_at TEXT NOT NULL, sent_at TEXT);
CREATE TABLE IF NOT EXISTS notification_preferences(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, event_type TEXT NOT NULL, channel TEXT NOT NULL, enabled INTEGER DEFAULT 1, UNIQUE(user_id,event_type,channel));
CREATE TABLE IF NOT EXISTS integration_queue(id INTEGER PRIMARY KEY AUTOINCREMENT, provider TEXT NOT NULL, operation TEXT NOT NULL, payload TEXT NOT NULL, status TEXT DEFAULT 'PENDING', attempts INTEGER DEFAULT 0, last_error TEXT DEFAULT '', created_at TEXT NOT NULL, completed_at TEXT);
CREATE TABLE IF NOT EXISTS employee_sales_summary(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, sale_id INTEGER NOT NULL, amount REAL DEFAULT 0, created_at TEXT NOT NULL, UNIQUE(user_id,sale_id));
"""


def install(App):
    if getattr(App, '_enterprise_pos_features_installed', False): return App
    old_init = App.__init__
    def init(self,*args,**kwargs):
        old_init(self,*args,**kwargs)
        self.s.c.executescript(SCHEMA)
        self.s.c.commit()
    App.__init__=init

    def queue_offline(self,operation,entity=None,entity_id=None,payload=None):
        self.s.q('INSERT INTO offline_queue(operation,entity,entity_id,payload,created_at) VALUES(?,?,?,?,?)',(operation,entity,entity_id,json.dumps(payload or {}),now())); self.s.c.commit()
    def pending_offline(self): return self.s.rows("SELECT * FROM offline_queue WHERE status='PENDING' ORDER BY id")
    def mark_offline_synced(self,row_id): self.s.q("UPDATE offline_queue SET status='SYNCED',synced_at=? WHERE id=?",(now(),row_id)); self.s.c.commit()
    App.queue_offline=queue_offline; App.pending_offline=pending_offline; App.mark_offline_synced=mark_offline_synced

    def add_loyalty_points(self,customer_id,points,transaction_type='EARN',sale_id=None,note=''):
        r=self.s.q('SELECT id FROM loyalty_accounts WHERE customer_id=?',(customer_id,)).fetchone()
        if r: lid=r['id']; self.s.q('UPDATE loyalty_accounts SET points=points+?,updated_at=? WHERE id=?',(points,now(),lid))
        else:
            cur=self.s.q('INSERT INTO loyalty_accounts(customer_id,points,created_at,updated_at) VALUES(?,?,?,?)',(customer_id,points,now(),now())); lid=cur.lastrowid
        self.s.q('INSERT INTO loyalty_transactions(loyalty_id,points,transaction_type,sale_id,note,created_at) VALUES(?,?,?,?,?,?)',(lid,points,transaction_type,sale_id,note,now())); self.s.c.commit(); return lid
    def redeem_loyalty_points(self,customer_id,points,sale_id=None):
        r=self.s.q('SELECT id,points FROM loyalty_accounts WHERE customer_id=?',(customer_id,)).fetchone()
        if not r or float(r['points'])<float(points): raise ValueError('Insufficient loyalty points')
        return self.add_loyalty_points(customer_id,-float(points),'REDEEM',sale_id,'Points redeemed')
    App.add_loyalty_points=add_loyalty_points; App.redeem_loyalty_points=redeem_loyalty_points

    def issue_gift_card(self,code,value,customer_id=None,expires_at=None):
        self.s.q('INSERT INTO gift_cards(code,initial_value,balance,customer_id,expires_at,created_at) VALUES(?,?,?,?,?,?)',(code,float(value),float(value),customer_id,expires_at,now())); self.s.c.commit()
    def redeem_gift_card(self,code,amount,sale_id=None):
        r=self.s.q('SELECT id,balance,status,expires_at FROM gift_cards WHERE code=?',(code,)).fetchone()
        if not r or r['status']!='ACTIVE': raise ValueError('Gift card is unavailable')
        if r['expires_at'] and r['expires_at']<now(): raise ValueError('Gift card expired')
        if float(r['balance'])<float(amount): raise ValueError('Insufficient gift card balance')
        self.s.q('UPDATE gift_cards SET balance=balance-? WHERE id=?',(float(amount),r['id']))
        self.s.q('INSERT INTO gift_card_transactions(gift_card_id,amount,transaction_type,sale_id,created_at) VALUES(?,?,?,?,?)',(r['id'],float(amount),'REDEEM',sale_id,now())); self.s.c.commit(); return float(r['balance'])-float(amount)
    App.issue_gift_card=issue_gift_card; App.redeem_gift_card=redeem_gift_card

    def clock_in(self,user_id,store_id=None):
        open_row=self.s.q('SELECT id FROM attendance WHERE user_id=? AND clock_out IS NULL',(user_id,)).fetchone()
        if open_row: raise ValueError('Employee is already clocked in')
        cur=self.s.q('INSERT INTO attendance(user_id,store_id,clock_in) VALUES(?,?,?)',(user_id,store_id,now())); self.s.c.commit(); return cur.lastrowid
    def clock_out(self,user_id):
        r=self.s.q('SELECT id FROM attendance WHERE user_id=? AND clock_out IS NULL ORDER BY id DESC LIMIT 1',(user_id,)).fetchone()
        if not r: raise ValueError('Employee is not clocked in')
        self.s.q('UPDATE attendance SET clock_out=? WHERE id=?',(now(),r['id'])); self.s.c.commit()
    App.clock_in=clock_in; App.clock_out=clock_out

    def queue_receipt(self,sale_id,channel,destination):
        if channel not in ('EMAIL','SMS','PRINT'): raise ValueError('Unsupported receipt channel')
        self.s.q('INSERT INTO receipt_delivery_queue(sale_id,channel,destination,created_at) VALUES(?,?,?,?)',(sale_id,channel,destination,now())); self.s.c.commit()
    App.queue_receipt=queue_receipt

    def page_enterprise_pos_features(self):
        self.title('Enterprise POS Operations','Offline queue, loyalty, gift cards, attendance, receipts and integrations.')
        book=ttk.Notebook(self.bodyinner);book.pack(fill='both',expand=True)
        tabs={k:ttk.Frame(book,padding=10) for k in ('Offline Sync','Loyalty','Gift Cards','Attendance','Receipts','Employee Sales')}
        for k,f in tabs.items(): book.add(f,text=k)
        # Offline sync
        t=ttk.Treeview(tabs['Offline Sync'],columns=('id','operation','entity','status','created'),show='headings');
        for c,h in zip(t['columns'],('ID','Operation','Entity','Status','Created')):t.heading(c,text=h);t.column(c,width=160)
        t.pack(fill='both',expand=True)
        def reload_q():
            t.delete(*t.get_children())
            for r in self.s.rows('SELECT id,operation,entity,status,created_at FROM offline_queue ORDER BY id DESC LIMIT 500'):t.insert('','end',values=tuple(r))
        ttk.Button(tabs['Offline Sync'],text='REFRESH QUEUE',command=reload_q).pack(fill='x',pady=5);reload_q()
        ttk.Label(tabs['Offline Sync'],text='Sales remain local-first. External cloud/provider synchronization is queued and can be processed when connectivity/provider credentials are available.',wraplength=800).pack(anchor='w',pady=8)
        # Loyalty
        lt=ttk.Treeview(tabs['Loyalty'],columns=('customer','points','tier','spend'),show='headings');
        for c,h in zip(lt['columns'],('Customer ID','Points','Tier','Lifetime Spend')):lt.heading(c,text=h)
        lt.pack(fill='both',expand=True)
        for r in self.s.rows('SELECT customer_id,points,tier,lifetime_spend FROM loyalty_accounts ORDER BY points DESC LIMIT 500'):lt.insert('','end',values=(r['customer_id'],r['points'],r['tier'],money(r['lifetime_spend'])))
        # Gift cards
        gt=ttk.Treeview(tabs['Gift Cards'],columns=('code','initial','balance','status','expiry'),show='headings');
        for c,h in zip(gt['columns'],('Code','Initial','Balance','Status','Expiry')):gt.heading(c,text=h)
        gt.pack(fill='both',expand=True)
        for r in self.s.rows('SELECT code,initial_value,balance,status,expires_at FROM gift_cards ORDER BY id DESC LIMIT 500'):gt.insert('','end',values=(r['code'],money(r['initial_value']),money(r['balance']),r['status'],r['expires_at'] or ''))
        # Attendance
        at=ttk.Treeview(tabs['Attendance'],columns=('user','in','out','store'),show='headings');
        for c,h in zip(at['columns'],('Employee','Clock In','Clock Out','Store')):at.heading(c,text=h)
        at.pack(fill='both',expand=True)
        for r in self.s.rows('SELECT user_id,clock_in,clock_out,store_id FROM attendance ORDER BY id DESC LIMIT 500'):at.insert('','end',values=tuple(r))
        # Receipts
        rt=ttk.Treeview(tabs['Receipts'],columns=('sale','channel','destination','status','created'),show='headings');
        for c,h in zip(rt['columns'],('Sale','Channel','Destination','Status','Created')):rt.heading(c,text=h)
        rt.pack(fill='both',expand=True)
        for r in self.s.rows('SELECT sale_id,channel,destination,status,created_at FROM receipt_delivery_queue ORDER BY id DESC LIMIT 500'):rt.insert('','end',values=tuple(r))
        # Employee sales
        et=ttk.Treeview(tabs['Employee Sales'],columns=('employee','orders','sales'),show='headings');
        for c,h in zip(et['columns'],('Employee','Orders','Sales')):et.heading(c,text=h)
        et.pack(fill='both',expand=True)
        for r in self.s.rows('SELECT user_id,COUNT(*) orders,COALESCE(SUM(amount),0) sales FROM employee_sales_summary GROUP BY user_id ORDER BY sales DESC'):et.insert('','end',values=(r['user_id'],r['orders'],money(r['sales'])))
    App.page_enterprise_pos_features=page_enterprise_pos_features
    nav=list(getattr(App,'NAV',[]))
    if 'Enterprise POS' not in nav: nav.append('Enterprise POS')
    App.NAV=nav
    App._enterprise_pos_features_installed=True
    return App
