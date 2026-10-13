"""Compound DB full-row viewer/editor for modern Tk GUI."""
from __future__ import annotations
from . import gui_common as state


def _load_df():
    state.ensure_app_path()
    from spps_planner.database import load_compounds
    return load_compounds()


def _save_df(df):
    state.ensure_app_path()
    from spps_planner.database import save_compounds
    save_compounds(df, validate=True, backup=True)


def _status(gui, text: str):
    try: gui.db_status.configure(text=text)
    except Exception: pass


def _current_df(gui):
    try:
        df = getattr(gui, '_db_current_df')
        if df is not None:
            return df
    except Exception:
        pass
    return _load_df()


def refresh_db(gui):
    try:
        df=_load_df()
        query=state.get_var(gui,'db_search','').strip().lower()
        if query:
            mask=df.astype(str).apply(lambda col: col.str.lower().str.contains(query, na=False)).any(axis=1)
            df=df[mask]
        gui._db_current_df=df.copy()
        state.write_tree(gui.db_tree, df.head(1000))
        _status(gui, f"Rows shown: {len(df)} | Full row editor enabled")
        try:
            gui.db_column_combo.configure(values=list(df.columns))
        except Exception:
            pass
        return df
    except Exception as exc:
        try:
            from tkinter import messagebox
            messagebox.showerror('DB Editor', str(exc))
        except Exception: pass
        return None


def _write_row_tree(gui, row: dict):
    import pandas as pd
    gui._db_row_values = dict(row or {})
    kv = pd.DataFrame([{'column': k, 'value': v} for k, v in gui._db_row_values.items()])
    state.write_tree(gui.db_row_tree, kv)
    try:
        gui.db_column_combo.configure(values=list(gui._db_row_values.keys()))
    except Exception:
        pass


def load_selected(gui):
    try:
        tree=gui.db_tree
        sel=tree.selection()
        if not sel: return
        cols=list(tree['columns']); vals=tree.item(sel[0],'values')
        row=dict(zip(cols, vals))
        gui._db_selected_original_token = row.get('Token','')
        # Keep the fast six-field editor populated for common edits.
        gui.db_token.set(row.get('Token',''))
        gui.db_class.set(row.get('Class',''))
        gui.db_reagent_form.set(row.get('Reagent/protected form',''))
        gui.db_reagent_mw.set(row.get('Reagent MW (g/mol)',''))
        gui.db_product_mw.set(row.get('Product MW contribution (g/mol)',''))
        gui.db_active.set(row.get('Active?',''))
        _write_row_tree(gui, row)
    except Exception: pass


def load_row_column(gui):
    try:
        sel=gui.db_row_tree.selection()
        if not sel: return
        vals=gui.db_row_tree.item(sel[0],'values')
        if not vals: return
        col=str(vals[0]); val='' if len(vals)<2 else vals[1]
        gui.db_full_column.set(col)
        gui.db_full_value.delete('1.0','end')
        gui.db_full_value.insert('1.0', str(val))
    except Exception: pass


def set_column_value(gui):
    try:
        col=state.get_var(gui,'db_full_column','').strip()
        if not col:
            raise ValueError('Choose or type a DB column name first.')
        value=gui.db_full_value.get('1.0','end-1c')
        row=dict(getattr(gui,'_db_row_values',{}) or {})
        row[col]=value
        _write_row_tree(gui,row)
    except Exception as exc:
        try:
            from tkinter import messagebox
            messagebox.showerror('Set DB column', str(exc))
        except Exception: pass


def new_blank_row(gui):
    try:
        df=_load_df()
        row={c:'' for c in df.columns}
        row['Active?']='yes'
        _write_row_tree(gui,row)
        for var in [gui.db_token, gui.db_class, gui.db_reagent_form, gui.db_reagent_mw, gui.db_product_mw]: var.set('')
        gui.db_active.set('yes')
    except Exception as exc:
        try:
            from tkinter import messagebox
            messagebox.showerror('New DB row', str(exc))
        except Exception: pass


