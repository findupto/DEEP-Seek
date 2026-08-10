"""Robust reconnect layer for PrinterManager.

The POS remembers the actual transport and attempts recovery without asking
users to guess COM ports or baud rates. No print data is sent during discovery.
"""
import asyncio
import platform


def install(PrinterManager):
    if getattr(PrinterManager, "_reconnect_patch_installed", False):
        return
    old_auto = PrinterManager.auto_reconnect

    def auto_reconnect(self):
        saved = self.config.get("printer")
        if not isinstance(saved, dict):
            return False
        try:
            return self.connect(saved, auto=True)
        except Exception:
            pass
        typ = str(saved.get("type", ""))
        # BLE: address is stable; retry directly with the saved address.
        if typ in ("Bluetooth LE", "BLE") and saved.get("address"):
            try:
                return self.connect({**saved, "type": "Bluetooth LE"}, auto=True)
            except Exception:
                return False
        # COM/SPP: Windows can assign a different COM number after a re-pair.
        # Match the saved device by description/hardware id where possible,
        # then try the discovered port. We never iterate unrelated COM ports.
        if typ in ("Bluetooth/Serial COM", "Serial/COM", "Windows Serial/COM") or str(saved.get("port", "")).upper().startswith("COM"):
            try:
                import serial.tools.list_ports
                old_name = str(saved.get("name", "")).lower()
                old_addr = str(saved.get("address", "")).lower()
                candidates = []
                for p in serial.tools.list_ports.comports():
                    text = " ".join([str(p.device), str(p.description), str(p.hwid), str(getattr(p, "serial_number", ""))]).lower()
                    score = 0
                    if old_name and old_name in text: score += 5
                    if old_addr and old_addr in text: score += 5
                    if "bluetooth" in text: score += 2
                    if score: candidates.append((score, p))
                for _, p in sorted(candidates, key=lambda x: x[0], reverse=True):
                    d = dict(saved)
                    d.update({"port": p.device, "address": p.device, "name": p.description or saved.get("name", p.device), "type": "Bluetooth/Serial COM"})
                    try:
                        return self.connect(d, auto=True)
                    except Exception:
                        continue
            except Exception:
                pass
        # Installed Windows printer: its queue name is stable even when its
        # underlying Bluetooth/USB port changes.
        if typ == "Windows Printer" and platform.system() == "Windows":
            try:
                return self.connect(saved, auto=True)
            except Exception:
                return False
        return False

    def auto_detect_and_connect(self, callback=None):
        def worker():
            ok = self.auto_reconnect()
            if callback:
                callback("Printer reconnected automatically." if ok else "Saved printer could not be reconnected. Open discovery to select it again.")
        import threading
        threading.Thread(target=worker, daemon=True).start()

    PrinterManager.auto_reconnect = auto_reconnect
    PrinterManager.auto_detect_and_connect = auto_detect_and_connect
    PrinterManager._reconnect_patch_installed = True
    return PrinterManager
