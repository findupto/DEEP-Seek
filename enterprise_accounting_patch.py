"""Enterprise accounting and multi-store foundation for DEEP-Seek.

Additive layer: double-entry ledger, chart of accounts, AP/AR, supplier bills,
tax liability, inventory valuation policy, accounting periods, financial reports,
store/branch configuration, and integration registry. Existing POS data is kept.
"""
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime


def now(): return datetime.now().isoformat(timespec="seconds")
def money(v): return f"Rs. {float(v or 0):,.2f}"

SCHEMA = """
CREATE TABLE IF NOT EXISTS stores(id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE, name TEXT NOT NULL, address TEXT DEFAULT '', phone TEXT DEFAULT '', email TEXT DEFAULT '', currency TEXT DEFAULT 'Rs.', timezone TEXT DEFAULT 'Asia/Karachi', language TEXT DEFAULT 'en', active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS user_stores(user_id INTEGER, store_id INTEGER, is_default INTEGER DEFAULT 0, PRIMARY KEY(user_id,store_id));
CREATE TABLE IF NOT EXISTS account_groups(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS accounts(id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE NOT NULL, name TEXT NOT NULL, account_type TEXT NOT NULL, parent_id INTEGER, store_id INTEGER, active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS accounting_periods(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, start_date TEXT NOT NULL, end_date TEXT NOT NULL, status TEXT DEFAULT 'OPEN', closed_at TEXT, closed_by INTEGER);
CREATE TABLE IF NOT EXISTS journal_entries(id INTEGER PRIMARY KEY AUTOINCREMENT, entry_no TEXT UNIQUE NOT NULL, entry_date TEXT NOT NULL, description TEXT DEFAULT '', source_type TEXT DEFAULT '', source_id INTEGER, status TEXT DEFAULT 'POSTED', created_by INTEGER, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS journal_lines(id INTEGER PRIMARY KEY AUTOINCREMENT, journal_id INTEGER NOT NULL, account_id INTEGER NOT NULL, debit REAL DEFAULT 0, credit REAL DEFAULT 0, memo TEXT DEFAULT '', store_id INTEGER);
CREATE INDEX IF NOT EXISTS idx_journal_lines_account ON journal_lines(account_id);
CREATE TABLE IF NOT EXISTS supplier_bills(id INTEGER PRIMARY KEY AUTOINCREMENT, supplier_id INTEGER, invoice_no TEXT NOT NULL, bill_date TEXT NOT NULL, due_date TEXT, subtotal REAL DEFAULT 0, tax REAL DEFAULT 0, total REAL DEFAULT 0, paid REAL DEFAULT 0, status TEXT DEFAULT 'OPEN', store_id INTEGER);
CREATE TABLE IF NOT EXISTS bill_payments(id INTEGER PRIMARY KEY AUTOINCREMENT, bill_id INTEGER NOT NULL, amount REAL NOT NULL, method TEXT, payment_date TEXT NOT NULL, reference TEXT DEFAULT '', user_id INTEGER);
CREATE TABLE IF NOT EXISTS customer_receivables(id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER, sale_id INTEGER, amount REAL NOT NULL, due_date TEXT, paid REAL DEFAULT 0, status TEXT DEFAULT 'OPEN', store_id INTEGER);
CREATE TABLE IF NOT EXISTS tax_ledger(id INTEGER PRIMARY KEY AUTOINCREMENT, tax_code TEXT NOT NULL, tax_rate REAL DEFAULT 0, tax_type TEXT DEFAULT 'OUTPUT', source_type TEXT, source_id INTEGER, amount REAL NOT NULL, tax_date TEXT NOT NULL, store_id INTEGER);
CREATE TABLE IF NOT EXISTS inventory_layers(id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL, received_at TEXT NOT NULL, quantity REAL NOT NULL, remaining REAL NOT NULL, unit_cost REAL NOT NULL, source_type TEXT DEFAULT 'OPENING', source_id INTEGER, store_id INTEGER);
CREATE TABLE IF NOT EXISTS inventory_valuation_settings(id INTEGER PRIMARY KEY CHECK(id=1), method TEXT NOT NULL DEFAULT 'WEIGHTED_AVERAGE');
INSERT OR IGNORE INTO inventory_valuation_settings(id,method) VALUES(1,'WEIGHTED_AVERAGE');
CREATE TABLE IF NOT EXISTS accounting_settings(id INTEGER PRIMARY KEY CHECK(id=1), tax_inclusive INTEGER DEFAULT 0, default_tax_rate REAL DEFAULT 0, fiscal_year_start TEXT DEFAULT '01-01', default_currency TEXT DEFAULT 'Rs.', timezone TEXT DEFAULT 'Asia/Karachi');
INSERT OR IGNORE INTO accounting_settings(id) VALUES(1);
CREATE TABLE IF NOT EXISTS integration_registry(id INTEGER PRIMARY KEY AUTOINCREMENT, provider TEXT NOT NULL, category TEXT NOT NULL, enabled INTEGER DEFAULT 0, config_json TEXT DEFAULT '{}', updated_at TEXT);
CREATE TABLE IF NOT EXISTS audit_ledger(id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT NOT NULL, entity TEXT, entity_id INTEGER, payload TEXT, created_at TEXT NOT NULL, user_id INTEGER);
CREATE TABLE IF NOT EXISTS stock_counts(id INTEGER PRIMARY KEY AUTOINCREMENT, store_id INTEGER, count_date TEXT NOT NULL, status TEXT DEFAULT 'OPEN', notes TEXT DEFAULT '', user_id INTEGER);
CREATE TABLE IF NOT EXISTS stock_transfers(id INTEGER PRIMARY KEY AUTOINCREMENT, from_store_id INTEGER, to_store_id INTEGER, transfer_date TEXT NOT NULL, status TEXT DEFAULT 'DRAFT', notes TEXT DEFAULT '', user_id INTEGER);
CREATE TABLE IF NOT EXISTS wastage(id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER, quantity REAL NOT NULL, unit_cost REAL DEFAULT 0, reason TEXT DEFAULT '', created_at TEXT NOT NULL, store_id INTEGER, user_id INTEGER);
CREATE TABLE IF NOT EXISTS product_batches(id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL, batch_no TEXT, lot_no TEXT, expiry_date TEXT, quantity REAL DEFAULT 0, unit_cost REAL DEFAULT 0, store_id INTEGER);
CREATE TABLE IF NOT EXISTS reorder_rules(id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER UNIQUE, min_stock REAL DEFAULT 0, reorder_qty REAL DEFAULT 0, supplier_id INTEGER, enabled INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS approval_requests(id INTEGER PRIMARY KEY AUTOINCREMENT, action_type TEXT NOT NULL, entity TEXT, entity_id INTEGER, requested_by INTEGER, approved_by INTEGER, status TEXT DEFAULT 'PENDING', reason TEXT DEFAULT '', created_at TEXT NOT NULL, approved_at TEXT);
"""

