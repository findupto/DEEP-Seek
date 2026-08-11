"""Live ledger triggers for POS transaction tables."""

SCHEMA = """
CREATE TRIGGER IF NOT EXISTS trg_ledger_sale AFTER INSERT ON sales
WHEN NEW.status!='Cancelled' AND COALESCE(NEW.total,0)>0
BEGIN
 INSERT OR IGNORE INTO ledger_entries(source_type,source_id,description,created_at) VALUES('SALE',NEW.id,'Sale '||NEW.invoice_no,NEW.created_at);
 INSERT INTO ledger_lines(entry_id,account_code,debit,credit,memo) SELECT id,'1100',NEW.total,0,'Customer receivable' FROM ledger_entries WHERE source_type='SALE' AND source_id=NEW.id;
 INSERT INTO ledger_lines(entry_id,account_code,debit,credit,memo) SELECT id,'4000',0,NEW.total,'Sales revenue' FROM ledger_entries WHERE source_type='SALE' AND source_id=NEW.id;
END;
CREATE TRIGGER IF NOT EXISTS trg_ledger_payment AFTER INSERT ON payments
WHEN COALESCE(NEW.amount,0)>0
BEGIN
 INSERT OR IGNORE INTO ledger_entries(source_type,source_id,description,created_at) VALUES('PAYMENT',NEW.id,'Payment for sale',NEW.created_at);
 INSERT INTO ledger_lines(entry_id,account_code,debit,credit,memo) SELECT id,CASE WHEN NEW.method IN ('Card','Other') THEN '1010' ELSE '1000' END,NEW.amount,0,NEW.method||' received' FROM ledger_entries WHERE source_type='PAYMENT' AND source_id=NEW.id;
 INSERT INTO ledger_lines(entry_id,account_code,debit,credit,memo) SELECT id,'1100',0,NEW.amount,'Customer receivable settled' FROM ledger_entries WHERE source_type='PAYMENT' AND source_id=NEW.id;
END;
CREATE TRIGGER IF NOT EXISTS trg_ledger_expense AFTER INSERT ON expenses
WHEN COALESCE(NEW.amount,0)>0
BEGIN
 INSERT OR IGNORE INTO ledger_entries(source_type,source_id,description,created_at) VALUES('EXPENSE',NEW.id,COALESCE(NEW.category,'Expense'),NEW.created_at);
 INSERT INTO ledger_lines(entry_id,account_code,debit,credit,memo) SELECT id,'6000',NEW.amount,0,COALESCE(NEW.category,'Expense') FROM ledger_entries WHERE source_type='EXPENSE' AND source_id=NEW.id;
 INSERT INTO ledger_lines(entry_id,account_code,debit,credit,memo) SELECT id,'1000',0,NEW.amount,'Cash expense' FROM ledger_entries WHERE source_type='EXPENSE' AND source_id=NEW.id;
END;
CREATE TRIGGER IF NOT EXISTS trg_ledger_purchase AFTER INSERT ON purchases
WHEN COALESCE(NEW.total,0)>0
BEGIN
 INSERT OR IGNORE INTO ledger_entries(source_type,source_id,description,created_at) VALUES('PURCHASE',NEW.id,'Purchase '||NEW.invoice_no,NEW.created_at);
 INSERT INTO ledger_lines(entry_id,account_code,debit,credit,memo) SELECT id,'1200',NEW.total,0,'Inventory received' FROM ledger_entries WHERE source_type='PURCHASE' AND source_id=NEW.id;
 INSERT INTO ledger_lines(entry_id,account_code,debit,credit,memo) SELECT id,CASE WHEN NEW.payment_status='Paid' THEN '1000' ELSE '2000' END,0,NEW.total,CASE WHEN NEW.payment_status='Paid' THEN 'Supplier settlement' ELSE 'Supplier payable' END FROM ledger_entries WHERE source_type='PURCHASE' AND source_id=NEW.id;
END;
CREATE TRIGGER IF NOT EXISTS trg_ledger_party_payment AFTER INSERT ON party_transactions
WHEN COALESCE(NEW.amount,0)>0 AND ((NEW.party_type='Customer' AND NEW.txn_type IN ('Payment','Advance')) OR (NEW.party_type='Supplier' AND NEW.txn_type='Payment'))
BEGIN
 INSERT OR IGNORE INTO ledger_entries(source_type,source_id,description,created_at) VALUES('PARTY_TXN',NEW.id,NEW.party_type||' '||NEW.txn_type,NEW.created_at);
 INSERT INTO ledger_lines(entry_id,account_code,debit,credit,memo) SELECT id,CASE WHEN NEW.party_type='Supplier' THEN '2000' ELSE '1000' END,NEW.amount,0,NEW.party_type||' '||NEW.txn_type FROM ledger_entries WHERE source_type='PARTY_TXN' AND source_id=NEW.id;
 INSERT INTO ledger_lines(entry_id,account_code,debit,credit,memo) SELECT id,CASE WHEN NEW.party_type='Supplier' THEN '1000' WHEN NEW.txn_type='Advance' THEN '2200' ELSE '1100' END,0,NEW.amount,'Party balance update' FROM ledger_entries WHERE source_type='PARTY_TXN' AND source_id=NEW.id;
END;
"""

def install(App):
    if getattr(App,"_financial_live_triggers_installed",False):
        return App
    old_init=App.__init__
    def init(self,*args,**kwargs):
        old_init(self,*args,**kwargs)
        self.s.c.executescript(SCHEMA)
        self.s.c.commit()
    App.__init__=init
    App._financial_live_triggers_installed=True
    return App
