"""Financial subledger bridge for the canonical POS.

The legacy POS stores sales, payments, expenses, purchases and party transactions
in operational tables but previously did not post them into one consistent ledger.
This patch adds a local-first double-entry subledger and staff accounts.
"""
import sqlite3
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox

def now():
    return datetime.now().isoformat(timespec="seconds")

SCHEMA = """
CREATE TABLE IF NOT EXISTS ledger_accounts(code TEXT PRIMARY KEY,name TEXT NOT NULL,type TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ledger_entries(id INTEGER PRIMARY KEY AUTOINCREMENT,source_type TEXT NOT NULL,source_id INTEGER NOT NULL,description TEXT DEFAULT '',created_at TEXT NOT NULL,UNIQUE(source_type,source_id));
CREATE TABLE IF NOT EXISTS ledger_lines(id INTEGER PRIMARY KEY AUTOINCREMENT,entry_id INTEGER NOT NULL,account_code TEXT NOT NULL,debit REAL DEFAULT 0,credit REAL DEFAULT 0,memo TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS staff_transactions(id INTEGER PRIMARY KEY AUTOINCREMENT,staff_id INTEGER NOT NULL,txn_type TEXT NOT NULL,amount REAL NOT NULL,note TEXT DEFAULT '',created_at TEXT NOT NULL,user_id INTEGER);
CREATE INDEX IF NOT EXISTS idx_ledger_lines_account ON ledger_lines(account_code);
CREATE INDEX IF NOT EXISTS idx_staff_transactions_staff ON staff_transactions(staff_id,created_at);
"""

ACCOUNTS = [
    ("1000","Cash","ASSET"),("1010","Card / Bank Clearing","ASSET"),
    ("1100","Customer Receivables","ASSET"),("1200","Inventory","ASSET"),
    ("1300","Staff Receivables","ASSET"),("2000","Supplier Payables","LIABILITY"),
    ("2200","Customer Advances","LIABILITY"),("3000","Owner Equity","EQUITY"),
    ("4000","Sales Revenue","REVENUE"),("5000","Cost of Goods Sold","EXPENSE"),
    ("6000","Operating Expenses","EXPENSE"),("6100","Other Expenses","EXPENSE"),
]

def _post(c, source_type, source_id, description, lines):
    if not lines:
        return
    if abs(round(sum(float(x[1]) for x in lines),2)-round(sum(float(x[2]) for x in lines),2)) > .01:
        raise ValueError("Unbalanced ledger entry")
    try:
        cur=c.execute("INSERT INTO ledger_entries(source_type,source_id,description,created_at) VALUES(?,?,?,?)",(source_type,source_id,description,now()))
    except sqlite3.IntegrityError:
        return
    eid=cur.lastrowid
    for account,debit,credit,memo in lines:
        c.execute("INSERT INTO ledger_lines(entry_id,account_code,debit,credit,memo) VALUES(?,?,?,?,?)",(eid,account,float(debit),float(credit),memo or ""))

def _rebuild(c):
    """Backfill missing ledger entries from the canonical POS transaction tables."""
    for r in c.execute("SELECT id,total,payment_method,customer_id,created_at FROM sales WHERE status!='Cancelled'").fetchall():
        total=float(r['total'] or 0)
        if total>0:
            _post(c,"SALE",r['id'],"Sale "+str(r['id']),[("1100",total,0,"Customer receivable"),("4000",0,total,"Sales revenue")])
    for r in c.execute("SELECT id,sale_id,method,amount FROM payments").fetchall():
        a=float(r['amount'] or 0)
        if a>0:
            _post(c,"PAYMENT",r['id'],"Payment for sale "+str(r['sale_id']),[("1010" if r['method'] in ('Card','Other') else "1000",a,0,r['method']+" received"),("1100",0,a,"Customer receivable settled")])
    for r in c.execute("SELECT id,category,amount FROM expenses").fetchall():
        a=float(r['amount'] or 0)
        if a>0:
            _post(c,"EXPENSE",r['id'],r['category'] or "Expense",[("6000",a,0,r['category'] or "Expense"),("1000",0,a,"Cash expense")])
    for r in c.execute("SELECT id,total,payment_status FROM purchases").fetchall():
        a=float(r['total'] or 0)
        if a>0:
            _post(c,"PURCHASE",r['id'],"Purchase "+str(r['id']),[("1200",a,0,"Inventory received"),("1000" if r['payment_status']=='Paid' else "2000",0,a,"Supplier settlement" if r['payment_status']=='Paid' else "Supplier payable")])
    for r in c.execute("SELECT id,party_type,party_id,txn_type,amount,note FROM party_transactions").fetchall():
        a=float(r['amount'] or 0); typ=str(r['party_type']); tx=str(r['txn_type'])
        if a<=0:
            continue
        if typ=='Customer' and tx=='Payment':
            lines=[("1000",a,0,"Customer payment"),("1100",0,a,"Receivable settled")]
        elif typ=='Customer' and tx=='Advance':
            lines=[("1000",a,0,"Customer advance"),("2200",0,a,"Customer advance liability")]
        elif typ=='Supplier' and tx=='Payment':
            lines=[("2000",a,0,"Supplier payable settled"),("1000",0,a,"Supplier payment")]
        elif typ=='Supplier' and tx=='Advance':
            lines=[("2000",a,0,"Supplier advance"),("1000",0,a,"Supplier advance paid")]
        else:
            continue
        _post(c,"PARTY_TXN",r['id'],typ+" "+tx,lines)
    c.commit()