ACCOUNTS = [
 ('1000','Cash','ASSET'),('1010','Bank / Card Clearing','ASSET'),('1100','Accounts Receivable','ASSET'),
 ('1200','Inventory','ASSET'),('2000','Accounts Payable','LIABILITY'),('2100','Tax Payable','LIABILITY'),
 ('3000','Owner Equity','EQUITY'),('4000','Sales Revenue','REVENUE'),('4010','Discounts Allowed','CONTRA_REVENUE'),
 ('4020','Refunds / Returns','CONTRA_REVENUE'),('5000','Cost of Goods Sold','COGS'),('5100','Wastage / Spoilage','EXPENSE'),
 ('6000','Operating Expenses','EXPENSE'),('6100','Other Expenses','EXPENSE'),('7000','Other Income','OTHER_INCOME'),
 ('8000','Tax Expense','EXPENSE')]


def install(App):
    if getattr(App, '_enterprise_accounting_installed', False): return App
    old_init = App.__init__
    def init(self,*args,**kwargs):
        old_init(self,*args,**kwargs)
        self.s.c.executescript(SCHEMA)
        for code,name,typ in ACCOUNTS:
            self.s.q('INSERT OR IGNORE INTO accounts(code,name,account_type) VALUES(?,?,?)',(code,name,typ))
        # Create an opening inventory layer for existing stock so valuation is deterministic.
        for r in self.s.rows("SELECT id,stock,cost FROM products WHERE active=1 AND stock>0"):
            exists=self.s.q("SELECT 1 FROM inventory_layers WHERE product_id=? AND source_type='OPENING' LIMIT 1",(r['id'],)).fetchone()
            if not exists:
                self.s.q("INSERT INTO inventory_layers(product_id,received_at,quantity,remaining,unit_cost,source_type) VALUES(?,?,?,?,?,?)",(r['id'],now(),float(r['stock']),float(r['stock']),float(r['cost'] or 0),'OPENING'))
        self.s.c.commit()
    App.__init__=init

    def valuation_method(self):
        return self.s.q('SELECT method FROM inventory_valuation_settings WHERE id=1').fetchone()['method']
    def set_valuation_method(self,method):
        if method not in ('FIFO','WEIGHTED_AVERAGE'): raise ValueError('Unsupported valuation method')
        self.s.q('UPDATE inventory_valuation_settings SET method=? WHERE id=1',(method,)); self.s.c.commit()
    App.inventory_valuation_method=valuation_method; App.set_inventory_valuation_method=set_valuation_method

    def post_journal(self,description,lines,source_type='',source_id=None,user_id=None,entry_date=None):
        if not lines: raise ValueError('Journal requires lines')
        debit=round(sum(float(x[1]) for x in lines),2); credit=round(sum(float(x[2]) for x in lines),2)
        if abs(debit-credit)>0.01: raise ValueError(f'Unbalanced journal: debit {debit}, credit {credit}')
        d=entry_date or now()[:10]; p=self.s.q("SELECT id FROM accounting_periods WHERE start_date<=? AND end_date>=? AND status='LOCKED' LIMIT 1",(d,d)).fetchone()
        if p: raise ValueError('Accounting period is locked')
        no='JE-'+datetime.now().strftime('%Y%m%d%H%M%S%f')
        cur=self.s.q('INSERT INTO journal_entries(entry_no,entry_date,description,source_type,source_id,created_by,created_at) VALUES(?,?,?,?,?,?,?)',(no,d,description,source_type,source_id,user_id,now()))
        jid=cur.lastrowid
        for aid,dr,cr,memo,store_id in lines:
            self.s.q('INSERT INTO journal_lines(journal_id,account_id,debit,credit,memo,store_id) VALUES(?,?,?,?,?,?)',(jid,aid,dr,cr,memo,store_id))
        self.s.q('INSERT INTO audit_ledger(event_type,entity,entity_id,payload,created_at,user_id) VALUES(?,?,?,?,?,?)',('JOURNAL_POSTED','journal',jid,description,now(),user_id))
        self.s.c.commit(); return jid
    App.post_journal=post_journal

    def page_accounting(self):
        self.title('Accounting','Double-entry ledger, trial balance, P&L, balance sheet and cash-flow controls.')
        book=ttk.Notebook(self.bodyinner); book.pack(fill='both',expand=True)
        tabs={k:ttk.Frame(book,padding=10) for k in ('Trial Balance','P&L','Balance Sheet','Cash Flow','Journal','Settings','Periods')}
        for k,f in tabs.items(): book.add(f,text=k)
        def account_balances():
            return self.s.rows("SELECT a.code,a.name,a.account_type,COALESCE(SUM(l.debit),0) debit,COALESCE(SUM(l.credit),0) credit FROM accounts a LEFT JOIN journal_lines l ON l.account_id=a.id GROUP BY a.id ORDER BY a.code")
        t=ttk.Treeview(tabs['Trial Balance'],columns=('code','name','type','debit','credit'),show='headings')
        for c,h in zip(t['columns'],('Code','Account','Type','Debit','Credit')): t.heading(c,text=h);t.column(c,width=160)
        t.pack(fill='both',expand=True)
        for r in account_balances(): t.insert('','end',values=(r['code'],r['name'],r['account_type'],money(r['debit']),money(r['credit'])))
        out=tk.Text(tabs['P&L'],height=20);out.pack(fill='both',expand=True)
        def pnl():
            rows=account_balances(); rev=sum(float(r['credit'])-float(r['debit']) for r in rows if r['account_type'] in ('REVENUE','CONTRA_REVENUE')); cogs=sum(float(r['debit'])-float(r['credit']) for r in rows if r['account_type']=='COGS'); exp=sum(float(r['debit'])-float(r['credit']) for r in rows if r['account_type'] in ('EXPENSE',)); other=sum(float(r['credit'])-float(r['debit']) for r in rows if r['account_type']=='OTHER_INCOME'); gp=rev-cogs; net=gp-exp+other
            out.delete('1.0','end');out.insert('end',f'Net Revenue: {money(rev)}\nCOGS: {money(cogs)}\nGross Profit: {money(gp)}\nOperating/Other Expenses: {money(exp)}\nOther Income: {money(other)}\nNET PROFIT / LOSS: {money(net)}\n')
        ttk.Button(tabs['P&L'],text='RECALCULATE',command=pnl).pack(fill='x');pnl()
        bs=tk.Text(tabs['Balance Sheet'],height=20);bs.pack(fill='both',expand=True)
        rows=account_balances(); assets=sum(float(r['debit'])-float(r['credit']) for r in rows if r['account_type']=='ASSET'); liab=sum(float(r['credit'])-float(r['debit']) for r in rows if r['account_type']=='LIABILITY'); eq=sum(float(r['credit'])-float(r['debit']) for r in rows if r['account_type']=='EQUITY'); bs.insert('end',f'ASSETS: {money(assets)}\nLIABILITIES: {money(liab)}\nEQUITY: {money(eq)}\nBALANCE CHECK: {money(assets-liab-eq)}')
        cf=tk.Text(tabs['Cash Flow'],height=20);cf.pack(fill='both',expand=True); cash=self.s.q("SELECT COALESCE(SUM(l.debit-l.credit),0) x FROM journal_lines l JOIN accounts a ON a.id=l.account_id WHERE a.code='1000'").fetchone()['x'];cf.insert('end',f'Net cash movement (ledger): {money(cash)}\nUse Journal/Cash Drawer reports for operating/investing/financing classification.')
        jt=ttk.Treeview(tabs['Journal'],columns=('no','date','description','status'),show='headings');[jt.heading(c,text=h) for c,h in zip(jt['columns'],('Entry','Date','Description','Status'))];jt.pack(fill='both',expand=True)
        for r in self.s.rows('SELECT entry_no,entry_date,description,status FROM journal_entries ORDER BY id DESC LIMIT 500'):jt.insert('','end',values=tuple(r))
        sm=ttk.Frame(tabs['Settings']);sm.pack(fill='x');m=tk.StringVar(value=self.inventory_valuation_method());ttk.Label(sm,text='Inventory valuation').pack(anchor='w');ttk.Combobox(sm,textvariable=m,values=('FIFO','WEIGHTED_AVERAGE'),state='readonly').pack(fill='x');ttk.Button(sm,text='SAVE',command=lambda:(self.set_inventory_valuation_method(m.get()),messagebox.showinfo('Accounting','Valuation method saved.',parent=self))).pack(fill='x',pady=8)
        ttk.Label(sm,text='Tax-inclusive pricing and tax profiles are stored in accounting settings and should be selected explicitly per store/product.',wraplength=700).pack(anchor='w',pady=10)
        pt=ttk.Treeview(tabs['Periods'],columns=('name','start','end','status'),show='headings');[pt.heading(c,text=h) for c,h in zip(pt['columns'],('Period','Start','End','Status'))];pt.pack(fill='both',expand=True)
        for r in self.s.rows('SELECT name,start_date,end_date,status FROM accounting_periods ORDER BY start_date DESC'):pt.insert('','end',values=tuple(r))
    App.page_accounting=page_accounting

    def page_enterprise_settings(self):
        self.title('Enterprise Settings','Company, branch, tax, payment, notification and integration configuration.')
        f=ttk.Frame(self.bodyinner,padding=10);f.pack(fill='both',expand=True)
        fields=[('Store code','code'),('Store name','name'),('Address','address'),('Phone','phone'),('Email','email'),('Currency','currency'),('Timezone','timezone'),('Language','language')]
        vars={k:tk.StringVar() for _,k in fields}
        for i,(label,key) in enumerate(fields): ttk.Label(f,text=label).grid(row=i,column=0,sticky='w',padx=5,pady=5);ttk.Entry(f,textvariable=vars[key]).grid(row=i,column=1,sticky='ew',padx=5,pady=5)
        f.columnconfigure(1,weight=1)
        ttk.Label(f,text='External providers (GPS/maps, payment terminals, wallet, email/SMS/push, accounting API) are represented by integration_registry and require provider credentials.',wraplength=800).grid(row=len(fields),column=0,columnspan=2,sticky='w',pady=15)
    App.page_enterprise_settings=page_enterprise_settings

    nav=list(getattr(App,'NAV',[]))
    for item in ('Accounting','Enterprise Settings'):
        if item not in nav: nav.append(item)
    App.NAV=nav
    App._enterprise_accounting_installed=True
    return App
