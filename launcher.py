"""Canonical enterprise POS launcher with deterministic feature integration."""
import os
import pos_app
from first_run_bootstrap import needs_first_run, reset_for_new_installation, mark_initialized
from persistent_data_patch import install as install_persistent_data
from advanced_features import install
from operational_patch import install as install_operational
from catalog_features import install as install_catalog
from catalog_helpers_patch import install as install_catalog_helpers
from catalog_runtime_final import install as install_catalog_runtime_final
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
from product_visual_ui_patch import install as install_product_visual_ui
from supplier_management_patch import install as install_supplier_management
from pos_stability_patch import install as install_pos_stability
from premium_ui_patch import install as install_premium_ui
from printer_page_final_patch import install as install_printer_page_final
from enterprise_hardening_patch import install as install_enterprise_hardening
from financial_integrity_patch import install as install_financial_integrity
from ultimate_pos_patch import install as install_ultimate_pos
from pos_completion_patch import install as install_pos_completion
from refund_fix_patch import install as install_refund_fix
from profit_notifications_patch import install as install_profit_notifications
from enterprise_accounting_patch import install as install_enterprise_accounting
from enterprise_controls_patch import install as install_enterprise_controls
from enterprise_pos_features_patch import install as install_enterprise_pos_features
from provider_runtime_patch import install as install_provider_runtime
from provider_worker_patch import install as install_provider_worker
from provider_admin_ui_patch import install as install_provider_admin_ui
from enterprise_completion_patch import install as install_enterprise_completion
import enterprise_completion_compat
from enterprise_services import install as install_enterprise_services
from financial_bridge_patch import install as install_financial_bridge
from financial_live_triggers_patch import install as install_financial_live_triggers
from database_reset_patch import install as install_database_reset
from fresh_database_patch import install as install_fresh_database
from luxury_theme_patch import install as install_luxury_theme
from enterprise_transaction_guard import install as install_enterprise_transaction_guard

# Never let a packaged development/test database become the database of a new
# installation. This executes only before any Store/UI construction. Once the
# installation marker exists, the application will never silently reset data.
try:
    first_run = needs_first_run(pos_app.DB)
    if first_run:
        reset_for_new_installation(pos_app.DB)
except Exception:
    first_run = False

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
install_catalog_runtime_final(pos_app.App)
install_product_visual_ui(pos_app.App)
install_pos_stability(pos_app.App, pos_app.Store, pos_app.Login)
if os.name == 'nt' or os.environ.get('DISPLAY'):
    install_premium_ui(pos_app.App, pos_app.Login)
install_printer_page_final(pos_app.App)
install_enterprise_hardening(pos_app.App, pos_app.Login)
install_financial_integrity(pos_app.App)
install_ultimate_pos(pos_app.App, pos_app.Login)
install_pos_completion(pos_app.App)
install_refund_fix(pos_app.App)
install_profit_notifications(pos_app.App)
install_enterprise_accounting(pos_app.App)
install_enterprise_controls(pos_app.App)
install_enterprise_pos_features(pos_app.App)
install_provider_runtime(pos_app.App)
install_provider_worker(pos_app.App)
install_provider_admin_ui(pos_app.App)
install_enterprise_completion(pos_app.App)
install_enterprise_services(pos_app.App)
install_financial_bridge(pos_app.App)
install_financial_live_triggers(pos_app.App)
install_database_reset(pos_app.App)
install_fresh_database(pos_app.App)
install_luxury_theme(pos_app.App)
install_enterprise_transaction_guard(pos_app.App)

# The Store constructor creates the schema/default system records. The marker
# is written only after that initialization path succeeds, so a fresh install
# is then permanently recognized as initialized on subsequent launches.
if first_run:
    try:
        probe = pos_app.Store(pos_app.DB)
        probe.c.close()
        mark_initialized(pos_app.DB)
    except Exception:
        # Do not mark an incomplete installation as initialized.
        pass

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
