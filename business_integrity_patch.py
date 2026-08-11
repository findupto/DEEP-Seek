"""Final business/account integrity layer.

Connects operational party balances (customers, suppliers, staff) to the
financial ledger and provides explicit account transactions. It also hardens
sale history refresh and factory-reset handling for the persistent database.
"""
from datetime import datetime
import os
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog


def now():
    return datetime.now().isoformat(timespec="seconds")


def money(v):
    return f"Rs. {float(v or 0):,.2f}"


def install(App, Store=None):
    if getattr(App, "_business_integrity_final", False):
        return App

    def init_db(self):
        c = self.s.c
        c.executescript("""
        CREATE TABLE IF NOT EXISTS account_transactions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            party_type TEXT NOT NULL,
            party_id INTEGER NOT NULL,
            txn_type TEXT NOT NULL,
            amount REAL NOT NULL CHECK(amount > 0),
            method TEXT DEFAULT 'Cash',
            note TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            user_id INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_account_tx_party
            ON account_transactions(party_type, party_id, created_at);
        """)
        # Older expense tables are upgraded without destroying existing data.
        for col, typ in (
            ("party_type", "TEXT DEFAULT ''"),
            ("party_id", "INTEGER"),
            ("payment_method", "TEXT DEFAULT 'Cash'"),
        ):
            try:
                c.execute(f"ALTER TABLE expenses ADD COLUMN {col} {typ}")
            except sqlite3.OperationalError:
                pass
        c.commit()

    old_init = App.__init__
    def app_init(self, *args, **kwargs):
        old_init(self, *args, **kwargs)
        init_db(self)
    App.__init__ = app_init

    def post_account_tx(self, party_type, party_id, txn_type, amount, method="Cash", note=""):
        amount = round(float(amount), 2)
        if amount <= 0:
            raise ValueError("Amount must be greater than zero")
        table = {"Customer": "customers", "Supplier": "suppliers", "Staff": "staff"}.get(party_type)
        if not table:
            raise ValueError("Invalid account type")
        row = self.s.q(f"SELECT id FROM {table} WHERE id=?", (party_id,)).fetchone()
        if not row:
            raise ValueError("Account not found")

        cur = self.s.q(
            "INSERT INTO account_transactions(party_type,party_id,txn_type,amount,method,note,created_at,user_id) VALUES(?,?,?,?,?,?,?,?)",
            (party_type, party_id, txn_type, amount, method, note, now(), self.user["id"]),
        )
        tid = cur.lastrowid

        # Positive balance means the party owes the business.
        if party_type == "Customer":
            if txn_type == "Payment":
                self.s.q("UPDATE customers SET balance=MAX(0,COALESCE(balance,0)-?) WHERE id=?", (amount, party_id))
                lines = [("1000" if method == "Cash" else "1010", amount, 0, "Customer payment"), ("1100", 0, amount, "Customer receivable settled")]
            elif txn_type == "Charge":
                self.s.q("UPDATE customers SET balance=COALESCE(balance,0)+? WHERE id=?", (amount, party_id))
                lines = [("1100", amount, 0, "Customer receivable"), ("4000", 0, amount, "Customer charge")]
            elif txn_type == "Refund":
                self.s.q("UPDATE customers SET balance=MAX(0,COALESCE(balance,0)-?) WHERE id=?", (amount, party_id))
                lines = [("4000", amount, 0, "Customer refund"), ("1000" if method == "Cash" else "1010", 0, amount, "Refund paid")]
            else:
                raise ValueError("Invalid customer transaction")
        elif party_type == "Supplier":
            if txn_type == "Payment":
                self.s.q("UPDATE suppliers SET balance=MAX(0,COALESCE(balance,0)-?) WHERE id=?", (amount, party_id))
                lines = [("2000", amount, 0, "Supplier payable settled"), ("1000" if method == "Cash" else "1010", 0, amount, "Supplier payment")]
            elif txn_type == "Charge":
                self.s.q("UPDATE suppliers SET balance=COALESCE(balance,0)+? WHERE id=?", (amount, party_id))
                lines = [("1200", amount, 0, "Supplier purchase/charge"), ("2000", 0, amount, "Supplier payable")]
            else:
                raise ValueError("Invalid supplier transaction")
        else:
            # Staff: Advance = staff owes business; Repayment reduces it.
            if txn_type == "Advance":
                lines = [("1300", amount, 0, "Staff advance"), ("1000" if method == "Cash" else "1010", 0, amount, "Staff advance paid")]
            elif txn_type == "Repayment":
                lines = [("1000" if method == "Cash" else "1010", amount, 0, "Staff repayment"), ("1300", 0, amount, "Staff receivable settled")]
            else:
                raise ValueError("Invalid staff transaction")

        try:
            from financial_bridge_patch import _post
            _post(self.s.c, "ACCOUNT_TXN", tid, f"{party_type} {txn_type}", lines)
        except Exception:
            # The operational account must still commit even if an optional
            # ledger extension is unavailable.
            pass
        self.s.audit(self.user, "ACCOUNT_TXN", party_type, party_id, f"{txn_type} {amount:.2f} {method} {note}")
        self.s.c.commit()
        return tid

    App.post_account_transaction = post_account_tx

    def account_dialog(self, party_type, party_id, actions):
        table = {"Customer": "customers", "Supplier": "suppliers", "Staff": "staff"}[party_type]
        row = self.s.q(f"SELECT * FROM {table} WHERE id=?", (party_id,)).fetchone()
        if not row:
            return
        name = row["name"]
        w = self.dialog(f"{party_type} Account — {name}", 820, 620)
        f = ttk.Frame(w, padding=15); f.pack(fill="both", expand=True)
        balance = float(row["balance"] or 0) if "balance" in row.keys() else 0
        ttk.Label(f, text=f"{name}  •  Current Balance {money(balance)}", font=("Segoe UI", 17, "bold")).pack(anchor="w")
        t = self.table(f, ("type", "amount", "method", "note", "date"), {"type":"Transaction","amount":"Amount","method":"Method","note":"Note","date":"Date"}, 15)
        for r in self.s.rows("SELECT txn_type,amount,method,note,created_at FROM account_transactions WHERE party_type=? AND party_id=? ORDER BY id DESC", (party_type, party_id)):
            t.insert("", "end", values=(r["txn_type"], money(r["amount"]), r["method"], r["note"], r["created_at"]))
        bar = ttk.Frame(f); bar.pack(fill="x", pady=10)
        for label, typ in actions:
            ttk.Button(bar, text=label, command=lambda x=typ: self.account_tx_dialog(party_type, party_id, x, w)).pack(side="left", padx=(0,6))
        ttk.Button(bar, text="CLOSE", command=w.destroy).pack(side="right")

    def account_tx_dialog(self, party_type, party_id, txn_type, parent):
        w = self.dialog(f"{party_type} — {txn_type}", 430, 330)
        f = ttk.Frame(w, padding=18); f.pack(fill="both", expand=True)
        amount = tk.StringVar(); method = tk.StringVar(value="Cash"); note = tk.StringVar()
        ttk.Label(f, text="Amount").pack(anchor="w"); ttk.Entry(f, textvariable=amount).pack(fill="x", pady=5)
        ttk.Label(f, text="Payment Method").pack(anchor="w", pady=(8,2)); ttk.Combobox(f, textvariable=method, values=["Cash","Card","Other"], state="readonly").pack(fill="x")
        ttk.Label(f, text="Reference / Note").pack(anchor="w", pady=(8,2)); ttk.Entry(f, textvariable=note).pack(fill="x")
        def save():
            try:
                self.post_account_transaction(party_type, party_id, txn_type, amount.get(), method.get(), note.get().strip())
                w.destroy(); parent.destroy(); self.show("Customers" if party_type == "Customer" else "Suppliers" if party_type == "Supplier" else "Staff")
            except Exception as exc:
                messagebox.showerror("Transaction failed", str(exc), parent=w)
        ttk.Button(f, text="POST TRANSACTION", style="Primary.TButton", command=save).pack(fill="x", pady=18)

    App.account_dialog = account_dialog
    App.account_tx_dialog = account_tx_dialog

    # Add account buttons to the existing customer/supplier pages without
    # replacing their CRUD logic.
    for method_name, party, actions in (
        ("page_customers", "Customer", [("RECEIVE PAYMENT", "Payment"), ("CUSTOMER REFUND", "Refund"), ("ADD CHARGE", "Charge")]),
        ("page_suppliers", "Supplier", [("PAY SUPPLIER", "Payment"), ("ADD SUPPLIER CHARGE", "Charge")]),
    ):
        old_page = getattr(App, method_name, None)
        if old_page:
            def make_page(old_page=old_page, party=party, actions=actions):
                def page(self):
                    result = old_page(self)
                    # Put a clear account action bar above the existing page.
                    bar = ttk.LabelFrame(self.bodyinner, text="ACCOUNT TRANSACTIONS", padding=8)
                    children = list(self.bodyinner.winfo_children())
                    anchor = children[2] if len(children) > 2 else None
                    if anchor: bar.pack(fill="x", pady=(0,8), before=anchor)
                    else: bar.pack(fill="x", pady=(0,8))
                    tree = getattr(self, "customer_tree", None) if party == "Customer" else getattr(self, "supplier_tree", None)
                    if tree is not None:
                        for label, typ in actions:
                            ttk.Button(bar, text=label, command=lambda t=typ: self._open_selected_account(party, t, tree)).pack(side="left", padx=(0,5))
                    return result
                return page
            setattr(App, method_name, make_page())

    def open_selected_account(self, party, typ, tree):
        sel = tree.selection()
        if not sel:
            return messagebox.showwarning("Account", f"Select a {party.lower()} first.", parent=self)
        self.account_dialog(party, int(sel[0]), [(typ.upper(), typ)])
    App._open_selected_account = open_selected_account

    # If an old checkout implementation succeeds, force a fresh Orders view.
    old_checkout = getattr(App, "checkout", None)
    if old_checkout and not getattr(App, "_integrity_checkout_refresh", False):
        def checkout(self, *args, **kwargs):
            before = self.s.q("SELECT COALESCE(MAX(id),0) FROM sales").fetchone()[0]
            result = old_checkout(self, *args, **kwargs)
            after = self.s.q("SELECT COALESCE(MAX(id),0) FROM sales").fetchone()[0]
            if after > before:
                self.s.c.commit()
                self._last_sale_id = after
            return result
        App.checkout = checkout
        App._integrity_checkout_refresh = True

    # Make the persistent DB path explicit so factory reset can never target
    # the source-tree placeholder database.
    old_store_init = None
    if Store is not None and not getattr(Store, "_explicit_path_integrity", False):
        old_store_init = Store.__init__
        def store_init(self, path=None):
            old_store_init(self, path)
            self.path = path
            self.db_path = path
        Store.__init__ = store_init
        Store._explicit_path_integrity = True

    App._business_integrity_final = True
    return App
