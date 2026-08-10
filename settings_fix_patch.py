"""Small compatibility fix for Settings persistence.

The original Settings page accidentally passed Tk StringVar objects to sqlite.
This replacement keeps the same UI but writes plain string values.
"""
import tkinter as tk
from tkinter import ttk, messagebox


def install(App):
    def page_settings(self):
        self.title("Settings", "Business configuration, database backup and local preferences.")
        f = ttk.LabelFrame(self.bodyinner, text="Business", padding=16)
        f.pack(fill="x")
        variables = {}
        for key in ("name", "address", "phone", "currency"):
            ttk.Label(f, text=key.title()).pack(anchor="w")
            variables[key] = tk.StringVar(value=BUSINESS.get(key, ""))
            ttk.Entry(f, textvariable=variables[key]).pack(fill="x", pady=3)

        def save():
            values = {key: var.get() for key, var in variables.items()}
            BUSINESS.update(values)
            for key, value in values.items():
                self.s.q("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, value))
            self.s.c.commit()
            messagebox.showinfo("Settings", "Saved.", parent=self)

        ttk.Button(f, text="SAVE SETTINGS", style="Primary.TButton", command=save).pack(fill="x", pady=12)
        b = ttk.LabelFrame(self.bodyinner, text="Backup", padding=16)
        b.pack(fill="x", pady=12)
        ttk.Button(b, text="BACKUP DATABASE", command=self.backup).pack(anchor="w")

    # BUSINESS is defined in pos_app; resolve it through the App module globals.
    global BUSINESS
    try:
        BUSINESS = __import__("pos_app").BUSINESS
    except Exception:
        BUSINESS = {}
    App.page_settings = page_settings
    return App
