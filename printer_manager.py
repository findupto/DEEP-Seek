import asyncio, json, platform, threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

CONFIG_PATH = Path('printer_config.json')

def _load():
    try:
        data=json.loads(CONFIG_PATH.read_text(encoding='utf-8')) if CONFIG_PATH.exists() else {}
        return data if isinstance(data,dict) else {}
    except Exception: return {}

class PrinterManager:
    def __init__(self):
        self.config=_load(); self.config.setdefault('printer',None); self.sock=None; self.device=None; self._last_error=''
    def save(self): CONFIG_PATH.write_text(json.dumps(self.config,indent=2),encoding='utf-8')
    def _windows_ble(self):
        out=[]
        try:
            from bleak import BleakScanner
            async def scan(): return await BleakScanner.discover(timeout=8,return_adv=True)
            rows=asyncio.run(scan())
            for key,value in rows.items() if isinstance(rows,dict) else []:
                dev,adv=value; out.append({'name':getattr(dev,'name',None) or 'Bluetooth LE device','address':str(getattr(dev,'address','')),'type':'Bluetooth LE','details':f'RSSI={getattr(adv,"rssi","?")}'})
        except Exception as e: self._last_error=str(e)
        return out
    def _windows_com(self):
        out=[]
        try:
            import serial.tools.list_ports
            for p in serial.tools.list_ports.comports(): out.append({'name':p.description or p.device,'address':p.device,'port':p.device,'type':'Bluetooth/Serial COM' if 'bluetooth' in (p.description or '').lower() else 'Serial/COM','details':p.hwid or ''})
        except Exception as e: self._last_error=str(e)
        return out
    def _windows_printers(self):
        out=[]
        if platform.system()!='Windows': return out
        try:
            import win32print
            for p in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL|win32print.PRINTER_ENUM_CONNECTIONS): out.append({'name':p[2],'address':p[2],'type':'Windows Printer','details':str(p[1] or '')})
        except Exception as e: self._last_error=str(e)
        return out
    def discover_sync(self):
        rows=self._windows_com()+self._windows_printers()+self._windows_ble(); seen=set(); unique=[]
        for r in rows:
            k=(r.get('type'),r.get('address') or r.get('port') or r.get('name'))
            if k not in seen: seen.add(k); unique.append(r)
        return unique
    def discover(self,callback=None):
        def worker():
            rows=self.discover_sync()
            if callback: callback(rows,True)
        threading.Thread(target=worker,daemon=True).start()
    def disconnect(self):
        try:
            if self.sock is not None and hasattr(self.sock,'close'): self.sock.close()
        except Exception: pass
        self.sock=None; self.device=None
    def _connect_com(self,d):
        import serial
        port=d.get('port') or d.get('address'); configured=int(d.get('baudrate') or 9600); rates=[]
        for rate in (configured,9600,19200,38400,57600,115200):
            if rate not in rates: rates.append(rate)
        last=None
        for rate in rates:
            try:
                s=serial.Serial(port=port,baudrate=rate,bytesize=8,parity='N',stopbits=1,timeout=1,write_timeout=2)
                self.sock=s; self.device=dict(d); self.device.update(port=port,baudrate=rate,transport='COM/SPP'); self.config['printer']=self.device; self.save(); return True
            except Exception as e: last=e
        raise RuntimeError(f'Cannot open {port}: {last}')
    def _connect_windows_printer(self,d):
        import win32print
        h=win32print.OpenPrinter(d.get('name') or d.get('address')); self.sock=h; self.device=dict(d); self.device['transport']='WINDOWS_SPOOLER'; self.config['printer']=self.device; self.save(); return True
    def _connect_ble(self,d):
        from bleak import BleakClient
        address=d.get('address')
        async def run():
            client=BleakClient(address); await client.connect(); writable=[]
            for service in client.services:
                for ch in service.characteristics:
                    if 'write' in ch.properties or 'write-without-response' in ch.properties: writable.append(ch)
            if not writable: await client.disconnect(); raise RuntimeError('BLE connected, but no writable GATT characteristic was exposed.')
            chosen=writable[0]
            for ch in writable:
                if str(ch.service_uuid).lower() in {'000018f0-0000-1000-8000-00805f9b34fb','0000ff00-0000-1000-8000-00805f9b34fb','0000ffe0-0000-1000-8000-00805f9b34fb','49535343-fe7d-4ae5-8fa9-9fafd205e455'}: chosen=ch; break
            return client,str(chosen.uuid)
        client,char=asyncio.run(run()); self.sock=client; self.device=dict(d); self.device.update(transport='BLE-GATT',characteristic=char); self.config['printer']=self.device; self.save(); return True
    def connect(self,device=None,auto=False):
        d=device or self.config.get('printer')
        if not isinstance(d,dict): raise RuntimeError('Select a printer first.')
        self.disconnect(); typ=str(d.get('type',''))
        if typ in ('Bluetooth/Serial COM','Serial/COM','Windows Serial/COM') or str(d.get('port','')).upper().startswith('COM'): return self._connect_com(d)
        if typ in ('Bluetooth LE','BLE'): return self._connect_ble(d)
        if typ=='Windows Printer': return self._connect_windows_printer(d)
        raise RuntimeError(f'Unsupported transport: {typ}')
    def auto_reconnect(self):
        saved=self.config.get('printer')
        if not isinstance(saved,dict): self._last_error='No saved printer.'; return False
        try: return self.connect(saved,auto=True)
        except Exception as first:
            self._last_error=str(first)
        # Windows Bluetooth COM assignments can change. Rediscover and match the saved
        # hardware identity/name instead of blindly reopening an obsolete COM number.
        try:
            rows=self.discover_sync(); target=str(saved.get('address') or saved.get('name') or '').lower()
            candidates=[]
            for r in rows:
                ident=str(r.get('address') or r.get('port') or '').lower(); name=str(r.get('name') or '').lower()
                if target and (target==ident or target==name or (saved.get('name') and name==str(saved.get('name')).lower())): candidates.append(r)
            for r in candidates:
                try:
                    if self.connect(r,auto=True): return True
                except Exception as e: self._last_error=str(e)
        except Exception as e: self._last_error=str(e)
        return False
    def auto_detect_and_connect(self,callback=None):
        def worker():
            ok=self.auto_reconnect()
            if callback: callback('Reconnected to saved printer' if ok else 'Saved printer could not be reconnected; discover devices to select it.')
        threading.Thread(target=worker,daemon=True).start()
    def status(self): return {'connected':self.sock is not None,'printer':self.config.get('printer'),'theme':self.config.get('theme','Classic'),'error':self._last_error}
    def write_raw(self,data):
        if not self.sock and not self.auto_reconnect(): raise RuntimeError(self._last_error or 'Printer is not connected.')
        if self.device and self.device.get('transport')=='BLE-GATT':
            async def send():
                try: await self.sock.write_gatt_char(self.device['characteristic'],data,response=False)
                except Exception: await self.sock.write_gatt_char(self.device['characteristic'],data,response=True)
            asyncio.run(send()); return
        if self.device and self.device.get('transport')=='WINDOWS_SPOOLER':
            import win32print
            win32print.StartDocPrinter(self.sock,1,('MK Pizza POS',None,'RAW'))
            try: win32print.StartPagePrinter(self.sock); win32print.WritePrinter(self.sock,data); win32print.EndPagePrinter(self.sock)
            finally: win32print.EndDocPrinter(self.sock)
            return
        self.sock.write(data); self.sock.flush()
    def test_print(self): self.write_raw(b'\x1b@\x1ba\x01MK Pizza & Ice Bar\x0aPrinter Test\x0a\x0a\x1dV\x00')

