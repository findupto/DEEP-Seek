"""Factory-reset the real persistent POS database, not the project-folder placeholder."""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime


def install(App):
    if getattr(App,"_fresh_database_patch_installed",False): return App
    def _is_admin(self): return str(self.user.get("role","")).strip().lower() in {"admin","owner"}
    def _factory_reset(self):
        if not _is_admin(self): return messagebox.showerror("Permission denied","Only Admin or Owner can perform a factory reset.",parent=self)
        if not messagebox.askyesno("FACTORY RESET","This clears ALL business/master data from the active persistent POS database. Users/login settings are kept. A backup is created first. Continue?",icon="warning",parent=self): return
        username=str(self.user.get("username","")); password=simpledialog.askstring("Confirm Administrator",f"Enter the current password for '{username}' to continue:",show="*",parent=self)
        if password is None or not self.s.login(username,password): return messagebox.showerror("Reset cancelled","Administrator password is incorrect.",parent=self)
        db_path=getattr(self.s,"path",None) or getattr(self.s,"db_path",None)
        if not db_path:
            import pos_app; db_path=getattr(pos_app,"DB","pos.db")
        import os,shutil
        db_path=os.path.abspath(db_path); backup_dir=os.path.join(os.path.dirname(db_path),"backups");os.makedirs(backup_dir,exist_ok=True)
        backup_path=os.path.join(backup_dir,"pos_before_factory_reset_"+datetime.now().strftime("%Y%m%d_%H%M%S")+".db")
        try:
            self.s.c.commit();shutil.copy2(db_path,backup_path)
            preserve={"users","settings","ledger_accounts","accounts","account_groups","inventory_valuation_settings","accounting_settings","integration_registry","ent_settings","ent_accounts","ent_stores"}
            rows=self.s.rows("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            self.s.q("PRAGMA foreign_keys=OFF")
            for row in rows:
                table=row["name"]
                if table not in preserve:self.s.q('DELETE FROM "'+table.replace('"','""')+'"')
            # Do not reset sqlite_sequence: preserved user IDs remain stable.
            self.s.q("PRAGMA foreign_keys=ON");self.s.c.commit();self.s.audit(self.user,"FACTORY_RESET","database",None,"Business data cleared; backup: "+backup_path)
            messagebox.showinfo("Fresh POS Ready","The active persistent POS database has been factory-reset.\n\nBackup:\n"+backup_path+"\n\nProducts, customers, suppliers, staff, sales, purchases, expenses, payments, inventory and account history are empty. Login/system configuration is preserved.",parent=self);self.show("Dashboard")
        except Exception as exc:
            try:self.s.c.rollback()
            except Exception:pass
            messagebox.showerror("Factory reset failed",str(exc),parent=self)
    def page_database_reset(self):
        if not _is_admin(self): self.title("Database Reset","Administrator access required.");ttk.Label(self.bodyinner,text="Only Admin or Owner can access this function.").pack(anchor="w",pady=20);return
        self.title("Database Reset","Factory-reset the actual persistent database used by this installation.")
        box=ttk.LabelFrame(self.bodyinner,text="DANGER ZONE",padding=18);box.pack(fill="x",pady=15);ttk.Label(box,text="Fresh POS Database",font=("Segoe UI",16,"bold")).pack(anchor="w");ttk.Label(box,text="Clears business/master data, including old products, customers, suppliers, staff and all transaction history. A timestamped backup is created first and the current Admin/Owner password is required.",wraplength=900,justify="left").pack(anchor="w",pady=10);ttk.Button(box,text="FACTORY RESET — START FRESH",command=self._factory_reset).pack(anchor="w",pady=8);ttk.Label(self.bodyinner,text="The active database is stored under the application data directory; deleting a source-tree pos.db may not affect the live POS database.",foreground="#64748b",wraplength=900).pack(anchor="w",pady=8)
    App._factory_reset=_factory_reset;App.page_database_reset=page_database_reset;App._fresh_database_patch_installed=True
    # Load the final accounting/party layer after every earlier patch.
    try:
        import pos_app
        from business_integrity_patch import install as install_business_integrity
        install_business_integrity(pos_app.App,pos_app.Store)
    except Exception:
        pass
    return App
