"""ML Lab panel for modern Tk GUI."""
from __future__ import annotations
from pathlib import Path
from . import gui_common as state

MIN_TRAIN_ROWS = 5


def _log_path():
    state.ensure_app_path()
    from spps_v4_gui.modules.data_log_panel import _log_path as data_log_path
    return data_log_path()


def _models_dir():
    state.ensure_app_path()
    from spps_planner.user_paths import user_models_dir
    return user_models_dir()


def _outputs_dir():
    state.ensure_app_path()
    from spps_planner.user_paths import user_outputs_dir
    return user_outputs_dir()


def _status_df(message: str, level: str = 'INFO'):
    import pandas as pd
    return pd.DataFrame([{'level': level, 'message': message}])


def refresh_ml(gui):
    try:
        import pandas as pd
        path=_log_path(); df=pd.read_csv(path) if path.exists() and path.stat().st_size > 0 else pd.DataFrame()
        state.write_tree(gui.ml_data_tree, df)
        cols=list(df.columns)
        try: gui.ml_target_combo.configure(values=cols)
        except Exception: pass
        target = state.get_var(gui, 'ml_target', '')
        valid_rows = 0
        if target and target in df.columns:
            valid_rows = int(df[target].notna().sum())
        msg = f"Actual run rows: {len(df)}. Need at least {MIN_TRAIN_ROWS} rows with target values before training. Data path: {path}"
        try: gui.ml_status.configure(text=msg)
        except Exception: pass
        state.write_tree(gui.ml_result_tree, _status_df(msg))
        return df
    except Exception as exc:
        try:
            from tkinter import messagebox
            messagebox.showerror('ML Lab', str(exc))
        except Exception: pass


def train_model(gui):
    try:
        import pandas as pd
        state.ensure_app_path()
        from spps_planner.ml import train_supervised
        target=state.get_var(gui,'ml_target','')
        task=state.get_var(gui,'ml_task','regression')
        if not target: raise ValueError('Choose target column first.')
        path = _log_path()
        df = pd.read_csv(path) if path.exists() and path.stat().st_size > 0 else pd.DataFrame()
        if target not in df.columns:
            raise ValueError(f'Target column not found: {target}')
        valid = df[target].dropna()
        if len(valid) < MIN_TRAIN_ROWS:
            msg = f'Need at least {MIN_TRAIN_ROWS} actual run rows with target values. Current valid rows for {target}: {len(valid)}. Use Data Log first.'
            state.write_tree(gui.ml_result_tree, _status_df(msg, 'NEED_DATA'))
            try: gui.ml_status.configure(text=msg)
            except Exception: pass
            return None
        out=_models_dir(); out.mkdir(exist_ok=True)
        metrics=train_supervised(path, target, out/f'{target}_{task}.joblib', task=task)
        state.write_tree(gui.ml_result_tree, pd.DataFrame([metrics]))
        try: gui._log(f"ML model trained: {metrics}\n")
        except Exception: pass
        return metrics
    except Exception as exc:
        try:
            from tkinter import messagebox
            messagebox.showerror('Train model', str(exc))
        except Exception: pass


def run_anomaly(gui):
    try:
        state.ensure_app_path()
        from spps_planner.ml import detect_anomalies
        out=_outputs_dir()/'actual_runs_anomaly.csv'; out.parent.mkdir(exist_ok=True)
        df=detect_anomalies(_log_path(), out)
        state.write_tree(gui.ml_result_tree, df)
        try: gui._log(f"Anomaly detection saved: {out}\n")
        except Exception: pass
    except Exception as exc:
        try:
            from tkinter import messagebox
            messagebox.showerror('Anomaly detection', str(exc))
        except Exception: pass


def build_ml_lab_tab(gui, notebook):
    import tkinter as tk
    import tkinter.ttk as ttk
    frame=ttk.Frame(notebook,padding=8); notebook.add(frame,text='ML Lab')
    frame.rowconfigure(2,weight=1); frame.columnconfigure(0,weight=1)
    gui.ml_target=tk.StringVar(value=''); gui.ml_task=tk.StringVar(value='regression')
    top=ttk.Frame(frame); top.grid(row=0,column=0,sticky='ew',pady=(0,6))
    ttk.Button(top,text='Refresh actual_runs.csv',command=lambda: refresh_ml(gui)).pack(side='left')
    ttk.Label(top,text='Target').pack(side='left',padx=(12,2))
    gui.ml_target_combo=ttk.Combobox(top,textvariable=gui.ml_target,width=22,state='readonly'); gui.ml_target_combo.pack(side='left')
    ttk.Label(top,text='Task').pack(side='left',padx=(12,2))
    ttk.Combobox(top,textvariable=gui.ml_task,values=['regression','classification'],width=14,state='readonly').pack(side='left')
    ttk.Button(top,text='Train model',command=lambda: train_model(gui)).pack(side='left',padx=6)
    ttk.Button(top,text='Run anomaly detection',command=lambda: run_anomaly(gui)).pack(side='left')
    gui.ml_status=ttk.Label(frame,text='Need at least 5 actual run rows with target values before training.',foreground='#555')
    gui.ml_status.grid(row=1,column=0,sticky='w',pady=(0,6))
    nb=ttk.Notebook(frame); nb.grid(row=2,column=0,sticky='nsew')
    gui.ml_data_tree=gui._add_tree_tab(nb,'Actual Run Data')
    gui.ml_result_tree=gui._add_tree_tab(nb,'ML Results')
    refresh_ml(gui)
