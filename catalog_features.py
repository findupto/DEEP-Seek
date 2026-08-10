"""Functional product/menu/catalog UI extension. No sample records are created."""
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
        init_catalog(self); self.title('Products & Menu','Manage the real menu catalog. Nothing is pre-populated.');
        bar=ttk.Frame(self.body); bar.pack(fill='x',pady=8)
        ttk.Button(bar,text='ADD PRODUCT',style='Primary.TButton',command=lambda:self.catalog_edit()).pack(side='left')
        ttk.Button(bar,text='EDIT',command=lambda:self.catalog_edit()).pack(side='left',padx=4)
        ttk.Button(bar,text='DELETE',command=self.product_delete).pack(side='left')
        ttk.Button(bar,text='PRODUCT HISTORY',command=self.catalog_history).pack(side='left',padx=4)
        ttk.Button(bar,text='MODIFIERS',command=self.modifiers).pack(side='left')
        ttk.Button(bar,text='CATEGORIES',command=self.categories).pack(side='left',padx=4)
        ttk.Button(bar,text='IMPORT CSV',command=self.product_import).pack(side='right')
        ttk.Button(bar,text='EXPORT CSV',command=self.product_export).pack(side='right',padx=4)
        filterbar=ttk.Frame(self.body); filterbar.pack(fill='x',pady=(0,8)); self.cat_filter=tk.StringVar(value='All'); self.prod_filter=tk.StringVar()
        ttk.Label(filterbar,text='Category').pack(side='left'); cats=['All']+[r['name'] for r in self.s.rows('SELECT name FROM product_categories WHERE active=1 ORDER BY name')]; ttk.Combobox(filterbar,textvariable=self.cat_filter,values=cats,state='readonly',width=20).pack(side='left',padx=5); ttk.Label(filterbar,text='Search').pack(side='left',padx=(15,3)); e=ttk.Entry(filterbar,textvariable=self.prod_filter); e.pack(side='left',fill='x',expand=True); e.bind('<KeyRelease>',lambda _:self.load_products())
        self.pr=self.table(self.body,('id','name','category','price','cost','stock','barcode','active'),{'id':'ID','name':'Product / Menu Item','category':'Category','price':'Sale Price','cost':'Cost','stock':'Stock','barcode':'Barcode','active':'POS Menu'},18); self.pr.bind('<Double-1>',lambda e:self.catalog_history()); self.load_products()
    def load_products(self):
        if not hasattr(self,'pr'): return
        for x in self.pr.get_children(): self.pr.delete(x)
        q='SELECT * FROM products WHERE active=1'; a=[]
        z=getattr(self,'prod_filter',tk.StringVar()).get().strip().lower()
        cat=getattr(self,'cat_filter',tk.StringVar(value='All')).get()
        if z: q+=' AND lower(name||" "||category||" "||barcode) LIKE ?'; a.append('%'+z+'%')
        if cat and cat!='All': q+=' AND category=?'; a.append(cat)
        q+=' ORDER BY category,name'
        for r in self.s.rows(q,tuple(a)): self.pr.insert('','end',iid=str(r['id']),values=(r['id'],r['name'],r['category'],f"{r['price']:.2f}",f"{r['cost']:.2f}",r['stock'],r['barcode'],'Yes'))
    def catalog_edit(self):
        init_catalog(self); sel=self.pr.selection() if hasattr(self,'pr') else (); old=self.s.q('SELECT * FROM products WHERE id=?',(int(sel[0]),)).fetchone() if sel else None
        w=self.dialog('Product / Menu Item',560,620); f=ttk.Frame(w,padding=18); f.pack(fill='both',expand=True); v={}
        fields=[('name','Name',str(old['name']) if old else ''),('category','Category',str(old['category']) if old else 'General'),('price','Sale Price',str(old['price']) if old else ''),('cost','Cost',str(old['cost']) if old else '0'),('stock','Opening Stock',str(old['stock']) if old else '0'),('barcode','Barcode',str(old['barcode']) if old else '')]
        for k,label,val in fields: ttk.Label(f,text=label).pack(anchor='w',pady=(7,2)); v[k]=tk.StringVar(value=val); ttk.Entry(f,textvariable=v[k]).pack(fill='x')
        ttk.Label(f,text='Menu visibility').pack(anchor='w',pady=(10,2)); menu=tk.BooleanVar(value=True); ttk.Checkbutton(f,text='Available in POS menu',variable=menu).pack(anchor='w')
        def save():
            try:
                name=v['name'].get().strip(); cat=v['category'].get().strip() or 'General'; price=float(v['price'].get()); cost=float(v['cost'].get() or 0); stock=float(v['stock'].get() or 0); barcode=v['barcode'].get().strip()
                if not name or price<0 or cost<0 or stock<0: raise ValueError('Invalid product values')
                self.s.q('INSERT OR IGNORE INTO product_categories(name) VALUES(?)',(cat,))
                active=1 if menu.get() else 0
                if old: self.s.q('UPDATE products SET name=?,category=?,price=?,cost=?,stock=?,barcode=?,active=? WHERE id=?',(name,cat,price,cost,stock,barcode,active,old['id'])); pid=old['id']
                else: cur=self.s.q('INSERT INTO products(name,category,price,cost,stock,barcode,active) VALUES(?,?,?,?,?,?,?)',(name,cat,price,cost,stock,barcode,active)); pid=cur.lastrowid
                self.s.c.commit(); self.s.audit(self.user,'SAVE','product',pid,name); w.destroy(); self.show('Products')
            except Exception as e: messagebox.showerror('Product',str(e),parent=w)
        ttk.Button(f,text='SAVE PRODUCT',style='Primary.TButton',command=save).pack(fill='x',pady=18)
    def catalog_history(self):
        sel=self.pr.selection() if hasattr(self,'pr') else ()
        if not sel:return messagebox.showwarning('Product','Select a product.',parent=self)
        pid=int(sel[0]); p=self.s.q('SELECT * FROM products WHERE id=?',(pid,)).fetchone(); w=self.dialog('Product History — '+p['name'],900,560); f=ttk.Frame(w,padding=12); f.pack(fill='both',expand=True)
        ttk.Label(f,text=f"{p['name']}  |  Stock {p['stock']}  |  Rs. {p['price']:,.2f}",font=('Segoe UI',14,'bold')).pack(anchor='w',pady=5)
        t=self.table(f,('date','type','qty','note','user'),{'date':'Date','type':'Movement','qty':'Quantity','note':'Reference','user':'User'},18)
        rows=self.s.rows('SELECT m.*,COALESCE(u.username,"") username FROM stock_movements m LEFT JOIN users u ON u.id=m.user_id WHERE m.product_id=? ORDER BY m.id DESC',(pid,))
        for r in rows:t.insert('','end',values=(r['created_at'],r['movement_type'],r['qty'],r['note'],r['username']))
    def categories(self):
        init_catalog(self); w=self.dialog('Menu Categories',520,430); f=ttk.Frame(w,padding=14); f.pack(fill='both',expand=True); t=self.table(f,('id','name'),{'id':'ID','name':'Category'},12)
        def reload_():
            t.delete(*t.get_children());
            for r in self.s.rows('SELECT id,name FROM product_categories WHERE active=1 ORDER BY name'): t.insert('','end',iid=str(r['id']),values=(r['id'],r['name']))
        def add_():
            from tkinter import simpledialog
            n=simpledialog.askstring('Category','Category name:',parent=w)
            if n and n.strip():
                try:self.s.q('INSERT INTO product_categories(name) VALUES(?)',(n.strip(),));self.s.c.commit();reload_()
                except sqlite3.IntegrityError: messagebox.showerror('Category','Category already exists.',parent=w)
        def delete_():
            s=t.selection();
            if s and messagebox.askyesno('Category','Deactivate this category?',parent=w): self.s.q('UPDATE product_categories SET active=0 WHERE id=?',(int(s[0]),)); self.s.c.commit(); reload_()
        b=ttk.Frame(f); b.pack(fill='x',pady=7); ttk.Button(b,text='ADD CATEGORY',command=add_).pack(side='left'); ttk.Button(b,text='DELETE',command=delete_).pack(side='left',padx=5); reload_()
    def modifiers(self):
        init_catalog(self); w=self.dialog('Product Modifiers / Add-ons',760,520); f=ttk.Frame(w,padding=14); f.pack(fill='both',expand=True); t=self.table(f,('id','modifier','item','delta'),{'id':'ID','modifier':'Modifier Group','item':'Option','delta':'Price +/-'},14)
        rows=self.s.rows('SELECT i.id,m.name modifier,i.name item,i.price_delta FROM product_modifier_items i JOIN product_modifiers m ON m.id=i.modifier_id WHERE i.active=1 ORDER BY m.name,i.name')
        for r in rows:t.insert('','end',iid=str(r['id']),values=(r['id'],r['modifier'],r['item'],f"{r['delta']:+.2f}"))
        def add_():
            d=self.dialog('Add Modifier',420,330); q=ttk.Frame(d,padding=16); q.pack(fill='both',expand=True); a=tk.StringVar(); b=tk.StringVar(); c=tk.DoubleVar(value=0); 
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
    return App
