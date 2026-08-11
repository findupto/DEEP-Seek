"""Refined low-motion visual system for the POS.
Dark obsidian workspace, deep navy navigation, muted neutrals and restrained metallic-gold/cyan accents.
"""
import tkinter as tk
from tkinter import ttk


def install(App):
    if getattr(App, "_luxury_theme_installed", False):
        return App
    style=ttk.Style()
    try: style.theme_use("clam")
    except tk.TclError: pass
    bg="#090d18"; surface="#111827"; surface2="#172033"; navy="#0b1220"; navy2="#16243a"; ink="#e7e5e4"; muted="#94a3b8"; gold="#c8a45d"; gold2="#a88647"; cyan="#22d3ee"; purple="#8b5cf6"; line="#273449"
    style.configure("TFrame",background=bg)
    style.configure("TLabel",background=bg,foreground=ink,font=("Segoe UI",10))
    style.configure("Title.TLabel",background=bg,foreground="#fafaf9",font=("Georgia",24,"bold"))
    style.configure("TButton",background=surface2,foreground=ink,font=("Segoe UI",9,"bold"),padding=(12,8),borderwidth=1,relief="solid")
    style.map("TButton",background=[("active", "#25324a")],foreground=[("active", "#ffffff")])
    style.configure("Primary.TButton",background=navy2,foreground="#ffffff",font=("Segoe UI",9,"bold"),padding=(13,9),borderwidth=1)
    style.map("Primary.TButton",background=[("active",purple)])
    style.configure("Success.TButton",background=gold,foreground="#101010",font=("Segoe UI",9,"bold"),padding=(12,9),borderwidth=0)
    style.map("Success.TButton",background=[("active",gold2)])
    style.configure("Danger.TButton",background="#7f1d1d",foreground="#ffffff",font=("Segoe UI",9,"bold"),padding=(12,8),borderwidth=0)
    style.map("Danger.TButton",background=[("active", "#991b1b")])
    style.configure("Soft.TButton",background="#1c2738",foreground="#dbeafe",font=("Segoe UI",9,"bold"),padding=(11,8),borderwidth=0)
    style.map("Soft.TButton",background=[("active", "#263650")])
    style.configure("TLabelframe",background=surface,foreground=ink,relief="solid",borderwidth=1)
    style.configure("TLabelframe.Label",background=surface,foreground=cyan,font=("Segoe UI",10,"bold"))
    style.configure("Treeview",background="#0f172a",fieldbackground="#0f172a",foreground=ink,rowheight=32,font=("Segoe UI",10),borderwidth=0)
    style.configure("Treeview.Heading",background="#1b2638",foreground="#cbd5e1",font=("Segoe UI",9,"bold"),padding=(8,8))
    style.map("Treeview",background=[("selected", "#3b2a68")],foreground=[("selected","#ffffff")])
    style.configure("TEntry",padding=7,fieldbackground="#0f172a",foreground=ink,insertcolor=cyan)
    style.configure("TCombobox",padding=6,fieldbackground="#0f172a",foreground=ink)
    style.configure("TCheckbutton",background=bg,foreground=ink)
    style.configure("TRadiobutton",background=bg,foreground=ink)

    old_build=App.build_shell
    def build_shell(self):
        old_build(self)
        try:
            self.configure(bg=bg)
            self.side.configure(bg=navy)
            self.bodyhost.configure(style="TFrame")
            self.body.canvas.configure(bg=bg)
            for b in getattr(self,"navbuttons",{}).values():
                b.configure(bg=navy,fg="#f6f0e6",activebackground=gold,activeforeground="#101010",font=("Segoe UI",10,"bold"),padx=18,pady=10,cursor="hand2")
        except Exception: pass
    App.build_shell=build_shell
    App._luxury_theme_installed=True
    return App
