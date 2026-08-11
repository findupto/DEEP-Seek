"""Operational POS safety layer: kitchen workflow and delivery-rate schema."""
import sqlite3
from datetime import datetime
from tkinter import ttk, messagebox


def install(App):
    if getattr(App, "_operational_patch_installed_v2", False):
        return App
    old_init = App.__init__

    def init(self, *args, **kwargs):
        old_init(self, *args, **kwargs)
        self.s.c.executescript("""
        CREATE TABLE IF NOT EXISTS rider_rates(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rider_id INTEGER UNIQUE,
            base_fee REAL DEFAULT 0,
            per_km REAL DEFAULT 0,
            minimum_fee REAL DEFAULT 0,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS order_events(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            note TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            user_id INTEGER
        );
        """)
        for col, typ in (
            ("rider_base_fee", "REAL DEFAULT 0"),
            ("rider_per_km", "REAL DEFAULT 0"),
            ("delivery_distance_km", "REAL DEFAULT 0"),
            ("delivery_fee", "REAL DEFAULT 0"),
            ("tracking_status", "TEXT DEFAULT 'Pending'"),
        ):
            try:
                self.s.q(f"ALTER TABLE sales ADD COLUMN {col} {typ}")
            except sqlite3.OperationalError:
                pass
        # Replace the older trigger if it exists. The live POS rider editor
        # stores rates directly on riders, so sales must snapshot that source.
        self.s.c.executescript("""
        DROP TRIGGER IF EXISTS trg_sale_rider_rate;
        CREATE TRIGGER trg_sale_rider_rate
        AFTER INSERT ON sales
        WHEN NEW.rider_id IS NOT NULL
        BEGIN
            UPDATE sales
            SET rider_base_fee=COALESCE((SELECT base_fee FROM riders WHERE id=NEW.rider_id),0),
                rider_per_km=COALESCE((SELECT per_km FROM riders WHERE id=NEW.rider_id),0)
            WHERE id=NEW.id;
        END;
        CREATE INDEX IF NOT EXISTS idx_order_events_sale ON order_events(sale_id,created_at);
        """)
        self.s.c.commit()

    App.__init__ = init
    App.page_kitchen = page_kitchen
    App._operational_patch_installed_v2 = True
    return App


def page_kitchen(self):
    self.title("Kitchen Display", "Live kitchen queue. Select an order and move it New → Preparing → Ready → Completed.")
    top = ttk.Frame(self.body)
    top.pack(fill="x", pady=(0, 8))
    ttk.Button(top, text="REFRESH", command=lambda: self.show("Kitchen")).pack(side="left")
    ttk.Button(top, text="PREPARING", style="Primary.TButton", command=lambda: _move(self, "Preparing", t)).pack(side="left", padx=5)
    ttk.Button(top, text="READY", style="Primary.TButton", command=lambda: _move(self, "Ready", t)).pack(side="left")
    ttk.Button(top, text="COMPLETED", style="Primary.TButton", command=lambda: _move(self, "Completed", t)).pack(side="left")
    ttk.Button(top, text="OPEN ORDER", command=lambda: _open(self, t)).pack(side="right")
    t = ttk.Treeview(self.body, columns=("id", "invoice", "time", "type", "customer", "items", "status", "payment"), show="headings", height=18)
    heads = {"id": "ID", "invoice": "Invoice", "time": "Time", "type": "Type", "customer": "Customer", "items": "Items", "status": "Kitchen Status", "payment": "Payment"}
    for c in t["columns"]:
        t.heading(c, text=heads[c]); t.column(c, width=130)
    sy = ttk.Scrollbar(self.body, orient="vertical", command=t.yview)
    t.configure(yscrollcommand=sy.set)
    t.pack(side="left", fill="both", expand=True); sy.pack(side="right", fill="y")
    rows = self.s.rows("SELECT s.id,s.invoice_no,s.created_at,s.order_type,COALESCE(c.name,'Walk-in') customer,s.status,s.payment_status,COALESCE((SELECT GROUP_CONCAT(si.product_name||' x'||si.quantity, ', ') FROM sale_items si WHERE si.sale_id=s.id),'') items FROM sales s LEFT JOIN customers c ON c.id=s.customer_id WHERE s.status IN ('New','Preparing','Ready') ORDER BY s.id ASC")
    for r in rows:
        t.insert("", "end", iid=str(r["id"]), values=(r["id"], r["invoice_no"], r["created_at"], r["order_type"], r["customer"], r["items"], r["status"], r["payment_status"]))


def _move(self, status, t):
    sel = t.selection()
    if not sel:
        return messagebox.showwarning("Kitchen", "Select an order first.", parent=self)
    sid = int(sel[0])
    self.s.q("UPDATE sales SET status=? WHERE id=?", (status, sid))
    self.s.q("INSERT INTO order_events(sale_id,status,note,created_at,user_id) VALUES(?,?,?,?,?)", (sid, status, "Kitchen update", datetime.now().isoformat(timespec="seconds"), self.user["id"]))
    self.s.c.commit()
    self.show("Kitchen")


def _open(self, t):
    sel = t.selection()
    if not sel:
        return messagebox.showwarning("Kitchen", "Select an order first.", parent=self)
    sid = int(sel[0])
    try:
        import advanced_features
        handler = getattr(advanced_features, "_order_detail", None)
        if handler:
            handler(self, sid)
            return
    except Exception:
        pass
    handler = getattr(self, "order_detail", None)
    if handler:
        handler(sid)
    else:
        messagebox.showinfo("Order", "Open the Orders page to view this order.", parent=self)
