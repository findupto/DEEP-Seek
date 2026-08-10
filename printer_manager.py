import asyncio, json, platform, socket, subprocess, threading, time, re
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

CONFIG_PATH=Path('printer_config.json'); THEMES_PATH=Path('receipt_themes.json')
DEFAULT_THEMES={'Classic':{'separator':'--------------------------------','items':'name_qty_total','footer_text':'Thank you for visiting!','show_address':True,'show_phone':True,'show_cashier':True,'show_invoice':True},'Compact':{'separator':'--------------------------------','items':'compact','footer_text':'Thank you!','show_address':False,'show_phone':True,'show_cashier':False,'show_invoice':True},'Detailed':{'separator':'================================','items':'name_qty_unit_total','footer_text':'Thank you for your order!','show_address':True,'show_phone':True,'show_cashier':True,'show_invoice':True}}

def load_json(path,default):
    try:
        if path.exists():
            value=json.loads(path.read_text(encoding='utf-8'))
            return value if isinstance(value,dict) else json.loads(json.dumps(default))
    except Exception:
        pass
    value=json.loads(json.dumps(default))
    path.write_text(json.dumps(value,indent=2),encoding='utf-8')
    return value

class PrinterManager:
    """ESC/POS printer manager.

    Windows Bluetooth thermal printers normally expose an SPP virtual COM port.
    This manager discovers those ports through pyserial and Windows WMI in addition
    to BLE discovery, then can automatically test likely printer ports.
    """
    def __init__(self):
        self.config=load_json(CONFIG_PATH,{'printer':None,'theme':'Classic'})
        if not isinstance(self.config.get('printer'),dict): self.config['printer']=None
        self.themes=load_json(THEMES_PATH,DEFAULT_THEMES)
        self.sock=None; self.device=None

    def save(self):
        CONFIG_PATH.write_text(json.dumps(self.config,indent=2),encoding='utf-8')
        THEMES_PATH.write_text(json.dumps(self.themes,indent=2),encoding='utf-8')

    def _add_unique(self,found,seen,device):
        key=str(device.get('port') or device.get('address') or device.get('name') or '').lower()
        if not key or key in seen:return
        seen.add(key); found.append(device)

    def _windows_serial_devices(self):
        found=[]
        try:
            import serial.tools.list_ports
            for p in serial.tools.list_ports.comports():
                desc=p.description or 'Serial/COM device'
                hwid=p.hwid or ''
                text=(desc+' '+hwid).lower()
                score=0
                if any(x in text for x in ('printer','thermal','receipt','pos','escpos','80mm','58mm')): score+=5
                if 'bluetooth' in text: score+=4
                found.append({'name':desc,'address':p.device,'port':p.device,'type':'Serial/COM','details':f'{p.device} | VID={p.vid} PID={p.pid} {hwid}','score':score,'vid':p.vid,'pid':p.pid})
        except Exception: pass
        # Win32_SerialPort catches some Bluetooth SPP mappings that pyserial descriptions
        # do not label clearly.
        try:
            cmd="Get-CimInstance Win32_SerialPort | Select-Object DeviceID,Name,Description,PNPDeviceID,ProviderType,Status | ConvertTo-Json -Compress"
            out=subprocess.check_output(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-Command',cmd],text=True,timeout=15)
            data=json.loads(out) if out.strip() else []
            if isinstance(data,dict): data=[data]
            for x in data:
                port=x.get('DeviceID') or ''
                if not port: continue
                text=' '.join(str(x.get(k) or '') for k in ('Name','Description','PNPDeviceID','ProviderType')).lower()
                score=5 if any(w in text for w in ('printer','thermal','receipt','pos','escpos','bluetooth')) else 1
                found.append({'name':x.get('Name') or x.get('Description') or port,'address':port,'port':port,'type':'Windows Serial/COM','details':f"{port} | {x.get('Description') or ''} | {x.get('PNPDeviceID') or ''}",'score':score})
        except Exception: pass
        return found

    def discover(self,callback=None):
        found=[];seen=set();lock=threading.Lock()
        def add(d):
            with lock:
                key=str(d.get('port') or d.get('address') or d.get('name') or '').lower()
                if not key or key in seen:return
                seen.add(key);found.append(d)
                snapshot=list(found)
            if callback:callback(snapshot,False)
        def worker():
            try:
                from bleak import BleakScanner
                async def scan():
                    for d in await BleakScanner.discover(timeout=7):
                        add({'name':d.name or 'Unknown BLE Device','address':str(d.address),'type':'BLE','details':str(d.metadata or {})})
                asyncio.run(scan())
            except Exception: pass
            if platform.system()=='Windows':
                for d in self._windows_serial_devices(): add(d)
                try:
                    cmd="Get-PnpDevice -Class Bluetooth -PresentOnly | Select-Object FriendlyName,InstanceId,Status | ConvertTo-Json -Compress"
                    out=subprocess.check_output(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-Command',cmd],text=True,timeout=15)
                    data=json.loads(out) if out.strip() else []
                    if isinstance(data,dict):data=[data]
                    for x in data:add({'name':x.get('FriendlyName') or 'Bluetooth Device','address':x.get('InstanceId',''),'type':'Windows Bluetooth','details':f"{x.get('Status','')} | {x.get('InstanceId','')}"})
                except Exception: pass
            else:
                try:
                    out=subprocess.check_output(['bluetoothctl','devices'],text=True,timeout=10)
                    for line in out.splitlines():
                        p=line.split(' ',2)
                        if len(p)==3 and p[0]=='Device':add({'name':p[2],'address':p[1],'type':'Classic Bluetooth','details':line})
                except Exception: pass
            if callback:callback(list(found),True)
        threading.Thread(target=worker,daemon=True).start();return found

    def set_printer(self,device,channel=1,baudrate=9600):
        d=dict(device);d['channel']=int(channel);d['baudrate']=int(baudrate);d['auto_reconnect']=True
        self.config['printer']=d;self.save()

    def disconnect(self):
        try:
            if self.sock:self.sock.close()
        except Exception:pass
        self.sock=None;self.device=None

    def _probe_serial(self,port,baudrates=(9600,19200,38400,57600,115200)):
        """Best-effort ESC/POS handshake. It never prints a receipt/test page."""
        try: import serial
        except ImportError: raise RuntimeError('Install pyserial: pip install pyserial')
        for baud in baudrates:
            s=None
            try:
                s=serial.Serial(port,baudrate=baud,timeout=0.7,write_timeout=0.7)
                # DLE EOT 1 is a standard ESC/POS real-time printer-status query.
                # Some printers answer, some stay silent. Silent ports are still valid
                # candidates and are handled by the fallback open below.
                s.reset_input_buffer();s.write(b'\x10\x04\x01');s.flush();time.sleep(0.15)
                reply=s.read(16)
                if reply:
                    return s,baud,True
                s.close()
            except Exception:
                try:
                    if s:s.close()
                except Exception:pass
        # Opening the port itself is the final compatibility fallback. Many Bluetooth
        # SPP printers do not implement the status command but accept normal ESC/POS.
        for baud in baudrates:
            try:return serial.Serial(port,baudrate=baud,timeout=3,write_timeout=3),baud,False
            except Exception:pass
        return None,None,False

    def connect(self,device=None,auto=False):
        device=device or self.config.get('printer')
        if not isinstance(device,dict):raise RuntimeError('No printer is configured.')
        self.disconnect();port=device.get('port') or device.get('address','');typ=str(device.get('type',''))
        if platform.system()=='Windows' and (str(port).upper().startswith('COM') or 'COM' in typ.upper()):
            s,baud,verified=self._probe_serial(str(port),(int(device.get('baudrate',9600)),9600,19200,38400,57600,115200))
            if not s:raise RuntimeError(f'Unable to open {port}. It may belong to another application/device.')
            self.sock=s;self.device=dict(device);self.device['baudrate']=baud;self.device['verified']=verified
            self.config['printer']=dict(self.device);self.save();return True
        if platform.system()!='Windows' and typ in ('Classic Bluetooth','Serial/COM','Windows Serial/COM'):
            if str(port).upper().startswith('/dev/'):
                s,baud,verified=self._probe_serial(str(port),(9600,19200,38400,57600,115200))
                if not s:raise RuntimeError(f'Unable to open {port}.')
                self.sock=s;self.device=dict(device);self.device['baudrate']=baud;self.device['verified']=verified;self.config['printer']=dict(self.device);self.save();return True
        if platform.system()!='Windows' and device.get('address'):
            self.sock=socket.socket(socket.AF_BLUETOOTH,socket.SOCK_STREAM,socket.BTPROTO_RFCOMM);self.sock.connect((device['address'],int(device.get('channel',1))));self.device=dict(device);return True
        raise RuntimeError('This Bluetooth device is not exposing a printable ESC/POS service. On Windows it must provide a virtual COM/SPP port or a supported USB printer interface.')

    def auto_detect_and_connect(self,callback=None):
        """Discover and automatically connect to the best available printer.
        A configured printer is tried first; if it fails, current Windows COM devices
        are scanned and tested without printing a test page.
        """
        def report(msg):
            if callback:
                try:callback(msg)
                except Exception:pass
        def worker():
            report('Trying saved printer...')
            saved=self.config.get('printer')
            if isinstance(saved,dict):
                try:
                    if self.connect(saved,auto=True):report(f"Connected: {self.device.get('name') or self.device.get('port')}");return
                except Exception:pass
            report('Scanning Bluetooth / COM printers...')
            candidates=[]
            if platform.system()=='Windows':candidates=self._windows_serial_devices()
            else:
                try:
                    import serial.tools.list_ports;candidates=[{'name':p.description or p.device,'address':p.device,'port':p.device,'type':'Serial/COM','details':p.hwid} for p in serial.tools.list_ports.comports()]
                except Exception:pass
            candidates.sort(key=lambda x:int(x.get('score',0)),reverse=True)
            for d in candidates:
                if not d.get('port'):continue
                report(f"Testing {d.get('port')} — {d.get('name','Serial device')}")
                try:
                    if self.connect(d,auto=True):report(f"Connected automatically: {d.get('name') or d.get('port')}");return
                except Exception:continue
            report('No compatible ESC/POS printer was detected.')
        threading.Thread(target=worker,daemon=True).start()

    def auto_reconnect(self):
        try:return self.connect()
        except Exception:return False

    def status(self):return {'connected':self.sock is not None,'printer':self.config.get('printer'),'theme':self.config.get('theme','Classic')}

    def _write(self,data):
        if not self.sock and not self.auto_reconnect():raise RuntimeError('Printer is not connected. Use Auto Detect & Connect or select a printer.')
        try:self.sock.write(data);self.sock.flush()
        except Exception:
            self.disconnect();self.connect();self.sock.write(data);self.sock.flush()

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
        self.parent=parent;self.m=manager;self.business=business or {};self.win=tk.Toplevel(parent);self.win.title('Printers & Receipt Settings');self.win.geometry('1080x720');self.build()

    def build(self):
        nb=ttk.Notebook(self.win);nb.pack(fill='both',expand=True,padx=10,pady=10);pt=ttk.Frame(nb,padding=10);tt=ttk.Frame(nb,padding=10);nb.add(pt,text='Printer Discovery');nb.add(tt,text='Receipt Themes')
        top=ttk.Frame(pt);top.pack(fill='x');ttk.Button(top,text='AUTO DETECT & CONNECT',command=self.auto_detect,style='Primary.TButton').pack(side='left');ttk.Button(top,text='Discover / Search Live',command=self.scan).pack(side='left',padx=6);self.status=ttk.Label(top,text='Ready');self.status.pack(side='right')
        self.tree=ttk.Treeview(pt,columns=('name','address','type','details'),show='headings');
        for c in ('name','address','type','details'):self.tree.heading(c,text=c.title());self.tree.column(c,width=240)
        self.tree.pack(fill='both',expand=True,pady=10)
        form=ttk.Frame(pt);form.pack(fill='x');ttk.Label(form,text='RFCOMM Channel').pack(side='left');self.channel=tk.StringVar(value=str((self.m.config.get('printer') or {}).get('channel',1)));ttk.Entry(form,textvariable=self.channel,width=8).pack(side='left',padx=5);ttk.Label(form,text='Baud').pack(side='left');self.baud=tk.StringVar(value=str((self.m.config.get('printer') or {}).get('baudrate',9600)));ttk.Combobox(form,textvariable=self.baud,values=['9600','19200','38400','57600','115200'],width=9).pack(side='left',padx=5);ttk.Button(form,text='Save & Connect',command=self.connect).pack(side='left',padx=5);ttk.Button(form,text='Reconnect',command=self.reconnect).pack(side='left');ttk.Button(form,text='Disconnect',command=self.disconnect).pack(side='left',padx=5);self.auto=tk.BooleanVar(value=True);ttk.Checkbutton(form,text='Auto reconnect on POS startup',variable=self.auto,command=self.save_auto).pack(side='right')
        ttk.Label(tt,text='Select the active receipt theme.').pack(anchor='w');self.theme= tk.StringVar(value=self.m.config.get('theme','Classic'));ttk.Combobox(tt,textvariable=self.theme,values=list(self.m.themes),state='readonly').pack(fill='x',pady=5);ttk.Button(tt,text='Set Active Theme',command=self.set_theme).pack(anchor='w');grid=ttk.Frame(tt);grid.pack(fill='x',pady=12);self.vars={}
        for i,k in enumerate(['footer_text','show_address','show_phone','show_cashier','show_invoice']):
            ttk.Label(grid,text=k.replace('_',' ').title()).grid(row=i,column=0,sticky='w',pady=4);v=tk.BooleanVar() if k.startswith('show_') else tk.StringVar();self.vars[k]=v;(ttk.Checkbutton(grid,variable=v) if k.startswith('show_') else ttk.Entry(grid,textvariable=v,width=60)).grid(row=i,column=1,sticky='w')
        ttk.Button(tt,text='Save Theme',command=self.save_theme).pack(side='left');ttk.Button(tt,text='New Theme',command=self.new_theme).pack(side='left',padx=5);ttk.Button(tt,text='Delete Custom Theme',command=self.delete_theme).pack(side='left');self.load_theme()

    def scan(self):
        self.tree.delete(*self.tree.get_children());self.status.config(text='Scanning Bluetooth / COM...')
        def cb(devs,done):
            def ui():
                self.tree.delete(*self.tree.get_children())
                for i,d in enumerate(devs):self.tree.insert('','end',iid=str(i),values=(d.get('name',''),d.get('address',''),d.get('type',''),d.get('details','')))
                if done:self.status.config(text=f'Found {len(devs)} device(s)')
            self.win.after(0,ui)
        self.m.discover(cb)

    def auto_detect(self):
        self.status.config(text='Auto-detecting printer...')
        def cb(msg):self.win.after(0,lambda:self.status.config(text=msg))
        self.m.auto_detect_and_connect(cb)

    def connect(self):
        s=self.tree.selection()
        if not s:return messagebox.showwarning('Printer','Select a discovered device.',parent=self.win)
        v=self.tree.item(s[0],'values');d={'name':v[0],'address':v[1],'type':v[2],'details':v[3]}
        try:
            self.m.set_printer(d,int(self.channel.get()),int(self.baud.get()));self.m.config['printer']['auto_reconnect']=bool(self.auto.get());self.m.connect();self.status.config(text='Connected: '+d['name']);messagebox.showinfo('Printer','Saved and connected.',parent=self.win)
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
