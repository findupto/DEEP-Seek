"""Prevent asynchronous printer callbacks from touching destroyed settings windows."""


def install(PrinterSettings):
    if getattr(PrinterSettings, "_ui_safety_patch", False):
        return PrinterSettings

    def safe_reconnect_done(self, ok, err):
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        try:
            self.status.config(
                text="Reconnected to saved printer" if ok else "Reconnect failed"
            )
        except Exception:
            return

        if not ok:
            try:
                from tkinter import messagebox
                messagebox.showerror(
                    "Printer",
                    err or "Saved printer could not be reconnected.",
                    parent=self,
                )
            except Exception:
                pass

    def safe_discover(self):
        try:
            if not self.winfo_exists():
                return
            self.status.config(
                text="Discovering COM, Windows printers and Bluetooth LE devices..."
            )
        except Exception:
            return

        self._rows = []

        def done(rows, ok):
            def ui():
                try:
                    if not self.winfo_exists():
                        return
                    self.tree.delete(*self.tree.get_children())
                    self._rows = rows
                    for i, r in enumerate(rows):
                        self.tree.insert(
                            "",
                            "end",
                            iid=str(i),
                            values=(
                                r.get("name", ""),
                                r.get("type", ""),
                                r.get("address") or r.get("port", ""),
                                r.get("details", ""),
                            ),
                        )
                    self.status.config(text=f"{len(rows)} devices found")
                except Exception:
                    pass

            try:
                self.after(0, ui)
            except Exception:
                pass

        try:
            self.m.discover(done)
        except Exception as e:
            try:
                self.status.config(text=f"Discovery failed: {e}")
            except Exception:
                pass

    PrinterSettings._reconnect_done = safe_reconnect_done
    PrinterSettings.discover = safe_discover
    PrinterSettings._ui_safety_patch = True
    return PrinterSettings
