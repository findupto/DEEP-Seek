"""Final UI and printer persistence fixes.

Keeps one canonical POS while fixing two real operational issues:
- printer configuration is stored beside the application, not in the process CWD;
- BLE connections use a persistent asyncio loop so a successful connection survives
  after the discovery coroutine returns;
- the sidebar has its own scrollable navigation area and never overlays the footer.
"""
import asyncio
import json
import shutil
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox


def install_printer(printer_manager_module):
    """Make printer configuration deterministic and BLE connections persistent."""
    app_dir = Path(__file__).resolve().parent
    config_path = app_dir / "printer_config.json"
    old_cwd_path = Path("printer_config.json").resolve()

    # Migrate an existing config created by an older build when the paths differ.
    if not config_path.exists() and old_cwd_path.exists() and old_cwd_path != config_path:
        try:
            shutil.copy2(old_cwd_path, config_path)
        except Exception:
            pass
    printer_manager_module.CONFIG_PATH = config_path
    PM = printer_manager_module.PrinterManager

    def _ble_start(self):
        if getattr(self, "_ble_loop", None) and self._ble_loop.is_running():
            return
        self._ble_loop = asyncio.new_event_loop()
        self._ble_thread = threading.Thread(target=self._ble_loop_runner, daemon=True, name="POS-BLE")
        self._ble_thread.start()

    def _ble_loop_runner(self):
        asyncio.set_event_loop(self._ble_loop)
        self._ble_loop.run_forever()
        self._ble_loop.close()

    def _ble_stop(self):
        loop = getattr(self, "_ble_loop", None)
        if loop and loop.is_running():
            loop.call_soon_threadsafe(loop.stop)
        self._ble_loop = None
        self._ble_thread = None

    def _ble_call(self, coro, timeout=15):
        self._ble_start()
        fut = asyncio.run_coroutine_threadsafe(coro, self._ble_loop)
        return fut.result(timeout=timeout)

    async def _ble_connect_coro(self, address):
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
            raise RuntimeError("Bluetooth LE connected, but the printer exposes no writable GATT characteristic.")
        preferred = {
            "000018f0-0000-1000-8000-00805f9b34fb",
            "0000ff00-0000-1000-8000-00805f9b34fb",
            "0000ffe0-0000-1000-8000-00805f9b34fb",
            "49535343-fe7d-4ae5-8fa9-9fafd205e455",
        }
        chosen = next((c for c in writable if str(c.service_uuid).lower() in preferred), writable[0])
        return client, str(chosen.uuid)

    def _connect_ble_persistent(self, d):
        address = d.get("address")
        if not address:
            raise RuntimeError("The Bluetooth printer has no usable address.")
        # Close an earlier BLE client without killing the application.
        try:
            if getattr(self, "_ble_client", None):
                self._ble_call(self._ble_client.disconnect(), timeout=5)
        except Exception:
            pass
        client, char = self._ble_call(self._ble_connect_coro(address), timeout=20)
        self._ble_client = client
        self._ble_char = char
        self.sock = client
        self.device = dict(d)
        self.device.update(transport="BLE-GATT", characteristic=char)
        self.config["printer"] = self.device
        self.save()
        return True

    def _write_ble_persistent(self, data):
        client = getattr(self, "_ble_client", None)
        char = getattr(self, "_ble_char", None)
        if not client or not char:
            raise RuntimeError("Bluetooth printer is not connected.")
        async def send():
            try:
                await client.write_gatt_char(char, data, response=False)
            except Exception:
                await client.write_gatt_char(char, data, response=True)
        self._ble_call(send(), timeout=15)

    original_init = PM.__init__
    def init(self):
        original_init(self)
        self._ble_loop = None
        self._ble_thread = None
        self._ble_client = None
        self._ble_char = None
    PM.__init__ = init

    original_connect = PM.connect
    def connect(self, device=None, auto=False):
        d = device or self.config.get("printer")
        typ = str((d or {}).get("type", ""))
        if typ in ("Bluetooth LE", "BLE"):
            self.disconnect()
            return _connect_ble_persistent(self, d)
        return original_connect(self, device=device, auto=auto)
    PM.connect = connect

    original_disconnect = PM.disconnect
    def disconnect(self):
        try:
            client = getattr(self, "_ble_client", None)
            if client and getattr(self, "_ble_loop", None) and self._ble_loop.is_running():
                try:
                    self._ble_call(client.disconnect(), timeout=5)
                except Exception:
                    pass
        finally:
            self._ble_client = None
            self._ble_char = None
            original_disconnect(self)
    PM.disconnect = disconnect

    original_write = PM.write_raw
    def write_raw(self, data):
        if self.device and self.device.get("transport") == "BLE-GATT":
            try:
                _write_ble_persistent(self, data)
                return
            except Exception as first:
                self._last_error = str(first)
                # One automatic reconnect before failing the print.
                try:
                    if self.auto_reconnect():
                        _write_ble_persistent(self, data)
                        return
                except Exception as second:
                    self._last_error = str(second)
                raise RuntimeError(self._last_error)
        return original_write(self, data)
    PM.write_raw = write_raw


