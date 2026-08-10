import asyncio, json, platform, socket, subprocess, threading, time
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

CONFIG_PATH=Path('printer_config.json')
THEMES_PATH=Path('receipt_themes.json')
DEFAULT_THEMES={
    'Classic': {'separator':'--------------------------------','items':'name_qty_total','footer_text':'Thank you for visiting!','show_address':True,'show_phone':True,'show_cashier':True,'show_invoice':True},
    'Compact': {'separator':'--------------------------------','items':'compact','footer_text':'Thank you!','show_address':False,'show_phone':True,'show_cashier':False,'show_invoice':True},
    'Detailed': {'separator':'================================','items':'name_qty_unit_total','footer_text':'Thank you for your order!','show_address':True,'show_phone':True,'show_cashier':True,'show_invoice':True}
}

# Common BLE thermal-printer service/characteristic UUIDs. Vendors also use
# proprietary UUIDs, so the manager additionally detects writable characteristics.
KNOWN_BLE_PRINTER_SERVICES={
    '000018f0-0000-1000-8000-00805f9b34fb',
    '0000ff00-0000-1000-8000-00805f9b34fb',
    '0000ffe0-0000-1000-8000-00805f9b34fb',
    '49535343-fe7d-4ae5-8fa9-9fafd205e455',
}
PRINTER_WORDS=('printer','thermal','receipt','pos','escpos','80mm','58mm','print','mpt','xprinter','rongta','zjiang','gprinter','goojprt','mpt-')

def load_json(path, default):
    try:
        if path.exists():
            value=json.loads(path.read_text(encoding='utf-8'))
            if isinstance(value,dict): return value
    except Exception:
        pass
    value=json.loads(json.dumps(default))
    path.write_text(json.dumps(value,indent=2),encoding='utf-8')
    return value