def _merge_fast_fields(gui, row: dict) -> dict:
    fast={
        'Token': gui.db_token.get().strip(),
        'Class': gui.db_class.get().strip(),
        'Reagent/protected form': gui.db_reagent_form.get().strip(),
        'Reagent MW (g/mol)': gui.db_reagent_mw.get().strip(),
        'Product MW contribution (g/mol)': gui.db_product_mw.get().strip(),
        'Active?': gui.db_active.get().strip() or 'yes',
    }
    # Only overwrite if the fast field has content, except Active defaults to yes.
    for k,v in fast.items():
        if v or k == 'Active?': row[k]=v
    return row


def validate_db(gui):
    try:
        import pandas as pd
        state.ensure_app_path()
        from spps_planner.database import validate_compounds_dataframe, compounds_db_source
        df=_load_df()
        issues=validate_compounds_dataframe(df)
        if issues.empty:
            issues=pd.DataFrame([{'level':'OK','column':'all','row_index':'','issue':'No schema validation issue detected.','value':''}])
        state.write_tree(gui.db_audit_tree, issues)
        src=compounds_db_source()
        _status(gui, f"DB source: {'user override' if src.get('using_user_override') else 'bundled'} | Validation rows: {len(issues)}")
        return issues
    except Exception as exc:
        try:
            from tkinter import messagebox
            messagebox.showerror('Validate DB', str(exc))
        except Exception: pass


def show_db_source(gui):
    try:
        import pandas as pd
        state.ensure_app_path()
        from spps_planner.database import compounds_db_source
        src=compounds_db_source()
        df=pd.DataFrame([src])
        state.write_tree(gui.db_audit_tree, df)
        _status(gui, f"Active DB: {src.get('active_path','')}")
        return src
    except Exception as exc:
        try:
            from tkinter import messagebox
            messagebox.showerror('DB source', str(exc))
        except Exception: pass


def backup_db(gui):
    try:
        import pandas as pd
        state.ensure_app_path()
        from spps_planner.database import backup_user_compounds
        backup=backup_user_compounds()
        msg = f"Backup created: {backup}" if backup else "No user override DB exists yet; nothing to back up."
        state.write_tree(gui.db_audit_tree, pd.DataFrame([{'level':'INFO','message':msg}]))
        _status(gui,msg)
        return backup
    except Exception as exc:
        try:
            from tkinter import messagebox
            messagebox.showerror('Backup DB', str(exc))
        except Exception: pass


def reset_to_bundled(gui):
    try:
        import pandas as pd
        from tkinter import messagebox
        state.ensure_app_path()
        from spps_planner.database import reset_user_compounds
        ok=True
        try:
            ok=messagebox.askyesno('Reset DB', 'Reset user override DB to bundled DB? A backup will be made first.')
        except Exception:
            ok=True
        if not ok: return None
        target=reset_user_compounds()
        refresh_db(gui); audit_db(gui)
        msg=f"User DB reset to bundled DB: {target}"
        state.write_tree(gui.db_audit_tree, pd.DataFrame([{'level':'INFO','message':msg}]))
        _status(gui,msg)
        return target
    except Exception as exc:
        try:
            from tkinter import messagebox
            messagebox.showerror('Reset DB', str(exc))
        except Exception: pass


def merge_bundled(gui):
    try:
        import pandas as pd
        state.ensure_app_path()
        from spps_planner.database import merge_bundled_compounds_into_user
        result=merge_bundled_compounds_into_user()
        refresh_db(gui); audit_db(gui)
        state.write_tree(gui.db_audit_tree, pd.DataFrame([result]))
        _status(gui, f"Merged bundled DB into user override. Added rows: {result.get('added_rows')}")
        return result
    except Exception as exc:
        try:
            from tkinter import messagebox
            messagebox.showerror('Merge DB', str(exc))
        except Exception: pass


