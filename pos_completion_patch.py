"""Completion layer for production POS operations.

Adds additive features without deleting or rewriting existing business data:
- Returns / refunds with partial quantity support and inventory restoration.
- End-of-day reconciliation using sales, refunds, expenses and cash shifts.
- System health checks for SQLite integrity, negative stock and orphaned records.
- Checkout stock preflight to prevent knowingly selling unavailable quantities.
"""
import os
import shutil
import sqlite3
import tkinter as tk
from datetime import datetime
from tkinter import ttk, messagebox, filedialog


def now():
    return datetime.now().isoformat(timespec="seconds")


def money(v):
    return f"Rs. {float(v or 0):,.2f}"


def install(App):
    if getattr(App, "_completion_layer_installed", False):
        return App

    old_init = App.__init__
    def init(self, *args, **kwargs):
        old_init(self, *args, **kwargs)
        db = self.s
        db.c.executescript("""
        CREATE TABLE IF NOT EXISTS refunds(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER NOT NULL,
            user_id INTEGER,
            amount REAL NOT NULL,
            method TEXT NOT NULL,
            reason TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS refund_items(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            refund_id INTEGER NOT NULL,
            sale_item_id INTEGER NOT NULL,
            product_id INTEGER,
            product_name TEXT,
            quantity REAL NOT NULL,
            unit_price REAL NOT NULL,
            line_total REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_refunds_sale ON refunds(sale_id,created_at);
        CREATE INDEX IF NOT EXISTS idx_refund_items_refund ON refund_items(refund_id);
        """)
        db.c.commit()

    App.__init__ = init

    old_checkout = getattr(App, "checkout", None)
    if old_checkout and not getattr(App, "_completion_checkout_installed", False):
        def checkout(self, *args, **kwargs):
            # Fail early before opening checkout if the current cart already
            # exceeds available stock. The final stock update remains owned by
            # the existing checkout transaction.
            try:
                shortages = []
                for item in getattr(self, "cart", {}).values():
                    row = self.s.q("SELECT stock,active FROM products WHERE id=?", (item["id"],)).fetchone()
                    if not row or not row["active"]:
                        shortages.append(f"{item['name']}: unavailable")
                    elif float(row["stock"]) < float(item["qty"]):
                        shortages.append(f"{item['name']}: {row['stock']} available")
                if shortages:
                    messagebox.showwarning("Stock unavailable", "Cannot checkout:\n\n" + "\n".join(shortages), parent=self)
                    return
            except Exception:
                pass
            return old_checkout(self, *args, **kwargs)
        App.checkout = checkout
        App._completion_checkout_installed = True

    # ----------------------------- Returns -----------------------------
    def page_returns_refunds(self):
        self.title("Returns / Refunds", "Refund full or partial quantities while restoring inventory and preserving an audit trail.")
        top = ttk.Frame(self.bodyinner); top.pack(fill="x", pady=(0, 8))
        q = tk.StringVar()
        ttk.Label(top, text="Invoice / customer / phone").pack(side="left", padx=(0, 6))
        entry = ttk.Entry(top, textvariable=q); entry.pack(side="left", fill="x", expand=True)
        ttk.Button(top, text="SEARCH", style="Soft.TButton", command=lambda: reload()).pack(side="left", padx=5)
        ttk.Button(top, text="REFRESH", command=lambda: reload()).pack(side="left")
        tree = self.table(self.bodyinner,
            ("id","invoice","date","customer","total","refunded","status"),
            {"id":"ID","invoice":"Invoice","date":"Date","customer":"Customer","total":"Sale Total","refunded":"Refunded","status":"Status"}, 18)

        def reload():
            tree.delete(*tree.get_children())
            term = q.get().strip().lower()
            rows = self.s.rows("""
                SELECT s.id,s.invoice_no,s.created_at,COALESCE(c.name,'Walk-in') customer,
                       s.total,s.status,COALESCE((SELECT SUM(amount) FROM refunds r WHERE r.sale_id=s.id),0) refunded
                FROM sales s LEFT JOIN customers c ON c.id=s.customer_id
                WHERE lower(s.invoice_no||' '||COALESCE(c.name,'')||' '||COALESCE(c.phone,'')) LIKE ?
                ORDER BY s.id DESC LIMIT 200
            """, (f"%{term}%",))
            for r in rows:
                tree.insert("", "end", iid=str(r["id"]), values=(r["id"],r["invoice_no"],r["created_at"],r["customer"],money(r["total"]),money(r["refunded"]),r["status"]))

        def open_selected():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Refund", "Select an invoice first.", parent=self); return
            refund_dialog(int(sel[0]))

        ttk.Button(self.bodyinner, text="OPEN SELECTED INVOICE", style="Primary.TButton", command=open_selected).pack(fill="x", pady=8)
        tree.bind("<Double-1>", lambda _e: open_selected())
        reload()

    def refund_dialog(sid):
        sale = self.s.q("SELECT s.*,COALESCE(c.name,'Walk-in') customer FROM sales s LEFT JOIN customers c ON c.id=s.customer_id WHERE s.id=?", (sid,)).fetchone()
        if not sale: return
        already = float(self.s.q("SELECT COALESCE(SUM(amount),0) x FROM refunds WHERE sale_id=?", (sid,)).fetchone()["x"])
        if already >= float(sale["total"]) - 0.001:
            messagebox.showinfo("Refund", "This invoice is already fully refunded.", parent=self); return
        w = self.dialog(f"Refund {sale['invoice_no']}", 980, 700)
        f = ttk.Frame(w, padding=15); f.pack(fill="both", expand=True)
        ttk.Label(f, text=f"{sale['invoice_no']} • {sale['customer']} • Sale {money(sale['total'])}", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(f, text=f"Previously refunded: {money(already)}", foreground="#64748b").pack(anchor="w", pady=(2, 10))
        cols=("id","product","sold","refunded","available","price","refund_qty")
        t=self.table(f, cols, {"id":"Line","product":"Product","sold":"Sold","refunded":"Refunded","available":"Available","price":"Unit Price","refund_qty":"Refund Qty"}, 14)
        lines={}
        for r in self.s.rows("""
            SELECT si.*, COALESCE((SELECT SUM(ri.quantity) FROM refund_items ri WHERE ri.sale_item_id=si.id),0) refunded_qty
            FROM sale_items si WHERE si.sale_id=? ORDER BY si.id
        """, (sid,)):
            available=max(0,float(r["quantity"])-float(r["refunded_qty"]))
            iid=str(r["id"]); lines[iid]=r
            t.insert("", "end", iid=iid, values=(r["id"],r["product_name"],r["quantity"],r["refunded_qty"],available,money(r["unit_price"]),"0"))
        bar=ttk.Frame(f); bar.pack(fill="x", pady=8)
        qty=tk.StringVar(value="0"); ttk.Label(bar,text="Selected refund quantity").pack(side="left"); ttk.Entry(bar,textvariable=qty,width=12).pack(side="left",padx=6)
        ttk.Button(bar,text="SET QTY",command=lambda: set_qty()).pack(side="left")
        method=tk.StringVar(value="Cash"); reason=tk.StringVar()
        ttk.Label(f,text="Refund Method").pack(anchor="w",pady=(8,2)); ttk.Combobox(f,textvariable=method,values=["Cash","Card","Other","Credit Balance"],state="readonly").pack(fill="x")
        ttk.Label(f,text="Reason").pack(anchor="w",pady=(8,2)); ttk.Entry(f,textvariable=reason).pack(fill="x")
        total_var=tk.StringVar(value=money(0)); ttk.Label(f,textvariable=total_var,font=("Segoe UI",18,"bold")).pack(anchor="e",pady=8)

        def set_qty():
            sel=t.selection()
            if not sel:
                messagebox.showwarning("Refund","Select a sale line first.",parent=w); return
            try:
                n=float(qty.get()); r=lines[sel[0]]; available=max(0,float(r["quantity"])-float(r["refunded_qty"]))
                if n<=0 or n>available: raise ValueError("Quantity exceeds refundable quantity.")
                t.set(sel[0],"refund_qty",n); recalc()
            except Exception as exc: messagebox.showerror("Refund",str(exc),parent=w)

        def recalc():
            total=0
            for iid in t.get_children():
                try: total += float(t.set(iid,"refund_qty")) * float(lines[iid]["unit_price"])
                except Exception: pass
            total_var.set(money(total))

        def save():
            selected=[]; total=0
            for iid in t.get_children():
                try: n=float(t.set(iid,"refund_qty"))
                except Exception: n=0
                if n>0:
                    r=lines[iid]; selected.append((r,n)); total += n*float(r["unit_price"])
            if not selected or total<=0:
                messagebox.showwarning("Refund","Set at least one refund quantity.",parent=w); return
            if already+total > float(sale["total"])+0.001:
                messagebox.showerror("Refund","Refund exceeds the invoice total.",parent=w); return
            try:
                cur=self.s.q("INSERT INTO refunds(sale_id,user_id,amount,method,reason,created_at) VALUES(?,?,?,?,?,?)",(sid,self.user["id"],total,method.get(),reason.get().strip(),now()))
                rid=cur.lastrowid
                for r,n in selected:
                    line_total=n*float(r["unit_price"])
                    self.s.q("INSERT INTO refund_items(refund_id,sale_item_id,product_id,product_name,quantity,unit_price,line_total) VALUES(?,?,?,?,?,?,?)",(rid,r["id"],r["product_id"],r["product_name"],n,r["unit_price"],line_total))
                    self.s.q("UPDATE products SET stock=stock+? WHERE id=?",(n,r["product_id"]))
                    self.s.q("INSERT INTO stock_movements(product_id,qty,movement_type,note,created_at,user_id) VALUES(?,?,?,?,?,?)",(r["product_id"],n,"REFUND",sale["invoice_no"],now(),self.user["id"]))
                if sale["customer_id"] and sale["payment_method"]=="Credit":
                    self.s.q("UPDATE customers SET balance=MAX(0,COALESCE(balance,0)-?) WHERE id=?",(total,sale["customer_id"]))
                    self.s.q("INSERT INTO party_transactions(party_type,party_id,txn_type,amount,note,created_at,user_id) VALUES(?,?,?,?,?,?,?)",("Customer",sale["customer_id"],"Refund",total,sale["invoice_no"],now(),self.user["id"]))
                refunded=already+total
                status="Refunded" if refunded >= float(sale["total"])-0.001 else sale["status"]
                self.s.q("UPDATE sales SET status=? WHERE id=?",(status,sid))
                self.s.q("INSERT INTO audit_log(user_id,action,entity,entity_id,details,created_at) VALUES(?,?,?,?,?,?)",(self.user["id"],"REFUND","sale",sid,f"{money(total)} via {method.get()}",now()))
                self.s.c.commit(); w.destroy(); self.show("Returns / Refunds")
            except Exception as exc:
                self.s.c.rollback(); messagebox.showerror("Refund failed",str(exc),parent=w)
        ttk.Button(f,text="PROCESS REFUND / RESTORE STOCK",style="Primary.TButton",command=save).pack(fill="x",pady=12)

    App.page_returns_refunds=page_returns_refunds
    App._refund_dialog=refund_dialog

    # ----------------------------- End of day --------------------------
    def page_end_of_day(self):
        self.title("End of Day", "Reconcile sales, refunds, expenses and cash before closing the business day.")
        datev=tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        top=ttk.Frame(self.bodyinner); top.pack(fill="x",pady=(0,10))
        ttk.Label(top,text="Business date").pack(side="left"); ttk.Entry(top,textvariable=datev,width=14).pack(side="left",padx=6)
        result=ttk.Frame(self.bodyinner); result.pack(fill="x")
        def refresh():
            for w in result.winfo_children(): w.destroy()
            d=datev.get().strip();
            sales=self.s.q("SELECT COUNT(*) n,COALESCE(SUM(total),0) total,COALESCE(SUM(CASE WHEN payment_method='Cash' THEN total ELSE 0 END),0) cash FROM sales WHERE date(created_at)=? AND status!='Cancelled'",(d,)).fetchone()
            refunds=self.s.q("SELECT COALESCE(SUM(amount),0) total FROM refunds WHERE date(created_at)=?",(d,)).fetchone()["total"]
            expenses=self.s.q("SELECT COALESCE(SUM(amount),0) total FROM expenses WHERE date(created_at)=?",(d,)).fetchone()["total"]
            paid=self.s.q("SELECT COALESCE(SUM(amount),0) total FROM payments WHERE date(created_at)=? AND method='Cash'",(d,)).fetchone()["total"]
            opening=self.s.q("SELECT COALESCE(SUM(opening_cash),0) total FROM shifts WHERE date(opened_at)=?",(d,)).fetchone()["total"]
            net=float(sales["total"])-float(refunds)-float(expenses)
            expected=float(opening)+float(paid)-float(refunds)-float(expenses)
            for title,value,note in [("Gross Sales",money(sales["total"]),f"{sales['n']} orders"),("Refunds",money(refunds),"Returns processed"),("Expenses",money(expenses),"Operating expenses"),("Net Sales",money(net),"Gross − refunds − expenses"),("Expected Cash",money(expected),f"Opening {money(opening)} + cash movements")]:
                box=ttk.LabelFrame(result,text=title,padding=14); box.pack(side="left",fill="both",expand=True,padx=3); ttk.Label(box,text=value,font=("Segoe UI",17,"bold")).pack(anchor="w"); ttk.Label(box,text=note,foreground="#64748b").pack(anchor="w")
            t=self.table(self.bodyinner,("method","amount"),{"method":"Payment Method","amount":"Amount"},8)
            for r in self.s.rows("SELECT method,COALESCE(SUM(amount),0) amount FROM payments WHERE date(created_at)=? GROUP BY method ORDER BY method",(d,)): t.insert("","end",values=(r["method"],money(r["amount"])))
        ttk.Button(top,text="RECALCULATE",style="Primary.TButton",command=refresh).pack(side="left")
        ttk.Button(top,text="BACKUP DATABASE",command=self.backup).pack(side="left",padx=5)
        refresh()
    App.page_end_of_day=page_end_of_day

    # ----------------------------- System health ----------------------
    def page_system_health(self):
        self.title("System Health", "Database integrity, stock anomalies, orphan checks and safe backup tools.")
        out=tk.Text(self.bodyinner,height=20,wrap="word",font=("Consolas",10)); out.pack(fill="both",expand=True)
        def run():
            out.delete("1.0","end")
            checks=[]
            try:
                integrity=self.s.q("PRAGMA integrity_check").fetchone()[0]; checks.append(("SQLite integrity",integrity))
                negative=self.s.q("SELECT COUNT(*) FROM products WHERE stock<0").fetchone()[0]; checks.append(("Negative stock",negative))
                orphan=self.s.q("SELECT COUNT(*) FROM sale_items si LEFT JOIN sales s ON s.id=si.sale_id WHERE s.id IS NULL").fetchone()[0]; checks.append(("Orphan sale items",orphan))
                orphan_stock=self.s.q("SELECT COUNT(*) FROM stock_movements m LEFT JOIN products p ON p.id=m.product_id WHERE p.id IS NULL").fetchone()[0]; checks.append(("Orphan stock movements",orphan_stock))
                for label,value in checks: out.insert("end",f"{label}: {value}\n")
                out.insert("end","\nDatabase: " + str(getattr(self.s,'path', 'pos.db')) + "\n")
                out.insert("end","\nStatus: " + ("HEALTHY" if integrity=="ok" and negative==0 and orphan==0 and orphan_stock==0 else "REVIEW REQUIRED") + "\n")
            except Exception as exc: out.insert("end",f"Health check failed: {exc}\n")
        bar=ttk.Frame(self.bodyinner); bar.pack(fill="x",pady=8)
        ttk.Button(bar,text="RUN HEALTH CHECK",style="Primary.TButton",command=run).pack(side="left")
        def backup_as():
            try:
                target=filedialog.asksaveasfilename(parent=self,defaultextension=".db",filetypes=[("SQLite database","*.db")],initialfile=f"pos-backup-{datetime.now():%Y%m%d-%H%M%S}.db")
                if not target:return
                self.s.c.commit(); shutil.copy2(self.s.c.execute("PRAGMA database_list").fetchone()[2],target); messagebox.showinfo("Backup",f"Backup saved to:\n{target}",parent=self)
            except Exception as exc: messagebox.showerror("Backup",str(exc),parent=self)
        ttk.Button(bar,text="EXPORT DATABASE COPY",command=backup_as).pack(side="left",padx=5)
        run()
    App.page_system_health=page_system_health

    # Navigation is additive; existing labels and pages stay intact.
    old_build_shell=App.build_shell
    def build_shell(self):
        old_build_shell(self)
        additions=["Returns / Refunds","End of Day","System Health"]
        for name in additions:
            if name in getattr(self,"navbuttons",{}): continue
            b=tk.Button(self.navbar,text=name,anchor="w",bg="#111827",fg="white",activebackground="#2563eb",activeforeground="white",relief="flat",bd=0,font=("Segoe UI",10,"bold"),padx=20,pady=9,command=lambda x=name:self.show(x))
            b.pack(fill="x"); self.navbuttons[name]=b
    App.build_shell=build_shell

    old_show=App.show
    def show(self,name):
        aliases={"Returns":"Returns / Refunds","Refunds":"Returns / Refunds","Z Report":"End of Day","Health":"System Health"}
        return old_show(self,aliases.get(name,name))
    App.show=show

    App._completion_layer_installed=True
    return App
