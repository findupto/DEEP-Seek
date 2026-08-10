"""Single canonical POS launcher with operational feature integration."""
import pos_app
from advanced_features import install

install(pos_app.App)


def _install_title_compat():
    app_cls = pos_app.App
    page_header = getattr(app_cls, "title", None)
    if page_header is None or getattr(app_cls, "_title_compat_installed", False):
        return
    tk_title = __import__("tkinter").Tk.title
    def title(self, text="", subtitle=None):
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