def save_full_row(gui):
    try:
        import pandas as pd
        df=_load_df()
        row=dict(getattr(gui,'_db_row_values',{}) or {})
        row=_merge_fast_fields(gui,row)
        token=str(row.get('Token','')).strip()
        if not token:
            raise ValueError('Token is required.')
        for c in row.keys():
            if c not in df.columns: df[c]=''
        for c in df.columns:
            row.setdefault(c,'')
        mask=df['Token'].fillna('').astype(str).str.lower().eq(token.lower()) if 'Token' in df.columns else pd.Series([False]*len(df))
        if mask.any():
            idx=df.index[mask][0]
            for k,v in row.items(): df.at[idx,k]=v
        else:
            df=pd.concat([df, pd.DataFrame([{c: row.get(c,'') for c in df.columns}])], ignore_index=True)
        state.ensure_app_path()
        from spps_planner.database import validate_compounds_dataframe, normalize_compounds_dataframe
        df = normalize_compounds_dataframe(df)
        issues = validate_compounds_dataframe(df)
        if not issues.empty and issues['level'].eq('ERROR').any():
            state.write_tree(gui.db_audit_tree, issues)
            raise ValueError('DB validation failed. See DB Audit tab for details before saving.')
        _save_df(df)
        refresh_db(gui)
        _write_row_tree(gui,row)
        validate_db(gui)
        try: gui._log(f"DB full row saved/upserted token: {token}\n")
        except Exception: pass
    except Exception as exc:
        try:
            from tkinter import messagebox
            messagebox.showerror('Save full DB row', str(exc))
        except Exception: pass


def upsert_row(gui):
    # Backward-compatible button path now uses the full-row saver.
    return save_full_row(gui)


def audit_db(gui):
    try:
        state.ensure_app_path()
        from spps_planner.database import audit_compound_database, validate_compounds_dataframe, load_compounds
        df=audit_compound_database()
        schema_issues = validate_compounds_dataframe(load_compounds())
        if not schema_issues.empty:
            schema_issues = schema_issues.rename(columns={'column':'item','issue':'issue'})
            schema_issues['table'] = 'schema_validation'
            schema_issues['recommended_action'] = schema_issues.get('value','')
            cols=['level','table','item','issue','recommended_action']
            df = __import__('pandas').concat([df, schema_issues.reindex(columns=cols)], ignore_index=True)
        state.write_tree(gui.db_audit_tree, df)
        return df
    except Exception as exc:
        try:
            from tkinter import messagebox
            messagebox.showerror('DB Audit', str(exc))
        except Exception: pass


