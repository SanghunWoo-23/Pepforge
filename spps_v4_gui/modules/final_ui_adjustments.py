"""V2.2.14 focused fixes: sequence chemicals, CTC(합성용), compact checklist."""
from __future__ import annotations
from tkinter import ttk

APP_VERSION='V4.0.0'
VERSION_LABEL='SPPS Planner V4.0.0'

ACTIVE_RESINS = [
'Rink Amide AM','Rink Amide MBHA','Rink Amide ChemMatrix','Rink Amide Tentagel',
'2-CTC','CTC(합성기)','Wang','HMPB','Sieber Amide','PAL resin','Tentagel','Manual']


def _walk(root):
    try: children=root.winfo_children()
    except Exception: return
    for c in children:
        yield c
        yield from _walk(c)


def _restore_resin_widgets(gui):
    try:
        gui.RESIN_VALUES=list(ACTIVE_RESINS)
    except Exception: pass
    for w in _walk(gui):
        if isinstance(w,ttk.Combobox):
            try:
                vals=[str(v) for v in w.cget('values')]
                if any(('CTC' in v or 'Rink Amide' in v) for v in vals):
                    current=str(w.get() or '')
                    w.configure(values=ACTIVE_RESINS)
                    if current in ACTIVE_RESINS: w.set(current)
            except Exception: pass


def _compact_checklist(gui):
    tree=getattr(gui,'progress_tree',None)
    if tree is None: return
    widths={'line':42,'done':48,'checked_at':88,'operation':145,'unit':105,'next_step':145,'note':220}
    try:
        tree.configure(height=16)
        for col in tree['columns']:
            tree.column(col,width=widths.get(col,90),minwidth=30,stretch=(col=='note'),anchor='w')
    except Exception: pass
    # Keep only a compact single-line control band above the table.
    try:
        parent=tree.master
        parent.rowconfigure(1,weight=1,minsize=240)
        for child in parent.winfo_children():
            info=child.grid_info()
            if int(info.get('row',-1))==0:
                try: child.configure(padding=(3,2))
                except Exception: pass
    except Exception: pass
