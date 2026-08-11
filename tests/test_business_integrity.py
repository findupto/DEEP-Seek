import pos_app
from business_integrity_patch import install


class FakeApp:
    pass


def make_app():
    s = pos_app.Store(":memory:")
    s.q("INSERT INTO suppliers(name) VALUES('Supplier A')")
    s.q("INSERT INTO customers(name) VALUES('Customer A')")
    s.q("INSERT INTO staff(name) VALUES('Staff A')")
    s.q("INSERT INTO users(username,role,password_hash) VALUES('tester','Admin','x')")
    user = s.q("SELECT * FROM users WHERE username='tester'").fetchone()
    app = FakeApp()
    app.s = s
    app.user = user
    return app


def test_supplier_payment_updates_operational_account_and_ledger():
    app = make_app()
    install(FakeApp, pos_app.Store)
    app.post_account_transaction( "Supplier", 1, "Payment", 1250, "Cash", "Supplier settlement")
    assert app.s.q("SELECT balance FROM suppliers WHERE id=1").fetchone()[0] == 0
    assert app.s.q("SELECT COUNT(*) FROM account_transactions WHERE party_type='Supplier'").fetchone()[0] == 1
    app.s.c.close()


def test_customer_payment_reduces_due():
    app = make_app()
    app.s.q("UPDATE customers SET balance=5000 WHERE id=1")
    app.s.c.commit()
    app.post_account_transaction("Customer", 1, "Payment", 1500, "Cash", "Customer paid dues")
    assert app.s.q("SELECT balance FROM customers WHERE id=1").fetchone()[0] == 3500
    app.s.c.close()


def test_staff_advance_is_recorded():
    app = make_app()
    app.post_account_transaction("Staff", 1, "Advance", 800, "Cash", "Staff request")
    row = app.s.q("SELECT txn_type,amount FROM account_transactions WHERE party_type='Staff'").fetchone()
    assert (row["txn_type"], row["amount"]) == ("Advance", 800)
    app.s.c.close()
