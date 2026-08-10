"""Enhanced product visual controls: emoji/icon picker, gift label and POS badges."""
import os
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_NAME = "MK Pizza & Ice Bar"

EMOJIS = [
    "🍕", "🍔", "🍟", "🌭", "🌮", "🌯", "🍗", "🥪",
    "🥗", "🍝", "🍜", "🍣", "🍤", "🍩", "🍪", "🍰",
    "🧁", "🍦", "🍨", "☕", "🥤", "🧋", "🎁", "🎉",
    "⭐", "🔥", "❤️", "😊", "😋", "👍", "✨",
]

ICONS = [
    "★", "☆", "✓", "✔", "♥", "♡", "●", "◆", "■",
    "☕", "⚡", "♛", "➤", "✦", "✧", "❖", "🔥",
]


def install(App):
    if getattr(App, "_visuals_v2_installed", False):
        return App

    def init_visuals(self):
        self.s.c.execute("""
            CREATE TABLE IF NOT EXISTS product_media(
                product_id INTEGER PRIMARY KEY,
                image_path TEXT DEFAULT '',
                icon TEXT DEFAULT '',
                emoji TEXT DEFAULT '',
                is_gift INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT '',
                gift_label TEXT DEFAULT 'Gift'
            )
        """)
        try:
            self.s.q(
                "ALTER TABLE product_media ADD COLUMN gift_label TEXT DEFAULT 'Gift'"
            )
        except Exception:
            pass
        self.s.c.commit()

    def choose_symbol(self, title, choices, variable, parent):
        w = self.dialog(title, 540, 360)
        f = ttk.Frame(w, padding=12)
        f.pack(fill="both", expand=True)

        ttk.Label(
            f,
            text="Click a symbol or close the window to type your own.",
            foreground="#64748b",
        ).pack(anchor="w", pady=(0, 8))

        grid = ttk.Frame(f)
        grid.pack(fill="both", expand=True)

        for i, ch in enumerate(choices):
            ttk.Button(
                grid,
                text=ch,
                width=5,
                command=lambda x=ch: (variable.set(x), w.destroy()),
            ).grid(row=i // 8, column=i % 8, padx=3, pady=3)

        ttk.Button(
            f,
            text="CLEAR",
            command=lambda: (variable.set(""), w.destroy()),
        ).pack(fill="x", pady=8)

    def product_media_v2(self):
        init_visuals(self)
        p = self._selected_product() if hasattr(self, "_selected_product") else None
        if not p:
            messagebox.showwarning(
                "Product Visuals",
                "Select a product first.",
                parent=self,
            )
            return

        old = self.s.q(
            "SELECT * FROM product_media WHERE product_id=?",
            (p["id"],),
        ).fetchone()

        w = self.dialog("Product Visuals — " + p["name"], 650, 650)
        f = ttk.Frame(w, padding=16)
        f.pack(fill="both", expand=True)
        f.columnconfigure(1, weight=1)
        f.rowconfigure(2, weight=1)

        image_var = tk.StringVar(value=old["image_path"] if old else "")
        icon_var = tk.StringVar(value=old["icon"] if old else "")
        emoji_var = tk.StringVar(value=old["emoji"] if old else "")
        gift_var = tk.BooleanVar(value=bool(old["is_gift"]) if old else False)
        gift_label = tk.StringVar(
            value=(
                old["gift_label"]
                if old and "gift_label" in old.keys()
                else "Gift"
            )
        )

        ttk.Label(
            f,
            text=p["name"],
            font=("Segoe UI", 16, "bold"),
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 12))

        ttk.Label(f, text="Product Image").grid(
            row=1, column=0, sticky="w", pady=7
        )

        path_label = ttk.Label(
            f,
            text=os.path.basename(image_var.get()) if image_var.get() else "No image",
        )
        path_label.grid(row=1, column=2, sticky="w")

        preview = ttk.Label(f, text="IMAGE PREVIEW", anchor="center")
        preview.grid(
            row=2,
            column=0,
            columnspan=3,
            sticky="nsew",
            pady=8,
        )

        def preview_image(path):
            if not path or not os.path.exists(path):
                preview.configure(text="No image selected", image="")
                preview.image = None
                path_label.configure(text="No image")
                return

            try:
                from PIL import Image, ImageTk
                im = Image.open(path).convert("RGB")
                im.thumbnail((300, 220))
                photo = ImageTk.PhotoImage(im)
            except Exception:
                try:
                    photo = tk.PhotoImage(file=path)
                except Exception:
                    preview.configure(
                        text="Image selected (preview unavailable)",
                        image="",
                    )
                    preview.image = None
                    path_label.configure(text=os.path.basename(path))
                    return

            preview.configure(image=photo, text="")
            preview.image = photo
            path_label.configure(text=os.path.basename(path))

        def choose_image():
            path = filedialog.askopenfilename(
                parent=w,
                title="Choose Product Image",
                filetypes=[
                    ("Images", "*.png;*.jpg;*.jpeg;*.webp;*.gif;*.bmp"),
                    ("All files", "*.*"),
                ],
            )
            if not path:
                return

            root = os.environ.get("APPDATA") or os.path.expanduser("~")
            dest_dir = os.path.join(root, APP_NAME, "product_images")
            os.makedirs(dest_dir, exist_ok=True)

            ext = os.path.splitext(path)[1].lower() or ".png"
            dest = os.path.join(dest_dir, f"product_{p['id']}{ext}")

            try:
                shutil.copy2(path, dest)
                image_var.set(dest)
                preview_image(dest)
            except Exception as e:
                messagebox.showerror("Product Image", str(e), parent=w)

        ttk.Button(
            f,
            text="CHOOSE / CHANGE IMAGE",
            style="Primary.TButton",
            command=choose_image,
        ).grid(row=1, column=1, sticky="w")

        ttk.Button(
            f,
            text="REMOVE",
            command=lambda: (image_var.set(""), preview_image("")),
        ).grid(row=3, column=0, sticky="w", pady=4)

        ttk.Label(f, text="Emoji / Smiley").grid(
            row=4, column=0, sticky="w", pady=8
        )
        ttk.Entry(f, textvariable=emoji_var, width=12).grid(
            row=4, column=1, sticky="w"
        )
        ttk.Button(
            f,
            text="EMOJI 😊",
            command=lambda: self.choose_symbol(
                "Emoji / Smiley", EMOJIS, emoji_var, w
            ),
        ).grid(row=4, column=2, sticky="w", padx=5)

        ttk.Label(f, text="Icon / Badge").grid(
            row=5, column=0, sticky="w", pady=8
        )
        ttk.Entry(f, textvariable=icon_var, width=12).grid(
            row=5, column=1, sticky="w"
        )
        ttk.Button(
            f,
            text="ICON",
            command=lambda: self.choose_symbol(
                "Product Icon", ICONS, icon_var, w
            ),
        ).grid(row=5, column=2, sticky="w", padx=5)

        ttk.Checkbutton(
            f,
            text="🎁 Gift / Promotional Item",
            variable=gift_var,
        ).grid(row=6, column=0, columnspan=3, sticky="w", pady=8)

        ttk.Label(f, text="Gift label").grid(
            row=7, column=0, sticky="w", pady=6
        )
        ttk.Entry(
            f,
            textvariable=gift_label,
        ).grid(row=7, column=1, columnspan=2, sticky="ew")

        def save():
            from datetime import datetime

            self.s.q(
                """
                INSERT INTO product_media(
                    product_id, image_path, icon, emoji,
                    is_gift, updated_at, gift_label
                ) VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(product_id) DO UPDATE SET
                    image_path=excluded.image_path,
                    icon=excluded.icon,
                    emoji=excluded.emoji,
                    is_gift=excluded.is_gift,
                    updated_at=excluded.updated_at,
                    gift_label=excluded.gift_label
                """,
                (
                    p["id"],
                    image_var.get().strip(),
                    icon_var.get().strip(),
                    emoji_var.get().strip(),
                    1 if gift_var.get() else 0,
                    datetime.now().isoformat(timespec="seconds"),
                    gift_label.get().strip() or "Gift",
                ),
            )
            self.s.c.commit()

            if hasattr(self.s, "audit"):
                self.s.audit(
                    self.user,
                    "MEDIA_UPDATE",
                    "product",
                    p["id"],
                    f"image={bool(image_var.get())};emoji={emoji_var.get()};icon={icon_var.get()};gift={gift_var.get()}",
                )

            w.destroy()
            if hasattr(self, "load_products"):
                self.load_products()

        ttk.Button(
            f,
            text="SAVE PRODUCT VISUALS",
            style="Primary.TButton",
            command=save,
        ).grid(row=8, column=0, columnspan=3, sticky="ew", pady=16)

        preview_image(image_var.get())

    def wrap_pos_menu():
        original = getattr(App, "load_menu", None)
        if not original or getattr(App, "_visuals_menu_wrapped", False):
            return

        def load_menu(self):
            original(self)
            if not hasattr(self, "menu"):
                return

            init_visuals(self)

            for iid in self.menu.get_children():
                try:
                    product_id = int(iid)
                except (TypeError, ValueError):
                    continue

                r = self.s.q(
                    """
                    SELECT p.*,
                           COALESCE(m.emoji,'') AS emoji,
                           COALESCE(m.icon,'') AS icon,
                           COALESCE(m.is_gift,0) AS is_gift,
                           COALESCE(m.gift_label,'Gift') AS gift_label
                    FROM products p
                    LEFT JOIN product_media m ON m.product_id=p.id
                    WHERE p.id=?
                    """,
                    (product_id,),
                ).fetchone()

                if not r:
                    continue

                visual = f"{r['emoji']} {r['icon']}".strip()
                label = r["name"]
                if visual:
                    label = f"{visual} {label}"
                if r["is_gift"]:
                    label = f"🎁 {r['gift_label']} • {label}"

                vals = list(self.menu.item(iid, "values"))
                if vals:
                    vals[0] = label
                    self.menu.item(iid, values=vals)

        App.load_menu = load_menu
        App._visuals_menu_wrapped = True

    App.choose_symbol = choose_symbol
    App.product_media = product_media_v2
    wrap_pos_menu()
    App._visuals_v2_installed = True
    return App
