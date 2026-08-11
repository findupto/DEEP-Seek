import os
import sqlite3
import tempfile
import unittest
from decimal import Decimal

from enterprise_transaction_guard import money

class EnterpriseMoneyTests(unittest.TestCase):
    def test_money_rounds_half_up(self):
        self.assertEqual(money("115.005"), Decimal("115.01"))
        self.assertEqual(money("200"), Decimal("200.00"))

    def test_database_invariants(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            c = sqlite3.connect(path)
            c.executescript("""
            CREATE TABLE tx_guard_events(id INTEGER PRIMARY KEY AUTOINCREMENT,source_type TEXT,source_id INTEGER,amount NUMERIC,created_at TEXT,UNIQUE(source_type,source_id));
            CREATE TABLE tx_guard_reconciliation(id INTEGER PRIMARY KEY AUTOINCREMENT,checked_at TEXT,sales_total NUMERIC,payments_total NUMERIC,expenses_total NUMERIC,purchases_total NUMERIC,customer_balance NUMERIC,supplier_balance NUMERIC,ledger_debit NUMERIC,ledger_credit NUMERIC,status TEXT,details TEXT);
            """)
            c.execute("INSERT INTO tx_guard_events(source_type,source_id,amount,created_at) VALUES('SALE',1,200,'2026-01-01T00:00:00')")
            with self.assertRaises(sqlite3.IntegrityError):
                c.execute("INSERT INTO tx_guard_events(source_type,source_id,amount,created_at) VALUES('SALE',1,200,'2026-01-01T00:00:01')")
        finally:
            try: c.close()
            except Exception: pass
            os.remove(path)

if __name__ == '__main__':
    unittest.main()
