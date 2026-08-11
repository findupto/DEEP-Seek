"""Profit/Loss accounting and operational notification center for the POS.

Profit method:
Revenue (net sales after discounts/refunds) - COGS - operating expenses = Net Profit/Loss.
COGS is based on the cost price captured on each sale line; a trigger snapshots the
current product cost for new sales while legacy rows fall back to current product cost.
"""
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime


def now():
    return datetime.now().isoformat(timespec="seconds")


def money(v):
    return f"Rs. {float(v or 0):,.2f}"


def install(App):
    if getattr(App, "_profit_notifications_installed", False):
        return App
    old_init = App.__init__

    def init(self, *args, **kwargs):
        old_init(self, *args, **kwargs)
        try:
            self.s.c.executescript("""
            ALTER TABLE sale_items ADD COLUMN cost_price REAL DEFAULT NULL;
            """)
        except sqlite3.OperationalError:
            pass
        try:
            self.s.c.executescript("""
            CREATE TRIGGER IF NOT EXISTS trg_sale_item_snapshot_cost
            AFTER INSERT ON sale_items
            WHEN NEW.cost_price IS NULL
            BEGIN
                UPDATE sale_items SET cost_price=(SELECT COALESCE(cost,0) FROM products WHERE id=NEW.product_id)
                WHERE id=NEW.id;
            END;
            CREATE TABLE IF NOT EXISTS notifications(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                severity TEXT DEFAULT 'info',
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                entity TEXT DEFAULT '',
                entity_id INTEGER,
                is_read INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                UNIQUE(type,entity,entity_id)
            );
            CREATE INDEX IF NOT EXISTS idx_notifications_read ON notifications(is_read,created_at);
            CREATE INDEX IF NOT EXISTS idx_notifications_type ON notifications(type,created_at);
            """)
            self.s.c.commit()
        except sqlite3.Error:
            pass

    App.__init__ = init

    def notify(self, title, message, type="general", severity="info", entity="", entity_id=None):
        self.s.q("""INSERT OR IGNORE INTO notifications(type,severity,title,message,entity,entity_id,is_read,created_at)
                    VALUES(?,?,?,?,?,?,0,?)""", (type,severity,title,message,entity,entity_id,now()))
        self.s.c.commit()

    def refresh_notifications(self):
        """Generate current actionable alerts and return unread notifications."""
        try:
            for r in self.s.rows("SELECT id,name,stock FROM products WHERE active=1 AND stock<=0"):
                self.notify("Out of Stock", f"{r['name']} has no stock remaining.", "out_of_stock", "critical", "product", r['id'])
            for r in self.s.rows("SELECT id,name,stock FROM products WHERE active=1 AND stock>0 AND stock<=5"):
                self.notify("Low Stock", f"{r['name']} has only {r['stock']} units remaining.", "low_stock", "warning", "product", r['id'])
            for r in self.s.rows("SELECT id,name,balance FROM customers WHERE active=1 AND COALESCE(balance,0)>0 ORDER BY balance DESC LIMIT 100"):
                self.notify("Customer Due", f"{r['name']} has an outstanding balance of {money(r['balance'])}.", "customer_due", "warning", "customer", r['id'])
            neg = self.s.q("SELECT COUNT(*) n FROM products WHERE stock<0").fetchone()["n"]
            if neg:
                self.notify("Inventory Integrity", f"{neg} product(s) have negative stock.", "negative_stock", "critical", "inventory", 0)
            return self.s.rows("SELECT * FROM notifications WHERE is_read=0 ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END, id DESC LIMIT 100")
        except Exception:
            return []

    App.notify = notify
    App.refresh_notifications = refresh_notifications

    def page_profit_loss(self):
        self.title("Profit / Loss", "Revenue − cost of goods sold − operating expenses = net profit/loss.")
        top = ttk.Frame(self.bodyinner); top.pack(fill="x", pady=(0,10))
        datev=tk.StringVar(value=datetime.now().strftime("%Y-%m-%d")); ttk.Label(top,text="From").pack(side="left"); ttk.Entry(top,textvariable=datev,width=13).pack(side="left",padx=5)
        date2=tk.StringVar(value=datetime.now().strftime("%Y-%m-%d")); ttk.Label(top,text="To").pack(side="left"); ttk.Entry(top,textvariable=date2,width=13).pack(side="left",padx=5)
        result=ttk.Frame(self.bodyinner); result.pack(fill="x", pady=(0,10))
        detail=ttk.Frame(self.bodyinner); detail.pack(fill="both",expand=True)
        def refresh():
            for w in result.winfo_children(): w.destroy()
            for w in detail.winfo_children(): w.destroy()
            a,b=datev.get().strip(),date2.get().strip()
            sales=self.s.q("SELECT COALESCE(SUM(subtotal-discount),0) revenue,COALESCE(SUM(discount),0) discounts,COUNT(*) orders FROM sales WHERE date(created_at) BETWEEN ? AND ? AND status!='Cancelled'",(a,b)).fetchone()
            refunds=self.s.q("SELECT COALESCE(SUM(amount),0) x FROM refunds WHERE date(created_at) BETWEEN ? AND ?",(a,b)).fetchone()["x"]
            refund2=self.s.q("SELECT COALESCE(SUM(amount),0) x FROM sale_returns WHERE date(created_at) BETWEEN ? AND ?",(a,b)).fetchone()["x"] if self.s.q("SELECT name FROM sqlite_master WHERE type='table' AND name='sale_returns'").fetchone() else 0
            cogs=self.s.q("""SELECT COALESCE(SUM(si.quantity*COALESCE(si.cost_price,p.cost,0)),0) x
                              FROM sale_items si JOIN sales s ON s.id=si.sale_id LEFT JOIN products p ON p.id=si.product_id
                              WHERE date(s.created_at) BETWEEN ? AND ? AND s.status!='Cancelled'""",(a,b)).fetchone()["x"]
            expenses=self.s.q("SELECT COALESCE(SUM(amount),0) x FROM expenses WHERE date(created_at) BETWEEN ? AND ?",(a,b)).fetchone()["x"]
            net_revenue=float(sales["revenue"] or 0)-float(refunds or 0)-float(refund2 or 0)
            gross=float(net_revenue)-float(cogs or 0); net=gross-float(expenses or 0)
            margin=(net/net_revenue*100) if net_revenue else 0
            cards=[("Net Revenue",money(net_revenue)),("COGS",money(cogs)),("Gross Profit",money(gross)),("Expenses",money(expenses)),("NET PROFIT / LOSS",money(net)),("Net Margin",f"{margin:.2f}%")]
            for label,val in cards:
                box=ttk.LabelFrame(result,text=label,padding=12); box.pack(side="left",fill="both",expand=True,padx=3); ttk.Label(box,text=val,font=("Segoe UI",15,"bold")).pack(anchor="w")
            ttk.Label(detail,text=f"Orders: {sales['orders']}   •   Gross sales before refunds: {money(sales['revenue'])}   •   Discounts: {money(sales['discounts'])}",foreground="#64748b").pack(anchor="w",pady=5)
            t=ttk.Treeview(detail,columns=("category","amount"),show="headings",height=10); t.heading("category",text="Profit & Loss Line");t.heading("amount",text="Amount");t.column("category",width=350);t.column("amount",width=220);t.pack(fill="both",expand=True)
            for x,y in [("Net Revenue",net_revenue),("Cost of Goods Sold",cogs),("Gross Profit",gross),("Operating Expenses",expenses),("Net Profit / Loss",net)]: t.insert("","end",values=(x,money(y)))
        ttk.Button(top,text="CALCULATE",style="Primary.TButton",command=refresh).pack(side="left",padx=5)
        ttk.Button(top,text="REFRESH ALERTS",command=lambda:(self.refresh_notifications(),messagebox.showinfo("Notifications","Alerts refreshed.",parent=self))).pack(side="left")
        refresh()

    def page_notifications(self):
        self.title("Notifications", "Central operational alerts for stock, customer dues and system issues.")
        self.refresh_notifications()
        top=ttk.Frame(self.bodyinner);top.pack(fill="x",pady=(0,8))
        t=ttk.Treeview(self.bodyinner,columns=("severity","title","message","date","read"),show="headings",height=18)
        for c,h,w in (("severity","Level",90),("title","Alert",180),("message","Message",500),("date","Created",170),("read","Read",80)):
            t.heading(c,text=h);t.column(c,width=w,minwidth=70)
        t.pack(fill="both",expand=True)
        def reload():
            t.delete(*t.get_children()); self.refresh_notifications()
            for r in self.s.rows("SELECT * FROM notifications ORDER BY is_read ASC, id DESC LIMIT 300"):
                t.insert("","end",iid=str(r["id"]),values=(r["severity"],r["title"],r["message"],r["created_at"],"Yes" if r["is_read"] else "No"))
        def mark():
            for iid in t.selection(): self.s.q("UPDATE notifications SET is_read=1 WHERE id=?",(int(iid),))
            self.s.c.commit(); reload()
        ttk.Button(top,text="MARK SELECTED READ",style="Soft.TButton",command=mark).pack(side="left")
        ttk.Button(top,text="REFRESH",command=reload).pack(side="left",padx=5)
        reload()

    App.page_profit_loss=page_profit_loss
    App.page_notifications=page_notifications
    nav=list(getattr(App,"NAV",[]))
    for item in ["Profit / Loss","Notifications"]:
        if item not in nav:
            try: nav.insert(nav.index("Reports / Analytics")+1,item)
            except ValueError: nav.append(item)
    App.NAV=nav
    App._profit_notifications_installed=True
    return App
