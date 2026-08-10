import asyncio, json, platform, threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "printer_config.json"


def _load():
    try:
        candidates = [CONFIG_PATH, Path.cwd() / "printer_config.json"]
        for path in candidates:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    if path != CONFIG_PATH:
                        try:
                            CONFIG_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
                        except Exception:
                            pass
                    return data
        return {}
    except Exception:
        return {}


class _BLELoop:
    def __init__(self):
        self.loop = None
        self.thread = None
        self.ready = threading.Event()

    def start(self):
        if self.thread and self.thread.is_alive():
            return

        def runner():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.ready.set()
            self.loop.run_forever()

        self.thread = threading.Thread(target=runner, daemon=True, name="POS-BLE")
        self.thread.start()
        self.ready.wait(3)

    def run(self, coro, timeout=15):
        self.start()
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout)


class PrinterManager:
    def __init__(self):
        self.config = _load()
        self.config.setdefault("printer", None)
        self.config.setdefault("theme", "Classic")
        self.sock = None
        self.device = None
        self._last_error = ""
        self._ble = None

    def reload_config(self):
        """Refresh the saved printer/theme without destroying a live connection."""
        data = _load()
        if isinstance(data, dict):
            self.config = data
        self.config.setdefault("printer", None)
        self.config.setdefault("theme", "Classic")
        return self.config

    def save(self):
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = CONFIG_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.config, indent=2), encoding="utf-8")
        tmp.replace(CONFIG_PATH)

    def _windows_ble(self):
        out = []
        try:
            from bleak import BleakScanner

            async def scan():
                return await BleakScanner.discover(timeout=8, return_adv=True)

            rows = asyncio.run(scan())
            for key, value in rows.items() if isinstance(rows, dict) else []:
                dev, adv = value
                out.append({
                    "name": getattr(dev, "name", None) or "Bluetooth LE device",
                    "address": str(getattr(dev, "address", "")),
                    "type": "Bluetooth LE",
                    "details": f"RSSI={getattr(adv, 'rssi', '?')}",
                })
        except Exception as e:
            self._last_error = str(e)
        return out

    def _windows_com(self):
        out = []
        try:
            import serial.tools.list_ports
            for p in serial.tools.list_ports.comports():
                desc = p.description or ""
                hwid = p.hwid or ""
                out.append({
                    "name": desc or p.device,
                    "address": p.device,
                    "port": p.device,
                    "type": "Bluetooth/Serial COM" if "bluetooth" in desc.lower() or "bthenum" in hwid.lower() else "Serial/COM",
                    "details": hwid,
                    "serial_number": getattr(p, "serial_number", "") or "",
                    "manufacturer": getattr(p, "manufacturer", "") or "",
                })
        except Exception as e:
            self._last_error = str(e)
        return out

    def _windows_printers(self):
        out = []
        if platform.system() != "Windows":
            return out
        try:
            import win32print
            for p in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS):
                out.append({
                    "name": p[2],
                    "address": p[2],
                    "type": "Windows Printer",
                    "details": str(p[1] or ""),
                })
        except Exception as e:
            self._last_error = str(e)
        return out

    def discover_sync(self):
        rows = self._windows_com() + self._windows_printers() + self._windows_ble()
        seen = set()
        unique = []
        for r in rows:
            k = (r.get("type"), r.get("address") or r.get("port") or r.get("name"))
            if k not in seen:
                seen.add(k)
                unique.append(r)
        return unique

    def discover(self, callback=None):
        def worker():
            rows = self.discover_sync()
            if callback:
                callback(rows, True)
        threading.Thread(target=worker, daemon=True, name="POS-Printer-Discovery").start()

    def disconnect(self):
        if self.device and self.device.get("transport") == "BLE-GATT" and self.sock is not None and self._ble:
            try:
                self._ble.run(self.sock.disconnect(), timeout=5)
            except Exception:
                pass
        try:
            if self.sock is not None and hasattr(self.sock, "close"):
                self.sock.close()
        except Exception:
            pass
        self.sock = None
        self.device = None

    def _connect_com(self, d):
        import serial
        port = d.get("port") or d.get("address")
        configured = int(d.get("baudrate") or 9600)
        rates = []
        for rate in (configured, 9600, 19200, 38400, 57600, 115200):
            if rate not in rates:
                rates.append(rate)
        last = None
        for rate in rates:
            try:
                s = serial.Serial(port=port, baudrate=rate, bytesize=8, parity="N", stopbits=1, timeout=1, write_timeout=2)
                self.sock = s
                self.device = dict(d)
                self.device.update(port=port, baudrate=rate, transport="COM/SPP")
                self.config["printer"] = self.device
                self.save()
                return True
            except Exception as e:
                last = e
        raise RuntimeError(f"Cannot open {port}: {last}")

    def _connect_windows_printer(self, d):
        import win32print
        h = win32print.OpenPrinter(d.get("name") or d.get("address"))
        self.sock = h
        self.device = dict(d)
        self.device["transport"] = "WINDOWS_SPOOLER"
        self.config["printer"] = self.device
        self.save()
        return True

    async def _ble_connect_async(self, address, preferred=None):
        from bleak import BleakClient
        client = BleakClient(address)
        await client.connect()
        writable = []
        for service in client.services:
            for ch in service.characteristics:
                props = {str(p).lower() for p in ch.properties}
                if "write" in props or "write-without-response" in props:
                    writable.append(ch)
        if not writable:
            await client.disconnect()
            raise RuntimeError("Bluetooth LE connected, but no writable GATT characteristic was exposed. This device may not be an ESC/POS printer.")
        preferred = (preferred or "").lower()
        chosen = writable[0]
        preferred_services = {
            "000018f0-0000-1000-8000-00805f9b34fb",
            "0000ff00-0000-1000-8000-00805f9b34fb",
            "0000ffe0-0000-1000-8000-00805f9b34fb",
            "49535343-fe7d-4ae5-8fa9-9fafd205e455",
        }
        for ch in writable:
            if str(ch.uuid).lower() == preferred or str(ch.service_uuid).lower() in preferred_services:
                chosen = ch
                break
        return client, str(chosen.uuid)

    def _connect_ble(self, d):
        address = str(d.get("address") or "").strip()
        if not address:
            raise RuntimeError("Bluetooth printer has no address.")
        self._ble = self._ble or _BLELoop()
        client, char = self._ble.run(self._ble_connect_async(address, d.get("characteristic")), timeout=20)
        self.sock = client
        self.device = dict(d)
        self.device.update(transport="BLE-GATT", address=address, characteristic=char)
        self.config["printer"] = self.device
        self.save()
        return True

    def connect(self, device=None, auto=False):
        if device is None:
            self.reload_config()
        d = device or self.config.get("printer")
        if not isinstance(d, dict):
            raise RuntimeError("Select a printer first.")
        self.disconnect()
        typ = str(d.get("type", ""))
        if typ in ("Bluetooth/Serial COM", "Serial/COM", "Windows Serial/COM") or str(d.get("port", "")).upper().startswith("COM"):
            return self._connect_com(d)
        if typ in ("Bluetooth LE", "BLE"):
            return self._connect_ble(d)
        if typ == "Windows Printer":
            return self._connect_windows_printer(d)
        raise RuntimeError(f"Unsupported transport: {typ}")

    def _com_matches_saved(self, r, saved):
        fields = [str(saved.get(k, "")).lower() for k in ("name", "details", "manufacturer", "serial_number") if saved.get(k)]
        text = " ".join(str(r.get(k, "")) for k in ("name", "details", "manufacturer", "serial_number")).lower()
        return any(x and x in text for x in fields)

    def auto_reconnect(self):
        self.reload_config()
        saved = self.config.get("printer")
        if not isinstance(saved, dict) or not saved:
            self._last_error = "No saved printer."
            return False
        try:
            return self.connect(saved, auto=True)
        except Exception as first:
            self._last_error = str(first)

        try:
            rows = self.discover_sync()
            candidates = []
            stype = str(saved.get("type", ""))
            for r in rows:
                if stype in ("Bluetooth LE", "BLE") and r.get("type") == "Bluetooth LE" and str(r.get("address", "")).lower() == str(saved.get("address", "")).lower():
                    candidates.append(r)
                elif stype in ("Bluetooth/Serial COM", "Serial/COM") and r.get("type") in ("Bluetooth/Serial COM", "Serial/COM") and self._com_matches_saved(r, saved):
                    candidates.append(r)
                elif stype == "Windows Printer" and r.get("type") == "Windows Printer" and str(r.get("name", "")).lower() == str(saved.get("name", "")).lower():
                    candidates.append(r)
            if not candidates and stype in ("Bluetooth/Serial COM", "Serial/COM"):
                candidates = [r for r in rows if r.get("type") in ("Bluetooth/Serial COM", "Serial/COM")]
            for r in candidates:
                try:
                    if self.connect(r, auto=True):
                        return True
                except Exception as e:
                    self._last_error = str(e)
        except Exception as e:
            self._last_error = str(e)
        return False

    def auto_detect_and_connect(self, callback=None):
        def worker():
            ok = self.auto_reconnect()
            if callback:
                callback("Reconnected to saved printer" if ok else "Saved printer could not be reconnected.")
        threading.Thread(target=worker, daemon=True, name="POS-Printer-Autoreconnect").start()

    def status(self):
        # Saved identity is read from disk so reopening the Printers tab always
        # shows the actual last saved printer, even if this manager instance was
        # created before the printer was paired.
        saved = self.reload_config().get("printer")
        return {
            "connected": self.sock is not None,
            "printer": self.device or saved,
            "theme": self.config.get("theme", "Classic"),
            "error": self._last_error,
        }

    def write_raw(self, data):
        if not self.sock and not self.auto_reconnect():
            raise RuntimeError(self._last_error or "Printer is not connected.")
        if self.device and self.device.get("transport") == "BLE-GATT":
            async def send():
                try:
                    await self.sock.write_gatt_char(self.device["characteristic"], data, response=False)
                except Exception:
                    await self.sock.write_gatt_char(self.device["characteristic"], data, response=True)
            self._ble.run(send(), timeout=15)
            return
        if self.device and self.device.get("transport") == "WINDOWS_SPOOLER":
            import win32print
            win32print.StartDocPrinter(self.sock, 1, ("MK Pizza POS", None, "RAW"))
            try:
                win32print.StartPagePrinter(self.sock)
                win32print.WritePrinter(self.sock, data)
                win32print.EndPagePrinter(self.sock)
            finally:
                win32print.EndDocPrinter(self.sock)
            return
        self.sock.write(data)
        self.sock.flush()

    def test_print(self):
        self.write_raw(b"\x1b@\x1ba\x01MK Pizza & Ice Bar\x0aPrinter Test\x0a\x0a\x1dV\x00")


