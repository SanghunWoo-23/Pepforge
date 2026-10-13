"""Actual run data log panel for modern Tk GUI."""
from __future__ import annotations
from datetime import datetime
from . import gui_common as state


def _log_path():
    state.ensure_app_path()
    from spps_planner.user_paths import user_data_file
    from spps_planner.database import DATA_DIR
    import shutil
    target = user_data_file('actual_runs.csv')
    if not target.exists():
        src = DATA_DIR / 'actual_runs.csv'
        tmpl = DATA_DIR / 'actual_runs_template.csv'
        if src.exists():
            shutil.copy2(src, target)
        elif tmpl.exists():
            shutil.copy2(tmpl, target)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('', encoding='utf-8')
    return target


def refresh_log(gui):
    try:
        import pandas as pd
        path=_log_path()
        df=pd.read_csv(path) if path.exists() and path.stat().st_size > 0 else pd.DataFrame()
        state.write_tree(gui.data_log_tree, df)
        try: gui.data_log_status.configure(text=f"Rows: {len(df)} | {path}")
        except Exception: pass
        return df
    except Exception as exc:
        try:
            from tkinter import messagebox
            messagebox.showerror('Data Log', str(exc))
        except Exception: pass


def append_current(gui):
    try:
        import pandas as pd
        inp, meta, tables = state.core_tables(gui)
        row=dict(meta)
        row.update({'date': datetime.now().isoformat(timespec='seconds'), 'run_id': f"{meta.get('lot_no','')}_{datetime.now().strftime('%H%M%S')}",
                    'planned_dmf_mL': tables['summary'].iloc[0].get('total_DMF_mL','') if not tables['summary'].empty else '',
                    'planned_tfa_mL': tables['summary'].iloc[0].get('total_TFA_mL','') if not tables['summary'].empty else '',
                    'actual_yield_percent': state.get_var(gui,'actual_yield_percent',''),
                    'actual_purity_percent': state.get_var(gui,'actual_purity_percent',''),
                    'issue_note': state.get_var(gui,'actual_issue_note','')})
        path=_log_path(); old=pd.read_csv(path) if path.exists() and path.stat().st_size > 0 else pd.DataFrame()
        pd.concat([old,pd.DataFrame([row])], ignore_index=True).to_csv(path,index=False,encoding='utf-8-sig')
        refresh_log(gui)
        try: gui._log(f"Actual run appended: {path}\n")
        except Exception: pass
    except Exception as exc:
        try:
            from tkinter import messagebox
            messagebox.showerror('Append actual run', str(exc))
        except Exception: pass


def import_log(gui):
    try:
        from tkinter import filedialog
        import pandas as pd
        path=filedialog.askopenfilename(filetypes=[('CSV/XLSX','*.csv *.xlsx'),('All files','*.*')])
        if not path: return
        new=pd.read_csv(path) if path.lower().endswith('.csv') else pd.read_excel(path)
        target=_log_path(); old=pd.read_csv(target) if target.exists() and target.stat().st_size > 0 else pd.DataFrame()
        pd.concat([old,new], ignore_index=True).to_csv(target,index=False,encoding='utf-8-sig')
        refresh_log(gui)
    except Exception as exc:
        try:
            from tkinter import messagebox
            messagebox.showerror('Import actual run', str(exc))
        except Exception: pass


def build_data_log_tab(gui, notebook):
    import tkinter as tk
    import tkinter.ttk as ttk
    frame=ttk.Frame(notebook,padding=8); notebook.add(frame,text='Data Log')
    frame.rowconfigure(2,weight=1); frame.columnconfigure(0,weight=1)
    gui.actual_yield_percent=tk.StringVar(value=''); gui.actual_purity_percent=tk.StringVar(value=''); gui.actual_issue_note=tk.StringVar(value='')
    top=ttk.LabelFrame(frame,text='Append current planned run with actual results',padding=6); top.grid(row=0,column=0,sticky='ew',pady=(0,6))
    top.columnconfigure(5,weight=1)
    ttk.Label(top,text='Yield %').grid(row=0,column=0); ttk.Entry(top,textvariable=gui.actual_yield_percent,width=10).grid(row=0,column=1,padx=4)
    ttk.Label(top,text='Purity %').grid(row=0,column=2); ttk.Entry(top,textvariable=gui.actual_purity_percent,width=10).grid(row=0,column=3,padx=4)
    ttk.Label(top,text='Note').grid(row=0,column=4); ttk.Entry(top,textvariable=gui.actual_issue_note).grid(row=0,column=5,sticky='ew',padx=4)
    ttk.Button(top,text='Append current run',command=lambda: append_current(gui)).grid(row=0,column=6,padx=4)
    bar=ttk.Frame(frame); bar.grid(row=1,column=0,sticky='ew',pady=(0,6))
    ttk.Button(bar,text='Refresh',command=lambda: refresh_log(gui)).pack(side='left')
    ttk.Button(bar,text='Import CSV/XLSX',command=lambda: import_log(gui)).pack(side='left',padx=6)
    gui.data_log_status=ttk.Label(bar,text='Rows: 0'); gui.data_log_status.pack(side='left',padx=12)
    nb=ttk.Notebook(frame); nb.grid(row=2,column=0,sticky='nsew')
    gui.data_log_tree=gui._add_tree_tab(nb,'Actual Runs')
    refresh_log(gui)