def install_ui(App):
    """Replace the fixed sidebar with a scrollable navigation shell."""
    def build(self):
        side = tk.Frame(self, bg="#111827", width=235)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)

        tk.Label(side, text="MK PIZZA\n& ICE BAR", bg="#111827", fg="white",
                 font=("Segoe UI", 17, "bold"), justify="left").pack(anchor="w", padx=18, pady=(20, 10))
        tk.Label(side, text=f"{self.user['username']} • {self.user['role']}",
                 bg="#111827", fg="#9ca3af", font=("Segoe UI", 9)).pack(anchor="w", padx=18, pady=(0, 10))

        nav_host = tk.Frame(side, bg="#111827")
        nav_host.pack(fill="both", expand=True)
        canvas = tk.Canvas(nav_host, bg="#111827", highlightthickness=0, bd=0)
        scroll = ttk.Scrollbar(nav_host, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg="#111827")
        window_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        modules = ['POS','Dashboard','Orders','Kitchen','Customers','Tables / Dine-in','Suppliers',
                   'Products','Riders','Staff','Reports','Printers','Settings']
        buttons = {}
        for name in modules:
            b = tk.Button(inner, text=name, anchor="w", relief="flat", bd=0,
                          bg="#111827", fg="white", activebackground="#1f2937",
                          activeforeground="white", font=("Segoe UI", 10, "bold"),
                          padx=18, pady=10, cursor="hand2",
                          command=lambda x=name: self.show(x))
            b.pack(fill="x", padx=4, pady=1)
            buttons[name] = b

        def refresh_scroll(_=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfigure(window_id, width=canvas.winfo_width())
        inner.bind("<Configure>", refresh_scroll)
        canvas.bind("<Configure>", refresh_scroll)

        def wheel(event):
            canvas.yview_scroll(-1 * int(event.delta / 120), "units")
        canvas.bind_all("<MouseWheel>", wheel, add="+")

        footer = tk.Frame(side, bg="#111827", height=42)
        footer.pack(side="bottom", fill="x")
        footer.pack_propagate(False)
        tk.Label(footer, text="MK Pizza & Ice Bar", bg="#111827", fg="#64748b",
                 font=("Segoe UI", 8)).pack(anchor="w", padx=18, pady=10)

        self.nav_buttons = buttons
        self.body = ttk.Frame(self, padding=22)
        self.body.pack(side="left", fill="both", expand=True)

    App.build = build

    # Keep the active module visible/highlighted without changing the page API.
    original_show = App.show
    def show(self, name):
        result = original_show(self, name)
        for key, b in getattr(self, "nav_buttons", {}).items():
            active = key == name
            b.configure(bg="#2563eb" if active else "#111827",
                         fg="white", activebackground="#1d4ed8")
        return result
    App.show = show
