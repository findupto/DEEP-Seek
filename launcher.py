"""Single canonical POS launcher.

Keeps the application compatible with Tk's Window.title() while the
POS pages use a two-argument title(text, subtitle) helper.
"""
import pos_app


def _install_title_compat():
    app_cls = pos_app.App
    page_header = getattr(app_cls, "title", None)
    if page_header is None or getattr(app_cls, "_title_compat_installed", False):
        return

    # App.title() currently serves as a page-header helper and accidentally
    # shadows tkinter.Tk.title(). During App.__init__, Tk calls self.title()
    # before self.body exists, causing the reported AttributeError. Preserve
    # the page helper while delegating the normal one-argument call to Tk.
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
