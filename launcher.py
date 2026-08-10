"""Single canonical POS launcher with functional feature integrations."""
import pos_app
from advanced_features import install
from operational_patch import install as install_operational
from catalog_features import install as install_catalog
from printer_reconnect_patch import install as install_printer_reconnect
from ui_shell import install as install_shell
from printer_manager import PrinterManager
from final_ui_patch import install_printer, install_ui
from canonical_ui_patch import install as install_canonical_ui

# Install data/workflow features first, then install exactly one final UI shell.
# The legacy ui_responsive_patch is intentionally not loaded: it expects
# App.build(), which the canonical application does not expose.
install(pos_app.App)
install_operational(pos_app.App)
install_catalog(pos_app.App)
install_printer_reconnect(PrinterManager)
install_shell(pos_app.App)
install_printer(__import__('printer_manager'))
install_ui(pos_app.App)
install_canonical_ui(pos_app.App)


def _install_title_compat():
    app_cls = pos_app.App
    page_header = getattr(app_cls, 'title', None)
    if page_header is None or getattr(app_cls, '_title_compat_installed', False):
        return
    tk_title = __import__('tkinter').Tk.title
    def title(self, text='', subtitle=None):
        if subtitle is None:
            return tk_title(self, text)
        return page_header(self, text, subtitle)
    app_cls.title = title
    app_cls._title_compat_installed = True

_install_title_compat()


def main():
    pos_app.main()


if __name__ == '__main__':
    main()
