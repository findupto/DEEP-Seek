"""Responsive POS shell. Keeps every module reachable on small and large displays."""
import tkinter as tk
from tkinter import ttk

NAV = [
    ('POS','POS'), ('Dashboard','Dashboard'), ('Orders','Orders'), ('Kitchen','Kitchen'),
    ('Customers','Customers'), ('Tables / Dine-in','Tables / Dine-in'), ('Suppliers','Suppliers'),
    ('Products / Menu','Products'), ('Riders','Riders'), ('Staff','Staff'),
    ('Reports / Analytics','Reports'), ('Printers','Printers'), ('Settings','Settings')
]

def install(App):
    def build(self):
        self.configure(bg='#0f172a')
        # Sidebar is a real Tk canvas instead of ttk buttons on a dark frame, so it remains visible on all ttk themes.
        side=tk.Frame(self,bg='#0f172a',width=235)
        side.pack(side='left',fill='y'); side.pack_propagate(False)
        head=tk.Frame(side,bg='#0f172a'); head.pack(fill='x',padx=16,pady=(18,10))
        tk.Label(head,text='MK PIZZA\n& ICE BAR',bg='#0f172a',fg='#ffffff',font=('Segoe UI',17,'bold'),justify='left').pack(anchor='w')
        tk.Label(head,text=f"{self.user['username']} • {self.user['role']}",bg='#0f172a',fg='#94a3b8',font=('Segoe UI',9)).pack(anchor='w',pady=(8,0))
        navhost=tk.Frame(side,bg='#0f172a'); navhost.pack(fill='both',expand=True,padx=(8,4),pady=4)
        canvas=tk.Canvas(navhost,bg='#0f172a',highlightthickness=0,borderwidth=0)
        sb=tk.Scrollbar(navhost,orient='vertical',command=canvas.yview)
        inner=tk.Frame(canvas,bg='#0f172a')
        win=canvas.create_window((0,0),window=inner,anchor='nw')
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side='left',fill='both',expand=True); sb.pack(side='right',fill='y')
        def sync(_=None):
            canvas.configure(scrollregion=canvas.bbox('all')); canvas.itemconfigure(win,width=max(1,canvas.winfo_width()-2))
        inner.bind('<Configure>',sync); canvas.bind('<Configure>',sync)
        self._nav_canvas=canvas
        for label,page in NAV:
            b=tk.Button(inner,text=label,anchor='w',relief='flat',bd=0,bg='#0f172a',fg='#e2e8f0',activebackground='#1e293b',activeforeground='#ffffff',font=('Segoe UI',10,'bold'),padx=14,pady=10,cursor='hand2',command=lambda p=page:self.show(p))
            b.pack(fill='x',pady=1)
            b.bind('<Enter>',lambda e,w=b:w.configure(bg='#1e293b'))
            b.bind('<Leave>',lambda e,w=b:w.configure(bg='#0f172a'))
        # Main content gets all remaining pixels and is allowed to shrink.
        main=tk.Frame(self,bg='#f8fafc')
        main.pack(side='left',fill='both',expand=True)
        self.body=ttk.Frame(main,padding=22)
        self.body.pack(fill='both',expand=True)
        self._main_frame=main
        # Make mouse wheel useful for the navigation when it overflows.
        canvas.bind_all('<MouseWheel>',lambda e: canvas.yview_scroll(int(-e.delta/120),'units'))
        canvas.bind_all('<Button-4>',lambda e: canvas.yview_scroll(-1,'units'))
        canvas.bind_all('<Button-5>',lambda e: canvas.yview_scroll(1,'units'))
    App.build=build
    return App
