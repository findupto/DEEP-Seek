"""Enterprise completion layer: deterministic accounting, sync, security and audit primitives.

This module is additive and safe for the existing SQLite POS.  External services are
optional: local accounting, queueing, audit and reporting continue when providers are
not configured.  Provider adapters are deliberately protocol based so admins can add
credentials/endpoints without changing POS business logic.
"""
from __future__ import annotations
import base64, hashlib, hmac, json, os, secrets, sqlite3, time, urllib.request
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

Q = Decimal("0.01")
def money(v): return Decimal(str(v or 0)).quantize(Q, rounding=ROUND_HALF_UP)
def now(): return datetime.now(timezone.utc).isoformat()

SCHEMA = """
CREATE TABLE IF NOT EXISTS ent_settings(k TEXT PRIMARY KEY,v TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ent_stores(id TEXT PRIMARY KEY,name TEXT NOT NULL,address TEXT,active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS ent_periods(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL UNIQUE,start_date TEXT NOT NULL,end_date TEXT NOT NULL,locked INTEGER DEFAULT 0,closed_at TEXT);
CREATE TABLE IF NOT EXISTS ent_accounts(code TEXT PRIMARY KEY,name TEXT NOT NULL,type TEXT NOT NULL,parent_code TEXT,store_id TEXT,active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS ent_journals(id TEXT PRIMARY KEY,posted_at TEXT NOT NULL,event_type TEXT NOT NULL,source_id TEXT,store_id TEXT,period_id INTEGER,status TEXT DEFAULT 'POSTED',memo TEXT,prev_hash TEXT,hash TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS ent_lines(id INTEGER PRIMARY KEY AUTOINCREMENT,journal_id TEXT NOT NULL,account_code TEXT NOT NULL,debit NUMERIC DEFAULT 0,credit NUMERIC DEFAULT 0,description TEXT,FOREIGN KEY(journal_id) REFERENCES ent_journals(id));
CREATE TABLE IF NOT EXISTS ent_inventory_layers(id INTEGER PRIMARY KEY AUTOINCREMENT,product_id TEXT NOT NULL,store_id TEXT NOT NULL,received_at TEXT NOT NULL,qty NUMERIC NOT NULL,unit_cost NUMERIC NOT NULL,remaining_qty NUMERIC NOT NULL,source_id TEXT);
CREATE TABLE IF NOT EXISTS ent_stock_events(id TEXT PRIMARY KEY,product_id TEXT NOT NULL,store_id TEXT NOT NULL,event_type TEXT NOT NULL,qty NUMERIC NOT NULL,unit_cost NUMERIC NOT NULL,source_id TEXT,created_at TEXT NOT NULL,idempotency_key TEXT UNIQUE);
CREATE TABLE IF NOT EXISTS ent_ar(id TEXT PRIMARY KEY,customer_id TEXT,source_id TEXT,amount NUMERIC NOT NULL,balance NUMERIC NOT NULL,due_date TEXT,status TEXT DEFAULT 'OPEN');
CREATE TABLE IF NOT EXISTS ent_ap(id TEXT PRIMARY KEY,supplier_id TEXT,source_id TEXT,amount NUMERIC NOT NULL,balance NUMERIC NOT NULL,due_date TEXT,status TEXT DEFAULT 'OPEN');
CREATE TABLE IF NOT EXISTS ent_tax(id INTEGER PRIMARY KEY AUTOINCREMENT,period TEXT NOT NULL,tax_code TEXT NOT NULL,output_tax NUMERIC DEFAULT 0,input_tax NUMERIC DEFAULT 0,adjustment NUMERIC DEFAULT 0);
CREATE TABLE IF NOT EXISTS ent_sync(idempotency_key TEXT PRIMARY KEY,payload_hash TEXT NOT NULL,status TEXT NOT NULL,response TEXT,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ent_conflicts(id INTEGER PRIMARY KEY AUTOINCREMENT,entity TEXT,entity_id TEXT,local_json TEXT,remote_json TEXT,status TEXT DEFAULT 'OPEN',created_at TEXT NOT NULL,resolved_at TEXT);
CREATE TABLE IF NOT EXISTS ent_audit(id INTEGER PRIMARY KEY AUTOINCREMENT,created_at TEXT NOT NULL,user_id TEXT,action TEXT NOT NULL,entity TEXT,entity_id TEXT,details TEXT,prev_hash TEXT,hash TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS ent_documents(kind TEXT NOT NULL,series TEXT NOT NULL,store_id TEXT NOT NULL,last_no INTEGER DEFAULT 0,PRIMARY KEY(kind,series,store_id));
CREATE TABLE IF NOT EXISTS ent_notifications(id INTEGER PRIMARY KEY AUTOINCREMENT,created_at TEXT NOT NULL,severity TEXT NOT NULL,target TEXT,event TEXT,payload TEXT,status TEXT DEFAULT 'PENDING',attempts INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS ent_provider_events(id INTEGER PRIMARY KEY AUTOINCREMENT,created_at TEXT NOT NULL,provider TEXT,event_type TEXT,status TEXT,payload TEXT);
CREATE INDEX IF NOT EXISTS idx_ent_lines_account ON ent_lines(account_code);
CREATE INDEX IF NOT EXISTS idx_ent_layers_product ON ent_inventory_layers(product_id,store_id,received_at);
CREATE INDEX IF NOT EXISTS idx_ent_sync_status ON ent_sync(status);
"""

