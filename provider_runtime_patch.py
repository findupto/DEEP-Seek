"""Optional provider runtime for DEEP-Seek.
Local-first: every external service is disabled until an Admin configures it.
Configured providers run live; missing/offline providers leave work queued.
"""
import json, os, smtplib, ssl, urllib.request, urllib.error
from email.message import EmailMessage
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox


def now(): return datetime.now().isoformat(timespec="seconds")

SCHEMA = """
CREATE TABLE IF NOT EXISTS provider_runtime(id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT UNIQUE NOT NULL, provider TEXT DEFAULT '', enabled INTEGER DEFAULT 0, config_json TEXT DEFAULT '{}', updated_at TEXT);
CREATE TABLE IF NOT EXISTS provider_events(id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT NOT NULL, operation TEXT NOT NULL, status TEXT NOT NULL, reference TEXT DEFAULT '', response TEXT DEFAULT '', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS gps_locations(id INTEGER PRIMARY KEY AUTOINCREMENT, rider_id INTEGER, latitude REAL, longitude REAL, accuracy REAL, speed REAL, heading REAL, captured_at TEXT NOT NULL, source TEXT DEFAULT 'mobile');
CREATE INDEX IF NOT EXISTS idx_gps_rider_time ON gps_locations(rider_id,captured_at);
"""
DEFAULTS = [('SMS',''),('EMAIL','SMTP'),('CLOUD','Webhook'),('CARD','Terminal API'),('WALLET','Wallet API'),('GPS','Maps/GPS')]


def _env(category, key):
    return os.getenv("DEEPSEEK_%s_%s" % (category, key), "")


