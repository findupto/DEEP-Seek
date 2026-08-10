import json
import os
import platform
import socket
import subprocess
import threading
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

CONFIG_PATH = Path("printer_config.json")
THEMES_PATH = Path("receipt_themes.json")

DEFAULT_THEMES = {
    "Classic": {
        "header": "center_bold",
        "business": "center_bold",
        "separator": "--------------------------------",
        "items": "name_qty_total",
        "footer": "center",
        "footer_text": "Thank you for visiting!",
        "show_address": True,
        "show_phone": True,
        "show_cashier": True,
        "show_invoice": True,
    },
    "Compact": {
        "header": "center_bold",
        "business": "center",
        "separator": "--------------------------------",
        "items": "compact",
        "footer": "center",
        "footer_text": "Thank you!",
        "show_address": False,
        "show_phone": True,
        "show_cashier": False,
        "show_invoice": True,
    },
    "Detailed": {
        "header": "center_bold",
        "business": "center_bold",
        "separator": "================================",
        "items": "name_qty_unit_total",
        "footer": "center",
        "footer_text": "Thank you for your order!",
        "show_address": True,
        "show_phone": True,
        "show_cashier": True,
        "show_invoice": True,
    },
}


def load_json(path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    path.write_text(json.dumps(default, indent=2), encoding="utf-8")
    return default.copy() if isinstance(default, dict) else default


class PrinterManager:
    """Bluetooth 80mm ESC/POS printer discovery, persistence, reconnect and printing."""

    def __init__(self):
        self.config = load_json(CONFIG_PATH, {"printer": None, "theme": "Classic"})
        self.themes = load_json(THEMES_PATH, DEFAULT_THEMES)
        self.device = None
        self.sock = None

    def save(self):
        CONFIG_PATH.write_text(json.dumps(self.config, indent=2), encoding="utf-8")
        THEMES_PATH.write_text(json.dumps(self.themes, indent=2), encoding="utf-8")

    def discover(self, callback=None):
        """Discover BLE and classic Bluetooth devices. Callback receives list incrementally."""
        found = []
        lock = threading.Lock()

        def add(d):
            key = (d.get("address") or d.get("device_id") or d.get("name") or "").lower()
            if not key:
                return
            with lock:
                if any((x.get("address") or x.get("device_id") or x.get("name") or "").lower() == key for x in found):
                    return
                found.append(d)
                if callback:
                    callback(list(found))

        def worker():
            try:
                from bleak import BleakScanner
                import asyncio
                async def scan():
                    devices = await BleakScanner.discover(timeout=6)
                    for d in devices:
                        name = d.name or "Unknown Bluetooth Device"
                        add({"name": name, "address": d.address, "type": "BLE", "details": str(d.metadata or {})})
                asyncio.run(scan())
            except Exception:
                pass
            try:
                if platform.system() == "Windows":
                    out = subprocess.check_output(["powershell", "-NoProfile", "-Command", "Get-PnpDevice -Class Bluetooth | Select-Object FriendlyName,InstanceId | ConvertTo-Json -Compress"], text=True, timeout=15)
                    data = json.loads(out) if out.strip() else []
                    if isinstance(data, dict): data = [data]
                    for x in data:
                        add({"name": x.get("FriendlyName") or "Bluetooth Device", "address": x.get("InstanceId", ""), "type": "Windows Bluetooth", "details": x.get("InstanceId", "")})
            except Exception:
                pass
            try:
                if platform.system() != "Windows":
                    out = subprocess.check_output(["bluetoothctl", "devices"], text=True, timeout=10)
                    for line in out.splitlines():
                        parts = line.split(" ", 2)
                        if len(parts) >= 3 and parts[0] == "Device":
                            add({"name": parts[2], "address": parts[1], "type": "Classic Bluetooth", "details": line})
            except Exception:
                pass
            if callback:
                callback(list(found), done=True)

        threading.Thread(target=worker, daemon=True).start()
        return found

    def set_printer(self, device, channel=1):
        self.config["printer"] = dict(device)
        self.config["printer"]["channel"] = int(channel)
        self.save()

    def disconnect(self):
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass
        self.sock = None

    def connect(self, device=None):
        device = device or self.config.get("printer")
        if not device:
            raise RuntimeError("No printer is configured.")
        self.disconnect()
        address = device.get("address", "")
        channel = int(device.get("channel", 1))
        # RFCOMM/SPP connection used by many classic Bluetooth ESC/POS printers.
        if platform.system() == "Windows":
            # Windows paired printers are normally exposed as a COM port. The configured address
            # can be replaced with a COM port in Settings (for example COM7).
            if address.upper().startswith("COM"):
                import serial
                self.sock = serial.Serial(address, 9600, timeout=3)
            else:
                raise RuntimeError("Pair the printer in Windows Bluetooth first, then select its COM port.")
        else:
            self.sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
            self.sock.connect((address, channel))
        self.device = device
        return True

    def auto_reconnect(self):
        try:
            return self.connect()
        except Exception:
            return False

    def status(self):
        return {"connected": self.sock is not None, "printer": self.config.get("printer"), "theme": self.config.get("theme", "Classic")}

    def _write(self, data):
        if not self.sock and not self.auto_reconnect():
            raise RuntimeError("Printer is not connected. Configure/pair the printer first.")
        try:
            self.sock.write(data)
        except Exception:
            self.disconnect()
            if not self.auto_reconnect():
                raise
            self.sock.write(data)

    def print_bytes(self, data):
        self._write(data)

    def render_receipt(self, business, invoice, items, subtotal, tax, total, payment, cashier=""):
        theme = self.themes.get(self.config.get("theme", "Classic"), DEFAULT_THEMES["Classic"])
        width = 48  # 80mm paper, typical 203dpi ESC/POS text width.
        lines = []
        def txt(value=""):
            return str(value)[:width]
        def center(value):
            return txt(value).center(width)
        lines += [center(business.get("name", "")), center("RECEIPT"), txt(theme.get("separator", "-"))]
        if theme.get("show_address"): lines.append(center(business.get("address", "")))
        if theme.get("show_phone"): lines.append(center(business.get("phone", "")))
        if theme.get("show_invoice"): lines.append(txt(f"Invoice: {invoice}"))
        lines.append(txt(datetime.now().strftime("Date: %Y-%m-%d %H:%M")))
        if theme.get("show_cashier") and cashier: lines.append(txt(f"Cashier: {cashier}"))
        lines.append(txt(theme.get("separator", "-")))
        for item in items:
            name = str(item.get("name", ""))
            qty = item.get("qty", 0)
            unit = float(item.get("price", 0))
            line = float(item.get("qty", 0)) * unit
            if theme.get("items") == "compact":
                lines.append(txt(f"{name[:28]} x{qty} {line:,.2f}"))
            elif theme.get("items") == "name_qty_unit_total":
                lines.append(txt(name))
                lines.append(txt(f"  {qty} x {unit:,.2f} = {line:,.2f}"))
            else:
                lines.append(txt(f"{name[:28]} x{qty} {line:,.2f}"))
        lines += [txt(theme.get("separator", "-")), txt(f"Subtotal: {business.get('currency','Rs.')} {subtotal:,.2f}"), txt(f"Tax: {business.get('currency','Rs.')} {tax:,.2f}"), txt(f"TOTAL: {business.get('currency','Rs.')} {total:,.2f}"), txt(f"Payment: {payment}"), txt(theme.get("separator", "-")), center(theme.get("footer_text", "Thank you!")), "", ""]
        return "\n".join(lines).encode("cp437", errors="replace")

    def print_receipt(self, business, invoice, items, subtotal, tax, total, payment, cashier=""):
        ESC = b"\x1b"
        data = ESC + b"@" + ESC + b"a\x01" + ESC + b"E\x01" + self.render_receipt(business, invoice, items, subtotal, tax, total, payment, cashier) + ESC + b"E\x00" + ESC + b"a\x01" + b"\n\n\n" + b"\x1dV\x00"
        self.print_bytes(data)


class PrinterSettings:
    def __init__(self, parent, manager, business=None):
        self.parent = parent
        self.m = manager
        self.business = business or {}
        self.win = tk.Toplevel(parent)
        self.win.title("Printers & Receipt Settings")
        self.win.geometry("920x650")
        self.build()

    def build(self):
        nb = ttk.Notebook(self.win); nb.pack(fill="both", expand=True, padx=10, pady=10)
        ptab = ttk.Frame(nb, padding=10); ttab = ttk.Frame(nb, padding=10); nb.add(ptab, text="Bluetooth Printer"); nb.add(ttab, text="Receipt Themes")
        top = ttk.Frame(ptab); top.pack(fill="x")
        ttk.Button(top, text="Discover / Search Live", command=self.scan).pack(side="left")
        self.status_label = ttk.Label(top, text="Not connected"); self.status_label.pack(side="right")
        self.tree = ttk.Treeview(ptab, columns=("name","address","type","details"), show="headings")
        for c in ("name","address","type","details"): self.tree.heading(c, text=c.title()); self.tree.column(c, width=190)
        self.tree.pack(fill="both", expand=True, pady=10)
        form = ttk.Frame(ptab); form.pack(fill="x")
        ttk.Label(form,text="RFCOMM / COM Channel").pack(side="left"); self.channel=tk.StringVar(value=str(self.m.config.get("printer",{}).get("channel",1))); ttk.Entry(form,textvariable=self.channel,width=8).pack(side="left",padx=5)
        ttk.Button(form,text="Save & Connect",command=self.connect).pack(side="left",padx=5); ttk.Button(form,text="Reconnect",command=self.reconnect).pack(side="left")
        self.auto=tk.BooleanVar(value=True); ttk.Checkbutton(form,text="Auto reconnect on POS startup",variable=self.auto,command=self.save_auto).pack(side="right")
        ttk.Label(ttab,text="Select a theme, then edit fields. Changes are saved locally.").pack(anchor="w")
        self.theme_list=ttk.Combobox(ttab,values=list(self.m.themes),state="readonly"); self.theme_list.pack(fill="x",pady=5); self.theme_list.bind("<<ComboboxSelected>>",lambda e:self.load_theme())
        grid=ttk.Frame(ttab); grid.pack(fill="x",pady=8)
        self.vars={}
        for i,key in enumerate(["footer_text","show_address","show_phone","show_cashier","show_invoice"]):
            ttk.Label(grid,text=key.replace('_',' ').title()).grid(row=i,column=0,sticky='w',pady=4)
            if key.startswith('show_'):
                v=tk.BooleanVar(); ttk.Checkbutton(grid,variable=v).grid(row=i,column=1,sticky='w'); self.vars[key]=v
            else:
                v=tk.StringVar(); ttk.Entry(grid,textvariable=v,width=60).grid(row=i,column=1,sticky='w'); self.vars[key]=v
        buttons=ttk.Frame(ttab); buttons.pack(fill='x',pady=10); ttk.Button(buttons,text='Save Theme',command=self.save_theme).pack(side='left'); ttk.Button(buttons,text='New Theme',command=self.new_theme).pack(side='left',padx=5); ttk.Button(buttons,text='Delete Theme',command=self.delete_theme).pack(side='left')
        self.theme_list.set(self.m.config.get('theme','Classic')); self.load_theme()

    def scan(self):
        for x in self.tree.get_children(): self.tree.delete(x)
        self.status_label.config(text="Searching Bluetooth devices…")
        def cb(devices, done=False):
            def ui():
                for x in self.tree.get_children(): self.tree.delete(x)
                for i,d in enumerate(devices): self.tree.insert('', 'end', iid=str(i), values=(d.get('name',''),d.get('address',''),d.get('type',''),d.get('details','')))
                if done: self.status_label.config(text=f"Found {len(devices)} device(s)")
            self.win.after(0,ui)
        self.m.discover(cb)

    def connect(self):
        sel=self.tree.selection()
        if not sel:return messagebox.showwarning('Printer','Select a discovered printer.',parent=self.win)
        vals=self.tree.item(sel[0],'values'); d={'name':vals[0],'address':vals[1],'type':vals[2],'details':vals[3]}
        try:
            self.m.set_printer(d,int(self.channel.get())); self.m.connect(); self.status_label.config(text='Connected: '+d['name']); messagebox.showinfo('Printer','Printer saved and connected.',parent=self.win)
        except Exception as e: messagebox.showerror('Printer connection failed',str(e),parent=self.win)

    def reconnect(self):
        if self.m.auto_reconnect(): self.status_label.config(text='Connected')
        else: self.status_label.config(text='Unable to connect')

    def save_auto(self):
        self.m.config['printer']['auto_reconnect']=bool(self.auto.get()) if self.m.config.get('printer') else bool(self.auto.get()); self.m.save()

    def load_theme(self):
        name=self.theme_list.get(); data=self.m.themes.get(name,{})
        for k,v in self.vars.items(): self.vars[k].set(data.get(k,False if k.startswith('show_') else ''))

    def save_theme(self):
        name=self.theme_list.get();
        if not name:return
        self.m.themes[name].update({k:v.get() for k,v in self.vars.items()}); self.m.save(); messagebox.showinfo('Theme','Theme saved.',parent=self.win)

    def new_theme(self):
        name=tk.simpledialog.askstring('New Theme','Theme name:',parent=self.win) if hasattr(tk,'simpledialog') else None
        if not name:return
        self.m.themes[name]=dict(DEFAULT_THEMES['Classic']); self.m.save(); self.theme_list['values']=list(self.m.themes); self.theme_list.set(name); self.load_theme()

    def delete_theme(self):
        name=self.theme_list.get()
        if name in ('Classic','Compact','Detailed'):
            return messagebox.showwarning('Theme','Default themes cannot be deleted.',parent=self.win)
        if name and messagebox.askyesno('Delete Theme',f'Delete {name}?',parent=self.win):
            self.m.themes.pop(name,None); self.m.save(); self.theme_list['values']=list(self.m.themes); self.theme_list.set('Classic'); self.load_theme()
