import sqlite3
from financial_bridge_patch import SCHEMA, ACCOUNTS, _rebuild, _post


def db():
    c=sqlite3.connect(':memory:')
    c.row_factory=sqlite3.Row
    c.executescript('''
    CREATE TABLE sales(id INTEGER PRIMARY KEY,total REAL,payment_method TEXT,customer_id INTEGER,created_at TEXT,status TEXT);
    CREATE TABLE payments(id INTEGER PRIMARY KEY,sale_id INTEGER,method TEXT,amount REAL);
    CREATE TABLE expenses(id INTEGER PRIMARY KEY,category TEXT,amount REAL);
    CREATE TABLE purchases(id INTEGER PRIMARY KEY,total REAL,payment_status TEXT);
    CREATE TABLE party_transactions(id INTEGER PRIMARY KEY,party_type TEXT,party_id INTEGER,txn_type TEXT,amount REAL,note TEXT);
    ''')
    c.executescript(SCHEMA)
    for a in ACCOUNTS: c.execute('INSERT INTO ledger_accounts(code,name,type) VALUES(?,?,?)',a)
    return c


def test_rebuild_posts_sale_payment_expense_purchase_and_party_txn():
    c=db()
    c.execute("INSERT INTO sales VALUES(1,100,'Cash',1,'2026-08-11T10:00:00','New')")
    c.execute("INSERT INTO payments VALUES(1,1,'Cash',100)")
    c.execute("INSERT INTO expenses VALUES(1,'Electricity',20)")
    c.execute("INSERT INTO purchases VALUES(1,50,'Unpaid')")
    c.execute("INSERT INTO party_transactions VALUES(1,'Supplier',7,'Payment',10,'bill payment')")
    _rebuild(c)
    assert c.execute('SELECT COUNT(*) FROM ledger_entries').fetchone()[0] == 5
    assert c.execute('SELECT ROUND(SUM(debit),2) FROM ledger_lines').fetchone()[0] == 280.0
    assert c.execute('SELECT ROUND(SUM(credit),2) FROM ledger_lines').fetchone()[0] == 280.0


def test_rebuild_is_idempotent():
    c=db()
    c.execute("INSERT INTO sales VALUES(1,100,'Cash',1,'2026-08-11T10:00:00','New')")
    _rebuild(c)
    first=c.execute('SELECT COUNT(*) FROM ledger_entries').fetchone()[0]
    _rebuild(c)
    second=c.execute('SELECT COUNT(*) FROM ledger_entries').fetchone()[0]
    assert first == second == 1


def test_manual_post_requires_balanced_lines():
    c=db()
    try:
        _post(c,'TEST',1,'bad',[("1000",10,0,"x")])
    except ValueError:
        pass
    else:
        raise AssertionError('unbalanced ledger entry was accepted')