def install(App):
    if getattr(App, '_provider_runtime_installed', False): return App
    old_init = App.__init__
    def init(self,*a,**kw):
        old_init(self,*a,**kw)
        self.s.c.executescript(SCHEMA)
        for cat,provider in DEFAULTS:
            self.s.q("INSERT OR IGNORE INTO provider_runtime(category,provider,enabled,config_json,updated_at) VALUES(?,?,0,'{}',?)",(cat,provider,now()))
        self.s.c.commit()
    App.__init__ = init

    def provider_config(self, category):
        r=self.s.q("SELECT * FROM provider_runtime WHERE category=?",(category,)).fetchone()
        if not r: return {'enabled':0,'provider':'','config':{}}
        try: cfg=json.loads(r['config_json'] or '{}')
        except Exception: cfg={}
        return {'enabled':int(r['enabled']), 'provider':r['provider'] or '', 'config':cfg}

    def save_provider(self, category, provider, enabled, config):
        self.s.q("INSERT INTO provider_runtime(category,provider,enabled,config_json,updated_at) VALUES(?,?,?,?,?) ON CONFLICT(category) DO UPDATE SET provider=excluded.provider,enabled=excluded.enabled,config_json=excluded.config_json,updated_at=excluded.updated_at",(category,provider,int(enabled),json.dumps(config),now()))
        self.s.c.commit()

    def event(self, category, operation, status, reference='', response=''):
        self.s.q("INSERT INTO provider_events(category,operation,status,reference,response,created_at) VALUES(?,?,?,?,?,?)",(category,operation,status,reference,response[:1000],now())); self.s.c.commit()

    def _post(self, url, payload, headers=None, timeout=12):
        data=json.dumps(payload).encode(); req=urllib.request.Request(url,data=data,headers={'Content-Type':'application/json',**(headers or {})},method='POST')
        with urllib.request.urlopen(req,timeout=timeout) as r: return r.status, r.read().decode(errors='replace')[:1000]

    def send_email(self,to,subject,body):
        p=self.provider_config('EMAIL')
        if not p['enabled']: raise RuntimeError('Email provider is disabled')
        c=p['config']; host=c.get('host') or _env('EMAIL','HOST'); port=int(c.get('port') or _env('EMAIL','PORT') or 587); user=c.get('username') or _env('EMAIL','USERNAME'); password=c.get('password') or _env('EMAIL','PASSWORD'); sender=c.get('from') or user
        if not host or not sender: raise RuntimeError('SMTP host/from is not configured')
        msg=EmailMessage(); msg['Subject']=subject; msg['From']=sender; msg['To']=to; msg.set_content(body)
        with smtplib.SMTP(host,port,timeout=15) as s:
            if c.get('starttls',True): s.starttls(context=ssl.create_default_context())
            if user: s.login(user,password)
            s.send_message(msg)
        self.event('EMAIL','SEND','SUCCESS',to,'SMTP accepted'); return True

    def send_sms(self,to,message):
        p=self.provider_config('SMS')
        if not p['enabled']: raise RuntimeError('SMS provider is disabled')
        c=p['config']; url=c.get('url') or _env('SMS','URL'); token=c.get('token') or _env('SMS','TOKEN')
        if not url: raise RuntimeError('SMS provider URL is not configured')
        status,body=self._post(url,{'to':to,'message':message}, {'Authorization':'Bearer '+token} if token else {})
        if status<200 or status>=300: raise RuntimeError('SMS provider returned HTTP %s'%status)
        self.event('SMS','SEND','SUCCESS',to,body); return True

    def sync_cloud(self,payload):
        p=self.provider_config('CLOUD')
        if not p['enabled']: raise RuntimeError('Cloud sync is disabled')
        c=p['config']; url=c.get('url') or _env('CLOUD','URL'); token=c.get('token') or _env('CLOUD','TOKEN')
        if not url: raise RuntimeError('Cloud API URL is not configured')
        status,body=self._post(url,payload,{'Authorization':'Bearer '+token} if token else {})
        if status<200 or status>=300: raise RuntimeError('Cloud API returned HTTP %s'%status)
        self.event('CLOUD','SYNC','SUCCESS','',body); return True

    def payment_request(self,category,operation,payload):
        p=self.provider_config(category)
        if not p['enabled']: raise RuntimeError(category+' provider is disabled')
        c=p['config']; url=c.get('url') or _env(category,'URL'); token=c.get('token') or _env(category,'TOKEN')
        if not url: raise RuntimeError(category+' API URL is not configured')
        payload=dict(payload); payload['operation']=operation
        status,body=self._post(url,payload,{'Authorization':'Bearer '+token} if token else {})
        if status<200 or status>=300: raise RuntimeError(category+' API returned HTTP %s'%status)
        self.event(category,operation,'SUCCESS',str(payload.get('reference','')),body); return json.loads(body) if body.strip().startswith('{') else {'status':'success','response':body}

    def record_gps(self,rider_id,latitude,longitude,accuracy=0,speed=0,heading=0,source='mobile'):
        self.s.q("INSERT INTO gps_locations(rider_id,latitude,longitude,accuracy,speed,heading,captured_at,source) VALUES(?,?,?,?,?,?,?,?)",(rider_id,float(latitude),float(longitude),float(accuracy or 0),float(speed or 0),float(heading or 0),now(),source)); self.s.c.commit()
        return True

    App.provider_config=provider_config; App.save_provider=save_provider; App.send_email=send_email; App.send_sms=send_sms; App.sync_cloud=sync_cloud; App.payment_request=payment_request; App.record_gps=record_gps

    def page_provider_setup(self):
        if str(self.user.get('role','')).lower() not in ('admin','owner'):
            messagebox.showerror('Admin only','External provider configuration is restricted to Admin/Owner.',parent=self); return
        self.title('Live Integrations','Optional providers. Keep them disabled to operate fully local/offline; enable any provider after credentials and endpoints are configured.')
        nb=ttk.Notebook(self.bodyinner); nb.pack(fill='both',expand=True)
        cfgtab=ttk.Frame(nb,padding=12); logtab=ttk.Frame(nb,padding=12); nb.add(cfgtab,text='Providers'); nb.add(logtab,text='Provider Log')
        categories=['SMS','EMAIL','CLOUD','CARD','WALLET','GPS']; vars={}
        for i,cat in enumerate(categories):
            p=self.provider_config(cat); box=ttk.LabelFrame(cfgtab,text=cat,padding=10); box.grid(row=i//2,column=i%2,sticky='nsew',padx=6,pady=6); cfg=vars.setdefault(cat,{})
            cfg['enabled']=tk.IntVar(value=p['enabled']); cfg['provider']=tk.StringVar(value=p['provider']); cfg['url']=tk.StringVar(value=p['config'].get('url','')); cfg['token']=tk.StringVar(value=p['config'].get('token',''))
            ttk.Checkbutton(box,text='Enable live provider',variable=cfg['enabled']).grid(row=0,column=0,columnspan=2,sticky='w'); ttk.Label(box,text='Provider').grid(row=1,column=0,sticky='w'); ttk.Entry(box,textvariable=cfg['provider']).grid(row=1,column=1,sticky='ew'); ttk.Label(box,text='API / Webhook URL').grid(row=2,column=0,sticky='w'); ttk.Entry(box,textvariable=cfg['url'],width=34).grid(row=2,column=1,sticky='ew'); ttk.Label(box,text='Token / API key').grid(row=3,column=0,sticky='w'); ttk.Entry(box,textvariable=cfg['token'],show='*',width=34).grid(row=3,column=1,sticky='ew'); box.columnconfigure(1,weight=1)
            ttk.Button(box,text='SAVE',command=lambda c=cat:self._save_provider_ui(c,vars[c])).grid(row=4,column=0,columnspan=2,sticky='ew',pady=(8,0))
        cfgtab.columnconfigure(0,weight=1);cfgtab.columnconfigure(1,weight=1)
        ttk.Label(cfgtab,text='EMAIL additionally supports SMTP host/port/username/password/starttls through environment variables DEEPSEEK_EMAIL_* or provider config. Other providers use a standard JSON POST contract and can be replaced with vendor-specific adapters.',wraplength=900).grid(row=3,column=0,columnspan=2,sticky='w',padx=6,pady=10)
        t=ttk.Treeview(logtab,columns=('time','category','operation','status','reference','response'),show='headings');
        for c,h in zip(t['columns'],('Time','Category','Operation','Status','Reference','Response')):t.heading(c,text=h);t.column(c,width=150)
        t.pack(fill='both',expand=True)
        for r in self.s.rows('SELECT created_at,category,operation,status,reference,response FROM provider_events ORDER BY id DESC LIMIT 500'):t.insert('','end',values=tuple(r))
    def _save_provider_ui(self,cat,v):
        old=self.provider_config(cat); cfg=dict(old['config']); cfg.update({'url':v['url'].get().strip(),'token':v['token'].get().strip()}); self.save_provider(cat,v['provider'].get().strip(),v['enabled'].get(),cfg); messagebox.showinfo('Saved',cat+' provider configuration saved.',parent=self)
    App.page_provider_setup=page_provider_setup
    nav=list(getattr(App,'NAV',[]));
    if 'Live Integrations' not in nav: nav.append('Live Integrations')
    App.NAV=nav; App._provider_runtime_installed=True
    return App
