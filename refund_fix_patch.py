"""Hotfix for Returns/Refunds NameError and robust refund workflow."""
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime


def now():
    return datetime.now().isoformat(timespec="seconds")


def money(v):
    return f"Rs. {float(v or 0):,.2f}"


def install(App):
    def page_returns_refunds(self):
        self.title("Returns / Refunds", "Process full or partial refunds with stock restoration and audit logging.")
        top = ttk.Frame(self.bodyinner); top.pack(fill="x", pady=(0, 8))
        q = tk.StringVar()
        ttk.Label(top, text="Invoice / customer / phone").pack(side="left", padx=(0, 6))
        ttk.Entry(top, textvariable=q).pack(side="left", fill="x", expand=True)
        tree = self.table(self.bodyinner, ("id","invoice","date","customer","total","refunded","status"),
                          {"id":"ID","invoice":"Invoice","date":"Date","customer":"Customer","total":"Sale Total","refunded":"Refunded","status":"Status"}, 18)

        def reload_rows():
            tree.delete(*tree.get_children())
            term = q.get().strip().lower()
            rows = self.s.rows("""SELECT s.id,s.invoice_no,s.created_at,COALESCE(c.name,'Walk-in') customer,
                s.total,s.status,COALESCE((SELECT SUM(amount) FROM refunds r WHERE r.sale_id=s.id),0) refunded
                FROM sales s LEFT JOIN customers c ON c.id=s.customer_id
                WHERE lower(s.invoice_no||' '||COALESCE(c.name,'')||' '||COALESCE(c.phone,'')) LIKE ?
                ORDER BY s.id DESC LIMIT 200""", (f"%{term}%",))
            for r in rows:
                tree.insert("", "end", iid=str(r["id"]), values=(r["id"],r["invoice_no"],r["created_at"],r["customer"],money(r["total"]),money(r["refunded"]),r["status"]))

        def open_selected():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Refund", "Select an invoice first.", parent=self); return
            self._open_refund_dialog(int(sel[0]))

        ttk.Button(top, text="SEARCH", command=reload_rows).pack(side="left", padx=5)
        ttk.Button(top, text="REFRESH", command=reload_rows).pack(side="left")
        ttk.Button(self.bodyinner, text="OPEN SELECTED INVOICE", style="Primary.TButton", command=open_selected).pack(fill="x", pady=8)
        tree.bind("<Double-1>", lambda _e: open_selected())
        reload_rows()

    def open_refund_dialog(self, sid):
        sale = self.s.q("SELECT s.*,COALESCE(c.name,'Walk-in') customer FROM sales s LEFT JOIN customers c ON c.id=s.customer_id WHERE s.id=?", (sid,)).fetchone()
        if not sale:
            messagebox.showerror("Refund", "Sale not found.", parent=self); return
        already = float(self.s.q("SELECT COALESCE(SUM(amount),0) x FROM refunds WHERE sale_id=?", (sid,)).fetchone()["x"])
        if already >= float(sale["total"]) - 0.001:
            messagebox.showinfo("Refund", "This invoice is already fully refunded.", parent=self); return
        w = self.dialog(f"Refund {sale['invoice_no']}", 980, 700)
        f = ttk.Frame(w, padding=15); f.pack(fill="both", expand=True)
        ttk.Label(f, text=f"{sale['invoice_no']} • {sale['customer']} • Sale {money(sale['total'])}", font=("Segoe UI",16,"bold")).pack(anchor="w")
        ttk.Label(f, text=f"Previously refunded: {money(already)}", foreground="#64748b").pack(anchor="w", pady=(2,10))
        cols=("id","product","sold","refunded","available","price","refund_qty")
        t=self.table(f, cols, {"id":"Line","product":"Product","sold":"Sold","refunded":"Refunded","available":"Available","price":"Unit Price","refund_qty":"Refund Qty"}, 14)
        lines={}
        for r in self.s.rows("""SELECT si.*,COALESCE((SELECT SUM(ri.quantity) FROM refund_items ri WHERE ri.sale_item_id=si.id),0) refunded_qty
            FROM sale_items si WHERE si.sale_id=? ORDER BY si.id""", (sid,)):
            available=max(0,float(r["quantity"])-float(r["refunded_qty"]))
            iid=str(r["id"]); lines[iid]=r
            t.insert("","end",iid=iid,values=(r["id"],r["product_name"],r["quantity"],r["refunded_qty"],available,money(r["unit_price"]),"0"))
        bar=ttk.Frame(f); bar.pack(fill="x",pady=8)
        qty=tk.StringVar(value="0")
        ttk.Label(bar,text="Selected refund quantity").pack(side="left"); ttk.Entry(bar,textvariable=qty,width=12).pack(side="left",padx=6)
        method=tk.StringVar(value="Cash"); reason=tk.StringVar()
        ttk.Label(f,text="Refund Method").pack(anchor="w",pady=(8,2)); ttk.Combobox(f,textvariable=method,values=["Cash","Card","Other","Credit Balance"],state="readonly").pack(fill="x")
        ttk.Label(f,text="Reason").pack(anchor="w",pady=(8,2)); ttk.Entry(f,textvariable=reason).pack(fill="x")
        total_var=tk.StringVar(value=money(0)); ttk.Label(f,textvariable=total_var,font=("Segoe UI",18,"bold")).pack(anchor="e",pady=8)

        def recalc():
            total=0.0
            for iid in t.get_children():
                try: total += float(t.set(iid,"refund_qty"))*float(lines[iid]["unit_price"])
                except (ValueError,TypeError): pass
            total_var.set(money(total))

        def set_qty():
            sel=t.selection()
            if not sel:
                messagebox.showwarning("Refund","Select a sale line first.",parent=w); return
            try:
                n=float(qty.get()); r=lines[sel[0]]; available=max(0,float(r["quantity"])-float(r["refunded_qty"]))
                if n<=0 or n>available: raise ValueError("Quantity exceeds refundable quantity.")
                t.set(sel[0],"refund_qty",n); recalc()
            except Exception as exc:
                messagebox.showerror("Refund",str(exc),parent=w)

        def save():
            selected=[]; total=0.0
            for iid in t.get_children():
                try: n=float(t.set(iid,"refund_qty"))
                except (ValueError,TypeError): n=0
                if n>0:
                    r=lines[iid]; selected.append((r,n)); total += n*float(r["unit_price"])
            if not selected or total<=0:
                messagebox.showwarning("Refund","Set at least one refund quantity.",parent=w); return
            if already+total > float(sale["total"])+0.001:
                messagebox.showerror("Refund","Refund exceeds the invoice total.",parent=w); return
            try:
                self.s.c.execute("BEGIN")
                cur=self.s.q("INSERT INTO refunds(sale_id,user_id,amount,method,reason,created_at) VALUES(?,?,?,?,?,?)",(sid,self.user["id"],total,method.get(),reason.get().strip(),now()))
                rid=cur.lastrowid
                for r,n in selected:
                    line_total=n*float(r["unit_price"])
                    self.s.q("INSERT INTO refund_items(refund_id,sale_item_id,product_id,product_name,quantity,unit_price,line_total) VALUES(?,?,?,?,?,?,?)",(rid,r["id"],r["product_id"],r["product_name"],n,r["unit_price"],line_total))
                    self.s.q("UPDATE products SET stock=stock+? WHERE id=?",(n,r["product_id"]))
                    self.s.q("INSERT INTO stock_movements(product_id,qty,movement_type,note,created_at,user_id) VALUES(?,?,?,?,?,?)",(r["product_id"],n,"REFUND",sale["invoice_no"],now(),self.user["id"]))
                refunded=already+total
                status="Refunded" if refunded >= float(sale["total"])-0.001 else sale["status"]
                self.s.q("UPDATE sales SET status=? WHERE id=?",(status,sid))
                self.s.q("INSERT INTO audit_log(user_id,action,entity,entity_id,details,created_at) VALUES(?,?,?,?,?,?)",(self.user["id"],"REFUND","sale",sid,f"{money(total)} via {method.get()}: {reason.get().strip()}",now()))
                self.s.c.commit(); w.destroy(); self.show("Returns / Refunds")
            except Exception as exc:
                try: self.s.c.rollback()
                except Exception: pass
                messagebox.showerror("Refund failed", f"The refund could not be completed.\n\n{type(exc).__name__}: {exc}", parent=w)
        ttk.Button(bar,text="SET QTY",command=set_qty).pack(side="left")
        ttk.Button(f,text="PROCESS REFUND / RESTORE STOCK",style="Primary.TButton",command=save).pack(fill="x",pady=12)

    App.page_returns_refunds = page_returns_refunds
    App._open_refund_dialog = open_refund_dialog
    return App
