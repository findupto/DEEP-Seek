import tkinter as tk
from tkinter import ttk, messagebox
import pos_app

_original_show = pos_app.App.show

def show(self, name):
    if name == 'Tables / Dine-in':
        self.clear()
        self.page_tables__dine_in()
        return
    return _original_show(self, name)

def collect_payment(self, t):
    sel=t.selection()
    if not sel: return
    sid=int(sel[0]); r=self.s.q('SELECT * FROM sales WHERE id=?',(sid,)).fetchone()
    if r['payment_status']=='Paid':
        return messagebox.showinfo('Payment','This order is already paid.',parent=self)
    w=tk.Toplevel(self); w.title('Collect Payment'); f=ttk.Frame(w,padding=20); f.pack()
    ttk.Label(f,text=f"Invoice {r['invoice_no']} — Rs. {r['total']:,.2f}",font=('Segoe UI',14,'bold')).pack(pady=8)
    m=tk.StringVar(value='Cash'); ttk.Combobox(f,textvariable=m,values=['Cash','Card','Other'],state='readonly').pack(fill='x',pady=8)
    ref=tk.StringVar(); ttk.Entry(f,textvariable=ref).pack(fill='x',pady=8)
    def pay():
        now=__import__('datetime').datetime.now().isoformat(timespec='seconds')
        self.s.q('INSERT INTO payments(sale_id,method,amount,reference,created_at,user_id) VALUES(?,?,?,?,?,?)',(sid,m.get(),r['total'],ref.get(),now,self.user['id']))
        if r['payment_method']=='Credit' and r['customer_id']:
            self.s.q('UPDATE customers SET balance=MAX(0,balance-?) WHERE id=?',(r['total'],r['customer_id']))
            self.s.q('INSERT INTO party_transactions(party_type,party_id,txn_type,amount,note,created_at,user_id) VALUES(?,?,?,?,?,?,?)',('Customer',r['customer_id'],'Payment',r['total'],r['invoice_no'],now,self.user['id']))
        self.s.q('UPDATE sales SET payment_status=?,payment_method=? WHERE id=?',('Paid',m.get(),sid)); self.s.c.commit(); self.s.audit(self.user,'Collect Payment','sale',sid,m.get())
        try: self.print_receipt(sid)
        except Exception as e: messagebox.showwarning('Printer','Payment saved, but receipt could not be printed:\n'+str(e),parent=w)
        w.destroy(); self.show('Orders')
    ttk.Button(f,text='TAKE PAYMENT & PRINT RECEIPT',style='Primary.TButton',command=pay).pack(fill='x',pady=8)

pos_app.App.show=show
pos_app.App.collect_payment=collect_payment

if __name__ == '__main__':
    pos_app.main()