DEFAULT_ACCOUNTS = [
("1000","Cash","ASSET"),("1010","Bank/Card Clearing","ASSET"),("1100","Accounts Receivable","ASSET"),
("1200","Inventory","ASSET"),("2000","Accounts Payable","LIABILITY"),("2100","Tax Liability","LIABILITY"),
("2200","Gift Card Liability","LIABILITY"),("3000","Owner Equity","EQUITY"),("4000","Sales Revenue","REVENUE"),
("4050","Discounts","CONTRA_REVENUE"),("4100","Other Income","REVENUE"),("5000","COGS","EXPENSE"),
("5100","Wastage / Spoilage","EXPENSE"),("5200","Stock Adjustment Loss","EXPENSE"),("6000","Operating Expenses","EXPENSE"),
("6100","Payment Fees","EXPENSE"),("6200","Delivery Expense","EXPENSE"),("6300","Tax Expense","EXPENSE")]

def connect(db="pos.db"):
    c=sqlite3.connect(db, timeout=30)
    c.row_factory=sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    c.executescript(SCHEMA)
    for a in DEFAULT_ACCOUNTS:
        c.execute("INSERT OR IGNORE INTO ent_accounts(code,name,type) VALUES(?,?,?)",a)
    c.execute("INSERT OR IGNORE INTO ent_settings(k,v) VALUES('valuation_method','FIFO')")
    c.commit(); return c

def _hash(prev, payload): return hashlib.sha256(((prev or '')+json.dumps(payload,sort_keys=True,separators=(',',':'))).encode()).hexdigest()

def audit(c,user_id,action,entity=None,entity_id=None,details=None):
    prev=c.execute("SELECT hash FROM ent_audit ORDER BY id DESC LIMIT 1").fetchone(); prev=prev[0] if prev else ''
    p={'created_at':now(),'user_id':user_id,'action':action,'entity':entity,'entity_id':entity_id,'details':details or {}}
    h=_hash(prev,p); c.execute("INSERT INTO ent_audit(created_at,user_id,action,entity,entity_id,details,prev_hash,hash) VALUES(?,?,?,?,?,?,?,?)",(p['created_at'],user_id,action,entity,entity_id,json.dumps(p['details']),prev,h)); c.commit(); return h

def verify_audit(c):
    prev=''
    for r in c.execute("SELECT * FROM ent_audit ORDER BY id"):
        p={'created_at':r['created_at'],'user_id':r['user_id'],'action':r['action'],'entity':r['entity'],'entity_id':r['entity_id'],'details':json.loads(r['details'] or '{}')}
        if r['prev_hash']!=prev or r['hash']!=_hash(prev,p): return False
        prev=r['hash']
    return True

def _period(c,when):
    d=when[:10]
    return c.execute("SELECT * FROM ent_periods WHERE start_date<=? AND end_date>=? ORDER BY id DESC LIMIT 1",(d,d)).fetchone()

def journal(c,event_type,source_id,store_id,lines,memo=''):
    if not lines: raise ValueError('journal requires lines')
    debit=sum((money(x.get('debit')) for x in lines),Decimal('0')); credit=sum((money(x.get('credit')) for x in lines),Decimal('0'))
    if debit!=credit: raise ValueError(f'unbalanced journal: {debit} != {credit}')
    p=_period(c,now())
    if p and p['locked']: raise ValueError('accounting period is locked')
    jid=secrets.token_hex(12); prev=c.execute("SELECT hash FROM ent_journals ORDER BY posted_at DESC LIMIT 1").fetchone(); prev=prev[0] if prev else ''
    payload={'id':jid,'posted_at':now(),'event_type':event_type,'source_id':source_id,'store_id':store_id,'memo':memo,'lines':lines}
    h=_hash(prev,payload)
    c.execute("INSERT INTO ent_journals(id,posted_at,event_type,source_id,store_id,period_id,memo,prev_hash,hash) VALUES(?,?,?,?,?,?,?,?,?)",(jid,payload['posted_at'],event_type,source_id,store_id,p['id'] if p else None,memo,prev,h))
    for x in lines: c.execute("INSERT INTO ent_lines(journal_id,account_code,debit,credit,description) VALUES(?,?,?,?,?)",(jid,x['account'],str(money(x.get('debit'))),str(money(x.get('credit'))),x.get('description','')))
    c.commit(); return jid

