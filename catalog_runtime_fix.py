"""Final, self-contained Products/Menu runtime layer."""
import csv
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog


def install(App):
    if getattr(App, "_catalog_runtime_fix_v2", False):
        return App

    def init_catalog(self):
        self.s.c.executescript("""
        CREATE TABLE IF NOT EXISTS product_categories(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE NOT NULL,active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS product_modifiers(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT UNIQUE NOT NULL,active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS product_modifier_items(id INTEGER PRIMARY KEY AUTOINCREMENT,modifier_id INTEGER NOT NULL,name TEXT NOT NULL,price_delta REAL DEFAULT 0,active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS combo_items(id INTEGER PRIMARY KEY AUTOINCREMENT,product_id INTEGER NOT NULL,component_product_id INTEGER NOT NULL,quantity REAL NOT NULL DEFAULT 1);
        """)
        self.s.c.commit()

    def host(self): return getattr(self, "bodyinner", getattr(self, "body", self))

    def selected(self):
        tree=getattr(self,"pr",None); sel=tree.selection() if tree else ()
        if not sel:
            messagebox.showwarning("Product","Select a product first.",parent=self); return None
        try: pid=int(sel[0])
        except (TypeError,ValueError): return None
        return self.s.q("SELECT * FROM products WHERE id=?",(pid,)).fetchone()

    def reload_products(self,all_rows=False):
        tree=getattr(self,"pr",None)
        if tree is None or not tree.winfo_exists(): return
        tree.delete(*tree.get_children()); sql="SELECT * FROM products WHERE 1=1"; args=[]
        if not all_rows: sql += " AND active=1"
        qv=getattr(self,"prod_filter",None); cv=getattr(self,"cat_filter",None); query=qv.get().strip().lower() if qv else ""; category=cv.get() if cv else "All"
        if query: sql += " AND lower(COALESCE(name,'') || ' ' || COALESCE(category,'') || ' ' || COALESCE(barcode,'')) LIKE ?"; args.append("%"+query+"%")
        if category and category!="All": sql += " AND category=?"; args.append(category)
        sql += " ORDER BY active DESC, category, name"
        for r in self.s.rows(sql,tuple(args)):
            tree.insert("","end",iid=str(r["id"]),values=(r["id"],r["name"],r["category"],f"{float(r['price']):.2f}",f"{float(r['cost']):.2f}",r["stock"],r["barcode"],"Yes" if r["active"] else "Archived"))

    def catalog_edit(self):
        init_catalog(self); old=selected(self) if getattr(self,"pr",None) and self.pr.selection() else None
        w=self.dialog("Edit Product" if old else "Add Product",560,620); f=ttk.Frame(w,padding=18); f.pack(fill="both",expand=True); vars_={}
        fields=[("name","Name",old["name"] if old else ""),("category","Category",old["category"] if old else "General"),("price","Sale Price",old["price"] if old else ""),("cost","Cost",old["cost"] if old else "0"),("stock","Opening / Current Stock",old["stock"] if old else "0"),("barcode","Barcode / SKU",old["barcode"] if old else "")]
        for k,label,val in fields: ttk.Label(f,text=label).pack(anchor="w",pady=(7,2)); vars_[k]=tk.StringVar(value=str(val or "")); ttk.Entry(f,textvariable=vars_[k]).pack(fill="x")
        visible=tk.BooleanVar(value=bool(old["active"]) if old else True); ttk.Checkbutton(f,text="Available in POS menu",variable=visible).pack(anchor="w",pady=8)
        def save():
            try:
                name=vars_["name"].get().strip(); category=vars_["category"].get().strip() or "General"; price=float(vars_["price"].get()); cost=float(vars_["cost"].get() or 0); stock=float(vars_["stock"].get() or 0); barcode=vars_["barcode"].get().strip()
                if not name or price<0 or cost<0 or stock<0: raise ValueError("Name is required and numeric values cannot be negative.")
                self.s.q("INSERT OR IGNORE INTO product_categories(name) VALUES(?)",(category,)); active=1 if visible.get() else 0
                if old: self.s.q("UPDATE products SET name=?,category=?,price=?,cost=?,stock=?,barcode=?,active=? WHERE id=?",(name,category,price,cost,stock,barcode,active,old["id"])); pid,action=old["id"],"UPDATE"
                else:
                    cur=self.s.q("INSERT INTO products(name,category,price,cost,stock,barcode,active) VALUES(?,?,?,?,?,?,?)",(name,category,price,cost,stock,barcode,active)); pid,action=cur.lastrowid,"CREATE"
                    if stock:self.s.q("INSERT INTO stock_movements(product_id,qty,movement_type,note,created_at,user_id) VALUES(?,?,?,?,datetime('now','localtime'),?)",(pid,stock,"Opening Stock","Product creation",self.user["id"]))
                self.s.c.commit(); self.s.audit(self.user,action,"product",pid,name); w.destroy(); self.show("Products / Menu")
            except Exception as exc: messagebox.showerror("Product",str(exc),parent=w)
        ttk.Button(f,text="SAVE PRODUCT",style="Primary.TButton",command=save).pack(fill="x",pady=18)

    def product_delete(self):
        p=selected(self)
        if not p:return
        if not messagebox.askyesno("Archive Product",f"Archive '{p['name']}' from the active POS menu?\n\nSales and history will be preserved.",parent=self):return
        self.s.q("UPDATE products SET active=0 WHERE id=?",(p["id"],)); self.s.c.commit(); self.s.audit(self.user,"ARCHIVE","product",p["id"],p["name"]); reload_products(self)

    def product_delete_all(self):
        count=int(self.s.q("SELECT COUNT(*) n FROM products WHERE active=1").fetchone()["n"])
        if not count:return messagebox.showinfo("Menu","There are no active menu products.",parent=self)
        if not messagebox.askyesno("DELETE ALL MENU",f"Archive ALL {count} active menu products?\n\nOld orders and history will remain intact.",parent=self):return
        self.s.q("UPDATE products SET active=0 WHERE active=1"); self.s.c.commit(); self.s.audit(self.user,"ARCHIVE_ALL","product",None,f"{count} products archived"); reload_products(self)

    def product_import(self):
        path=filedialog.askopenfilename(parent=self,title="Upload Menu CSV",filetypes=[("CSV files","*.csv"),("All files","*.*")])
        if not path:return
        created=updated=skipped=0; errors=[]
        try:
            with open(path,"r",encoding="utf-8-sig",newline="") as fh:
                reader=csv.DictReader(fh); headers={str(x or "").strip().lower() for x in (reader.fieldnames or [])}
                if not {"name","price"}.issubset(headers):raise ValueError("CSV must contain at least: name, price. Optional: category, cost, stock, barcode, active.")
                for line_no,raw in enumerate(reader,start=2):
                    try:
                        row={str(k or "").strip().lower():(str(v).strip() if v is not None else "") for k,v in raw.items()}; name=row.get("name","").strip()
                        if not name:raise ValueError("missing name")
                        price=float(row.get("price","0") or 0); cost=float(row.get("cost","0") or 0); stock=float(row.get("stock","0") or 0); category=row.get("category","General").strip() or "General"; barcode=row.get("barcode","").strip(); active=0 if row.get("active","1").lower() in ("0","no","false","off","archived") else 1
                        if price<0 or cost<0 or stock<0:raise ValueError("negative numeric value")
                        self.s.q("INSERT OR IGNORE INTO product_categories(name) VALUES(?)",(category,)); existing=None
                        if barcode:existing=self.s.q("SELECT id FROM products WHERE barcode=? AND barcode<>'' LIMIT 1",(barcode,)).fetchone()
                        if not existing:existing=self.s.q("SELECT id FROM products WHERE lower(name)=lower(?) LIMIT 1",(name,)).fetchone()
                        if existing:
                            pid=existing["id"]; self.s.q("UPDATE products SET name=?,category=?,price=?,cost=?,stock=?,barcode=?,active=? WHERE id=?",(name,category,price,cost,stock,barcode,active,pid)); updated+=1
                        else:
                            cur=self.s.q("INSERT INTO products(name,category,price,cost,stock,barcode,active) VALUES(?,?,?,?,?,?,?)",(name,category,price,cost,stock,barcode,active)); pid=cur.lastrowid; created+=1
                            if stock:self.s.q("INSERT INTO stock_movements(product_id,qty,movement_type,note,created_at,user_id) VALUES(?,?,?,?,datetime('now','localtime'),?)",(pid,stock,"Opening Stock","Bulk CSV import",self.user["id"]))
                    except Exception as exc:skipped+=1; errors.append(f"Line {line_no}: {exc}")
            self.s.c.commit(); self.s.audit(self.user,"BULK_IMPORT","product",None,f"created={created}, updated={updated}, skipped={skipped}"); reload_products(self); msg=f"Import complete.\n\nCreated: {created}\nUpdated: {updated}\nSkipped: {skipped}"; msg += ("\n\nFirst errors:\n"+"\n".join(errors[:8])) if errors else ""; messagebox.showinfo("Menu Import",msg,parent=self)
        except Exception as exc:messagebox.showerror("Menu Import",str(exc),parent=self)

    def product_export(self):
        path=filedialog.asksaveasfilename(parent=self,title="Download Menu CSV",defaultextension=".csv",initialfile="menu_export.csv",filetypes=[("CSV files","*.csv")])
        if not path:return
        try:
            rows=self.s.rows("SELECT name,category,price,cost,stock,barcode,active FROM products ORDER BY category,name")
            with open(path,"w",encoding="utf-8-sig",newline="") as fh:
                writer=csv.DictWriter(fh,fieldnames=["name","category","price","cost","stock","barcode","active"]); writer.writeheader()
                for r in rows: writer.writerow(dict(r))
            self.s.audit(self.user,"BULK_EXPORT","product",None,f"{len(rows)} products"); messagebox.showinfo("Menu Export",f"Exported {len(rows)} products.",parent=self)
        except Exception as exc:messagebox.showerror("Menu Export",str(exc),parent=self)

    def product_template(self):
        path=filedialog.asksaveasfilename(parent=self,title="Download Menu CSV Template",defaultextension=".csv",initialfile="menu_template.csv",filetypes=[("CSV files","*.csv")])
        if not path:return
        try:
            with open(path,"w",encoding="utf-8-sig",newline="") as fh:
                writer=csv.writer(fh); writer.writerow(["name","category","price","cost","stock","barcode","active"]); writer.writerow(["Example Pizza","Pizza","500","300","0","","1"])
            messagebox.showinfo("CSV Template","Template created. Remove the example row before importing real products.",parent=self)
        except Exception as exc:messagebox.showerror("CSV Template",str(exc),parent=self)

    def bulk_center(self):
        w=self.dialog("Bulk Menu Operations",580,410); f=ttk.Frame(w,padding=18); f.pack(fill="both",expand=True); ttk.Label(f,text="Bulk Menu Operations",font=("Segoe UI",18,"bold")).pack(anchor="w"); ttk.Label(f,text="Upload a CSV to create/update products, or download the complete menu as CSV.",foreground="#64748b",wraplength=520).pack(anchor="w",pady=(5,16)); ttk.Button(f,text="UPLOAD / IMPORT MENU CSV",style="Primary.TButton",command=lambda:product_import(self)).pack(fill="x",pady=5); ttk.Button(f,text="DOWNLOAD / EXPORT MENU CSV",command=lambda:product_export(self)).pack(fill="x",pady=5); ttk.Button(f,text="DOWNLOAD CSV TEMPLATE",command=lambda:product_template(self)).pack(fill="x",pady=5); ttk.Button(f,text="CLOSE",command=w.destroy).pack(fill="x",pady=(18,0))

    def catalog_history(self):
        p=selected(self)
        if not p:return
        w=self.dialog("Product History — "+p["name"],1000,620); f=ttk.Frame(w,padding=12); f.pack(fill="both",expand=True); ttk.Label(f,text=f"{p['name']}  |  Category: {p['category']}  |  Stock: {p['stock']}  |  Sale: Rs. {float(p['price']):,.2f}",font=("Segoe UI",14,"bold")).pack(anchor="w",pady=5); ttk.Label(f,text="Sales, stock movements and product audit events.",foreground="#64748b").pack(anchor="w",pady=(0,8)); t=self.table(f,("date","type","qty","reference","user"),{"date":"Date","type":"Event","qty":"Qty / Value","reference":"Reference","user":"User"},18)
        rows=self.s.rows("""SELECT s.created_at date,'SALE' type,si.quantity qty,s.invoice_no reference,COALESCE(u.username,'') user FROM sale_items si JOIN sales s ON s.id=si.sale_id LEFT JOIN users u ON u.id=s.user_id WHERE si.product_id=? UNION ALL SELECT m.created_at,m.movement_type,m.qty,COALESCE(m.note,''),COALESCE(u.username,'') FROM stock_movements m LEFT JOIN users u ON u.id=m.user_id WHERE m.product_id=? UNION ALL SELECT a.created_at,a.action,'',COALESCE(a.details,''),COALESCE(u.username,'') FROM audit_log a LEFT JOIN users u ON u.id=a.user_id WHERE a.entity='product' AND a.entity_id=? ORDER BY date DESC""",(p["id"],p["id"],p["id"]))
        for r in rows:t.insert("","end",values=(r["date"],r["type"],r["qty"],r["reference"],r["user"]))
        if not rows:ttk.Label(f,text="No history recorded yet.").pack(anchor="w",pady=15)

    def categories(self):
        init_catalog(self); w=self.dialog("Menu Categories",560,460); f=ttk.Frame(w,padding=14); f.pack(fill="both",expand=True); t=self.table(f,("id","name","status"),{"id":"ID","name":"Category","status":"Status"},12)
        def reload_():
            t.delete(*t.get_children())
            for r in self.s.rows("SELECT id,name,active FROM product_categories ORDER BY active DESC,name"):t.insert("","end",iid=str(r["id"]),values=(r["id"],r["name"],"Active" if r["active"] else "Archived"))
        def add_():
            name=simpledialog.askstring("Category","Category name:",parent=w)
            if not name or not name.strip():return
            try:self.s.q("INSERT INTO product_categories(name,active) VALUES(?,1)",(name.strip(),)); self.s.c.commit(); reload_()
            except sqlite3.IntegrityError:messagebox.showerror("Category","Category already exists.",parent=w)
        def remove_():
            sel=t.selection()
            if sel and messagebox.askyesno("Category","Archive this category? Products are not deleted.",parent=w):self.s.q("UPDATE product_categories SET active=0 WHERE id=?",(int(sel[0]),)); self.s.c.commit(); reload_()
        b=ttk.Frame(f); b.pack(fill="x",pady=8); ttk.Button(b,text="ADD CATEGORY",style="Primary.TButton",command=add_).pack(side="left"); ttk.Button(b,text="ARCHIVE",command=remove_).pack(side="left",padx=5); reload_()

    def modifiers(self):
        init_catalog(self); w=self.dialog("Product Modifiers / Add-ons",760,520); f=ttk.Frame(w,padding=14); f.pack(fill="both",expand=True); t=self.table(f,("id","modifier","item","delta"),{"id":"ID","modifier":"Modifier Group","item":"Option","delta":"Price +/-"},14)
        for r in self.s.rows("SELECT i.id,m.name modifier,i.name item,i.price_delta FROM product_modifier_items i JOIN product_modifiers m ON m.id=i.modifier_id WHERE i.active=1 ORDER BY m.name,i.name"):t.insert("","end",iid=str(r["id"]),values=(r["id"],r["modifier"],r["item"],f"{float(r['price_delta']):+.2f}"))
        def add_():
            d=self.dialog("Add Modifier Option",430,350); q=ttk.Frame(d,padding=16); q.pack(fill="both",expand=True); group=tk.StringVar(); item=tk.StringVar(); delta=tk.StringVar(value="0")
            for label,var in (("Modifier Group",group),("Option",item),("Price Adjustment",delta)):ttk.Label(q,text=label).pack(anchor="w",pady=(6,2)); ttk.Entry(q,textvariable=var).pack(fill="x")
            def save():
                if not group.get().strip() or not item.get().strip():return messagebox.showerror("Modifier","Group and option are required.",parent=d)
                try:
                    pd=float(delta.get() or 0); self.s.q("INSERT OR IGNORE INTO product_modifiers(name,active) VALUES(?,1)",(group.get().strip(),)); mid=self.s.q("SELECT id FROM product_modifiers WHERE name=?",(group.get().strip(),)).fetchone()["id"]; self.s.q("INSERT INTO product_modifier_items(modifier_id,name,price_delta,active) VALUES(?,?,?,1)",(mid,item.get().strip(),pd)); self.s.c.commit(); d.destroy(); w.destroy(); self.modifiers()
                except Exception as exc:messagebox.showerror("Modifier",str(exc),parent=d)
            ttk.Button(q,text="SAVE",style="Primary.TButton",command=save).pack(fill="x",pady=15)
        ttk.Button(f,text="ADD MODIFIER OPTION",style="Primary.TButton",command=add_).pack(fill="x",pady=8)

    def page(self):
        init_catalog(self); self.title("Products & Menu","Manage products, history, categories, media and bulk menu files."); root=host(self)
        bar=ttk.Frame(root); bar.pack(fill="x",pady=8)
        buttons=[("ADD PRODUCT",lambda:catalog_edit(self)),("EDIT SELECTED",lambda:catalog_edit(self)),("VIEW HISTORY",lambda:catalog_history(self)),("DELETE / ARCHIVE",lambda:product_delete(self)),("DELETE ALL MENU",lambda:product_delete_all(self)),("IMAGE / ICON / EMOJI / GIFT",lambda:getattr(self,"product_media",lambda:messagebox.showinfo("Product Visuals","Product visuals are not available.",parent=self))())]
        for i,(text,command) in enumerate(buttons):ttk.Button(bar,text=text,style="Primary.TButton" if i==0 else "TButton",command=command).pack(side="left",padx=(0,4))
        bulk=ttk.LabelFrame(root,text="BULK MENU — CSV IMPORT / EXPORT",padding=8); bulk.pack(fill="x",pady=(0,8)); ttk.Button(bulk,text="UPLOAD / IMPORT MENU CSV",style="Primary.TButton",command=lambda:product_import(self)).pack(side="left",padx=(0,5)); ttk.Button(bulk,text="DOWNLOAD / EXPORT MENU CSV",command=lambda:product_export(self)).pack(side="left",padx=5); ttk.Button(bulk,text="DOWNLOAD CSV TEMPLATE",command=lambda:product_template(self)).pack(side="left",padx=5); ttk.Button(bulk,text="BULK MENU CENTER",command=lambda:bulk_center(self)).pack(side="left",padx=5)
        tools=ttk.Frame(root); tools.pack(fill="x",pady=(0,8)); ttk.Button(tools,text="CATEGORIES",command=lambda:categories(self)).pack(side="left",padx=(0,5)); ttk.Button(tools,text="MODIFIERS / ADD-ONS",command=lambda:modifiers(self)).pack(side="left",padx=5)
        filters=ttk.Frame(root); filters.pack(fill="x",pady=(0,8)); self.cat_filter=tk.StringVar(value="All"); self.prod_filter=tk.StringVar(); cats=["All"]+[r["name"] for r in self.s.rows("SELECT name FROM product_categories WHERE active=1 ORDER BY name")]; combo=ttk.Combobox(filters,textvariable=self.cat_filter,values=cats,state="readonly",width=20); combo.pack(side="left"); combo.bind("<<ComboboxSelected>>",lambda _e:reload_products(self)); ttk.Label(filters,text="Search").pack(side="left",padx=(12,3)); search=ttk.Entry(filters,textvariable=self.prod_filter); search.pack(side="left",fill="x",expand=True); search.bind("<KeyRelease>",lambda _e:reload_products(self)); ttk.Button(filters,text="SHOW ALL / ARCHIVED",command=lambda:reload_products(self,True)).pack(side="left",padx=5)
        self.pr=self.table(root,("id","name","category","price","cost","stock","barcode","active"),{"id":"ID","name":"Product / Menu Item","category":"Category","price":"Sale Price","cost":"Cost","stock":"Stock","barcode":"Barcode / SKU","active":"POS Menu"},18); self.pr.bind("<Double-1>",lambda _e:catalog_history(self)); self.pr.bind("<Return>",lambda _e:catalog_history(self)); reload_products(self)

    App.product_delete=delete
    App.product_delete_all=delete_all
    App.bulk_center=bulk_center
    App.bulk_menu_center=bulk_center
    App._selected_product=selected
    App.load_products=lambda self:reload(self)
    App.load_products_all=lambda self:reload(self,True)
    App.page_products=page
    App.page_products_menu=page
    App.init_catalog=getattr(App,"init_catalog",None) or init_catalog
    App.catalog_edit=getattr(App,"catalog_edit",None) or getattr(App,"product_edit",None)
    App.catalog_history=getattr(App,"catalog_history",None) or catalog_history
    App.product_import=getattr(App,"product_import",None)
    App.product_export=getattr(App,"product_export",None)
    App.product_template=getattr(App,"product_template",None)
    App.categories=categories
    App.modifiers=modifiers
    App._catalog_runtime_fix_v2=True
    return App
