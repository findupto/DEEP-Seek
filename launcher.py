"""Single canonical POS launcher with functional feature integrations."""
import pos_app
from persistent_data_patch import install as install_persistent_data
from advanced_features import install
from operational_patch import install as install_operational
from catalog_features import install as install_catalog
from catalog_helpers_patch import install as install_catalog_helpers
from catalog_runtime_fix import install as install_catalog_runtime_fix
from product_media_patch import install as install_product_media
from printer_reconnect_patch import install as install_printer_reconnect
from printer_ui_safety_patch import install as install_printer_ui_safety
from settings_fix_patch import install as install_settings_fix
from ui_shell import install as install_shell
from printer_manager import PrinterManager, PrinterSettings
from final_ui_patch import install_printer, install_ui
from canonical_ui_patch import install as install_canonical_ui
from app_icon_patch import install as install_app_icon
from product_visuals_patch import install as install_product_visuals
from supplier_management_patch import install as install_supplier_management

install_persistent_data(pos_app)
install(pos_app.App)
install_operational(pos_app.App)
install_catalog(pos_app.App)
install_catalog_helpers(pos_app.App)
install_supplier_management(pos_app.App)
install_product_media(pos_app.App)
install_printer_reconnect(PrinterManager)
install_printer_ui_safety(PrinterSettings)
install_settings_fix(pos_app.App)
install_shell(pos_app.App)
install_printer(__import__('printer_manager'))
install_ui(pos_app.App)
install_canonical_ui(pos_app.App)
install_app_icon(pos_app.App)
install_product_visuals(pos_app.App)
# Products/Menu runtime is deliberately the final App-page layer.
# It provides its own controller registration so older feature patches cannot
# leave page callbacks pointing at missing methods such as bulk_center.
install_catalog_runtime_fix(pos_app.App)

# Last-resort compatibility aliases. These do not alter database data and make
# old callers using either bulk_center spelling resolve to the same controller.
if hasattr(pos_app.App, "bulk_menu_center") and not hasattr(pos_app.App, "bulk_center"):
    pos_app.App.bulk_center = pos_app.App.bulk_menu_center
elif hasattr(pos_app.App, "bulk_center") and not hasattr(pos_app.App, "bulk_menu_center"):
    pos_app.App.bulk_menu_center = pos_app.App.bulk_center


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
