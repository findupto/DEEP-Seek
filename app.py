import hashlib
import sqlite3
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, simpledialog, ttk

DB = "pos.db"
BUSINESS = {
    "name": "MK Pizza & Ice Bar",
    "address": "Collage Road Abbas Chowk, Bhakkar, Pakistan",
    "phone": "0316 9700025",
    "currency": "Rs.",
    "tax": 0.0,
}

DEFAULT_PRODUCTS = [
    ("Zinger Burger", 350.0, "Burgers"),
    ("Chicken Burger", 300.0, "Burgers"),
    ("Small Pizza", 550.0, "Pizza"),
    ("Medium Pizza", 900.0, "Pizza"),
    ("Large Pizza", 1250.0, "Pizza"),
    ("Fries", 180.0, "Sides"),
    ("Chicken Shawarma", 250.0, "Shawarma"),
    ("Cold Drink", 100.0, "Drinks"),
]


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


class Database:
    def __init__(self, path=DB):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.init()

    def init(self):
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                role TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                category TEXT NOT NULL DEFAULT 'General',
                active INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_no TEXT UNIQUE NOT NULL,
                user_id INTEGER,
                subtotal REAL NOT NULL,
                tax REAL NOT NULL,
                total REAL NOT NULL,
                payment_method TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS sale_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_id INTEGER NOT NULL,
                product_id INTEGER,
                product_name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                line_total REAL NOT NULL,
                FOREIGN KEY(sale_id) REFERENCES sales(id)
            );
            """
        )
        users = [
            ("admin", "Admin", "0099"),
            ("owner", "Owner", "0099"),
            ("cashier", "Cashier", "0099"),
            ("accountant", "Accountant", "0099"),
        ]
        for username, role, password in users:
            self.conn.execute(
                "INSERT OR IGNORE INTO users(username, role, password_hash) VALUES (?, ?, ?)",
                (username, role, hash_password(password)),
            )
        if self.conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
            self.conn.executemany(
                "INSERT INTO products(name, price, category) VALUES (?, ?, ?)", DEFAULT_PRODUCTS
            )
        self.conn.commit()

    def login(self, username, password):
        return self.conn.execute(
            "SELECT * FROM users WHERE username=? AND password_hash=? AND active=1",
            (username.strip(), hash_password(password)),
        ).fetchone()

    def products(self):
        return self.conn.execute(
            "SELECT * FROM products WHERE active=1 ORDER BY category, name"
        ).fetchall()

    def add_product(self, name, price, category):
        self.conn.execute(
            "INSERT INTO products(name, price, category) VALUES (?, ?, ?)",
            (name, price, category or "General"),
        )
        self.conn.commit()

    def create_sale(self, user_id, cart, payment_method):
        subtotal = sum(x["qty"] * x["price"] for x in cart.values())
        tax = subtotal * BUSINESS["tax"] / 100
        total = subtotal + tax
        now = datetime.now()
        invoice = "INV-" + now.strftime("%Y%m%d-%H%M%S-%f")[:-3]
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO sales(invoice_no,user_id,subtotal,tax,total,payment_method,created_at) VALUES(?,?,?,?,?,?,?)",
            (invoice, user_id, subtotal, tax, total, payment_method, now.isoformat(timespec="seconds")),
        )
        sale_id = cur.lastrowid
        for product_id, item in cart.items():
            cur.execute(
                "INSERT INTO sale_items(sale_id,product_id,product_name,quantity,unit_price,line_total) VALUES(?,?,?,?,?,?)",
                (product_id, item["id"], item["name"], item["qty"], item["price"], item["qty"] * item["price"]),
            )
        self.conn.commit()
        return invoice, subtotal, tax, total

    def today_summary(self):
        row = self.conn.execute(
            "SELECT COUNT(*) count, COALESCE(SUM(total),0) total FROM sales WHERE date(created_at)=date('now','localtime')"
        ).fetchone()
        return row["count"], row["total"]


class LoginWindow(tk.Tk):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.title("MK Pizza & Ice Bar - POS Login")
        self.geometry("420x300")
        self.resizable(False, False)
        self.configure(padx=30, pady=25)
        ttk.Label(self, text=BUSINESS["name"], font=("Segoe UI", 20, "bold")).pack(pady=(5, 2))
        ttk.Label(self, text="Point of Sale").pack(pady=(0, 20))
        form = ttk.Frame(self)
        form.pack(fill="x")
        ttk.Label(form, text="Username").grid(row=0, column=0, sticky="w", pady=6)
        self.username = ttk.Entry(form)
        self.username.grid(row=0, column=1, sticky="ew", pady=6)
        ttk.Label(form, text="Password").grid(row=1, column=0, sticky="w", pady=6)
        self.password = ttk.Entry(form, show="*")
        self.password.grid(row=1, column=1, sticky="ew", pady=6)
        form.columnconfigure(1, weight=1)
        ttk.Button(self, text="Login", command=self.login).pack(pady=20, ipadx=35)
        self.password.bind("<Return>", lambda _: self.login())
        self.username.focus()

    def login(self):
        user = self.db.login(self.username.get(), self.password.get())
        if not user:
            messagebox.showerror("Login failed", "Invalid username or password.")
            return
        self.destroy()
        POSWindow(self.db, user).mainloop()


class POSWindow(tk.Tk):
    def __init__(self, db, user):
        super().__init__()
        self.db = db
        self.user = user
        self.cart = {}
        self.title(f"{BUSINESS['name']} - POS")
        self.geometry("1180x720")
        self.minsize(980, 620)
        self.build_ui()
        self.load_products()
        self.refresh_cart()

    def build_ui(self):
        header = ttk.Frame(self, padding=12)
        header.pack(fill="x")
        ttk.Label(header, text=BUSINESS["name"], font=("Segoe UI", 18, "bold")).pack(side="left")
        ttk.Label(header, text=f"{self.user['role']} | {self.user['username']}").pack(side="right")

        body = ttk.Frame(self, padding=(12, 0, 12, 12))
        body.pack(fill="both", expand=True)
        left = ttk.LabelFrame(body, text="Menu", padding=10)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        right = ttk.LabelFrame(body, text="Current Order", padding=10)
        right.pack(side="right", fill="both", expand=True)

        toolbar = ttk.Frame(left)
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Label(toolbar, text="Search").pack(side="left")
        self.search = ttk.Entry(toolbar)
        self.search.pack(side="left", fill="x", expand=True, padx=8)
        self.search.bind("<KeyRelease>", lambda _: self.load_products())
        if self.user["role"] in ("Admin", "Owner"):
            ttk.Button(toolbar, text="+ Product", command=self.add_product).pack(side="right")

        cols = ("name", "category", "price")
        self.product_tree = ttk.Treeview(left, columns=cols, show="headings", height=22)
        self.product_tree.heading("name", text="Product")
        self.product_tree.heading("category", text="Category")
        self.product_tree.heading("price", text="Price")
        self.product_tree.column("name", width=220)
        self.product_tree.column("category", width=120)
        self.product_tree.column("price", width=90, anchor="e")
        self.product_tree.pack(fill="both", expand=True)
        self.product_tree.bind("<Double-1>", lambda _: self.add_selected())
        ttk.Button(left, text="Add Selected", command=self.add_selected).pack(fill="x", pady=(8, 0))

        cart_cols = ("name", "qty", "price", "total")
        self.cart_tree = ttk.Treeview(right, columns=cart_cols, show="headings", height=18)
        for c, text in zip(cart_cols, ("Product", "Qty", "Unit", "Total")):
            self.cart_tree.heading(c, text=text)
        self.cart_tree.column("name", width=200)
        self.cart_tree.column("qty", width=55, anchor="center")
        self.cart_tree.column("price", width=85, anchor="e")
        self.cart_tree.column("total", width=95, anchor="e")
        self.cart_tree.pack(fill="both", expand=True)

        actions = ttk.Frame(right)
        actions.pack(fill="x", pady=8)
        ttk.Button(actions, text="+ Qty", command=lambda: self.change_qty(1)).pack(side="left", padx=2)
        ttk.Button(actions, text="- Qty", command=lambda: self.change_qty(-1)).pack(side="left", padx=2)
        ttk.Button(actions, text="Remove", command=self.remove_selected).pack(side="left", padx=2)
        ttk.Button(actions, text="Clear", command=self.clear_cart).pack(side="left", padx=2)

        summary = ttk.Frame(right)
        summary.pack(fill="x", pady=5)
        self.total_label = ttk.Label(summary, text="Rs. 0.00", font=("Segoe UI", 20, "bold"))
        self.total_label.pack(side="right")
        ttk.Label(summary, text="TOTAL").pack(side="right", padx=10)

        pay = ttk.Frame(right)
        pay.pack(fill="x", pady=8)
        self.payment = tk.StringVar(value="Cash")
        ttk.Label(pay, text="Payment").pack(side="left")
        ttk.Combobox(pay, textvariable=self.payment, values=("Cash", "Card", "Other"), state="readonly", width=12).pack(side="left", padx=8)
        ttk.Button(pay, text="Complete Sale", command=self.complete_sale).pack(side="right", ipadx=18)
        ttk.Button(pay, text="Today's Summary", command=self.summary).pack(side="right", padx=8)

    def load_products(self):
        query = self.search.get().strip().lower() if hasattr(self, "search") else ""
        for item in self.product_tree.get_children():
            self.product_tree.delete(item)
        for p in self.db.products():
            if query and query not in f"{p['name']} {p['category']}".lower():
                continue
            self.product_tree.insert("", "end", iid=str(p["id"]), values=(p["name"], p["category"], f"{BUSINESS['currency']} {p['price']:.2f}"))

    def add_selected(self):
        selected = self.product_tree.selection()
        if not selected:
            return
        product_id = int(selected[0])
        product = next((p for p in self.db.products() if p["id"] == product_id), None)
        if not product:
            return
        if product_id not in self.cart:
            self.cart[product_id] = {"id": product_id, "name": product["name"], "price": product["price"], "qty": 1}
        else:
            self.cart[product_id]["qty"] += 1
        self.refresh_cart()

    def refresh_cart(self):
        for item in self.cart_tree.get_children():
            self.cart_tree.delete(item)
        subtotal = 0
        for pid, item in self.cart.items():
            total = item["qty"] * item["price"]
            subtotal += total
            self.cart_tree.insert("", "end", iid=str(pid), values=(item["name"], item["qty"], f"{item['price']:.2f}", f"{total:.2f}"))
        tax = subtotal * BUSINESS["tax"] / 100
        self.total_label.config(text=f"{BUSINESS['currency']} {subtotal + tax:,.2f}")

    def change_qty(self, amount):
        selected = self.cart_tree.selection()
        if not selected:
            return
        pid = int(selected[0])
        if pid in self.cart:
            self.cart[pid]["qty"] += amount
            if self.cart[pid]["qty"] <= 0:
                del self.cart[pid]
        self.refresh_cart()

    def remove_selected(self):
        selected = self.cart_tree.selection()
        if selected:
            self.cart.pop(int(selected[0]), None)
            self.refresh_cart()

    def clear_cart(self):
        self.cart.clear()
        self.refresh_cart()

    def complete_sale(self):
        if not self.cart:
            messagebox.showwarning("Empty order", "Add at least one product.")
            return
        invoice, subtotal, tax, total = self.db.create_sale(self.user["id"], self.cart, self.payment.get())
        receipt = self.make_receipt(invoice, subtotal, tax, total)
        self.clear_cart()
        messagebox.showinfo("Sale completed", receipt)

    def make_receipt(self, invoice, subtotal, tax, total):
        lines = [BUSINESS["name"], BUSINESS["address"], BUSINESS["phone"], "-" * 40, invoice, datetime.now().strftime("%Y-%m-%d %H:%M"), "-" * 40]
        for item in self.cart.values():
            lines.append(f"{item['name']} x{item['qty']} = {BUSINESS['currency']} {item['qty'] * item['price']:.2f}")
        lines += ["-" * 40, f"Subtotal: {BUSINESS['currency']} {subtotal:.2f}", f"Tax: {BUSINESS['currency']} {tax:.2f}", f"TOTAL: {BUSINESS['currency']} {total:.2f}", f"Payment: {self.payment.get()}", "Thank you!"]
        return "\n".join(lines)

    def add_product(self):
        name = simpledialog.askstring("New Product", "Product name:", parent=self)
        if not name:
            return
        price = simpledialog.askfloat("New Product", "Price:", minvalue=0, parent=self)
        if price is None:
            return
        category = simpledialog.askstring("New Product", "Category:", initialvalue="General", parent=self)
        self.db.add_product(name, price, category or "General")
        self.load_products()

    def summary(self):
        count, total = self.db.today_summary()
        messagebox.showinfo("Today's Summary", f"Sales: {count}\nTotal: {BUSINESS['currency']} {total:,.2f}")


if __name__ == "__main__":
    db = Database()
    LoginWindow(db).mainloop()