class PrinterSettings(tk.Toplevel):
    def __init__(self,parent,manager,business=None):
        super().__init__(parent); self.m=manager; self.business=business or {}; self.title('Printer Discovery & Settings'); self.geometry('950x600'); self.transient(parent)
        self.tree=ttk.Treeview(self,columns=('name','type','address','details'),show='headings')
        for c in ('name','type','address','details'): self.tree.heading(c,text=c.title()); self.tree.column(c,width=180 if c!='details' else 300)
        self.tree.pack(fill='both',expand=True,padx=12,pady=12); bar=ttk.Frame(self); bar.pack(fill='x',padx=12,pady=(0,12))
        ttk.Button(bar,text='DISCOVER ALL DEVICES',command=self.discover).pack(side='left'); ttk.Button(bar,text='CONNECT SELECTED',command=self.connect_selected).pack(side='left',padx=6); ttk.Button(bar,text='RECONNECT SAVED',command=self.reconnect).pack(side='left'); ttk.Button(bar,text='TEST PRINT',command=self.test).pack(side='left',padx=6); ttk.Button(bar,text='DISCONNECT',command=self.disconnect).pack(side='left')
        self.status=ttk.Label(self,text='Ready'); self.status.pack(anchor='w',padx=12,pady=(0,10)); self.discover()
    def discover(self):
        self.status.config(text='Discovering COM, Windows printers and Bluetooth LE devices...'); self._rows=[]
        def done(rows,ok):
            def ui():
                self.tree.delete(*self.tree.get_children()); self._rows=rows
                for i,r in enumerate(rows): self.tree.insert('','end',iid=str(i),values=(r.get('name',''),r.get('type',''),r.get('address') or r.get('port',''),r.get('details','')))
                self.status.config(text=f'{len(rows)} devices found')
            self.after(0,ui)
        self.m.discover(done)
    def connect_selected(self):
        sel=self.tree.selection()
        if not sel: return messagebox.showwarning('Printer','Select a device first.',parent=self)
        d=self._rows[int(sel[0])]
        try: self.m.connect(d); self.status.config(text=f"Connected: {d.get('name','Printer')}"); messagebox.showinfo('Printer','Connected and saved for automatic reconnect.',parent=self)
        except Exception as e: messagebox.showerror('Connection failed',str(e),parent=self)
    def reconnect(self):
        self.status.config(text='Reconnecting...'); self.update_idletasks(); ok=self.m.auto_reconnect(); self.status.config(text='Reconnected to saved printer' if ok else 'Reconnect failed')
        if not ok: messagebox.showerror('Printer',self.m.status().get('error') or 'Saved printer could not be reconnected.',parent=self)
    def test(self):
        try: self.m.test_print(); messagebox.showinfo('Printer','Test print sent.',parent=self)
        except Exception as e: messagebox.showerror('Print failed',str(e),parent=self)
    def disconnect(self): self.m.disconnect(); self.status.config(text='Disconnected')
