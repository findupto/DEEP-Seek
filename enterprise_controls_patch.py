"""Enterprise controls: notification rules, approvals, tax/payment/device settings and audit safeguards."""
import json
import sqlite3
from datetime import datetime
from tkinter import ttk, messagebox
import tkinter as tk


def now(): return datetime.now().isoformat(timespec='seconds')

SCHEMA = """
CREATE TABLE IF NOT EXISTS notification_preferences(user_id INTEGER, channel TEXT, event_type TEXT, enabled INTEGER DEFAULT 1, PRIMARY KEY(user_id,channel,event_type));
CREATE TABLE IF NOT EXISTS notification_rules(id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT NOT NULL, severity TEXT DEFAULT 'warning', target_role TEXT DEFAULT '', channel TEXT DEFAULT 'in_app', threshold REAL, escalation_minutes INTEGER DEFAULT 0, enabled INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS notification_delivery_log(id INTEGER PRIMARY KEY AUTOINCREMENT, notification_id INTEGER, channel TEXT, recipient TEXT, provider TEXT, status TEXT, response TEXT, sent_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tax_profiles(id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE NOT NULL, name TEXT NOT NULL, rate REAL DEFAULT 0, inclusive INTEGER DEFAULT 0, active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS payment_methods(id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE NOT NULL, name TEXT NOT NULL, kind TEXT DEFAULT 'OTHER', enabled INTEGER DEFAULT 1, requires_signature INTEGER DEFAULT 0, requires_pin INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS device_settings(id INTEGER PRIMARY KEY AUTOINCREMENT, device_type TEXT NOT NULL, device_name TEXT, connection TEXT DEFAULT 'USB', address TEXT DEFAULT '', enabled INTEGER DEFAULT 1, config_json TEXT DEFAULT '{}');
CREATE TABLE IF NOT EXISTS receipt_templates(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, header TEXT DEFAULT '', footer TEXT DEFAULT '', paper_size TEXT DEFAULT '80mm', font_scale REAL DEFAULT 1.0, auto_print INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS invoice_sequences(id INTEGER PRIMARY KEY CHECK(id=1), prefix TEXT DEFAULT 'INV-', next_number INTEGER DEFAULT 1, padding INTEGER DEFAULT 6);
INSERT OR IGNORE INTO invoice_sequences(id) VALUES(1);
CREATE TABLE IF NOT EXISTS security_events(id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT NOT NULL, username TEXT DEFAULT '', details TEXT DEFAULT '', created_at TEXT NOT NULL, ip_address TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS backup_records(id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT, sha256 TEXT, encrypted INTEGER DEFAULT 0, verified INTEGER DEFAULT 0, created_at TEXT NOT NULL, user_id INTEGER);
CREATE TRIGGER IF NOT EXISTS trg_audit_ledger_no_update BEFORE UPDATE ON audit_ledger BEGIN SELECT RAISE(ABORT,'Audit ledger is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_audit_ledger_no_delete BEFORE DELETE ON audit_ledger BEGIN SELECT RAISE(ABORT,'Audit ledger is append-only'); END;
"""


def install(App):
    if getattr(App,'_enterprise_controls_installed',False): return App
    old_init=App.__init__
    def init(self,*a,**kw):
        old_init(self,*a,**kw)
        try:
            self.s.c.executescript(SCHEMA)
            defaults=[('CASH','Cash','CASH',0,0),('CARD','Card','CARD',0,1),('WALLET','Mobile Wallet','WALLET',0,1),('OTHER','Other','OTHER',0,0)]
            for x in defaults: self.s.q('INSERT OR IGNORE INTO payment_methods(code,name,kind,requires_signature,requires_pin) VALUES(?,?,?,?,?)',x)
            self.s.c.commit()
        except sqlite3.Error: pass
    App.__init__=init

    def page_enterprise_controls(self):
        self.title('Enterprise Controls','Tax profiles, payment methods, devices, receipts, notification rules and approvals.')
        nb=ttk.Notebook(self.bodyinner);nb.pack(fill='both',expand=True)
        tabs={x:ttk.Frame(nb,padding=10) for x in ('Tax','Payments','Devices','Receipts','Notifications','Approvals','Security')}
        for x,f in tabs.items(): nb.add(f,text=x)
        for name,sql,cols in [
            ('Tax','SELECT code,name,rate,inclusive,active FROM tax_profiles',('Code','Name','Rate','Inclusive','Active')),
            ('Payments','SELECT code,name,kind,enabled,requires_signature,requires_pin FROM payment_methods',('Code','Name','Kind','Enabled','Signature','PIN')),
            ('Devices','SELECT device_type,device_name,connection,address,enabled FROM device_settings',('Type','Name','Connection','Address','Enabled')),
            ('Notifications','SELECT event_type,severity,target_role,channel,threshold,escalation_minutes,enabled FROM notification_rules',('Event','Severity','Role','Channel','Threshold','Escalation','Enabled')),
            ('Approvals','SELECT action_type,entity,entity_id,requested_by,status,created_at FROM approval_requests ORDER BY id DESC LIMIT 300',('Action','Entity','ID','Requested By','Status','Created')),
            ('Security','SELECT event_type,username,details,created_at,ip_address FROM security_events ORDER BY id DESC LIMIT 300',('Event','User','Details','Created','IP'))]:
            t=ttk.Treeview(tabs[name],columns=tuple(str(i) for i in range(len(cols))),show='headings')
            for i,h in enumerate(cols): t.heading(str(i),text=h);t.column(str(i),width=max(110,120 if i else 160))
            t.pack(fill='both',expand=True)
            for r in self.s.rows(sql): t.insert('','end',values=tuple(r))
        ttk.Label(tabs['Receipts'],text='Receipt templates control header/footer, paper size, font scaling and automatic printing.',wraplength=700).pack(anchor='w',pady=10)
        for r in self.s.rows('SELECT name,header,footer,paper_size,font_scale,auto_print FROM receipt_templates ORDER BY name'):
            ttk.Label(tabs['Receipts'],text=f"{r['name']} • {r['paper_size']} • scale {r['font_scale']} • auto-print {r['auto_print']}").pack(anchor='w',pady=3)
        ttk.Label(tabs['Receipts'],text='External email/SMS/push/webhook and payment-terminal providers are configured through integration_registry; credentials must be supplied by the deployment.',wraplength=700).pack(anchor='w',pady=15)
    App.page_enterprise_controls=page_enterprise_controls
    nav=list(getattr(App,'NAV',[]))
    if 'Enterprise Controls' not in nav: nav.append('Enterprise Controls')
    App.NAV=nav;App._enterprise_controls_installed=True
    return App
