"""Final financial/inventory integrity checks for the local POS database."""
import sqlite3


def install(App):
    if getattr(App, "_financial_integrity_installed", False):
        return App

    old_init = App.__init__

    def init(self, *args, **kwargs):
        old_init(self, *args, **kwargs)
        try:
            self.s.c.executescript("""
            CREATE INDEX IF NOT EXISTS idx_sales_created_at ON sales(created_at);
            CREATE INDEX IF NOT EXISTS idx_sales_customer ON sales(customer_id,created_at);
            CREATE INDEX IF NOT EXISTS idx_sale_items_product ON sale_items(product_id,sale_id);
            CREATE INDEX IF NOT EXISTS idx_products_barcode ON products(barcode);
            CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone);
            CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log(entity,entity_id,created_at);

            CREATE TRIGGER IF NOT EXISTS trg_credit_sale_customer_balance
            AFTER INSERT ON sales
            WHEN NEW.payment_method='Credit'
              AND NEW.customer_id IS NOT NULL
              AND COALESCE(NEW.total,0) > 0
            BEGIN
                UPDATE customers
                SET balance=COALESCE(balance,0)+NEW.total
                WHERE id=NEW.customer_id;
            END;
            """)
            self.s.c.commit()
        except sqlite3.Error:
            # Keep compatibility with older installations containing legacy
            # schemas. Existing business data is never deleted by this layer.
            pass

    App.__init__ = init
    App._financial_integrity_installed = True
    return App
