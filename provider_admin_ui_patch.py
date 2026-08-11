"""Admin provider console with JSON config for vendor-specific credentials/endpoints."""
import json
import tkinter as tk
from tkinter import ttk, messagebox


def install(App):
    if getattr(App,'_provider_admin_ui_installed',False): return App
    def page_provider_setup(self):
        if str(self.user.get('role','')).lower() not in ('admin','owner'):
            messagebox.showerror('Admin only','External provider configuration is restricted to Admin/Owner.',parent=self); return
        self.title('Live Integrations','Enable providers only when configured. Disabled providers never block local POS operation.')
        f=ttk.Frame(self.bodyinner,padding=12);f.pack(fill='both',expand=True)
        ttk.Label(f,text='Provider').grid(row=0,column=0,sticky='w');ttk.Label(f,text='Enabled').grid(row=0,column=1,sticky='w');ttk.Label(f,text='Provider Name').grid(row=0,column=2,sticky='w');ttk.Label(f,text='Configuration JSON').grid(row=0,column=3,sticky='w')
        cats=['EMAIL','SMS','CLOUD','CARD','WALLET','GPS']; rows={}
        for i,cat in enumerate(cats,1):
            p=self.provider_config(cat); rows[cat]={'enabled':tk.IntVar(value=p['enabled']),'provider':tk.StringVar(value=p['provider']),'json':tk.StringVar(value=json.dumps(p['config'],separators=(',',':')))}
            ttk.Label(f,text=cat).grid(row=i,column=0,sticky='w',padx=4,pady=5);ttk.Checkbutton(f,variable=rows[cat]['enabled']).grid(row=i,column=1,sticky='w');ttk.Entry(f,textvariable=rows[cat]['provider'],width=20).grid(row=i,column=2,sticky='ew',padx=4);ttk.Entry(f,textvariable=rows[cat]['json'],width=70,show='*' if cat in ('EMAIL','SMS','CARD','WALLET') else '').grid(row=i,column=3,sticky='ew',padx=4);ttk.Button(f,text='SAVE',command=lambda c=cat:self._save_provider_json(c,rows[c])).grid(row=i,column=4,padx=4)
        f.columnconfigure(3,weight=1)
        ttk.Label(f,text='Examples: EMAIL {"host":"smtp.example.com","port":587,"username":"user","password":"secret","from":"pos@example.com","starttls":true}; other providers {"url":"https://provider.example/api","token":"..."}; GPS may also include {"port":8765,"ingest_token":"..."}.',wraplength=1000).grid(row=8,column=0,columnspan=5,sticky='w',pady=12)
        ttk.Button(f,text='PROCESS RECEIPTS',command=lambda:self._provider_process_receipts()).grid(row=9,column=0,sticky='ew',padx=4);ttk.Button(f,text='SYNC CLOUD',command=lambda:self._provider_process_cloud()).grid(row=9,column=1,sticky='ew',padx=4);ttk.Button(f,text='START GPS BRIDGE',command=lambda:self._provider_start_gps()).grid(row=9,column=2,sticky='ew',padx=4);ttk.Button(f,text='STOP GPS',command=self.stop_gps_bridge).grid(row=9,column=3,sticky='ew',padx=4)
        t=ttk.Treeview(f,columns=('time','category','operation','status','reference'),show='headings',height=12);t.grid(row=10,column=0,columnspan=5,sticky='nsew',pady=10);f.rowconfigure(10,weight=1)
        for c,h in zip(t['columns'],('Time','Category','Operation','Status','Reference')):t.heading(c,text=h);t.column(c,width=150)
        for r in self.s.rows('SELECT created_at,category,operation,status,reference FROM provider_events ORDER BY id DESC LIMIT 200'):t.insert('','end',values=tuple(r))
    def _save_provider_json(self,cat,v):
        try: cfg=json.loads(v['json'].get() or '{}'); assert isinstance(cfg,dict)
        except Exception as e: return messagebox.showerror('Configuration','Invalid JSON: '+str(e),parent=self)
        self.save_provider(cat,v['provider'].get().strip(),v['enabled'].get(),cfg);messagebox.showinfo('Saved',cat+' configuration saved.',parent=self)
    App.page_provider_setup=page_provider_setup;App._provider_admin_ui_installed=True;return App
