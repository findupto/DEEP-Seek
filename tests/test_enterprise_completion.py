import os,tempfile
from enterprise_completion_patch import connect,journal,receive_layer,issue_cost,post_sale,post_purchase,post_expense,post_wastage,p_and_l,trial_balance,verify_audit,next_document,queue_sync
from enterprise_services import Passwords

def db(): return tempfile.NamedTemporaryFile(suffix='.db',delete=False)

def test_journal_balances_and_reports():
    f=db(); c=connect(f.name); journal(c,'TEST','1','MAIN',[{'account':'1000','debit':10},{'account':'4000','credit':10}]); t=trial_balance(c); assert t['debit']==t['credit']=='10.00'; assert verify_audit(c); f.close(); os.unlink(f.name)

def test_fifo_cost():
    f=db(); c=connect(f.name); receive_layer(c,'P','MAIN',5,2,'a'); receive_layer(c,'P','MAIN',5,4,'b'); assert issue_cost(c,'P','MAIN',6,'FIFO')=='14.00'; f.close(); os.unlink(f.name)

def test_weighted_average_cost():
    f=db(); c=connect(f.name); receive_layer(c,'P','MAIN',5,2,'a'); receive_layer(c,'P','MAIN',5,4,'b'); assert issue_cost(c,'P','MAIN',5,'WEIGHTED_AVERAGE')=='15.00'; f.close(); os.unlink(f.name)

def test_business_events_and_pnl():
    f=db(); c=connect(f.name); post_purchase(c,'PO1','MAIN',100); post_sale(c,'S1','MAIN',200,200,60); post_expense(c,'E1','MAIN',20); post_wastage(c,'W1','MAIN',5); p=p_and_l(c); assert p['revenue']=='200.00'; assert p['net_profit']=='115.00'; f.close(); os.unlink(f.name)

def test_idempotency_and_documents():
    f=db(); c=connect(f.name); assert queue_sync(c,'abc12345',{'x':1}); assert not queue_sync(c,'abc12345',{'x':1}); assert next_document(c,'INVOICE','INV','MAIN')=='INV-00000001'; f.close(); os.unlink(f.name)

def test_passwords():
    h=Passwords.hash('correct horse battery staple'); assert Passwords.verify('correct horse battery staple',h); assert not Passwords.verify('wrong',h)
