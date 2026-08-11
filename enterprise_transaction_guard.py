"""Enterprise transaction integrity guard for DEEP-Seek.

This layer is deliberately small and deterministic. It adds database invariants,
idempotent source ledgers, monetary normalization and a reconciliation report
without replacing the existing POS UI or deleting legacy data.
"""
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
import sqlite3

Q = Decimal("0.01")

def money(value):
    return Decimal(str(value or 0)).quantize(Q, rounding=ROUND_HALF_UP)

def now():
    return datetime.now().isoformat(timespec="seconds")

SCHEMA = """
CREATE TABLE IF NOT EXISTS tx_guard_events(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 source_type TEXT NOT NULL,
 source_id INTEGER NOT NULL,
 amount NUMERIC NOT NULL,
 created_at TEXT NOT NULL,
 UNIQUE(source_type,source_id)
);
CREATE TABLE IF NOT EXISTS tx_guard_reconciliation(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 checked_at TEXT NOT NULL,
 sales_total NUMERIC NOT NULL,
 payments_total NUMERIC NOT NULL,
 expenses_total NUMERIC NOT NULL,
 purchases_total NUMERIC NOT NULL,
 customer_balance NUMERIC NOT NULL,
 supplier_balance NUMERIC NOT NULL,
 ledger_debit NUMERIC NOT NULL,
 ledger_credit NUMERIC NOT NULL,
 status TEXT NOT NULL,
 details TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_tx_guard_events_source ON tx_guard_events(source_type,source_id);
"""

def install(App):
    if getattr(App, "_enterprise_transaction_guard", False):
        return App
    old_init = App.__init__
    def init(self, *args, **kwargs):
        old_init(self, *args, **kwargs)
        c = self.s.c
        c.executescript(SCHEMA)
        c.execute("PRAGMA foreign_keys=ON")
        c.execute("PRAGMA busy_timeout=10000")
        c.commit()
    App.__init__ = init

    def normalize_money(self, value):
        return float(money(value))
    App.normalize_money = normalize_money

    def reconcile_financials(self, persist=True):
        c = self.s.c
        sales = money(c.execute("SELECT COALESCE(SUM(total),0) FROM sales WHERE status!='Cancelled'").fetchone()[0])
        payments = money(c.execute("SELECT COALESCE(SUM(amount),0) FROM payments").fetchone()[0])
        expenses = money(c.execute("SELECT COALESCE(SUM(amount),0) FROM expenses").fetchone()[0])
        purchases = money(c.execute("SELECT COALESCE(SUM(total),0) FROM purchases").fetchone()[0])
        customers = money(c.execute("SELECT COALESCE(SUM(balance),0) FROM customers").fetchone()[0])
        suppliers = money(c.execute("SELECT COALESCE(SUM(balance),0) FROM suppliers").fetchone()[0])
        debit = money(c.execute("SELECT COALESCE(SUM(debit),0) FROM ledger_lines").fetchone()[0]) if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='ledger_lines'").fetchone() else Decimal('0')
        credit = money(c.execute("SELECT COALESCE(SUM(credit),0) FROM ledger_lines").fetchone()[0]) if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='ledger_lines'").fetchone() else Decimal('0')
        issues=[]
        if abs(debit-credit) > Q: issues.append("ledger is unbalanced")
        if payments > sales + purchases + expenses + Decimal('0.01'):
            issues.append("payments exceed recorded transaction base")
        status = "OK" if not issues else "REVIEW"
        if persist:
            c.execute("INSERT INTO tx_guard_reconciliation(checked_at,sales_total,payments_total,expenses_total,purchases_total,customer_balance,supplier_balance,ledger_debit,ledger_credit,status,details) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(now(),str(sales),str(payments),str(expenses),str(purchases),str(customers),str(suppliers),str(debit),str(credit),status,"; ".join(issues)))
            c.commit()
        return {"status":status,"sales":str(sales),"payments":str(payments),"expenses":str(expenses),"purchases":str(purchases),"customer_balance":str(customers),"supplier_balance":str(suppliers),"ledger_debit":str(debit),"ledger_credit":str(credit),"issues":issues}
    App.reconcile_financials = reconcile_financials

    def page_integrity_monitor(self):
        self.title("Integrity Monitor", "Enterprise reconciliation for sales, payments, expenses, purchases, party balances and ledger totals.")
        import tkinter as tk
        from tkinter import ttk, messagebox
        out=tk.Text(self.bodyinner,height=22,wrap="word",font=("Consolas",10)); out.pack(fill="both",expand=True)
        def run():
            try:
                r=self.reconcile_financials(True)
                out.delete("1.0","end")
                for k,v in r.items(): out.insert("end",f"{k}: {v}\n")
                if r["status"] != "OK": messagebox.showwarning("Integrity Review","One or more reconciliation checks require review.",parent=self)
            except Exception as exc:
                out.delete("1.0","end"); out.insert("end",str(exc))
        ttk.Button(self.bodyinner,text="RUN FULL RECONCILIATION",style="Primary.TButton",command=run).pack(fill="x",pady=8)
        run()
    App.page_integrity_monitor = page_integrity_monitor
    nav=list(getattr(App,"NAV",[]))
    if "Integrity Monitor" not in nav: nav.append("Integrity Monitor")
    App.NAV=nav
    App._enterprise_transaction_guard=True
    return App