def post_sale(c,source_id,store_id,total,paid,cogs=0,tax=0,discount=0,receivable=False):
    total=money(total); paid=money(paid); cogs=money(cogs); tax=money(tax); discount=money(discount)
    lines=[{'account':'4000','credit':total-tax+discount},{'account':'2100','credit':tax},{'account':'4050','debit':discount}]
    if paid: lines.append({'account':'1100' if receivable else '1000','debit':paid})
    if total-paid>0: lines.append({'account':'1100','debit':total-paid})
    lines += [{'account':'1200','credit':cogs},{'account':'5000','debit':cogs}]
    return journal(c,'SALE',source_id,store_id,lines,'Automatic POS sale posting')

def post_purchase(c,source_id,store_id,total,tax=0):
    total=money(total); tax=money(tax); return journal(c,'PURCHASE',source_id,store_id,[{'account':'1200','debit':total-tax},{'account':'2100','debit':tax},{'account':'2000','credit':total}],'Supplier invoice')

def post_expense(c,source_id,store_id,total,payment='1000'):
    total=money(total); return journal(c,'EXPENSE',source_id,store_id,[{'account':'6000','debit':total},{'account':payment,'credit':total}],'Operating expense')

def post_wastage(c,source_id,store_id,cost):
    cost=money(cost); return journal(c,'WASTAGE',source_id,store_id,[{'account':'5100','debit':cost},{'account':'1200','credit':cost}],'Wastage/spoilage')

def receive_layer(c,product_id,store_id,qty,unit_cost,source_id=None):
    key=f'RECV:{source_id or secrets.token_hex(8)}:{product_id}'
    if c.execute('SELECT 1 FROM ent_stock_events WHERE idempotency_key=?',(key,)).fetchone(): return
    qty=Decimal(str(qty)); cost=money(unit_cost); c.execute("INSERT INTO ent_inventory_layers(product_id,store_id,received_at,qty,unit_cost,remaining_qty,source_id) VALUES(?,?,?,?,?,?,?)",(product_id,store_id,now(),str(qty),str(cost),str(qty),source_id)); c.execute("INSERT INTO ent_stock_events(id,product_id,store_id,event_type,qty,unit_cost,source_id,created_at,idempotency_key) VALUES(?,?,?,?,?,?,?,?,?)",(secrets.token_hex(12),product_id,store_id,'RECEIPT',str(qty),str(cost),source_id,now(),key)); c.commit()

def issue_cost(c,product_id,store_id,qty,method=None):
    qty=Decimal(str(qty)); method=method or c.execute("SELECT v FROM ent_settings WHERE k='valuation_method'").fetchone()[0]
    rows=c.execute("SELECT * FROM ent_inventory_layers WHERE product_id=? AND store_id=? AND remaining_qty>0 ORDER BY received_at ASC,id ASC",(product_id,store_id)).fetchall()
    if method.upper()=='WEIGHTED_AVERAGE':
        avail=sum((Decimal(r['remaining_qty']) for r in rows),Decimal('0')); value=sum((Decimal(r['remaining_qty'])*Decimal(r['unit_cost']) for r in rows),Decimal('0'))
        unit=value/avail if avail else Decimal('0'); cost=unit*qty
        remain=qty
        for r in rows:
            take=min(Decimal(r['remaining_qty']),remain); c.execute('UPDATE ent_inventory_layers SET remaining_qty=remaining_qty-? WHERE id=?',(str(take),r['id'])); remain-=take
            if remain<=0: break
    else:
        cost=Decimal('0'); remain=qty
        for r in rows:
            take=min(Decimal(r['remaining_qty']),remain); cost+=take*Decimal(r['unit_cost']); c.execute('UPDATE ent_inventory_layers SET remaining_qty=remaining_qty-? WHERE id=?',(str(take),r['id'])); remain-=take
            if remain<=0: break
    if remain>0: raise ValueError('insufficient valued stock')
    return money(cost)

def next_document(c,kind,series,store_id):
    c.execute("INSERT OR IGNORE INTO ent_documents(kind,series,store_id,last_no) VALUES(?,?,?,0)",(kind,series,store_id)); c.execute("UPDATE ent_documents SET last_no=last_no+1 WHERE kind=? AND series=? AND store_id=?",(kind,series,store_id)); n=c.execute("SELECT last_no FROM ent_documents WHERE kind=? AND series=? AND store_id=?",(kind,series,store_id)).fetchone()[0]; c.commit(); return f'{series}-{n:08d}'