def build_db_editor_tab(gui, notebook):
    import tkinter as tk
    import tkinter.ttk as ttk
    frame=ttk.Frame(notebook, padding=8); notebook.add(frame, text='DB Editor')
    frame.rowconfigure(3, weight=1); frame.columnconfigure(0, weight=1)
    gui.db_search=tk.StringVar(value='')
    top=ttk.Frame(frame); top.grid(row=0,column=0,sticky='ew',pady=(0,6)); top.columnconfigure(1, weight=1)
    ttk.Label(top,text='Search').grid(row=0,column=0,sticky='w')
    ttk.Entry(top,textvariable=gui.db_search).grid(row=0,column=1,sticky='ew',padx=6)
    ttk.Button(top,text='Refresh',command=lambda: refresh_db(gui)).grid(row=0,column=2,padx=2)
    ttk.Button(top,text='Audit',command=lambda: audit_db(gui)).grid(row=0,column=3,padx=2)
    ttk.Button(top,text='Validate',command=lambda: validate_db(gui)).grid(row=0,column=4,padx=2)
    ttk.Button(top,text='DB Source',command=lambda: show_db_source(gui)).grid(row=0,column=5,padx=2)
    gui.db_status=ttk.Label(top,text='Rows shown: 0'); gui.db_status.grid(row=0,column=6,padx=(10,0))

    edit=ttk.LabelFrame(frame,text='Common fields / quick edit',padding=6); edit.grid(row=1,column=0,sticky='ew',pady=(0,6))
    for i in range(6): edit.columnconfigure(i, weight=1)
    gui.db_token=tk.StringVar(); gui.db_class=tk.StringVar(); gui.db_reagent_form=tk.StringVar(); gui.db_reagent_mw=tk.StringVar(); gui.db_product_mw=tk.StringVar(); gui.db_active=tk.StringVar(value='yes')
    fields=[('Token',gui.db_token),('Class',gui.db_class),('Reagent/protected form',gui.db_reagent_form),('Reagent MW',gui.db_reagent_mw),('Product MW contribution',gui.db_product_mw),('Active?',gui.db_active)]
    for i,(lab,var) in enumerate(fields):
        ttk.Label(edit,text=lab).grid(row=0,column=i,sticky='w')
        ttk.Entry(edit,textvariable=var,width=18).grid(row=1,column=i,sticky='ew',padx=2)
    ttk.Button(edit,text='Load selected',command=lambda: load_selected(gui)).grid(row=2,column=0,sticky='ew',pady=(5,0))
    ttk.Button(edit,text='Save / Upsert full row',command=lambda: save_full_row(gui)).grid(row=2,column=1,sticky='ew',pady=(5,0))
    ttk.Button(edit,text='New blank row',command=lambda: new_blank_row(gui)).grid(row=2,column=2,sticky='ew',pady=(5,0))
    ttk.Button(edit,text='Backup DB',command=lambda: backup_db(gui)).grid(row=2,column=3,sticky='ew',pady=(5,0))
    ttk.Button(edit,text='Merge bundled',command=lambda: merge_bundled(gui)).grid(row=2,column=4,sticky='ew',pady=(5,0))
    ttk.Button(edit,text='Reset bundled',command=lambda: reset_to_bundled(gui)).grid(row=2,column=5,sticky='ew',pady=(5,0))

    full=ttk.LabelFrame(frame,text='Full-row editor: any DB column',padding=6); full.grid(row=2,column=0,sticky='ew',pady=(0,6))
    full.columnconfigure(1,weight=1); full.columnconfigure(3,weight=1)
    gui.db_full_column=tk.StringVar(value='')
    ttk.Label(full,text='Column').grid(row=0,column=0,sticky='w')
    gui.db_column_combo=ttk.Combobox(full,textvariable=gui.db_full_column,values=[],width=34)
    gui.db_column_combo.grid(row=0,column=1,sticky='ew',padx=4)
    ttk.Label(full,text='Value').grid(row=0,column=2,sticky='w',padx=(8,0))
    gui.db_full_value=tk.Text(full,height=2,wrap='word')
    gui.db_full_value.grid(row=0,column=3,sticky='ew',padx=4)
    ttk.Button(full,text='Load selected column',command=lambda: load_row_column(gui)).grid(row=0,column=4,padx=2)
    ttk.Button(full,text='Set column value',command=lambda: set_column_value(gui)).grid(row=0,column=5,padx=2)

    nb=ttk.Notebook(frame); nb.grid(row=3,column=0,sticky='nsew')
    gui.db_tree=gui._add_tree_tab(nb,'Compounds')
    gui.db_row_tree=gui._add_tree_tab(nb,'Selected Row Key/Value')
    gui.db_audit_tree=gui._add_tree_tab(nb,'DB Audit')
    try: gui.db_tree.bind('<<TreeviewSelect>>', lambda _e: load_selected(gui), add=True)
    except Exception: pass
    try: gui.db_row_tree.bind('<<TreeviewSelect>>', lambda _e: load_row_column(gui), add=True)
    except Exception: pass
    refresh_db(gui); audit_db(gui)
