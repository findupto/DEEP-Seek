"""Expose saved product artwork in the Products/Menu catalog without changing data."""
from tkinter import ttk


def install(App):
    if getattr(App, "_product_visual_ui_patch", False):
        return App

    def decorate(self):
        tree = getattr(self, "pr", None)
        if tree is None:
            return
        try:
            cols = list(tree["columns"])
            if "visual" not in cols:
                tree["columns"] = tuple(cols + ["visual"])
                tree.heading("visual", text="Visual")
                tree.column("visual", width=180, minwidth=100, anchor="w")
            for iid in tree.get_children():
                try:
                    pid = int(iid)
                    m = self.s.q("SELECT image_path,icon,emoji,is_gift,gift_label FROM product_media WHERE product_id=?", (pid,)).fetchone()
                    if not m:
                        visual = ""
                    else:
                        bits = []
                        if m["emoji"]: bits.append(m["emoji"])
                        if m["icon"]: bits.append(m["icon"])
                        if m["is_gift"]: bits.append("🎁 " + (m["gift_label"] or "Gift"))
                        if m["image_path"]: bits.append("📷 Image")
                        visual = " ".join(bits)
                    values = list(tree.item(iid, "values"))
                    if len(values) < len(cols) + 1:
                        values.append(visual)
                    else:
                        values[-1] = visual
                    tree.item(iid, values=values)
                except Exception:
                    pass
        except Exception:
            pass

    original_page = getattr(App, "page_products", None)
    original_load = getattr(App, "load_products", None)
    original_load_all = getattr(App, "load_products_all", None)

    if original_page and not getattr(App, "_visual_page_wrapped", False):
        def page_products(self):
            original_page(self)
            decorate(self)
        App.page_products = page_products
        App._visual_page_wrapped = True

    if original_load and not getattr(App, "_visual_load_wrapped", False):
        def load_products(self, *args, **kwargs):
            result = original_load(self, *args, **kwargs)
            decorate(self)
            return result
        App.load_products = load_products
        App._visual_load_wrapped = True

    if original_load_all and not getattr(App, "_visual_load_all_wrapped", False):
        def load_products_all(self, *args, **kwargs):
            result = original_load_all(self, *args, **kwargs)
            decorate(self)
            return result
        App.load_products_all = load_products_all
        App._visual_load_all_wrapped = True

    App._product_visual_ui_patch = True
    return App
