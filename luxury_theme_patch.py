"""Refined, low-motion visual system for the POS.
Uses a soft neutral workspace, deep navy navigation and restrained metallic-gold accents.
"""
import tkinter as tk
from tkinter import ttk


def install(App):
    if getattr(App, "_luxury_theme_installed", False):
        return App
    style=ttk.Style()
    try: style.theme_use("clam")
    except tk.TclError: pass
    bg="#f5f2ec"; surface="#fffdf9"; navy="#0d1b2a"; navy2="#15283d"; ink="#18212b"; muted="#66717d"; gold="#b08a45"; gold2="#8f6e35"; line="#ddd5c8"
    style.configure("TFrame",background=bg)
    style.configure("TLabel",background=bg,foreground=ink,font=("Segoe UI",10))
    style.configure("Title.TLabel",background=bg,foreground=navy,font=("Georgia",24,"bold"))
    style.configure("TButton",background=surface,foreground=ink,font=("Segoe UI",9,"bold"),padding=(12,8),borderwidth=1,relief="solid")
    style.map("TButton",background=[("active", "#eee8dd")])
    style.configure("Primary.TButton",background=navy,foreground="#ffffff",font=("Segoe UI",9,"bold"),padding=(13,9))
    style.map("Primary.TButton",background=[("active",navy2)])
    style.configure("Success.TButton",background=gold,foreground="#ffffff",font=("Segoe UI",9,"bold"),padding=(12,9))
    style.map("Success.TButton",background=[("active",gold2)])
    style.configure("Danger.TButton",background="#6e2d2d",foreground="#ffffff",font=("Segoe UI",9,"bold"),padding=(12,8))
    style.map("Danger.TButton",background=[("active", "#572424")])
    style.configure("Soft.TButton",background="#ebe5da",foreground=navy,font=("Segoe UI",9,"bold"),padding=(11,8))
    style.map("Soft.TButton",background=[("active", "#e0d7c8")])
    style.configure("TLabelframe",background=surface,relief="solid",borderwidth=1)
    style.configure("TLabelframe.Label",background=surface,foreground=navy,font=("Segoe UI",10,"bold"))
    style.configure("Treeview",background=surface,fieldbackground=surface,foreground=ink,rowheight=32,font=("Segoe UI",10),borderwidth=0)
    style.configure("Treeview.Heading",background="#e8e0d2",foreground=navy,font=("Segoe UI",9,"bold"),padding=(8,8))
    style.map("Treeview",background=[("selected", "#eadfca")],foreground=[("selected",navy)])
    style.configure("TEntry",padding=7,fieldbackground=surface)
    style.configure("TCombobox",padding=6,fieldbackground=surface)
    style.configure("TCheckbutton",background=bg,foreground=ink)

    old_build=App.build_shell
    def build_shell(self):
        old_build(self)
        try:
            self.configure(bg=bg)
            self.side.configure(bg=navy)
            for b in getattr(self,"navbuttons",{}).values():
                b.configure(bg=navy,fg="#f6f0e6",activebackground=gold,activeforeground="#ffffff",font=("Segoe UI",10,"bold"),padx=18,pady=10,cursor="hand2")
            self.bodyhost.configure(style="TFrame")
            self.body.canvas.configure(bg=bg)
        except Exception: pass
    App.build_shell=build_shell
    App._luxury_theme_installed=True
    return App
