import asyncio, json, platform, subprocess, threading, time
from pathlib import Path

CONFIG_PATH = Path('printer_config.json')


def _load():
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding='utf-8')) if CONFIG_PATH.exists() else {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


class PrinterManager:
    """Windows-first printer manager.

    Important: Bluetooth discovery and printing are separate. A Bluetooth LE
    device is NOT forced through a COM port. Classic SPP printers use COM;
    BLE printers use their writable GATT characteristic; Windows installed
    printers use the Windows spooler.
    """
    def __init__(self):
        self.config = _load()
        self.config.setdefault('printer', None)
        self.sock = None
        self.device = None

    def save(self):
        CONFIG_PATH.write_text(json.dumps(self.config, indent=2), encoding='utf-8')

    def _windows_ble(self):
        out=[]
        try:
            from bleak import BleakScanner
            async def scan():
                return await BleakScanner.discover(timeout=8, return_adv=True)
            rows=asyncio.run(scan())
            for key,value in rows.items() if isinstance(rows,dict) else []:
                dev,adv=value
                out.append({'name':getattr(dev,'name',None) or 'Bluetooth LE device','address':str(getattr(dev,'address','')),
                            'type':'Bluetooth LE','details':f'RSSI={getattr(adv,"rssi","?")}'})
        except Exception as e:
            self._last_error=str(e)
        return out

    def _windows_com(self):
        out=[]
        try:
            import serial.tools.list_ports
            for p in serial.tools.list_ports.comports():
                out.append({'name':p.description or p.device,'address':p.device,'port':p.device,
                            'type':'Bluetooth/Serial COM' if 'bluetooth' in (p.description or '').lower() else 'Serial/COM',
                            'details':p.hwid or ''})
        except Exception as e:
            self._last_error=str(e)
        return out

    def _windows_printers(self):
        out=[]
        if platform.system() != 'Windows': return out
        try:
            import win32print
            flags=win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
            for p in win32print.EnumPrinters(flags):
                name=p[2]
                out.append({'name':name,'address':name,'type':'Windows Printer','details':str(p[1] or '')})
        except Exception as e:
            self._last_error=str(e)
        return out

    def discover(self, callback=None):
        def worker():
            rows=[]
            rows += self._windows_com()
            rows += self._windows_printers()
            rows += self._windows_ble()
            # Never hide devices merely because they are not recognized as printers.
            seen=set(); unique=[]
            for r in rows:
                k=(r.get('type'),r.get('address') or r.get('port') or r.get('name'))
                if k not in seen: seen.add(k); unique.append(r)
            if callback: callback(unique, True)
        threading.Thread(target=worker, daemon=True).start()

    def disconnect(self):
        try:
            if self.sock is not None and hasattr(self.sock,'close'): self.sock.close()
        except Exception: pass
        self.sock=None; self.device=None

    def _connect_com(self, d):
        import serial
        port=d.get('port') or d.get('address')
        # Do not require a status response: many ESC/POS Bluetooth SPP printers
        # never answer status commands. Opening the port is the valid connection test.
        configured=int(d.get('baudrate') or 9600)
        rates=[]
        for rate in (configured,9600,19200,38400,57600,115200):
            if rate not in rates: rates.append(rate)
        last=None
        for rate in rates:
            try:
                s=serial.Serial(port=port, baudrate=rate, bytesize=8, parity='N', stopbits=1,
                                timeout=1, write_timeout=2)
                self.sock=s; self.device=dict(d); self.device['port']=port; self.device['baudrate']=rate
                self.device['transport']='COM/SPP'; self.config['printer']=self.device; self.save()
                return True
            except Exception as e: last=e
        raise RuntimeError(f'Cannot open {port}: {last}')

    def _connect_windows_printer(self,d):
        import win32print
        h=win32print.OpenPrinter(d.get('name') or d.get('address'))
        self.sock=h; self.device=dict(d); self.device['transport']='WINDOWS_SPOOLER'
        self.config['printer']=self.device; self.save(); return True

    def _connect_ble(self,d):
        from bleak import BleakClient
        address=d.get('address')
        async def run():
            client=BleakClient(address); await client.connect()
            writable=[]
            for service in client.services:
                for ch in service.characteristics:
                    if 'write' in ch.properties or 'write-without-response' in ch.properties:
                        writable.append(ch)
            if not writable:
                await client.disconnect()
                raise RuntimeError('BLE connected, but the device exposes no writable GATT characteristic. It is not possible to send ESC/POS to this device through BLE.')
            # Prefer a characteristic whose service is a common printer service.
            chosen=writable[0]
            for ch in writable:
                if str(ch.service_uuid).lower() in {
                    '000018f0-0000-1000-8000-00805f9b34fb',
                    '0000ff00-0000-1000-8000-00805f9b34fb',
                    '0000ffe0-0000-1000-8000-00805f9b34fb',
                    '49535343-fe7d-4ae5-8fa9-9fafd205e455'}:
                    chosen=ch; break
            return client, str(chosen.uuid)
        client,char=asyncio.run(run())
        self.sock=client; self.device=dict(d); self.device['transport']='BLE-GATT'; self.device['characteristic']=char
        self.config['printer']=self.device; self.save(); return True

    def connect(self, device=None, auto=False):
        d=device or self.config.get('printer')
        if not isinstance(d,dict): raise RuntimeError('Select a printer first.')
        self.disconnect(); typ=str(d.get('type',''))
        if typ in ('Bluetooth/Serial COM','Serial/COM','Windows Serial/COM') or d.get('port','').upper().startswith('COM'):
            return self._connect_com(d)
        if typ in ('Bluetooth LE','BLE'):
            return self._connect_ble(d)
        if typ=='Windows Printer':
            return self._connect_windows_printer(d)
        raise RuntimeError(f'Unsupported transport: {typ}. A Bluetooth device must expose SPP/COM or writable BLE GATT to accept ESC/POS.')

    def auto_reconnect(self):
        try: return self.connect()
        except Exception: return False

    def auto_detect_and_connect(self, callback=None):
        def worker():
            saved=self.config.get('printer')
            if isinstance(saved,dict):
                try:
                    if self.connect(saved,auto=True):
                        if callback: callback('Reconnected to saved printer'); return
                except Exception: pass
            # Never guess a random COM device silently. Discover and expose it.
            if callback: callback('No saved printer connection. Open discovery and select the detected printer transport.')
        threading.Thread(target=worker,daemon=True).start()

    def status(self):
        return {'connected':self.sock is not None,'printer':self.config.get('printer'),'theme':self.config.get('theme','Classic')}

    def write_raw(self,data):
        if not self.sock:
            if not self.auto_reconnect(): raise RuntimeError('Printer is not connected.')
        if self.device and self.device.get('transport')=='BLE-GATT':
            async def send():
                try: await self.sock.write_gatt_char(self.device['characteristic'],data,response=False)
                except Exception: await self.sock.write_gatt_char(self.device['characteristic'],data,response=True)
            asyncio.run(send()); return
        if self.device and self.device.get('transport')=='WINDOWS_SPOOLER':
            import win32print
            job=win32print.StartDocPrinter(self.sock,1,('MK Pizza POS',None,'RAW'))
            try:
                win32print.StartPagePrinter(self.sock); win32print.WritePrinter(self.sock,data); win32print.EndPagePrinter(self.sock)
            finally: win32print.EndDocPrinter(self.sock)
            return
        self.sock.write(data); self.sock.flush()

    def test_print(self):
        data=b'\x1b@\x1ba\x01MK Pizza & Ice Bar\x0aPrinter Test\x0a\x0a\x1dV\x00'
        self.write_raw(data)
