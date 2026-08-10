import asyncio, json, platform, socket, subprocess, threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

CONFIG_PATH=Path('printer_config.json'); THEMES_PATH=Path('receipt_themes.json')
DEFAULT_THEMES={'Classic':{'separator':'--------------------------------','items':'name_qty_total','footer_text':'Thank you for visiting!','show_address':True,'show_phone':True,'show_cashier':True,'show_invoice':True},'Compact':{'separator':'--------------------------------','items':'compact','footer_text':'Thank you!','show_address':False,'show_phone':True,'show_cashier':False,'show_invoice':True},'Detailed':{'separator':'================================','items':'name_qty_unit_total','footer_text':'Thank you for your order!','show_address':True,'show_phone':True,'show_cashier':True,'show_invoice':True}}

def load_json(path,default):
    try:
        if path.exists():
            value=json.loads(path.read_text(encoding='utf-8')); return value if isinstance(value,dict) else dict(default)
    except Exception: pass
    value=json.loads(json.dumps(default)); path.write_text(json.dumps(value,indent=2),encoding='utf-8'); return value

class PrinterManager:
    def __init__(self):
        self.config=load_json(CONFIG_PATH,{'printer':None,'theme':'Classic'})
        if not isinstance(self.config.get('printer'),dict):self.config['printer']=None
        self.themes=load_json(THEMES_PATH,DEFAULT_THEMES);self.sock=None;self.device=None
    def save(self):CONFIG_PATH.write_text(json.dumps(self.config,indent=2),encoding='utf-8');THEMES_PATH.write_text(json.dumps(self.themes,indent=2),encoding='utf-8')
    def discover(self,callback=None):
        found=[];seen=set();lock=threading.Lock()
        def add(d):
            key=(d.get('address') or d.get('port') or d.get('name') or '').lower()
            if not key:return
            with lock:
                if key in seen:return
                seen.add(key);found.append(d)
            if callback:callback(list(found),False)
        def worker():
            try:
                from bleak import BleakScanner
                async def scan():
                    for d in await BleakScanner.discover(timeout=6):add({'name':d.name or 'Unknown BLE Device','address':str(d.address),'type':'BLE','details':str(d.metadata or {})})
                asyncio.run(scan())
            except Exception:pass
            if platform.system()=='Windows':
                try:
                    import serial.tools.list_ports
                    for p in serial.tools.list_ports.comports():add({'name':p.description or p.device,'address':p.device,'port':p.device,'type':'Serial/COM','details':f'{p.device} | VID={p.vid} PID={p.pid} {p.hwid}'})
                except Exception:pass
                try:
                    out=subprocess.check_output(['powershell','-NoProfile','-Command','Get-PnpDevice -Class Bluetooth | Select-Object FriendlyName,InstanceId | ConvertTo-Json -Compress'],text=True,timeout=15);data=json.loads(out) if out.strip() else []
                    if isinstance(data,dict):data=[data]
                    for x in data:add({'name':x.get('FriendlyName') or 'Bluetooth Device','address':x.get('InstanceId',''),'type':'Windows Bluetooth','details':x.get('InstanceId','')})
                except Exception:pass
            else:
                try:
                    out=subprocess.check_output(['bluetoothctl','devices'],text=True,timeout=10)
                    for line in out.splitlines():
                        p=line.split(' ',2)
                        if len(p)==3 and p[0]=='Device':add({'name':p[2],'address':p[1],'type':'Classic Bluetooth','details':line})
                except Exception:pass
            if callback:callback(list(found),True)
        threading.Thread(target=worker,daemon=True).start();return found
    def set_printer(self,device,channel=1):
        d=dict(device);d['channel']=int(channel);self.config['printer']=d;self.save()
    def disconnect(self):
        try:
            if self.sock:self.sock.close()
        except Exception:pass
        self.sock=None
    def connect(self,device=None):
        device=device or self.config.get('printer')
        if not isinstance(device,dict):raise RuntimeError('No printer is configured.')
        self.disconnect();port=device.get('port') or device.get('address','');typ=device.get('type','')
        if platform.system()=='Windows' and (str(port).upper().startswith('COM') or typ=='Serial/COM'):
            try:import serial
            except ImportError:raise RuntimeError('Install pyserial: pip install pyserial')
            self.sock=serial.Serial(port,9600,timeout=3);self.device=device;return True
        if platform.system()!='Windows':
            self.sock=socket.socket(socket.AF_BLUETOOTH,socket.SOCK_STREAM,socket.BTPROTO_RFCOMM);self.sock.connect((device['address'],int(device.get('channel',1))));self.device=device;return True
        raise RuntimeError('On Windows, pair the printer and select its COM port from the discovered Serial/COM devices.')
    def auto_reconnect(self):
        try:return self.connect()
        except Exception:return False
    def status(self):return {'connected':self.sock is not None,'printer':self.config.get('printer'),'theme':self.config.get('theme','Classic')}
    def _write(self,data):
        if not self.sock and not self.auto_reconnect():raise RuntimeError('Printer is not connected. Pair/select a printer first.')
        try:self.sock.write(data)
        except Exception:self.disconnect();self.connect();self.sock.write(data)
    def render_receipt(self,business,invoice,items,subtotal,tax,total,payment,cashier=''):
        from datetime import datetime
        theme=self.themes.get(self.config.get('theme','Classic'),DEFAULT_THEMES['Classic']);width=48
        def t(x=''):return str(x)[:width]
        def center(x):return t(x).center(width)
        lines=[center(business.get('name','')),center('RECEIPT'),t(theme.get('separator','-'))]
        if theme.get('show_address'):lines.append(center(business.get('address','')))
        if theme.get('show_phone'):lines.append(center(business.get('phone','')))
        if theme.get('show_invoice'):lines.append(t(f'Invoice: {invoice}'))
        lines.append(t(datetime.now().strftime('Date: %Y-%m-%d %H:%M')))
        if theme.get('show_cashier') and cashier:lines.append(t(f'Cashier: {cashier}'))
        lines.append(t(theme.get('separator','-')))
        for i in items:
            name=str(i.get('name',''));q=i.get('qty',0);u=float(i.get('price',0));line=float(q)*u
            if theme.get('items')=='name_qty_unit_total':lines.extend([t(name),t(f'  {q} x {u:,.2f} = {line:,.2f}')])
            else:lines.append(t(f'{name[:28]} x{q} {line:,.2f}'))
        cur=business.get('currency','Rs.');lines += [t(theme.get('separator','-')),t(f'Subtotal: {cur} {subtotal:,.2f}'),t(f'Tax: {cur} {tax:,.2f}'),t(f'TOTAL: {cur} {total:,.2f}'),t(f'Payment: {payment}'),t(theme.get('separator','-')),center(theme.get('footer_text','Thank you!')),'','']
        return '\n'.join(lines).encode('cp437',errors='replace')
    def print_receipt(self,business,invoice,items,subtotal,tax,total,payment,cashier=''):
        esc=b'\x1b';data=esc+b'@'+esc+b'a\x01'+esc+b'E\x01'+self.render_receipt(business,invoice,items,subtotal,tax,total,payment,cashier)+esc+b'E\x00'+esc+b'a\x01'+b'\n\n\n'+b'\x1dV\x00';self._write(data)

