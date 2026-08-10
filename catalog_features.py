"""Functional product/menu/catalog UI extension.

Provides real CRUD, product history, category/modifier management and CSV
bulk import/export. Destructive operations preserve sales history by
archiving/deactivating products rather than deleting historical sale rows.
"""
import csv, sqlite3, tkinter as tk
from tkinter import ttk, messagebox, filedialog


def install(App):
    old = App.page_products

    def init_catalog(self):
        self.s.c.executescript('''
        CREATE TABLE IF NOT EXISTS product_categories(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE NOT NULL,active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS product_modifiers(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE NOT NULL,active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS product_modifier_items(id INTEGER PRIMARY KEY AUTOINCREMENT,modifier_id INTEGER NOT NULL,name TEXT NOT NULL,price_delta REAL DEFAULT 0,active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS combo_items(id INTEGER PRIMARY KEY AUTOINCREMENT,product_id INTEGER NOT NULL,component_product_id INTEGER NOT NULL,quantity REAL NOT NULL DEFAULT 1);
        ''')
        self.s.c.commit()

    def page_products(self):
        init_catalog(self)
        self.title('Products & Menu', 'Complete menu catalog: add, edit, history, archive, bulk import and bulk export.')

        bar = ttk.Frame(self.body)
        bar.pack(fill='x', pady=8)
        ttk.Button(bar, text='ADD PRODUCT', style='Primary.TButton', command=lambda: self.catalog_edit()).pack(side='left')
        ttk.Button(bar, text='EDIT SELECTED', command=lambda: self.catalog_edit()).pack(side='left', padx=4)
        ttk.Button(bar, text='VIEW HISTORY', command=self.catalog_history).pack(side='left', padx=4)
        ttk.Button(bar, text='DELETE / ARCHIVE', command=self.product_delete).pack(side='left', padx=4)
        ttk.Button(bar, text='DELETE ALL MENU', command=self.product_delete_all).pack(side='left', padx=4)
        ttk.Button(bar, text='MODIFIERS', command=self.modifiers).pack(side='left', padx=4)
        ttk.Button(bar, text='CATEGORIES', command=self.categories).pack(side='left', padx=4)

        bulk = ttk.Frame(self.body)
        bulk.pack(fill='x', pady=(0, 8))
        ttk.Button(bulk, text='UPLOAD MENU CSV', style='Primary.TButton', command=self.product_import).pack(side='left')
        ttk.Button(bulk, text='DOWNLOAD MENU CSV', command=self.product_export).pack(side='left', padx=5)
        ttk.Button(bulk, text='DOWNLOAD CSV TEMPLATE', command=self.product_template).pack(side='left')
        ttk.Label(bulk, text='CSV columns: name, category, price, cost, stock, barcode, active', foreground='#64748b').pack(side='left', padx=12)

        filterbar = ttk.Frame(self.body)
        filterbar.pack(fill='x', pady=(0, 8))
        self.cat_filter = tk.StringVar(value='All')
        self.prod_filter = tk.StringVar()
        ttk.Label(filterbar, text='Category').pack(side='left')
        cats = ['All'] + [r['name'] for r in self.s.rows('SELECT name FROM product_categories WHERE active=1 ORDER BY name')]
        ttk.Combobox(filterbar, textvariable=self.cat_filter, values=cats, state='readonly', width=20).pack(side='left', padx=5)
        ttk.Label(filterbar, text='Search').pack(side='left', padx=(15, 3))
        e = ttk.Entry(filterbar, textvariable=self.prod_filter)
        e.pack(side='left', fill='x', expand=True)
        e.bind('<KeyRelease>', lambda _: self.load_products())
        ttk.Button(filterbar, text='SHOW ALL / ARCHIVED', command=self.load_products_all).pack(side='left', padx=5)

        self.pr = self.table(self.body, ('id','name','category','price','cost','stock','barcode','active'),
            {'id':'ID','name':'Product / Menu Item','category':'Category','price':'Sale Price','cost':'Cost','stock':'Stock','barcode':'Barcode','active':'POS Menu'}, 18)
        self.pr.bind('<Double-1>', lambda _e: self.catalog_history())
        self.pr.bind('<Return>', lambda _e: self.catalog_history())
        self.load_products()

    def load_products(self):
        self._load_products(False)

    def load_products_all(self):
        self._load_products(True)

    def _load_products(self, include_archived=False):
        if not hasattr(self, 'pr'):
            return
        for x in self.pr.get_children():
            self.pr.delete(x)
        q = 'SELECT * FROM products WHERE 1=1'
        a = []
        if not include_archived:
            q += ' AND active=1'
        z = getattr(self, 'prod_filter', tk.StringVar()).get().strip().lower()
        cat = getattr(self, 'cat_filter', tk.StringVar(value='All')).get()
        if z:
            q += ' AND lower(name||" "||category||" "||barcode) LIKE ?'
            a.append('%' + z + '%')
        if cat and cat != 'All':
            q += ' AND category=?'
            a.append(cat)
        q += ' ORDER BY active DESC, category, name'
        for r in self.s.rows(q, tuple(a)):
            self.pr.insert('', 'end', iid=str(r['id']), values=(
                r['id'], r['name'], r['category'], f"{r['price']:.2f}",
                f"{r['cost']:.2f}", r['stock'], r['barcode'], 'Yes' if r['active'] else 'Archived'))

    def _selected_product(self):
        sel = self.pr.selection() if hasattr(self, 'pr') else ()
        if not sel:
            messagebox.showwarning('Product', 'Select a product first.', parent=self)
            return None
        return self.s.q('SELECT * FROM products WHERE id=?', (int(sel[0]),)).fetchone()

    def catalog_edit(self):
        init_catalog(self)
        old = self._selected_product() if hasattr(self, 'pr') and self.pr.selection() else None
        w = self.dialog('Product / Menu Item', 560, 620)
        f = ttk.Frame(w, padding=18)
        f.pack(fill='both', expand=True)
        v = {}
        fields = [
            ('name','Name',str(old['name']) if old else ''),
            ('category','Category',str(old['category']) if old else 'General'),
            ('price','Sale Price',str(old['price']) if old else ''),
            ('cost','Cost',str(old['cost']) if old else '0'),
            ('stock','Opening / Current Stock',str(old['stock']) if old else '0'),
            ('barcode','Barcode / SKU',str(old['barcode']) if old else '')]
        for k, label, val in fields:
            ttk.Label(f, text=label).pack(anchor='w', pady=(7,2))
            v[k] = tk.StringVar(value=val)
            ttk.Entry(f, textvariable=v[k]).pack(fill='x')
        ttk.Label(f, text='Menu visibility').pack(anchor='w', pady=(10,2))
        menu = tk.BooleanVar(value=bool(old['active']) if old else True)
        ttk.Checkbutton(f, text='Available in POS menu', variable=menu).pack(anchor='w')

        def save():
            try:
                name = v['name'].get().strip()
                cat = v['category'].get().strip() or 'General'
                price = float(v['price'].get())
                cost = float(v['cost'].get() or 0)
                stock = float(v['stock'].get() or 0)
                barcode = v['barcode'].get().strip()
                if not name or price < 0 or cost < 0 or stock < 0:
                    raise ValueError('Name is required and numeric values cannot be negative.')
                self.s.q('INSERT OR IGNORE INTO product_categories(name) VALUES(?)', (cat,))
                active = 1 if menu.get() else 0
                if old:
                    self.s.q('UPDATE products SET name=?,category=?,price=?,cost=?,stock=?,barcode=?,active=? WHERE id=?',
                             (name,cat,price,cost,stock,barcode,active,old['id']))
                    pid = old['id']
                    action = 'UPDATE'
                else:
                    cur = self.s.q('INSERT INTO products(name,category,price,cost,stock,barcode,active) VALUES(?,?,?,?,?,?,?)',
                                   (name,cat,price,cost,stock,barcode,active))
                    pid = cur.lastrowid
                    action = 'CREATE'
                    if stock:
                        self.s.q('INSERT INTO stock_movements(product_id,qty,movement_type,note,created_at,user_id) VALUES(?,?,?,?,?,?)',
                                 (pid,stock,'Opening Stock','Product creation',self._now_catalog(),self.user['id']))
                self.s.c.commit()
                self.s.audit(self.user, action, 'product', pid, name)
                w.destroy()
                self.show('Products')
            except Exception as e:
                messagebox.showerror('Product', str(e), parent=w)
        ttk.Button(f, text='SAVE PRODUCT', style='Primary.TButton', command=save).pack(fill='x', pady=18)

    def _now_catalog(self):
        from datetime import datetime
        return datetime.now().isoformat(timespec='seconds')

    def product_delete(self):
        p = self._selected_product()
        if not p:
            return
        if not messagebox.askyesno('Archive Product',
            f"Archive '{p['name']}' from the POS menu?\n\nSales and history will be preserved.", parent=self):
            return
        self.s.q('UPDATE products SET active=0 WHERE id=?', (p['id'],))
        self.s.c.commit()
        self.s.audit(self.user, 'ARCHIVE', 'product', p['id'], p['name'])
        self.load_products()

    def product_delete_all(self):
        row = self.s.q('SELECT COUNT(*) n FROM products WHERE active=1').fetchone()
        count = int(row['n'])
        if count == 0:
            return messagebox.showinfo('Menu', 'There are no active menu products.', parent=self)
        if not messagebox.askyesno('DELETE ALL MENU',
            f"Archive ALL {count} active menu products?\n\nThis removes them from POS immediately but preserves old orders, sales and product history.", parent=self):
            return
        self.s.q('UPDATE products SET active=0 WHERE active=1')
        self.s.c.commit()
        self.s.audit(self.user, 'ARCHIVE_ALL', 'product', None, f'{count} products archived')
        self.load_products()
        messagebox.showinfo('Menu', f'{count} products were removed from the active POS menu. History was preserved.', parent=self)

    def product_import(self):
        path = filedialog.askopenfilename(parent=self, title='Upload Menu CSV', filetypes=[('CSV files','*.csv'),('All files','*.*')])
        if not path:
            return
        created = updated = skipped = 0
        errors = []
        try:
            with open(path, 'r', encoding='utf-8-sig', newline='') as fh:
                reader = csv.DictReader(fh)
                required = {'name','price'}
                headers = {str(x or '').strip().lower() for x in (reader.fieldnames or [])}
                if not required.issubset(headers):
                    raise ValueError('CSV must contain at least: name, price. Optional: category, cost, stock, barcode, active.')
                for line_no, raw in enumerate(reader, start=2):
                    try:
                        row = {str(k or '').strip().lower(): (str(v).strip() if v is not None else '') for k,v in raw.items()}
                        name = row.get('name','').strip()
                        if not name:
                            skipped += 1; errors.append(f'Line {line_no}: missing name'); continue
                        price = float(row.get('price','0') or 0)
                        cost = float(row.get('cost','0') or 0)
                        stock = float(row.get('stock','0') or 0)
                        category = row.get('category','General').strip() or 'General'
                        barcode = row.get('barcode','').strip()
                        active = 0 if row.get('active','1').strip().lower() in ('0','no','false','off','archived') else 1
                        if price < 0 or cost < 0 or stock < 0:
                            raise ValueError('negative numeric value')
                        self.s.q('INSERT OR IGNORE INTO product_categories(name) VALUES(?)', (category,))
                        existing = None
                        if barcode:
                            existing = self.s.q('SELECT id FROM products WHERE barcode=? AND barcode<>"" LIMIT 1', (barcode,)).fetchone()
                        if not existing:
                            existing = self.s.q('SELECT id FROM products WHERE lower(name)=lower(?) LIMIT 1', (name,)).fetchone()
                        if existing:
                            pid = existing['id']
                            self.s.q('UPDATE products SET name=?,category=?,price=?,cost=?,stock=?,barcode=?,active=? WHERE id=?',
                                     (name,category,price,cost,stock,barcode,active,pid))
                            updated += 1
                        else:
                            cur = self.s.q('INSERT INTO products(name,category,price,cost,stock,barcode,active) VALUES(?,?,?,?,?,?,?)',
                                           (name,category,price,cost,stock,barcode,active))
                            pid = cur.lastrowid
                            created += 1
                            if stock:
                                self.s.q('INSERT INTO stock_movements(product_id,qty,movement_type,note,created_at,user_id) VALUES(?,?,?,?,?,?)',
                                         (pid,stock,'Opening Stock','Bulk CSV import',self._now_catalog(),self.user['id']))
                    except Exception as e:
                        skipped += 1; errors.append(f'Line {line_no}: {e}')
            self.s.c.commit()
            self.s.audit(self.user, 'BULK_IMPORT', 'product', None, f'created={created}, updated={updated}, skipped={skipped}')
            self.load_products()
            msg = f'Import complete.\n\nCreated: {created}\nUpdated: {updated}\nSkipped: {skipped}'
            if errors:
                msg += '\n\nFirst errors:\n' + '\n'.join(errors[:8])
            messagebox.showinfo('Menu Import', msg, parent=self)
        except Exception as e:
            messagebox.showerror('Menu Import', str(e), parent=self)

    def product_export(self):
        path = filedialog.asksaveasfilename(parent=self, title='Download Menu CSV', defaultextension='.csv', initialfile='menu_export.csv', filetypes=[('CSV files','*.csv')])
        if not path:
            return
        try:
            rows = self.s.rows('SELECT name,category,price,cost,stock,barcode,active FROM products ORDER BY category,name')
            with open(path, 'w', encoding='utf-8-sig', newline='') as fh:
                writer = csv.DictWriter(fh, fieldnames=['name','category','price','cost','stock','barcode','active'])
                writer.writeheader()
                for r in rows:
                    writer.writerow(dict(r))
            self.s.audit(self.user, 'BULK_EXPORT', 'product', None, f'{len(rows)} products')
            messagebox.showinfo('Menu Export', f'Exported {len(rows)} products.', parent=self)
        except Exception as e:
            messagebox.showerror('Menu Export', str(e), parent=self)

    def product_template(self):
        path = filedialog.asksaveasfilename(parent=self, title='Download Menu CSV Template', defaultextension='.csv', initialfile='menu_template.csv', filetypes=[('CSV files','*.csv')])
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8-sig', newline='') as fh:
                writer = csv.writer(fh)
                writer.writerow(['name','category','price','cost','stock','barcode','active'])
                writer.writerow(['Example Pizza','Pizza','500','300','0','', '1'])
            messagebox.showinfo('CSV Template', 'Template created. Remove the example row before importing your real menu.', parent=self)
        except Exception as e:
            messagebox.showerror('CSV Template', str(e), parent=self)

    def catalog_history(self):
        p = self._selected_product()
        if not p:
            return
        w = self.dialog('Product History — ' + p['name'], 1000, 620)
        f = ttk.Frame(w, padding=12)
        f.pack(fill='both', expand=True)
        ttk.Label(f, text=f"{p['name']}  |  Category: {p['category']}  |  Stock: {p['stock']}  |  Sale: Rs. {p['price']:,.2f}", font=('Segoe UI',14,'bold')).pack(anchor='w',pady=5)
        ttk.Label(f, text='Sales, stock movements and catalog audit events for this product.', foreground='#64748b').pack(anchor='w',pady=(0,8))
        t = self.table(f, ('date','type','qty','reference','user'), {'date':'Date','type':'Event','qty':'Qty / Value','reference':'Reference','user':'User'}, 18)
        rows = self.s.rows('''
            SELECT created_at date, 'SALE' type, quantity qty,
                   invoice_no reference, COALESCE(u.username,'') user
            FROM sale_items si
            JOIN sales s ON s.id=si.sale_id
            LEFT JOIN users u ON u.id=s.user_id
            WHERE si.product_id=?
            UNION ALL
            SELECT m.created_at, m.movement_type, m.qty, COALESCE(m.note,''), COALESCE(u.username,'')
            FROM stock_movements m LEFT JOIN users u ON u.id=m.user_id
            WHERE m.product_id=?
            UNION ALL
            SELECT a.created_at, a.action, '', COALESCE(a.details,''), COALESCE(u.username,'')
            FROM audit_log a LEFT JOIN users u ON u.id=a.user_id
            WHERE a.entity='product' AND a.entity_id=?
            ORDER BY date DESC
        ''', (p['id'], p['id'], p['id']))
        for r in rows:
            t.insert('', 'end', values=(r['date'],r['type'],r['qty'],r['reference'],r['user']))
        if not rows:
            ttk.Label(f, text='No history recorded yet.').pack(anchor='w', pady=15)

    def categories(self):
        init_catalog(self)
        w = self.dialog('Menu Categories', 520, 430)
        f = ttk.Frame(w, padding=14); f.pack(fill='both',expand=True)
        t = self.table(f, ('id','name'), {'id':'ID','name':'Category'}, 12)
        def reload_():
            t.delete(*t.get_children())
            for r in self.s.rows('SELECT id,name FROM product_categories WHERE active=1 ORDER BY name'):
                t.insert('', 'end', iid=str(r['id']), values=(r['id'],r['name']))
        def add_():
            from tkinter import simpledialog
            n = simpledialog.askstring('Category','Category name:',parent=w)
            if n and n.strip():
                try:
                    self.s.q('INSERT INTO product_categories(name) VALUES(?)',(n.strip(),)); self.s.c.commit(); reload_(); self.load_products()
                except sqlite3.IntegrityError:
                    messagebox.showerror('Category','Category already exists.',parent=w)
        def delete_():
            s=t.selection()
            if s and messagebox.askyesno('Category','Deactivate this category?',parent=w):
                self.s.q('UPDATE product_categories SET active=0 WHERE id=?',(int(s[0]),)); self.s.c.commit(); reload_(); self.load_products()
        b=ttk.Frame(f); b.pack(fill='x',pady=7)
        ttk.Button(b,text='ADD CATEGORY',command=add_).pack(side='left')
        ttk.Button(b,text='DELETE',command=delete_).pack(side='left',padx=5)
        reload_()

    def modifiers(self):
        init_catalog(self)
        w=self.dialog('Product Modifiers / Add-ons',760,520)
        f=ttk.Frame(w,padding=14); f.pack(fill='both',expand=True)
        t=self.table(f,('id','modifier','item','delta'),{'id':'ID','modifier':'Modifier Group','item':'Option','delta':'Price +/-'},14)
        rows=self.s.rows('SELECT i.id,m.name modifier,i.name item,i.price_delta FROM product_modifier_items i JOIN product_modifiers m ON m.id=i.modifier_id WHERE i.active=1 ORDER BY m.name,i.name')
        for r in rows:t.insert('','end',iid=str(r['id']),values=(r['id'],r['modifier'],r['item'],f"{r['price_delta']:+.2f}"))
        def add_():
            d=self.dialog('Add Modifier',420,330); q=ttk.Frame(d,padding=16); q.pack(fill='both',expand=True); a=tk.StringVar(); b=tk.StringVar(); c=tk.DoubleVar(value=0)
            for label,var in [('Modifier Group',a),('Option',b),('Price Adjustment',c)]: ttk.Label(q,text=label).pack(anchor='w',pady=(6,2)); ttk.Entry(q,textvariable=var).pack(fill='x')
            def save():
                if not a.get().strip() or not b.get().strip(): return messagebox.showerror('Modifier','Group and option are required.',parent=d)
                self.s.q('INSERT OR IGNORE INTO product_modifiers(name) VALUES(?)',(a.get().strip(),)); mid=self.s.q('SELECT id FROM product_modifiers WHERE name=?',(a.get().strip(),)).fetchone()['id']; self.s.q('INSERT INTO product_modifier_items(modifier_id,name,price_delta) VALUES(?,?,?)',(mid,b.get().strip(),c.get())); self.s.c.commit(); d.destroy(); w.destroy(); self.modifiers()
            ttk.Button(q,text='SAVE',style='Primary.TButton',command=save).pack(fill='x',pady=15)
        ttk.Button(f,text='ADD MODIFIER OPTION',style='Primary.TButton',command=add_).pack(fill='x',pady=8)

    App.page_products=page_products
    App.load_products=load_products
    App.catalog_edit=catalog_edit
    App.catalog_history=catalog_history
    App.product_delete=product_delete
    App.product_delete_all=product_delete_all
    App.product_import=product_import
    App.product_export=product_export
    App.product_template=product_template
    return App
