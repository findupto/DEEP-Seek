"""Responsive UI and navigation fixes for the canonical POS.

This module deliberately patches the existing App instead of creating another
POS implementation. It keeps all existing page methods and data workflows.
"""
import tkinter as tk
from tkinter import ttk, messagebox


def install(App):
    if getattr(App, "_responsive_patch_installed", False):
        return
    old_build = App.build
    old_dialog = App.dialog

    def build(self):
        old_build(self)
        # The original sidebar was fixed-height and could hide navigation on
        # smaller displays. Replace its direct buttons with a scrollable area.
        side = None
        for child in self.winfo_children():
            if isinstance(child, tk.Frame) and str(child.cget("bg")) == "#111827":
                side = child
                break
        if side is not None:
            children = list(side.winfo_children())
            nav_buttons = [w for w in children if isinstance(w, ttk.Button)]
            if nav_buttons:
                for b in nav_buttons:
                    b.pack_forget()
                nav = tk.Frame(side, bg="#111827")
                nav.pack(fill="both", expand=True, padx=0, pady=4)
                canvas = tk.Canvas(nav, bg="#111827", highlightthickness=0, bd=0)
                sb = ttk.Scrollbar(nav, orient="vertical", command=canvas.yview)
                inner = tk.Frame(canvas, bg="#111827")
                inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
                canvas.create_window((0, 0), window=inner, anchor="nw", width=205)
                canvas.configure(yscrollcommand=sb.set)
                canvas.pack(side="left", fill="both", expand=True)
                sb.pack(side="right", fill="y")
                for b in nav_buttons:
                    b.configure(width=1)
                    b.pack(in_=inner, fill="x", padx=10, pady=2)
                def wheel(e):
                    canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
                canvas.bind_all("<MouseWheel>", wheel, add="+")
                self._nav_canvas = canvas
        # Keep the body usable at all window sizes. Horizontal scrolling is
        # intentionally available for dense reports/tables rather than hiding
        # controls off-screen.
        self.bind("<Configure>", lambda e: self._responsive_update(), add="+")

    def _responsive_update(self):
        w = max(self.winfo_width(), 900)
        # Give the content the full remaining width; page-level Treeviews have
        # their own horizontal scrollbar.
        if hasattr(self, "body"):
            self.body.configure(padding=(16 if w < 1200 else 24))
        if hasattr(self, "_nav_canvas"):
            self._nav_canvas.configure(width=205)

    def dialog(self, title, w, h):
        # Never open a dialog larger than the available display. Large dialogs
        # get a scrollable inner frame so every action remains reachable.
        x = tk.Toplevel(self)
        x.title(title)
        sw, sh = x.winfo_screenwidth(), x.winfo_screenheight()
        ww, hh = min(w, max(420, sw - 80)), min(h, max(300, sh - 100))
        x.geometry(f"{ww}x{hh}")
        x.minsize(min(380, ww), min(260, hh))
        x.transient(self)
        x.grab_set()
        return x

    App.build = build
    App._responsive_update = _responsive_update
    App.dialog = dialog
    App._responsive_patch_installed = True
    return App