class PrinterSettings:
    def __init__(self,parent,manager,business=None):
        self.parent=parent;self.m=manager;self.business=business or {};self.win=tk.Toplevel(parent);self.win.title('Printers & Receipt Settings');self.win.geometry('980x680');self.build()
    def build(self):
        nb=ttk.Notebook(self.win);nb.pack(fill='both',expand=True,padx=10,pady=10);pt=ttk.Frame(nb,padding=10);tt=ttk.Frame(nb,padding=10);nb.add(pt,text='Printer Discovery');nb.add(tt,text='Receipt Themes');top=ttk.Frame(pt);top.pack(fill='x');ttk.Button(top,text='Discover / Search Live',command=self.scan).pack(side='left');self.status=ttk.Label(top,text='Ready');self.status.pack(side='right')
        self.tree=ttk.Treeview(pt,columns=('name','address','type','details'),show='headings');
        for c in ('name','address','type','details'):self.tree.heading(c,text=c.title());self.tree.column(c,width=220)
        self.tree.pack(fill='both',expand=True,pady=10);form=ttk.Frame(pt);form.pack(fill='x');ttk.Label(form,text='COM/RFCOMM Channel').pack(side='left');self.channel=tk.StringVar(value=str((self.m.config.get('printer') or {}).get('channel',1)));ttk.Entry(form,textvariable=self.channel,width=8).pack(side='left',padx=5);ttk.Button(form,text='Save & Connect',command=self.connect).pack(side='left',padx=5);ttk.Button(form,text='Reconnect',command=self.reconnect).pack(side='left');ttk.Button(form,text='Disconnect',command=self.disconnect).pack(side='left',padx=5);self.auto=tk.BooleanVar(value=bool((self.m.config.get('printer') or {}).get('auto_reconnect',True)));ttk.Checkbutton(form,text='Auto reconnect',variable=self.auto,command=self.save_auto).pack(side='right')
        ttk.Label(tt,text='Select the active receipt theme.').pack(anchor='w');self.theme=tk.StringVar(value=self.m.config.get('theme','Classic'));ttk.Combobox(tt,textvariable=self.theme,values=list(self.m.themes),state='readonly').pack(fill='x',pady=5);ttk.Button(tt,text='Set Active Theme',command=self.set_theme).pack(anchor='w');grid=ttk.Frame(tt);grid.pack(fill='x',pady=12);self.vars={}
        for i,k in enumerate(['footer_text','show_address','show_phone','show_cashier','show_invoice']):
            ttk.Label(grid,text=k.replace('_',' ').title()).grid(row=i,column=0,sticky='w',pady=4);v=tk.BooleanVar() if k.startswith('show_') else tk.StringVar();self.vars[k]=v;(ttk.Checkbutton(grid,variable=v) if k.startswith('show_') else ttk.Entry(grid,textvariable=v,width=60)).grid(row=i,column=1,sticky='w')
        ttk.Button(tt,text='Save Theme',command=self.save_theme).pack(side='left');ttk.Button(tt,text='New Theme',command=self.new_theme).pack(side='left',padx=5);ttk.Button(tt,text='Delete Custom Theme',command=self.delete_theme).pack(side='left');self.load_theme()
    def scan(self):
        self.tree.delete(*self.tree.get_children());self.status.config(text='Scanning...')
        def cb(devs,done):
            def ui():
                self.tree.delete(*self.tree.get_children())
                for i,d in enumerate(devs):self.tree.insert('','end',iid=str(i),values=(d.get('name',''),d.get('address',''),d.get('type',''),d.get('details','')))
                if done:self.status.config(text=f'Found {len(devs)} device(s)')
            self.win.after(0,ui)
        self.m.discover(cb)
    def connect(self):
        s=self.tree.selection()
        if not s:return messagebox.showwarning('Printer','Select a device.',parent=self.win)
        v=self.tree.item(s[0],'values');d={'name':v[0],'address':v[1],'type':v[2],'details':v[3]}
        try:self.m.set_printer(d,int(self.channel.get()));self.m.config['printer']['auto_reconnect']=bool(self.auto.get());self.m.connect();self.status.config(text='Connected: '+d[0] if False else 'Connected: '+d['name']);messagebox.showinfo('Printer','Saved and connected.',parent=self.win)
        except Exception as e:messagebox.showerror('Printer connection failed',str(e),parent=self.win)
    def reconnect(self):self.status.config(text='Connected' if self.m.auto_reconnect() else 'Unable to connect')
    def disconnect(self):self.m.disconnect();self.status.config(text='Disconnected')
    def save_auto(self):
        if isinstance(self.m.config.get('printer'),dict):self.m.config['printer']['auto_reconnect']=bool(self.auto.get());self.m.save()
    def set_theme(self):self.m.config['theme']=self.theme.get();self.m.save();self.load_theme()
    def load_theme(self):
        d=self.m.themes.get(self.theme.get(),DEFAULT_THEMES['Classic']);[v.set(d.get(k,False if k.startswith('show_') else '')) for k,v in self.vars.items()]
    def save_theme(self):
        name=self.theme.get();self.m.themes[name].update({k:v.get() for k,v in self.vars.items()});self.m.save();messagebox.showinfo('Theme','Saved.',parent=self.win)
    def new_theme(self):
        name=simpledialog.askstring('New Theme','Theme name:',parent=self.win)
        if name and name not in self.m.themes:self.m.themes[name]=dict(DEFAULT_THEMES['Classic']);self.m.save();self.theme['values']=list(self.m.themes);self.theme.set(name);self.load_theme()
    def delete_theme(self):
        n=self.theme.get()
        if n in DEFAULT_THEMES:return messagebox.showwarning('Theme','Default themes cannot be deleted.',parent=self.win)
        if messagebox.askyesno('Delete',f'Delete {n}?',parent=self.win):self.m.themes.pop(n,None);self.m.save();self.theme['values']=list(self.m.themes);self.theme.set('Classic');self.load_theme()