def install(App):
    if getattr(App,"_financial_bridge_installed",False):
        return App
    old_init=App.__init__
    def init(self,*args,**kwargs):
        old_init(self,*args,**kwargs)
        self.s.c.executescript(SCHEMA)
        for a in ACCOUNTS:
            self.s.q("INSERT OR IGNORE INTO ledger_accounts(code,name,type) VALUES(?,?,?)",a)
        _rebuild(self.s.c)
    App.__init__=init

    def add_staff_transaction(self,staff_id,txn_type,amount,note=""):
        amount=float(amount)
        if amount<=0:
            raise ValueError("Amount must be positive")
        if txn_type not in ("Advance","Repayment","Adjustment"):
            raise ValueError("Invalid staff transaction")
        r=self.s.q("SELECT id FROM staff WHERE id=? AND active=1",(staff_id,)).fetchone()
        if not r:
            raise ValueError("Staff member not found")
        cur=self.s.q("INSERT INTO staff_transactions(staff_id,txn_type,amount,note,created_at,user_id) VALUES(?,?,?,?,?,?)",(staff_id,txn_type,amount,note,now(),self.user['id']))
        tid=cur.lastrowid
        if txn_type=="Advance":
            lines=[("1300",amount,0,"Staff advance"),("1000",0,amount,"Cash paid to staff")]
        elif txn_type=="Repayment":
            lines=[("1000",amount,0,"Staff repayment"),("1300",0,amount,"Staff receivable settled")]
        else:
            lines=[("1300",amount,0,"Staff account adjustment"),("3000",0,amount,"Staff account adjustment")]
        _post(self.s.c,"STAFF_TXN",tid,"Staff account transaction",lines)
        self.s.c.commit()
    App.add_staff_transaction=add_staff_transaction

    def page_staff(self):
        self.title("Staff Accounts","Manage staff and every advance, repayment and account adjustment.")
        bar=ttk.Frame(self.bodyinner); bar.pack(fill="x",pady=8)
        ttk.Button(bar,text="ADD STAFF",style="Primary.TButton",command=lambda:self.people_edit("staff",["name","phone","role","salary"])).pack(side="left")
        ttk.Button(bar,text="STAFF ACCOUNT",command=self.staff_account).pack(side="left",padx=5)
        t=self.table(self.bodyinner,("id","name","phone","role","salary","balance"),{"id":"ID","name":"Name","phone":"Phone","role":"Role","salary":"Salary","balance":"Account Balance"},18)
        for r in self.s.rows("SELECT s.*,COALESCE((SELECT SUM(CASE WHEN txn_type='Advance' THEN amount WHEN txn_type='Repayment' THEN -amount ELSE amount END) FROM staff_transactions st WHERE st.staff_id=s.id),0) balance FROM staff s WHERE s.active=1 ORDER BY s.name"):
            t.insert("","end",iid=str(r['id']),values=(r['id'],r['name'],r['phone'],r['role'],self.money(r['salary']),self.money(r['balance'])))
        self.staff_tree=t

    def staff_account(self):
        sel=self.staff_tree.selection() if hasattr(self,"staff_tree") else ()
        if not sel:
            return messagebox.showwarning("Staff Account","Select a staff member first.",parent=self)
        sid=int(sel[0]); staff=self.s.q("SELECT * FROM staff WHERE id=?",(sid,)).fetchone()
        w=self.dialog("Staff Account — "+staff['name'],760,560); f=ttk.Frame(w,padding=15); f.pack(fill='both',expand=True)
        bal=self.s.q("SELECT COALESCE(SUM(CASE WHEN txn_type='Advance' THEN amount WHEN txn_type='Repayment' THEN -amount ELSE amount END),0) FROM staff_transactions WHERE staff_id=?",(sid,)).fetchone()[0]
        ttk.Label(f,text=f"{staff['name']} — Outstanding {self.money(bal)}",font=("Segoe UI",16,"bold")).pack(anchor='w')
        t=self.table(f,("type","amount","note","date"),{"type":"Transaction","amount":"Amount","note":"Note","date":"Date"},12)
        for r in self.s.rows("SELECT txn_type,amount,note,created_at FROM staff_transactions WHERE staff_id=? ORDER BY id DESC",(sid,)):
            t.insert("","end",values=(r['txn_type'],self.money(r['amount']),r['note'],r['created_at']))
        bar=ttk.Frame(f); bar.pack(fill='x',pady=10)
        ttk.Button(bar,text="ADD ADVANCE / MONEY OUT",command=lambda:self._staff_txn_dialog(sid,"Advance",w)).pack(side='left')
        ttk.Button(bar,text="RECEIVE REPAYMENT",command=lambda:self._staff_txn_dialog(sid,"Repayment",w)).pack(side='left',padx=5)

    def _staff_txn_dialog(self,sid,typ,parent):
        w=self.dialog("Staff "+typ,420,300); f=ttk.Frame(w,padding=18); f.pack(fill='both',expand=True); a=tk.DoubleVar(); n=tk.StringVar()
        ttk.Label(f,text="Amount").pack(anchor='w'); ttk.Entry(f,textvariable=a).pack(fill='x',pady=5); ttk.Label(f,text="Note").pack(anchor='w',pady=(8,2)); ttk.Entry(f,textvariable=n).pack(fill='x')
        def save():
            try:
                self.add_staff_transaction(sid,typ,a.get(),n.get().strip()); w.destroy(); parent.destroy(); self.show("Staff")
            except Exception as e:
                messagebox.showerror("Staff Account",str(e),parent=w)
        ttk.Button(f,text="SAVE TRANSACTION",style="Primary.TButton",command=save).pack(fill='x',pady=15)
    App.staff_account=staff_account; App._staff_txn_dialog=_staff_txn_dialog; App.page_staff=page_staff

    def page_financial_ledger(self):
        self.title("Financial Ledger","Every sale, payment, purchase, expense and party transaction is posted separately.")
        rows=self.s.rows("SELECT e.id,e.source_type,e.source_id,e.description,e.created_at,COALESCE(SUM(l.debit),0) debit,COALESCE(SUM(l.credit),0) credit FROM ledger_entries e JOIN ledger_lines l ON l.entry_id=e.id GROUP BY e.id ORDER BY e.id DESC LIMIT 500")
        t=self.table(self.bodyinner,("id","source","source_id","description","debit","credit","date"),{"id":"Entry","source":"Source","source_id":"Source ID","description":"Description","debit":"Debit","credit":"Credit","date":"Date"},20)
        for r in rows:
            t.insert("","end",values=(r['id'],r['source_type'],r['source_id'],r['description'],self.money(r['debit']),self.money(r['credit']),r['created_at']))
        ttk.Button(self.bodyinner,text="REBUILD / VERIFY LEDGER",command=lambda:(_rebuild(self.s.c),self.show("Financial Ledger"))).pack(fill='x',pady=8)
        ttk.Label(self.bodyinner,text="This ledger is derived from the POS transaction tables and can be rebuilt safely; it does not delete sales or other business data.",foreground="#64748b").pack(anchor='w')
    App.page_financial_ledger=page_financial_ledger
    nav=list(getattr(App,"NAV",[]))
    if "Financial Ledger" not in nav:
        nav.append("Financial Ledger")
    App.NAV=nav
    App._financial_bridge_installed=True
    return App
