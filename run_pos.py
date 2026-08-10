import pos
from printer_manager import PrinterManager, PrinterSettings

printer_manager = PrinterManager()
_original_build_nav = pos.Main.build_nav
_original_show = pos.Main.show


def build_nav_with_printer(self):
    _original_build_nav(self)
    nav = self.body.master.winfo_children()[1]
    import tkinter.ttk as ttk
    ttk.Button(nav, text="Printers", command=lambda: self.show("Printers")).pack(side="left", padx=2)


def show_with_printer(self, name):
    if name != "Printers":
        return _original_show(self, name)
    for w in self.body.winfo_children():
        w.destroy()
    import tkinter.ttk as ttk
    ttk.Label(self.body, text="Printers", font=("Segoe UI", 20, "bold")).pack(anchor="w")
    ttk.Label(self.body, text="80mm Bluetooth thermal printer discovery, connection and receipt themes").pack(anchor="w", pady=(0, 10))
    ttk.Button(self.body, text="Open Printer & Receipt Settings", command=lambda: PrinterSettings(self, printer_manager, pos.BUSINESS)).pack(anchor="w")
    status = printer_manager.status()
    printer = status.get("printer") or {}
    ttk.Label(self.body, text=f"Saved Printer: {printer.get('name', 'None')}").pack(anchor="w", pady=8)
    ttk.Label(self.body, text=f"Status: {'Connected' if status.get('connected') else 'Not connected'}").pack(anchor="w")
    ttk.Label(self.body, text=f"Receipt Theme: {status.get('theme', 'Classic')}").pack(anchor="w")
    if printer.get("auto_reconnect", True):
        self.after(250, printer_manager.auto_reconnect)


pos.Main.build_nav = build_nav_with_printer
pos.Main.show = show_with_printer

# Preserve the existing POS entry flow while adding printer auto-reconnect on startup.
_original_init = pos.Main.__init__
def init_with_printer(self, db, user):
    _original_init(self, db, user)
    if printer_manager.config.get("printer", {}).get("auto_reconnect", True):
        self.after(300, printer_manager.auto_reconnect)
pos.Main.__init__ = init_with_printer

if __name__ == "__main__":
    db = pos.DB()
    pos.Login(db).mainloop()