class PrinterSettings(tk.Toplevel):
    def __init__(self, parent, manager, business=None):
        super().__init__(parent)
        self.m = manager
        self.business = business or {}
        self.title("Printer Discovery & Settings")
        self.geometry("1000x620")
        self.minsize(700, 420)
        self.transient(parent)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(self, columns=("name", "type", "address", "details"), show="headings", selectmode="browse")
        for c in ("name", "type", "address", "details"):
            self.tree.heading(c, text=c.title())
            self.tree.column(c, width=190 if c != "details" else 360, minwidth=100)
        self.tree.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=12, pady=12)
        y = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        y.grid(row=0, column=2, sticky="ns", pady=12)
        self.tree.configure(yscrollcommand=y.set)
        bar = ttk.Frame(self)
        bar.grid(row=1, column=0, columnspan=3, sticky="ew", padx=12, pady=(0, 6))
        for text, cmd in [
            ("DISCOVER ALL DEVICES", self.discover),
            ("CONNECT SELECTED", self.connect_selected),
            ("RECONNECT SAVED", self.reconnect),
            ("TEST PRINT", self.test),
            ("DISCONNECT", self.disconnect),
        ]:
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=(0, 5))
        self.status = ttk.Label(self, text="Ready")
        self.status.grid(row=2, column=0, columnspan=3, sticky="w", padx=12, pady=(0, 10))
        self.discover()

    def discover(self):
        self.status.config(text="Discovering COM, Windows printers and Bluetooth LE devices...")
        self._rows = []

        def done(rows, ok):
            def ui():
                self.tree.delete(*self.tree.get_children())
                self._rows = rows
                for i, r in enumerate(rows):
                    self.tree.insert("", "end", iid=str(i), values=(r.get("name", ""), r.get("type", ""), r.get("address") or r.get("port", ""), r.get("details", "")))
                self.status.config(text=f"{len(rows)} devices found")
            self.after(0, ui)

        self.m.discover(done)

    def connect_selected(self):
        sel = self.tree.selection()
        if not sel:
            return messagebox.showwarning("Printer", "Select a device first.", parent=self)
        d = self._rows[int(sel[0])]
        try:
            self.m.connect(d)
            self.status.config(text=f"Connected: {d.get('name', 'Printer')}")
            messagebox.showinfo("Printer", "Connected and saved for automatic reconnect.", parent=self)
        except Exception as e:
            messagebox.showerror("Connection failed", str(e), parent=self)

    def reconnect(self):
        self.status.config(text="Reconnecting...")
        self.update_idletasks()

        def worker():
            ok = self.m.auto_reconnect()
            err = self.m.status().get("error", "")
            self.after(0, lambda: self._reconnect_done(ok, err))

        threading.Thread(target=worker, daemon=True, name="POS-Printer-Reconnect-UI").start()

    def _reconnect_done(self, ok, err):
        self.status.config(text="Reconnected to saved printer" if ok else "Reconnect failed")
        if not ok:
            messagebox.showerror("Printer", err or "Saved printer could not be reconnected.", parent=self)

    def test(self):
        try:
            self.m.test_print()
            messagebox.showinfo("Printer", "Test print sent.", parent=self)
        except Exception as e:
            messagebox.showerror("Print failed", str(e), parent=self)

    def disconnect(self):
        self.m.disconnect()
        self.status.config(text="Disconnected")
