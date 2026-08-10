"""Final printer persistence fixes.

Keeps printer configuration beside the application and keeps BLE connections
alive on a dedicated asyncio loop.  This module patches the existing
PrinterManager; it does not create a second printer implementation.
"""
import asyncio
import json
import shutil
import threading
from pathlib import Path


def install_printer(printer_manager_module):
    app_dir = Path(__file__).resolve().parent
    config_path = app_dir / "printer_config.json"
    old_cwd_path = Path("printer_config.json").resolve()
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

    def _ble_call(self, coro, timeout=15):
        self._ble_start()
        future = asyncio.run_coroutine_threadsafe(coro, self._ble_loop)
        return future.result(timeout=timeout)

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
            raise RuntimeError("Bluetooth LE connected, but no writable GATT characteristic was exposed.")
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
            raise RuntimeError("The Bluetooth printer has no usable Bluetooth address.")
        try:
            old = getattr(self, "_ble_client", None)
            if old:
                self._ble_call(old.disconnect(), timeout=5)
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
    def init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self._ble_loop = None
        self._ble_thread = None
        self._ble_client = None
        self._ble_char = None
    PM.__init__ = init

    # These are actual bound methods.  The previous patch only defined local
    # functions and then called self._ble_call(), causing the reported error.
    PM._ble_start = _ble_start
    PM._ble_loop_runner = _ble_loop_runner
    PM._ble_call = _ble_call

    original_connect = PM.connect
    def connect(self, device=None, auto=False):
        d = device or self.config.get("printer") or {}
        typ = str(d.get("type", ""))
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
    # Kept as a no-op compatibility hook.  The canonical shell is installed
    # by canonical_ui_patch, avoiding multiple competing sidebar builders.
    return App
