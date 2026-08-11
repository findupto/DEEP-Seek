"""Non-GUI smoke test for the POS integration layer.
Run: python smoke_test.py
It imports the real launcher and uses a temporary SQLite database, so it does
not touch the user's production POS database.
"""
import tempfile
from pathlib import Path

import launcher


def main():
    App = launcher.pos_app.App
    required = [
        "page_pos", "page_dashboard", "page_orders", "page_kitchen",
        "page_customers", "page_suppliers", "page_purchases",
        "page_products", "page_inventory", "page_riders_delivery",
        "page_staff", "page_expenses", "page_cash_shifts",
        "page_reports_analytics", "page_printers", "page_settings",
        "page_users_permissions", "product_edit", "product_delete",
        "product_delete_all", "product_import", "product_export",
        "product_template", "bulk_center", "catalog_history",
        "categories", "modifiers", "product_media",
    ]
    missing = [name for name in required if not hasattr(App, name)]
    if missing:
        raise AssertionError("Missing App callbacks: " + ", ".join(missing))

    with tempfile.TemporaryDirectory(prefix="mkpos_smoke_") as td:
        db_path = str(Path(td) / "smoke.db")
        store = launcher.pos_app.Store(db_path)
        try:
            for table in ("users", "products", "sales", "sale_items", "payments", "suppliers", "purchases", "purchase_items", "stock_movements", "audit_log"):
                store.q(f"SELECT 1 FROM {table} LIMIT 1").fetchone()
            store.q("INSERT INTO products(name,price,category,stock,cost,active) VALUES(?,?,?,?,?,1)", ("Smoke Pizza", 500, "Pizza", 5, 300))
            store.c.commit()
            product_id = store.q("SELECT id FROM products WHERE name='Smoke Pizza'").fetchone()["id"]
            assert product_id > 0
        finally:
            store.c.close()

    print("SMOKE TEST PASSED: launcher imports, required callbacks exist, and SQLite schema is writable.")


if __name__ == "__main__":
    main()
