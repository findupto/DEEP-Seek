"""Offline smoke check for the MK Pizza & Ice Bar POS codebase.
Run: python health_check.py
This does not open the GUI and does not modify the production database.
"""
import compileall
import sys


def main():
    print("[1/5] Compiling Python modules...")
    if not compileall.compile_dir(".", quiet=1, maxlevels=1):
        raise SystemExit("Python compilation failed.")

    print("[2/5] Importing launcher...")
    import launcher
    import pos_app

    print("[3/5] Checking required application methods...")
    required = [
        "page_pos", "page_customers", "page_suppliers", "page_products",
        "quick_customer", "catalog_history", "product_import", "product_export",
        "supplier_edit", "supplier_archive", "supplier_restore", "backup", "dialog",
        "page_returns_refunds", "page_end_of_day", "page_system_health",
    ]
    missing = [name for name in required if not hasattr(pos_app.App, name)]
    if missing:
        raise SystemExit("Missing App methods: " + ", ".join(missing))

    print("[4/5] Checking database schema in memory...")
    store = pos_app.Store(":memory:")
    try:
        required_tables = {
            "users", "products", "customers", "suppliers", "staff", "riders",
            "tables", "sales", "sale_items", "payments", "party_transactions",
            "stock_movements", "expenses", "audit_log", "order_events", "settings",
            "shifts", "purchases", "purchase_items", "refunds", "refund_items",
        }
        found = {r["name"] for r in store.rows("SELECT name FROM sqlite_master WHERE type='table'")}
        missing_tables = sorted(required_tables - found)
        if missing_tables:
            raise SystemExit("Missing database tables: " + ", ".join(missing_tables))
    finally:
        store.c.close()

    print("[5/5] Checking core SQL integrity query...")
    store = pos_app.Store(":memory:")
    try:
        result = store.q("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise SystemExit("SQLite integrity check failed: " + str(result))
    finally:
        store.c.close()

    print("POS health check PASSED.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
