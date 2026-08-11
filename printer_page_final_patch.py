"""Final printer page refresh/status UX without changing printer transport logic."""
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from printer_manager import PrinterSettings
from pos_app import BUSINESS


def install(App):
    if getattr(App, "_printer_page_final_installed", False):
        return App

    def page_printers(self):
        self.title("Printers & Receipt Themes", "Real ESC/POS, Windows spooler and Bluetooth printer support with saved identity and safe reconnect.")
        try:
            self.pm.reload_config()
        except Exception:
            pass
        status = self.pm.status()
        printer = status.get("printer") or {}

        card = ttk.LabelFrame(self.bodyinner, text="PRINTER CONNECTION", padding=16)
        card.pack(fill="x", pady=(8, 12))
        card.columnconfigure(1, weight=1)
        ttk.Label(card, text="Saved Printer", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w", pady=3)
        name_var = tk.StringVar(value=printer.get("name") or printer.get("address") or "None")
        ttk.Label(card, textvariable=name_var, font=("Segoe UI", 12, "bold")).grid(row=0, column=1, sticky="w", pady=3)
        ttk.Label(card, text="Transport", font=("Segoe UI", 10, "bold")).grid(row=1, column=0, sticky="w", pady=3)
        transport_var = tk.StringVar(value=printer.get("transport") or printer.get("type") or "-")
        ttk.Label(card, textvariable=transport_var).grid(row=1, column=1, sticky="w", pady=3)
        ttk.Label(card, text="Status", font=("Segoe UI", 10, "bold")).grid(row=2, column=0, sticky="w", pady=3)
        status_var = tk.StringVar(value="CONNECTED" if status.get("connected") else "NOT CONNECTED")
        ttk.Label(card, textvariable=status_var, font=("Segoe UI", 10, "bold")).grid(row=2, column=1, sticky="w", pady=3)

        buttons = ttk.Frame(card)
        buttons.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        ttk.Button(buttons, text="OPEN DISCOVERY / SETTINGS", style="Primary.TButton", command=lambda: PrinterSettings(self, self.pm, BUSINESS)).pack(side="left")

        def reconnect():
            status_var.set("RECONNECTING...")
            def worker():
                ok = False
                try:
                    ok = self.pm.auto_reconnect()
                except Exception:
                    ok = False
                def done():
                    if not self.winfo_exists():
                        return
                    self.pm.reload_config()
                    s = self.pm.status(); p = s.get("printer") or {}
                    name_var.set(p.get("name") or p.get("address") or "None")
                    transport_var.set(p.get("transport") or p.get("type") or "-")
                    status_var.set("CONNECTED" if s.get("connected") else "NOT CONNECTED")
                    if not ok:
                        err = s.get("error") or "Saved printer could not be reconnected."
                        messagebox.showwarning("Printer", err, parent=self)
                self.after(0, done)
            threading.Thread(target=worker, daemon=True, name="POS-Printer-Page-Reconnect").start()

        ttk.Button(buttons, text="RECONNECT SAVED", command=reconnect).pack(side="left", padx=5)
        ttk.Button(buttons, text="TEST PRINT", command=self.print_test).pack(side="left")
        ttk.Button(buttons, text="REFRESH STATUS", command=lambda: self.show("Printers")).pack(side="left", padx=5)

        theme_box = ttk.LabelFrame(self.bodyinner, text="RECEIPT THEME", padding=16)
        theme_box.pack(fill="x", pady=8)
        theme = tk.StringVar(value=status.get("theme", "Classic"))
        ttk.Combobox(theme_box, textvariable=theme, values=["Classic", "Compact", "Modern"], state="readonly", width=20).pack(side="left")
        ttk.Button(theme_box, text="SAVE THEME", style="Soft.TButton", command=lambda: self.save_theme(theme.get())).pack(side="left", padx=6)

    App.page_printers = page_printers
    App._printer_page_final_installed = True
    return App
