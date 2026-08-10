"""MK Pizza & Ice Bar Windows application icon integration."""
import os
import sys
import tkinter as tk

ICON_NAME = 'mk_pizza.ico'


def _asset_path():
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, 'assets', ICON_NAME)


def install(App):
    if getattr(App, '_mk_icon_installed', False):
        return App

    original_init = App.__init__

    def init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        path = _asset_path()
        if os.path.exists(path):
            try:
                self.iconbitmap(path)
                self._mk_icon_path = path
            except tk.TclError:
                pass

    App.__init__ = init
    App._mk_icon_installed = True
    return App