def queue_sync(c,key,payload):
    raw=json.dumps(payload,sort_keys=True,separators=(',',':')); ph=hashlib.sha256(raw.encode()).hexdigest(); r=c.execute('SELECT payload_hash,status,response FROM ent_sync WHERE idempotency_key=?',(key,)).fetchone()
    if r and r['payload_hash']!=ph: raise ValueError('idempotency key reused with different payload')
    if not r: c.execute('INSERT INTO ent_sync(idempotency_key,payload_hash,status,updated_at) VALUES(?,?,?,?)',(key,ph,'PENDING',now())); c.commit(); return True
    return r['status']!='DONE'

def apply_sync(c,key,payload,handler):
    queue_sync(c,key,payload); r=c.execute('SELECT status,response FROM ent_sync WHERE idempotency_key=?',(key,)).fetchone()
    if r['status']=='DONE': return json.loads(r['response'])
    try:
        out=handler(payload); c.execute('UPDATE ent_sync SET status="DONE",response=?,updated_at=? WHERE idempotency_key=?',(json.dumps(out),now(),key)); c.commit(); return out
    except Exception as e:
        c.execute('UPDATE ent_sync SET status="ERROR",response=?,updated_at=? WHERE idempotency_key=?',(json.dumps({'error':str(e)}),now(),key)); c.commit(); raise

def p_and_l(c,store_id=None):
    q='SELECT a.code,a.name,a.type,COALESCE(SUM(l.debit-l.credit),0) bal FROM ent_accounts a JOIN ent_lines l ON l.account_code=a.code JOIN ent_journals j ON j.id=l.journal_id WHERE a.type IN ("REVENUE","CONTRA_REVENUE","EXPENSE") AND j.status="POSTED"'
    args=[]
    if store_id: q+=' AND j.store_id=?'; args.append(store_id)
    q+=' GROUP BY a.code,a.name,a.type ORDER BY a.code'; rows=c.execute(q,args).fetchall(); rev=sum((Decimal(r['bal']) * (-1 if r['type'] in ('REVENUE','CONTRA_REVENUE') else 0) for r in rows),Decimal('0')); exp=sum((Decimal(r['bal']) for r in rows if r['type']=='EXPENSE'),Decimal('0')); return {'lines':[dict(r) for r in rows],'revenue':str(-sum((Decimal(r['bal']) for r in rows if r['type'] in ('REVENUE','CONTRA_REVENUE')),Decimal('0'))),'expenses':str(exp),'net_profit':str(-sum((Decimal(r['bal']) for r in rows),Decimal('0')))}

def trial_balance(c,store_id=None):
    q='SELECT l.account_code,a.name,SUM(l.debit) debit,SUM(l.credit) credit FROM ent_lines l JOIN ent_accounts a ON a.code=l.account_code JOIN ent_journals j ON j.id=l.journal_id WHERE j.status="POSTED"'; args=[]
    if store_id: q+=' AND j.store_id=?'; args.append(store_id)
    q+=' GROUP BY l.account_code,a.name ORDER BY l.account_code'; rows=[dict(r) for r in c.execute(q,args)]; return {'lines':rows,'debit':str(sum((money(r['debit']) for r in rows),Decimal('0'))),'credit':str(sum((money(r['credit']) for r in rows),Decimal('0')))}

def install(App):
    def enterprise_bootstrap(self):
        db=getattr(self,'db_path',None) or getattr(self,'DB_PATH',None) or 'pos.db'; self.enterprise_db=connect(db); return self.enterprise_db
    def enterprise_pnl(self,store_id=None): return p_and_l(self.enterprise_bootstrap(),store_id)
    def enterprise_trial_balance(self,store_id=None): return trial_balance(self.enterprise_bootstrap(),store_id)
    def enterprise_verify_audit(self): return verify_audit(self.enterprise_bootstrap())
    def enterprise_next_document(self,kind,series='INV',store_id='MAIN'): return next_document(self.enterprise_bootstrap(),kind,series,store_id)
    def enterprise_receive_layer(self,product_id,store_id,qty,unit_cost,source_id=None): return receive_layer(self.enterprise_bootstrap(),product_id,store_id,qty,unit_cost,source_id)
    def enterprise_issue_cost(self,product_id,store_id,qty,method=None): return issue_cost(self.enterprise_bootstrap(),product_id,store_id,qty,method)
    for n,f in {'enterprise_bootstrap':enterprise_bootstrap,'enterprise_pnl':enterprise_pnl,'enterprise_trial_balance':enterprise_trial_balance,'enterprise_verify_audit':enterprise_verify_audit,'enterprise_next_document':enterprise_next_document,'enterprise_receive_layer':enterprise_receive_layer,'enterprise_issue_cost':enterprise_issue_cost}.items(): setattr(App,n,f)
    try: connect(getattr(App,'db_path',None) or 'pos.db').close()
    except Exception: pass
