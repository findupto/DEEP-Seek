'''Product media, emoji/icon, gift badge and Windows application branding.

Adds real product artwork metadata without replacing catalog history.
Images are copied into the user's writable application-data directory so
installed/compiled builds do not depend on the original source path.
'''
import os
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    from PIL import Image, ImageTk
except Exception:
    Image = ImageTk = None

APP_NAME = 'MK Pizza & Ice Bar'


def install(App):
    if getattr(App, '_product_media_installed', False):
        return App

    def init_media(self):
        self.s.c.executescript('''
        CREATE TABLE IF NOT EXISTS product_media(
            product_id INTEGER PRIMARY KEY,
            image_path TEXT DEFAULT '',
            icon TEXT DEFAULT '',
            emoji TEXT DEFAULT '',
            is_gift INTEGER DEFAULT 0,
            updated_at TEXT DEFAULT ''
        );
        ''')
        self.s.c.commit()

    def media_dir(self):
        root = os.environ.get('APPDATA') or os.path.expanduser('~')
        path = os.path.join(root, APP_NAME, 'product_images')
        os.makedirs(path, exist_ok=True)
        return path

    def media_row(self, product_id):
        init_media(self)
        return self.s.q('SELECT * FROM product_media WHERE product_id=?', (product_id,)).fetchone()

    def selected_product_media(self):
        p = self._selected_product() if hasattr(self, '_selected_product') else None
        return p

    def product_media(self):
        init_media(self)
        p = selected_product_media(self)
        if not p:
            return
        old = media_row(self, p['id'])
        w = self.dialog('Product Images / Icons / Emoji / Gift', 620, 600)
        f = ttk.Frame(w, padding=16)
        f.pack(fill='both', expand=True)
        f.columnconfigure(1, weight=1)
        f.rowconfigure(3, weight=1)

        ttk.Label(f, text=p['name'], font=('Segoe UI', 16, 'bold')).grid(row=0, column=0, columnspan=3, sticky='w', pady=(0, 12))
        ttk.Label(f, text='Product Image').grid(row=1, column=0, sticky='w', pady=7)
        image_var = tk.StringVar(value=(old['image_path'] if old else ''))
        image_label = ttk.Label(f, text='No image selected')
        image_label.grid(row=2, column=0, columnspan=3, sticky='w', pady=(0, 8))
        preview = ttk.Label(f, text='IMAGE PREVIEW', anchor='center')
        preview.grid(row=3, column=0, columnspan=3, sticky='nsew', pady=8)

        def show_preview(path):
            if not path or not os.path.exists(path):
                preview.configure(text='No image selected', image='')
                preview.image = None
                image_label.configure(text='No image selected')
                return
            try:
                if Image and ImageTk:
                    im = Image.open(path).convert('RGB')
                    im.thumbnail((240, 180))
                    photo = ImageTk.PhotoImage(im)
                else:
                    photo = tk.PhotoImage(file=path)
                preview.configure(image=photo, text='')
                preview.image = photo
                image_label.configure(text=os.path.basename(path))
            except Exception:
                preview.configure(text='Image selected (preview unavailable)', image='')
                preview.image = None
                image_label.configure(text=os.path.basename(path))

        def choose_image():
            path = filedialog.askopenfilename(parent=w, title='Choose Product Image', filetypes=[
                ('Images', '*.png;*.jpg;*.jpeg;*.webp;*.gif;*.bmp'),
                ('PNG', '*.png'), ('JPEG', '*.jpg;*.jpeg'), ('All files', '*.*')])
            if not path:
                return
            ext = os.path.splitext(path)[1].lower() or '.png'
            dest = os.path.join(media_dir(self), f'product_{p["id"]}{ext}')
            try:
                if os.path.abspath(path) != os.path.abspath(dest):
                    shutil.copy2(path, dest)
                image_var.set(dest)
                show_preview(dest)
            except Exception as e:
                messagebox.showerror('Product Image', str(e), parent=w)

        def clear_image():
            image_var.set('')
            show_preview('')

        ttk.Button(f, text='CHOOSE IMAGE', command=choose_image).grid(row=1, column=1, sticky='w', padx=8)
        ttk.Button(f, text='REMOVE IMAGE', command=clear_image).grid(row=1, column=2, sticky='w')
        ttk.Label(f, text='Icon / Symbol').grid(row=4, column=0, sticky='w', pady=7)
        icon_var = tk.StringVar(value=(old['icon'] if old else ''))
        ttk.Entry(f, textvariable=icon_var, width=18).grid(row=4, column=1, sticky='ew', padx=8)
        ttk.Label(f, text='e.g. 🍕  🥤  🍔  🔥').grid(row=4, column=2, sticky='w')
        ttk.Label(f, text='Emoji').grid(row=5, column=0, sticky='w', pady=7)
        emoji_var = tk.StringVar(value=(old['emoji'] if old else ''))
        ttk.Entry(f, textvariable=emoji_var, width=18).grid(row=5, column=1, sticky='ew', padx=8)
        ttk.Label(f, text='Optional POS/menu emoji').grid(row=5, column=2, sticky='w')
        gift_var = tk.BooleanVar(value=bool(old['is_gift']) if old else False)
        ttk.Checkbutton(f, text='🎁 Mark this product as a Gift / Promotional Item', variable=gift_var).grid(row=6, column=0, columnspan=3, sticky='w', pady=10)
        ttk.Label(f, text='Images are copied into your user data folder and remain available after installing the EXE.', foreground='#64748b').grid(row=7, column=0, columnspan=3, sticky='w', pady=(4, 12))

        def save():
            from datetime import datetime
            self.s.q('''INSERT INTO product_media(product_id,image_path,icon,emoji,is_gift,updated_at)
                VALUES(?,?,?,?,?,?) ON CONFLICT(product_id) DO UPDATE SET
                image_path=excluded.image_path, icon=excluded.icon, emoji=excluded.emoji,
                is_gift=excluded.is_gift, updated_at=excluded.updated_at''',
                (p['id'], image_var.get().strip(), icon_var.get().strip(), emoji_var.get().strip(),
                 1 if gift_var.get() else 0, datetime.now().isoformat(timespec='seconds')))
            self.s.c.commit()
            self.s.audit(self.user, 'MEDIA_UPDATE', 'product', p['id'], f'image={bool(image_var.get().strip())}, gift={gift_var.get()}')
            w.destroy()
            if hasattr(self, 'load_products'):
                self.load_products()

        ttk.Button(f, text='SAVE MEDIA / ICON / GIFT', style='Primary.TButton', command=save).grid(row=8, column=0, columnspan=3, sticky='ew', pady=10)
        show_preview(image_var.get())

    def media_status(self):
        p = self._selected_product() if hasattr(self, '_selected_product') else None
        if not p:
            return
        r = media_row(self, p['id'])
        if not r:
            return messagebox.showinfo('Product Media', 'No image/icon/emoji/gift settings saved yet.', parent=self)
        image = 'Image' if r['image_path'] else 'No image'
        icon = r['icon'] or r['emoji'] or 'No icon/emoji'
        gift = '🎁 Gift' if r['is_gift'] else 'Normal'
        messagebox.showinfo('Product Media', f"{p['name']}\n\n{image}\nIcon/Emoji: {icon}\nType: {gift}", parent=self)

    # Defensive compatibility: the catalog page references these names.
    if not hasattr(App, 'product_delete'):
        def product_delete(self):
            p = self._selected_product() if hasattr(self, '_selected_product') else None
            if not p:
                return
            if not messagebox.askyesno('Archive Product', f"Archive '{p['name']}' from the active POS menu?\n\nOld sales/history will be preserved.", parent=self):
                return
            self.s.q('UPDATE products SET active=0 WHERE id=?', (p['id'],))
            self.s.c.commit()
            self.s.audit(self.user, 'ARCHIVE', 'product', p['id'], p['name'])
            self.load_products()
        App.product_delete = product_delete

    if not hasattr(App, 'product_delete_all'):
        def product_delete_all(self):
            n = self.s.q('SELECT COUNT(*) n FROM products WHERE active=1').fetchone()['n']
            if not n:
                return messagebox.showinfo('Menu', 'No active menu products.', parent=self)
            if not messagebox.askyesno('Archive Entire Menu', f'Archive all {n} active products?\n\nHistorical orders and product history remain intact.', parent=self):
                return
            self.s.q('UPDATE products SET active=0 WHERE active=1')
            self.s.c.commit()
            self.s.audit(self.user, 'ARCHIVE_ALL', 'product', None, f'{n} active products archived')
            self.load_products()
        App.product_delete_all = product_delete_all

    original_products = getattr(App, 'page_products', None)
    if original_products and not getattr(App, '_product_media_page_wrapped', False):
        def page_products(self):
            init_media(self)
            original_products(self)
            host = getattr(self, 'bodyinner', getattr(self, 'body', self))
            bar = ttk.Frame(host)
            children = host.winfo_children()
            if children:
                bar.pack(fill='x', pady=(0, 8), before=children[0])
            else:
                bar.pack(fill='x', pady=(0, 8))
            ttk.Button(bar, text='IMAGE / ICON / EMOJI / GIFT', style='Primary.TButton', command=self.product_media).pack(side='left')
            ttk.Button(bar, text='MEDIA STATUS', command=self.media_status).pack(side='left', padx=5)
            ttk.Label(bar, text='Select a product first.', foreground='#64748b').pack(side='left', padx=10)
        App.page_products = page_products
        App._product_media_page_wrapped = True

    App.product_media = product_media
    App.media_status = media_status
    App._product_media_installed = True
    return App
