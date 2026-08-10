import json
import tkinter as tk
from pathlib import Path
from tkinter import ttk
PREFS=Path('ui_preferences.json')
DEFAULTS={'theme':'Light','scale':'100','high_contrast':False,'compact_nav':False}
def load():
    try:return {**DEFAULTS,**json.loads(PREFS.read_text(encoding='utf-8'))}
    except Exception:return DEFAULTS.copy()
def save(data):PREFS.write_text(json.dumps(data,indent=2),encoding='utf-8')
def configure(root,prefs=None):
    prefs=prefs or load()
    try:root.tk.call('tk','scaling',float(prefs['scale'])/75.0)
    except Exception:pass
    s=ttk.Style(root)
    try:s.theme_use('clam')
    except Exception:pass
    dark=prefs['theme']=='Dark'; contrast=bool(prefs['high_contrast'])
    bg='#111827' if dark else ('#ffffff' if contrast else '#f5f7fa'); panel='#1f2937' if dark else '#ffffff'; fg='#f9fafb' if dark else '#172033'; muted='#cbd5e1' if dark else '#5b6575'; accent='#60a5fa' if dark else '#2563eb'
    s.configure('.',font=('Segoe UI',10),background=bg,foreground=fg)
    s.configure('TFrame',background=bg); s.configure('TLabel',background=bg,foreground=fg,padding=2)
    s.configure('Title.TLabel',font=('Segoe UI',22,'bold'),background=bg,foreground=fg); s.configure('Subtitle.TLabel',font=('Segoe UI',10),background=bg,foreground=muted)
    s.configure('TButton',font=('Segoe UI',10,'bold'),padding=(12,8),background=panel,foreground=fg); s.map('TButton',background=[('active',accent),('pressed',accent)],foreground=[('active','#fff'),('pressed','#fff')])
    s.configure('Accent.TButton',background=accent,foreground='#fff',padding=(14,9)); s.configure('TEntry',padding=8,fieldbackground=panel,foreground=fg); s.configure('TCombobox',padding=7,fieldbackground=panel,foreground=fg)
    s.configure('Treeview',rowheight=max(30,int(30*float(prefs['scale'])/100)),background=panel,fieldbackground=panel,foreground=fg,font=('Segoe UI',10)); s.configure('Treeview.Heading',font=('Segoe UI',10,'bold'),padding=8,background=accent,foreground='#fff'); s.map('Treeview',background=[('selected',accent)],foreground=[('selected','#fff')])
    s.configure('TLabelframe',background=bg,foreground=fg); s.configure('TLabelframe.Label',background=bg,foreground=fg,font=('Segoe UI',10,'bold')); root.configure(bg=bg); root.option_add('*TButton.takeFocus',True); return prefs
def make_accessibility_dialog(parent):
    p=load(); w=tk.Toplevel(parent); w.title('Display & Accessibility'); w.geometry('480x360'); w.minsize(440,330); w.transient(parent)
    f=ttk.Frame(w,padding=22); f.pack(fill='both',expand=True); ttk.Label(f,text='Display & Accessibility',style='Title.TLabel').pack(anchor='w'); ttk.Label(f,text='Adjust size, contrast and appearance for your display.',style='Subtitle.TLabel').pack(anchor='w',pady=(0,18))
    theme=tk.StringVar(value=p['theme']); scale=tk.StringVar(value=str(p['scale'])); hc=tk.BooleanVar(value=p['high_contrast']); compact=tk.BooleanVar(value=p['compact_nav'])
    ttk.Label(f,text='Appearance').pack(anchor='w'); ttk.Combobox(f,textvariable=theme,values=['Light','Dark'],state='readonly').pack(fill='x',pady=(4,12)); ttk.Label(f,text='Interface size').pack(anchor='w'); ttk.Combobox(f,textvariable=scale,values=['90','100','110','120','130','140'],state='readonly').pack(fill='x',pady=(4,12)); ttk.Checkbutton(f,text='High contrast mode',variable=hc).pack(anchor='w',pady=5); ttk.Checkbutton(f,text='Compact navigation',variable=compact).pack(anchor='w',pady=5)
    def apply():
        d={'theme':theme.get(),'scale':scale.get(),'high_contrast':hc.get(),'compact_nav':compact.get()}; save(d); configure(parent,d); w.destroy()
    ttk.Button(f,text='Apply & Save',style='Accent.TButton',command=apply).pack(anchor='e',pady=15); w.bind('<Return>',lambda e:apply()); w.bind('<Escape>',lambda e:w.destroy()); return w
