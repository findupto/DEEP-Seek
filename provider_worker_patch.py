"""Provider workers and GPS bridge.
Queues remain usable offline. Admin can start a local GPS ingest service and
process queued receipts/sync jobs after providers are configured.
"""
import json, threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import tkinter as tk
from tkinter import ttk, messagebox


def now(): return datetime.now().isoformat(timespec='seconds')


def install(App):
    if getattr(App,'_provider_worker_installed',False): return App
    def process_receipt_queue(self,limit=50):
        done=failed=0
        rows=self.s.rows("SELECT * FROM receipt_delivery_queue WHERE status='PENDING' ORDER BY id LIMIT ?",(int(limit),))
        for r in rows:
            try:
                sale=self.s.q("SELECT * FROM sales WHERE id=?",(r['sale_id'],)).fetchone()
                body=f"Invoice {sale['invoice_no']}\nTotal: {sale['total']}\nPayment: {sale['payment_status']}" if sale else f"Sale {r['sale_id']}"
                if r['channel']=='EMAIL': self.send_email(r['destination'],f"Receipt {sale['invoice_no'] if sale else r['sale_id']}",body)
                elif r['channel']=='SMS': self.send_sms(r['destination'],body)
                else: continue
                self.s.q("UPDATE receipt_delivery_queue SET status='SENT',sent_at=? WHERE id=?",(now(),r['id'])); done+=1
            except Exception as e:
                self.s.q("UPDATE receipt_delivery_queue SET status='FAILED',attempts=attempts+1,last_error=? WHERE id=?",(str(e),r['id'])); failed+=1
        self.s.c.commit(); return done,failed

    def process_cloud_queue(self,limit=50):
        done=failed=0
        rows=self.s.rows("SELECT * FROM offline_queue WHERE status='PENDING' ORDER BY id LIMIT ?",(int(limit),))
        for r in rows:
            try:
                self.sync_cloud({'operation':r['operation'],'entity':r['entity'],'entity_id':r['entity_id'],'payload':json.loads(r['payload'] or '{}'),'created_at':r['created_at']})
                self.s.q("UPDATE offline_queue SET status='SYNCED',synced_at=?,last_error='' WHERE id=?",(now(),r['id'])); done+=1
            except Exception as e:
                self.s.q("UPDATE offline_queue SET attempts=attempts+1,last_error=? WHERE id=?",(str(e),r['id'])); failed+=1
        self.s.c.commit(); return done,failed

    def start_gps_bridge(self,host='0.0.0.0',port=8765,token=''):
        if getattr(self,'_gps_server',None): return False
        app=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_POST(self):
                if self.path!='/gps': self.send_response(404);self.end_headers();return
                if token and self.headers.get('Authorization','')!='Bearer '+token: self.send_response(401);self.end_headers();return
                try:
                    n=int(self.headers.get('Content-Length','0')); data=json.loads(self.rfile.read(n) or '{}')
                    app.record_gps(data.get('rider_id'),data['latitude'],data['longitude'],data.get('accuracy',0),data.get('speed',0),data.get('heading',0),'mobile-http')
                    self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(b'{"ok":true}')
                except Exception as e:
                    self.send_response(400);self.end_headers()
        self._gps_server=ThreadingHTTPServer((host,int(port)),Handler); self._gps_thread=threading.Thread(target=self._gps_server.serve_forever,daemon=True);self._gps_thread.start();return True

    def stop_gps_bridge(self):
        s=getattr(self,'_gps_server',None)
        if s: s.shutdown();s.server_close();self._gps_server=None;return True
        return False

    App.process_receipt_queue=process_receipt_queue;App.process_cloud_queue=process_cloud_queue;App.start_gps_bridge=start_gps_bridge;App.stop_gps_bridge=stop_gps_bridge

    old_page=getattr(App,'page_provider_setup',None)
    def page_provider_setup(self):
        if old_page: old_page(self)
        if not hasattr(self,'bodyinner'): return
        bar=ttk.Frame(self.bodyinner);bar.pack(fill='x',pady=8)
        ttk.Button(bar,text='PROCESS RECEIPT QUEUE',command=self._provider_process_receipts).pack(side='left')
        ttk.Button(bar,text='SYNC CLOUD QUEUE',command=self._provider_process_cloud).pack(side='left',padx=5)
        ttk.Button(bar,text='START GPS BRIDGE',command=self._provider_start_gps).pack(side='left')
        ttk.Button(bar,text='STOP GPS BRIDGE',command=self.stop_gps_bridge).pack(side='left',padx=5)
    def _provider_process_receipts(self):
        try: d,f=self.process_receipt_queue();messagebox.showinfo('Receipts',f'Sent: {d}\nFailed: {f}',parent=self)
        except Exception as e: messagebox.showerror('Receipts',str(e),parent=self)
    def _provider_process_cloud(self):
        try: d,f=self.process_cloud_queue();messagebox.showinfo('Cloud Sync',f'Synced: {d}\nFailed/queued: {f}',parent=self)
        except Exception as e: messagebox.showerror('Cloud Sync',str(e),parent=self)
    def _provider_start_gps(self):
        if str(self.user.get('role','')).lower() not in ('admin','owner'): return messagebox.showerror('Admin only','Only Admin/Owner can start the GPS bridge.',parent=self)
        p=self.provider_config('GPS'); c=p['config'];port=int(c.get('port',8765));token=c.get('ingest_token','')
        try:self.start_gps_bridge(port=port,token=token);messagebox.showinfo('GPS Bridge',f'GPS ingest active on port {port}.\nMobile clients can POST JSON to /gps.',parent=self)
        except Exception as e:messagebox.showerror('GPS Bridge',str(e),parent=self)
    App.page_provider_setup=page_provider_setup;App._provider_worker_installed=True;return App
