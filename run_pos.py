import tkinter as tk
from tkinter import ttk
import pos
from printer_manager import PrinterManager, PrinterSettings
from ui_theme import configure, load, make_accessibility_dialog
import production
import fastfood_complete

printer_manager=PrinterManager()
_original_show=pos.Main.show
_original_main_init=pos.Main.__init__
_original_login_init=pos.Login.__init__


def login_init(self,db):
    _original_login_init(self,db)
    configure(self,load())
    self.geometry('460x330')
    self.minsize(420,300)
    self.bind('<Escape>',lambda e:self.destroy())


def build_nav_with_ui(self):
    configure(self,load())
    top=ttk.Frame(self,padding=(12,10)); top.pack(fill='x')
    ttk.Label(top,text=pos.BUSINESS['name'],font=('Segoe UI',18,'bold')).pack(side='left')
    ttk.Button(top,text='Display',command=lambda:make_accessibility_dialog(self)).pack(side='right',padx=5)
    ttk.Label(top,text=f"{self.user['role']} | {self.user['username']}",style='Subtitle.TLabel').pack(side='right',padx=5)
    nav_outer=ttk.Frame(self); nav_outer.pack(fill='x',padx=10,pady=(0,8))
    canvas=tk.Canvas(nav_outer,height=54,highlightthickness=0,bd=0); scroll=ttk.Scrollbar(nav_outer,orient='horizontal',command=canvas.xview); canvas.configure(xscrollcommand=scroll.set)
    inner=ttk.Frame(canvas); canvas.create_window((0,0),window=inner,anchor='nw'); inner.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.pack(fill='x',expand=True); scroll.pack(fill='x')
    for n in ['POS Sale','Dashboard','Customers','Suppliers','Products','Analytics','Stats','Staff','Counter Persons','Riders','Kitchen','Settings','Printers','Order Board','Cash Control','Expenses','Stock Control','Audit Log','Backup & Recovery','Purchases','Returns','Recipes']:
        ttk.Button(inner,text=n,command=lambda x=n:self.show(x)).pack(side='left',padx=3,pady=3)
    canvas.bind('<Shift-MouseWheel>',lambda e:canvas.xview_scroll(int(-e.delta/120),'units'))
    self.body=ttk.Frame(self,padding=12); self.body.pack(fill='both',expand=True)


def show_with_printer(self,name):
    if name!='Printers': return _original_show(self,name)
    for w in self.body.winfo_children():w.destroy()
    ttk.Label(self.body,text='Printers',font=('Segoe UI',20,'bold')).pack(anchor='w')
    ttk.Label(self.body,text='80mm Bluetooth thermal printer discovery, connection and receipt themes',style='Subtitle.TLabel').pack(anchor='w',pady=(0,12))
    card=ttk.LabelFrame(self.body,text='Printer Status',padding=16); card.pack(fill='x',pady=(0,12))
    s=printer_manager.status(); p=s.get('printer') or {}
    ttk.Label(card,text=f"Saved Printer: {p.get('name','None')}").pack(anchor='w',pady=2)
    ttk.Label(card,text=f"Status: {'Connected' if s.get('connected') else 'Not connected'}").pack(anchor='w',pady=2)
    ttk.Label(card,text=f"Receipt Theme: {s.get('theme','Classic')}").pack(anchor='w',pady=2)
    ttk.Button(card,text='Open Printer & Receipt Settings',style='Accent.TButton',command=lambda:PrinterSettings(self,printer_manager,pos.BUSINESS)).pack(anchor='w',pady=(10,0))
    if p.get('auto_reconnect',True):self.after(250,printer_manager.auto_reconnect)


def main_init(self,db,user):
    _original_main_init(self,db,user)
    configure(self,load())
    sw,sh=self.winfo_screenwidth(),self.winfo_screenheight(); width=min(1440,max(900,int(sw*.92))); height=min(900,max(600,int(sh*.88)))
    self.geometry(f'{width}x{height}'); self.minsize(820,540)
    self.bind('<Control-plus>',lambda e:self._resize_ui(10)); self.bind('<Control-minus>',lambda e:self._resize_ui(-10)); self.bind('<Control-0>',lambda e:self._resize_ui(0))
    if printer_manager.config.get('printer',{}).get('auto_reconnect',True):self.after(300,printer_manager.auto_reconnect)


def resize_ui(self,delta):
    p=load(); p['scale']=str(100 if delta==0 else max(90,min(140,int(p['scale'])+delta))); configure(self,p)

pos.Login.__init__=login_init
pos.Main.build_nav=build_nav_with_ui
pos.Main.show=show_with_printer
pos.Main.__init__=main_init
pos.Main._resize_ui=resize_ui

# Install all database extensions before login and patch the existing Main class.
db=pos.DB()
production.install(db)
production.patch(pos.Main)
fastfood_complete.install(db)
fastfood_complete.patch(pos.Main, pos.DB)
del db

if __name__=='__main__':pos.Login(pos.DB()).mainloop()
