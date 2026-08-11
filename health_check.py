"""Offline smoke check for the MK Pizza & Ice Bar POS codebase.
Run: python health_check.py
This does not open the GUI and does not modify the production database.
"""
import compileall
import sys


def main():
    print("[1/4] Compiling Python modules...")
    if not compileall.compile_dir(".", quiet=1, maxlevels=1):
        raise SystemExit("Python compilation failed.")

    print("[2/4] Importing launcher...")
    import launcher
    import pos_app

    print("[3/4] Checking required application methods...")
    required = [
        "page_pos", "page_customers", "page_suppliers", "page_products",
        "quick_customer", "catalog_history", "product_import", "product_export",
        "supplier_edit", "supplier_archive", "supplier_restore",
        "backup", "dialog",
    ]
    missing = [name for name in required if not hasattr(pos_app.App, name)]
    if missing:
        raise SystemExit("Missing App methods: " + ", ".join(missing))

    print("[4/4] Checking database schema in memory...")
    store = pos_app.Store(":memory:")
    try:
        required_tables = {
            "users", "products", "customers", "suppliers", "staff", "riders",
            "tables", "sales", "sale_items", "payments", "party_transactions",
            "stock_movements", "expenses", "audit_log", "order_events", "settings",
            "shifts", "purchases", "purchase_items",
        }
        found = {r["name"] for r in store.rows("SELECT name FROM sqlite_master WHERE type='table'")}
        missing_tables = sorted(required_tables - found)
        if missing_tables:
            raise SystemExit("Missing database tables: " + ", ".join(missing_tables))
    finally:
        store.c.close()

    print("POS health check PASSED.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