class PrinterManager:
    def __init__(self):
        self.config=load_json(CONFIG_PATH,{'printer':None,'theme':'Classic'})
        if not isinstance(self.config.get('printer'),dict): self.config['printer']=None
        self.themes=load_json(THEMES_PATH,DEFAULT_THEMES)
        self.sock=None
        self.device=None
        self._ble_loop_lock=threading.Lock()

    def save(self):
        CONFIG_PATH.write_text(json.dumps(self.config,indent=2),encoding='utf-8')
        THEMES_PATH.write_text(json.dumps(self.themes,indent=2),encoding='utf-8')

    def _emit(self,callback,devices,done=False):
        if callback:
            try: callback(list(devices),done)
            except Exception: pass

    def _windows_serial_devices(self):
        found=[]
        try:
            import serial.tools.list_ports
            for p in serial.tools.list_ports.comports():
                desc=p.description or 'Serial/COM device'; hwid=p.hwid or ''
                text=(desc+' '+hwid).lower()
                score=1
                if any(w in text for w in PRINTER_WORDS): score+=8
                if 'bluetooth' in text: score+=5
                found.append({'name':desc,'address':p.device,'port':p.device,'type':'Serial/COM','details':f'{p.device} | VID={p.vid} PID={p.pid} | {hwid}','score':score,'vid':p.vid,'pid':p.pid,'capable':'printer' if score>=8 else 'unknown'})
        except Exception: pass
        try:
            cmd="Get-CimInstance Win32_SerialPort | Select-Object DeviceID,Name,Description,PNPDeviceID,ProviderType,Status | ConvertTo-Json -Compress"
            out=subprocess.check_output(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-Command',cmd],text=True,timeout=15)
            data=json.loads(out) if out.strip() else []
            if isinstance(data,dict): data=[data]
            for x in data:
                port=x.get('DeviceID') or ''
                if not port: continue
                text=' '.join(str(x.get(k) or '') for k in ('Name','Description','PNPDeviceID','ProviderType')).lower()
                score=8 if any(w in text for w in PRINTER_WORDS) else 2
                found.append({'name':x.get('Name') or x.get('Description') or port,'address':port,'port':port,'type':'Windows Serial/COM','details':f"{port} | {x.get('Description') or ''} | {x.get('PNPDeviceID') or ''}",'score':score,'capable':'printer' if score>=8 else 'unknown'})
        except Exception: pass
        return found

    def _windows_usb_printers(self):
        found=[]
        try:
            cmd="Get-CimInstance Win32_Printer | Select-Object Name,DriverName,PortName,PrinterStatus,WorkOffline,USBDeviceID | ConvertTo-Json -Compress"
            out=subprocess.check_output(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-Command',cmd],text=True,timeout=15)
            data=json.loads(out) if out.strip() else []
            if isinstance(data,dict): data=[data]
            for x in data:
                name=x.get('Name') or 'Windows Printer'
                port=x.get('PortName') or ''
                found.append({'name':name,'address':port,'port':port,'type':'Windows Printer/USB','details':f"Driver={x.get('DriverName') or ''} | Port={port} | Status={x.get('PrinterStatus') or ''}",'score':10 if any(w in name.lower() for w in PRINTER_WORDS) else 7,'capable':'spooler'})
        except Exception: pass
        return found

    def _windows_bluetooth_devices(self):
        found=[]
        try:
            cmd="Get-PnpDevice -Class Bluetooth -PresentOnly | Select-Object FriendlyName,InstanceId,Status,Manufacturer | ConvertTo-Json -Compress"
            out=subprocess.check_output(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-Command',cmd],text=True,timeout=15)
            data=json.loads(out) if out.strip() else []
            if isinstance(data,dict): data=[data]
            for x in data:
                name=x.get('FriendlyName') or 'Bluetooth Device'; text=name.lower()
                score=6 if any(w in text for w in PRINTER_WORDS) else 1
                found.append({'name':name,'address':x.get('InstanceId',''),'type':'Windows Bluetooth','details':f"{x.get('Status','')} | {x.get('Manufacturer','')} | {x.get('InstanceId','')}",'score':score,'capable':'possible' if score>=6 else 'unknown'})
        except Exception: pass
        return found

    def discover(self,callback=None):
        found=[]; seen=set(); lock=threading.Lock()
        def add(d):
            key=str(d.get('port') or d.get('address') or d.get('name') or '').lower()
            if not key:return
            with lock:
                if key in seen:return
                seen.add(key); found.append(d); snap=list(found)
            self._emit(callback,snap,False)
        def worker():
            # BLE discovery lists ALL nearby BLE devices. It does not reject devices
            # merely because their GATT service is not known.
            try:
                from bleak import BleakScanner
                async def scan_ble():
                    for d in await BleakScanner.discover(timeout=8,return_adv=True):
                        dev,adv=d if isinstance(d,tuple) else (d,None)
                        name=getattr(dev,'name',None) or 'Unknown BLE Device'
                        address=str(getattr(dev,'address',''))
                        uuids=[]
                        if adv:
                            uuids=list(getattr(adv,'service_uuids',None) or [])
                        known=any(str(u).lower() in KNOWN_BLE_PRINTER_SERVICES for u in uuids)
                        score=10 if known else (6 if any(w in name.lower() for w in PRINTER_WORDS) else 1)
                        add({'name':name,'address':address,'type':'Bluetooth LE','details':f"Services={','.join(map(str,uuids)) or 'not advertised'} | RSSI={getattr(adv,'rssi','?') if adv else '?'}",'score':score,'capable':'printer' if known or score>=6 else 'unknown','service_uuids':uuids})
                asyncio.run(scan_ble())
            except Exception: pass
            if platform.system()=='Windows':
                for d in self._windows_serial_devices(): add(d)
                for d in self._windows_usb_printers(): add(d)
                for d in self._windows_bluetooth_devices(): add(d)
            else:
                try:
                    out=subprocess.check_output(['bluetoothctl','devices'],text=True,timeout=10)
                    for line in out.splitlines():
                        p=line.split(' ',2)
                        if len(p)==3 and p[0]=='Device':
                            add({'name':p[2],'address':p[1],'type':'Classic Bluetooth','details':line,'score':6 if any(w in p[2].lower() for w in PRINTER_WORDS) else 1,'capable':'possible'})
                except Exception: pass
                try:
                    import serial.tools.list_ports
                    for p in serial.tools.list_ports.comports(): add({'name':p.description or p.device,'address':p.device,'port':p.device,'type':'Serial/COM','details':p.hwid or '','score':5,'capable':'unknown'})
                except Exception: pass
            self._emit(callback,found,True)
        threading.Thread(target=worker,daemon=True).start()
        return found

    def set_printer(self,device,channel=1,baudrate=9600):
        d=dict(device); d['channel']=int(channel); d['baudrate']=int(baudrate); d['auto_reconnect']=True
        self.config['printer']=d; self.save()

    def disconnect(self):
        try:
            if self.sock:self.sock.close()
        except Exception: pass
        self.sock=None; self.device=None

    def _probe_serial(self,port,baudrates=(9600,19200,38400,57600,115200)):
        try: import serial
        except ImportError: raise RuntimeError('Install pyserial: pip install -r requirements.txt')
        for baud in dict.fromkeys(baudrates):
            try:
                s=serial.Serial(port,baudrate=int(baud),timeout=0.7,write_timeout=0.7)
                s.reset_input_buffer(); s.write(b'\x10\x04\x01'); s.flush(); time.sleep(0.15)
                reply=s.read(16)
                return s,int(baud),bool(reply)
            except Exception: pass
        return None,None,False

    async def _ble_open(self,address):
        from bleak import BleakClient
        client=BleakClient(address)
        await client.connect()
        writable=[]
        for service in client.services:
            for ch in service.characteristics:
                if 'write' in ch.properties or 'write-without-response' in ch.properties:
                    writable.append(ch)
        if not writable:
            await client.disconnect(); return None,None
        # Prefer known printer services/characteristics, otherwise first writable endpoint.
        chosen=writable[0]
        for ch in writable:
            su=str(ch.service_uuid).lower()
            if su in KNOWN_BLE_PRINTER_SERVICES: chosen=ch; break
        return client,chosen.uuid

    def _ble_connect(self,device):
        try: import bleak
        except ImportError: raise RuntimeError('Install bleak: pip install -r requirements.txt')
        async def run(): return await self._ble_open(device['address'])
        client,char=asyncio.run(run())
        if not client: raise RuntimeError('Bluetooth LE device connected but exposes no writable print characteristic.')
        device=dict(device); device['characteristic']=str(char); device['transport']='BLE-GATT'
        self.sock=client; self.device=device
        self.config['printer']=device; self.save(); return True

    def connect(self,device=None,auto=False):
        device=device or self.config.get('printer')
        if not isinstance(device,dict): raise RuntimeError('No printer is configured.')
        self.disconnect(); typ=str(device.get('type','')); port=str(device.get('port') or '')
        if port.upper().startswith('COM') or 'Serial/COM' in typ:
            s,baud,verified=self._probe_serial(port,(int(device.get('baudrate',9600)),9600,19200,38400,57600,115200))
            if not s: raise RuntimeError(f'Unable to open {port}. Windows may have assigned this port to another device/application.')
            self.sock=s; self.device=dict(device); self.device['baudrate']=baud; self.device['verified']=verified
            self.config['printer']=dict(self.device); self.save(); return True
        if typ=='Windows Printer/USB' or typ=='USB Printer':
            try: import win32print
            except ImportError: raise RuntimeError('Windows printer support requires pywin32. Install it with: pip install pywin32')
            handle=win32print.OpenPrinter(device.get('name') or device.get('address'))
            self.sock=handle; self.device=dict(device); self.device['transport']='windows-spooler'; self.config['printer']=dict(self.device); self.save(); return True
        if typ in ('Bluetooth LE','BLE'):
            return self._ble_connect(device)
        if platform.system()!='Windows' and device.get('address'):
            self.sock=socket.socket(socket.AF_BLUETOOTH,socket.SOCK_STREAM,socket.BTPROTO_RFCOMM); self.sock.connect((device['address'],int(device.get('channel',1)))); self.device=dict(device); self.config['printer']=dict(device); self.save(); return True
        raise RuntimeError('This device was discovered, but Windows does not expose a printable transport for it. Select the printer COM/SPP entry, USB printer entry, or a BLE printer exposing a writable GATT characteristic.')

    def _auto_candidates(self):
        candidates=[]
        if platform.system()=='Windows':
            candidates.extend(self._windows_serial_devices())
            candidates.extend(self._windows_usb_printers())
        else:
            try:
                import serial.tools.list_ports
                candidates.extend({'name':p.description or p.device,'address':p.device,'port':p.device,'type':'Serial/COM','details':p.hwid or '','score':5,'capable':'unknown'} for p in serial.tools.list_ports.comports())
            except Exception: pass
        candidates.sort(key=lambda x:int(x.get('score',0)),reverse=True)
        return candidates

    def auto_detect_and_connect(self,callback=None):
        def report(msg):
            if callback:
                try: callback(msg)
                except Exception: pass
        def worker():
            saved=self.config.get('printer')
            if isinstance(saved,dict):
                report('Trying saved printer...')
                try:
                    if self.connect(saved,auto=True): report(f"Connected: {self.device.get('name') or self.device.get('port') or self.device.get('address')}"); return
                except Exception: pass
            report('Checking Windows printer ports and USB printers...')
            for d in self._auto_candidates():
                if not d.get('port') and d.get('type')!='Windows Printer/USB': continue
                report(f"Testing {d.get('name') or d.get('port')}...")
                try:
                    if self.connect(d,auto=True): report(f"Connected automatically: {d.get('name') or d.get('port')}"); return
                except Exception: pass
            report('No printer transport was verified automatically. Nearby Bluetooth devices remain visible in the discovery list.')
        threading.Thread(target=worker,daemon=True).start()

    def auto_reconnect(self):
        try: return self.connect()
        except Exception: return False

    def status(self): return {'connected':self.sock is not None,'printer':self.config.get('printer'),'theme':self.config.get('theme','Classic')}

    def _write(self,data):
        if not self.sock and not self.auto_reconnect(): raise RuntimeError('Printer is not connected. Use Auto Detect & Connect or select a printer.')
        if self.device and self.device.get('transport')=='BLE-GATT':
            async def send():
                try:
                    await self.sock.write_gatt_char(self.device['characteristic'],data,response=False)
                except Exception:
                    await self.sock.write_gatt_char(self.device['characteristic'],data,response=True)
            try: asyncio.run(send())
            except Exception as e: self.disconnect(); raise RuntimeError(f'Bluetooth printer write failed: {e}')
            return
        if self.device and self.device.get('transport')=='windows-spooler':
            try:
                import win32print
                job=win32print.StartDocPrinter(self.sock,1,('MK Pizza POS',None,'RAW')); win32print.StartPagePrinter(self.sock); win32print.WritePrinter(self.sock,data); win32print.EndPagePrinter(self.sock); win32print.EndDocPrinter(self.sock); return
            except Exception as e: raise RuntimeError(f'Windows printer spooler failed: {e}')
        try: self.sock.write(data); self.sock.flush()
        except Exception:
            self.disconnect(); self.connect(); self.sock.write(data); self.sock.flush()

    def render_receipt(self,business,invoice,items,subtotal,tax,total,payment,cashier=''):
        from datetime import datetime
        theme=self.themes.get(self.config.get('theme','Classic'),DEFAULT_THEMES['Classic']); width=48
        def t(x=''): return str(x)[:width]
        def center(x): return t(x).center(width)
        lines=[center(business.get('name','')),center('RECEIPT'),t(theme.get('separator','-'))]
        if theme.get('show_address'): lines.append(center(business.get('address','')))
        if theme.get('show_phone'): lines.append(center(business.get('phone','')))
        if theme.get('show_invoice'): lines.append(t(f'Invoice: {invoice}'))
        lines.append(t(datetime.now().strftime('Date: %Y-%m-%d %H:%M')))
        if theme.get('show_cashier') and cashier: lines.append(t(f'Cashier: {cashier}'))
        lines.append(t(theme.get('separator','-')))
        for i in items:
            name=str(i.get('name','')); q=i.get('qty',0); u=float(i.get('price',0)); line=float(q)*u
            if theme.get('items')=='name_qty_unit_total': lines.extend([t(name),t(f'  {q} x {u:,.2f} = {line:,.2f}')])
            else: lines.append(t(f'{name[:28]} x{q} {line:,.2f}'))
        cur=business.get('currency','Rs.')
        lines += [t(theme.get('separator','-')),t(f'Subtotal: {cur} {subtotal:,.2f}'),t(f'Tax: {cur} {tax:,.2f}'),t(f'TOTAL: {cur} {total:,.2f}'),t(f'Payment: {payment}'),t(theme.get('separator','-')),center(theme.get('footer_text','Thank you!')),'','']
        return '\n'.join(lines).encode('cp437',errors='replace')

    def print_receipt(self,business,invoice,items,subtotal,tax,total,payment,cashier=''):
        esc=b'\x1b'; data=esc+b'@'+esc+b'a\x01'+esc+b'E\x01'+self.render_receipt(business,invoice,items,subtotal,tax,total,payment,cashier)+esc+b'E\x00'+esc+b'a\x01'+b'\n\n\n'+b'\x1dV\x00'; self._write(data)

class PrinterSettings:
    def __init__(self,parent,manager,business=None):
        self.parent=parent; self.m=manager; self.business=business or {}; self.win=tk.Toplevel(parent); self.win.title('Printers & Receipt Settings'); self.win.geometry('1120x740'); self.build()

    def build(self):
        nb=ttk.Notebook(self.win); nb.pack(fill='both',expand=True,padx=10,pady=10)
        pt=ttk.Frame(nb,padding=10); tt=ttk.Frame(nb,padding=10); nb.add(pt,text='Printer Discovery'); nb.add(tt,text='Receipt Themes')
        top=ttk.Frame(pt); top.pack(fill='x')
        ttk.Button(top,text='AUTO DETECT & CONNECT',command=self.auto_detect,style='Primary.TButton').pack(side='left')
        ttk.Button(top,text='DISCOVER ALL DEVICES',command=self.scan).pack(side='left',padx=6)
        self.status=ttk.Label(top,text='Ready'); self.status.pack(side='right')
        note=ttk.Label(pt,text='Discovery lists nearby Bluetooth devices, Windows Bluetooth devices, COM ports and installed printers. Only printer-capable transports are connected automatically.',foreground='#64748b'); note.pack(anchor='w',pady=(8,4))
        self.tree=ttk.Treeview(pt,columns=('name','address','type','capable','details'),show='headings')
        for c,w in [('name',210),('address',220),('type',150),('capable',100),('details',430)]: self.tree.heading(c,text=c.title()); self.tree.column(c,width=w)
        self.tree.pack(fill='both',expand=True,pady=10)
        form=ttk.Frame(pt); form.pack(fill='x')
        ttk.Label(form,text='RFCOMM Channel').pack(side='left'); self.channel=tk.StringVar(value=str((self.m.config.get('printer') or {}).get('channel',1))); ttk.Entry(form,textvariable=self.channel,width=8).pack(side='left',padx=5)
        ttk.Label(form,text='Baud').pack(side='left'); self.baud=tk.StringVar(value=str((self.m.config.get('printer') or {}).get('baudrate',9600))); ttk.Combobox(form,textvariable=self.baud,values=['9600','19200','38400','57600','115200'],width=9).pack(side='left',padx=5)
        ttk.Button(form,text='SAVE & CONNECT',command=self.connect).pack(side='left',padx=5); ttk.Button(form,text='Reconnect',command=self.reconnect).pack(side='left'); ttk.Button(form,text='Disconnect',command=self.disconnect).pack(side='left',padx=5)
        self.auto=tk.BooleanVar(value=True); ttk.Checkbutton(form,text='Auto reconnect on POS startup',variable=self.auto,command=self.save_auto).pack(side='right')
        ttk.Label(tt,text='Active receipt theme').pack(anchor='w'); self.theme=tk.StringVar(value=self.m.config.get('theme','Classic')); ttk.Combobox(tt,textvariable=self.theme,values=list(self.m.themes),state='readonly').pack(fill='x',pady=5); ttk.Button(tt,text='Set Active Theme',command=self.set_theme).pack(anchor='w')
        grid=ttk.Frame(tt); grid.pack(fill='x',pady=12); self.vars={}
        for i,k in enumerate(['footer_text','show_address','show_phone','show_cashier','show_invoice']):
            ttk.Label(grid,text=k.replace('_',' ').title()).grid(row=i,column=0,sticky='w',pady=4); v=tk.BooleanVar() if k.startswith('show_') else tk.StringVar(); self.vars[k]=v; (ttk.Checkbutton(grid,variable=v) if k.startswith('show_') else ttk.Entry(grid,textvariable=v,width=60)).grid(row=i,column=1,sticky='w')
        ttk.Button(tt,text='Save Theme',command=self.save_theme).pack(side='left'); ttk.Button(tt,text='New Theme',command=self.new_theme).pack(side='left',padx=5); ttk.Button(tt,text='Delete Custom Theme',command=self.delete_theme).pack(side='left'); self.load_theme()

    def scan(self):
        self.tree.delete(*self.tree.get_children()); self.status.config(text='Discovering all devices...')
        def cb(devs,done):
            def ui():
                self.tree.delete(*self.tree.get_children())
                for i,d in enumerate(devs): self.tree.insert('','end',iid=str(i),values=(d.get('name',''),d.get('address',''),d.get('type',''),d.get('capable','unknown'),d.get('details','')))
                if done: self.status.config(text=f'Found {len(devs)} device(s)')
            try:self.win.after(0,ui)
            except Exception:pass
        self.m.discover(cb)

    def auto_detect(self):
        self.status.config(text='Auto-detecting printer...')
        self.m.auto_detect_and_connect(lambda msg:self.win.after(0,lambda:self.status.config(text=msg)))

    def connect(self):
        s=self.tree.selection()
        if not s:return messagebox.showwarning('Printer','Select a device.',parent=self.win)
        v=self.tree.item(s[0],'values'); d={'name':v[0],'address':v[1],'type':v[2],'capable':v[3],'details':v[4]}
        try:
            self.m.set_printer(d,int(self.channel.get()),int(self.baud.get())); self.m.config['printer']['auto_reconnect']=bool(self.auto.get()); self.m.connect(); self.status.config(text='Connected: '+d['name']); messagebox.showinfo('Printer','Saved and connected.',parent=self.win)
        except Exception as e: messagebox.showerror('Printer connection failed',str(e),parent=self.win)

    def reconnect(self): self.status.config(text='Connected' if self.m.auto_reconnect() else 'Unable to connect')
    def disconnect(self): self.m.disconnect(); self.status.config(text='Disconnected')
    def save_auto(self):
        if isinstance(self.m.config.get('printer'),dict): self.m.config['printer']['auto_reconnect']=bool(self.auto.get()); self.m.save()
    def set_theme(self): self.m.config['theme']=self.theme.get(); self.m.save(); self.load_theme()
    def load_theme(self):
        d=self.m.themes.get(self.theme.get(),DEFAULT_THEMES['Classic']); [v.set(d.get(k,False if k.startswith('show_') else '')) for k,v in self.vars.items()]
    def save_theme(self):
        name=self.theme.get(); self.m.themes[name].update({k:v.get() for k,v in self.vars.items()}); self.m.save(); messagebox.showinfo('Theme','Saved.',parent=self.win)
    def new_theme(self):
        name=simpledialog.askstring('New Theme','Theme name:',parent=self.win)
        if name and name not in self.m.themes: self.m.themes[name]=dict(DEFAULT_THEMES['Classic']); self.m.save(); self.theme['values']=list(self.m.themes); self.theme.set(name); self.load_theme()
    def delete_theme(self):
        n=self.theme.get()
        if n in DEFAULT_THEMES:return messagebox.showwarning('Theme','Default themes cannot be deleted.',parent=self.win)
        if messagebox.askyesno('Delete',f'Delete {n}?',parent=self.win): self.m.themes.pop(n,None); self.m.save(); self.theme['values']=list(self.m.themes); self.theme.set('Classic'); self.load_theme()
