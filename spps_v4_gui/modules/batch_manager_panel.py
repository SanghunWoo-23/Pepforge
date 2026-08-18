"""Batch Manager tab for modern Tk GUI with real chunked cancel and consolidated totals."""
from __future__ import annotations
from . import gui_common as state


def _set_progress(gui, done: int, total: int, text: str = ''):
    try:
        gui.batch_progress.configure(maximum=max(total, 1), value=done)
        gui.batch_status.configure(text=text or f"{done}/{total}")
        gui.update_idletasks()
    except Exception:
        pass


def cancel_batch(gui):
    gui._batch_cancel_requested = True
    try: gui.batch_status.configure(text='Cancel requested...')
    except Exception: pass


def _one_summary_row(gui, i: int, item: dict):
    gui._v2097_active_index=i
    state.load_item_to_editor(gui, i)
    _, meta, tables = state.core_tables(gui)
    summ = tables['summary'].iloc[0].to_dict() if not tables['summary'].empty else {}
    return {**meta, **{f"summary_{k}":v for k,v in summ.items() if k not in meta}, 'status':'OK'}


def _one_material_df(gui, i: int):
    gui._v2097_active_index=i
    state.load_item_to_editor(gui, i)
    _, meta, tables = state.core_tables(gui)
    mat = tables['selected_materials_core'].copy()
    for k in ['project','peptide','sequence','lot_no','scale_mmol','resin_text']:
        mat[k] = meta.get(k, '')
    mat['batch_item_index'] = i
    return mat


def consolidate_materials(mat_df):
    """Return reagent/material totals across a batch while preserving mL-only behavior."""
    import pandas as pd
    if mat_df is None or mat_df.empty:
        return pd.DataFrame()
    df = mat_df.copy()
    keys = [c for c in ['material','class','reagent','unit','MW','density_g_mL','physical_state'] if c in df.columns]
    if not keys:
        return df
    numeric = [c for c in ['planned_mmol','planned_g','planned_mg','planned_mL'] if c in df.columns]
    for c in numeric:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)
    agg = {c: 'sum' for c in numeric}
    for c in ['source','warning']:
        if c in df.columns:
            agg[c] = lambda s: ' | '.join(sorted({str(x) for x in s if str(x).strip() and str(x).lower() != 'nan'}))[:2000]
    out = df.groupby(keys, dropna=False, as_index=False).agg(agg)
    # Liquid/solution rows remain mL-only in consolidated table as well.
    if 'unit' in out.columns:
        liquid_mask = out['unit'].fillna('').astype(str).str.lower().eq('ml')
        for col in ['planned_g','planned_mg']:
            if col in out.columns:
                out.loc[liquid_mask, col] = 0.0
    if 'batch_item_count' not in out.columns:
        out['batch_item_count'] = len(set(df.get('batch_item_index', []))) if 'batch_item_index' in df.columns else ''
    return out


def _batch_rows(gui):
    import pandas as pd
    rows=[]
    items=list(getattr(gui,'pm_items',[]) or [])
    total=len(items)
    old=getattr(gui,'_v2097_active_index',0)
    gui._batch_cancel_requested = False
    for i,item in enumerate(items):
        if getattr(gui, '_batch_cancel_requested', False):
            rows.append({'index':i,'project':item.get('project',''),'peptide':item.get('peptide',''),'sequence':item.get('sequence',''),'status':'CANCELLED'})
            break
        _set_progress(gui, i, total, f"Calculating {i+1}/{total}: {item.get('peptide','')}")
        try:
            rows.append(_one_summary_row(gui, i, item))
        except Exception as exc:
            rows.append({'index':i,'project':item.get('project',''),'peptide':item.get('peptide',''),'sequence':item.get('sequence',''),'status':'ERROR','error':str(exc)})
    try:
        gui._v2097_active_index=old
        state.load_item_to_editor(gui, old)
    except Exception: pass
    _set_progress(gui, len(rows), total, f"Done: {len(rows)}/{total}")
    return pd.DataFrame(rows)


def _batch_materials(gui):
    import pandas as pd
    mats=[]
    items=list(getattr(gui,'pm_items',[]) or [])
    total=len(items)
    old=getattr(gui,'_v2097_active_index',0)
    for i,item in enumerate(items):
        if getattr(gui, '_batch_cancel_requested', False):
            break
        _set_progress(gui, i, total, f"Aggregating materials {i+1}/{total}: {item.get('peptide','')}")
        try:
            mats.append(_one_material_df(gui, i))
        except Exception:
            pass
    try:
        gui._v2097_active_index=old
        state.load_item_to_editor(gui, old)
    except Exception: pass
    return pd.concat(mats, ignore_index=True) if mats else pd.DataFrame()


def generate_batch(gui):
    try:
        rows = _batch_rows(gui)
        state.write_tree(gui.batch_summary_tree, rows)
        mat_df = _batch_materials(gui)
        total_df = consolidate_materials(mat_df)
        state.write_tree(gui.batch_materials_tree, mat_df)
        state.write_tree(gui.batch_materials_total_tree, total_df)
        try: gui._log(f"Batch Manager generated {len(rows)} item summaries and {len(total_df)} consolidated material rows.\n")
        except Exception: pass
        return rows, mat_df, total_df
    except Exception as exc:
        try:
            from tkinter import messagebox
            messagebox.showerror('Batch Manager', str(exc))
        except Exception: pass
        return None


def generate_batch_async(gui):
    """Run one item per Tk event-loop tick so Cancel can be processed."""
    import pandas as pd
    items=list(getattr(gui,'pm_items',[]) or [])
    gui._batch_cancel_requested = False
    gui._batch_async_rows=[]
    gui._batch_async_mats=[]
    gui._batch_async_index=0
    gui._batch_async_total=len(items)
    gui._batch_async_old=getattr(gui,'_v2097_active_index',0)
    _set_progress(gui, 0, len(items), 'Starting batch...')

    def step():
        i=getattr(gui,'_batch_async_index',0)
        total=getattr(gui,'_batch_async_total',len(items))
        if getattr(gui,'_batch_cancel_requested',False) or i >= total:
            try:
                old=getattr(gui,'_batch_async_old',0)
                gui._v2097_active_index=old
                state.load_item_to_editor(gui, old)
            except Exception: pass
            rows=pd.DataFrame(getattr(gui,'_batch_async_rows',[]))
            mats=pd.concat(getattr(gui,'_batch_async_mats',[]), ignore_index=True) if getattr(gui,'_batch_async_mats',[]) else pd.DataFrame()
            totals=consolidate_materials(mats)
            state.write_tree(gui.batch_summary_tree, rows)
            state.write_tree(gui.batch_materials_tree, mats)
            state.write_tree(gui.batch_materials_total_tree, totals)
            status = 'Cancelled' if getattr(gui,'_batch_cancel_requested',False) else 'Done'
            _set_progress(gui, len(rows), max(total,1), f"{status}: {len(rows)}/{total}")
            return
        item=items[i]
        _set_progress(gui, i, total, f"Calculating {i+1}/{total}: {item.get('peptide','')}")
        try:
            gui._batch_async_rows.append(_one_summary_row(gui, i, item))
            gui._batch_async_mats.append(_one_material_df(gui, i))
        except Exception as exc:
            gui._batch_async_rows.append({'index':i,'project':item.get('project',''),'peptide':item.get('peptide',''),'sequence':item.get('sequence',''),'status':'ERROR','error':str(exc)})
        gui._batch_async_index=i+1
        try: gui.after(1, step)
        except Exception: step()
    try: gui.after(1, step)
    except Exception: step()
    return None


def export_batch(gui):
    try:
        import pandas as pd
        out = state.project_outdir(gui) / 'batch_manager'
        out.mkdir(parents=True, exist_ok=True)
        result = generate_batch(gui)
        if result is None: return None
        rows, mat_df, total_df = result
        rows.to_csv(out/'batch_summary.csv', index=False, encoding='utf-8-sig')
        mat_df.to_csv(out/'batch_materials_detail.csv', index=False, encoding='utf-8-sig')
        total_df.to_csv(out/'batch_materials_consolidated_total.csv', index=False, encoding='utf-8-sig')
        with pd.ExcelWriter(out/'batch_manager_outputs.xlsx', engine='openpyxl') as w:
            rows.to_excel(w, index=False, sheet_name='01_BATCH_SUMMARY')
            mat_df.to_excel(w, index=False, sheet_name='02_MATERIALS_DETAIL')
            total_df.to_excel(w, index=False, sheet_name='03_MATERIALS_TOTAL')
        try: gui._log(f"Batch exported: {out}\n")
        except Exception: pass
        return out
    except Exception as exc:
        try:
            from tkinter import messagebox
            messagebox.showerror('Batch export', str(exc))
        except Exception: pass
        return None


def build_batch_tab(gui, notebook):
    import tkinter.ttk as ttk
    frame=ttk.Frame(notebook, padding=8); notebook.add(frame, text='Batch Manager')
    frame.rowconfigure(2, weight=1); frame.columnconfigure(0, weight=1)
    bar=ttk.Frame(frame); bar.grid(row=0,column=0,sticky='ew',pady=(0,6))
    ttk.Button(bar,text='Generate Batch',command=lambda: generate_batch_async(gui)).pack(side='left')
    ttk.Button(bar,text='Export Batch',command=lambda: export_batch(gui)).pack(side='left',padx=6)
    ttk.Button(bar,text='Cancel',command=lambda: cancel_batch(gui)).pack(side='left')
    ttk.Label(bar,text='Generate uses chunked Tk processing so Cancel can be handled between items.',foreground='#555').pack(side='left',padx=10)
    prog=ttk.Frame(frame); prog.grid(row=1,column=0,sticky='ew',pady=(0,6)); prog.columnconfigure(0,weight=1)
    gui.batch_progress=ttk.Progressbar(prog,mode='determinate')
    gui.batch_progress.grid(row=0,column=0,sticky='ew')
    gui.batch_status=ttk.Label(prog,text='Ready')
    gui.batch_status.grid(row=0,column=1,sticky='e',padx=(8,0))
    nb=ttk.Notebook(frame); nb.grid(row=2,column=0,sticky='nsew')
    gui.batch_summary_tree = gui._add_tree_tab(nb, 'Batch Summary')
    gui.batch_materials_tree = gui._add_tree_tab(nb, 'Batch Materials - Detail')
    gui.batch_materials_total_tree = gui._add_tree_tab(nb, 'Batch Materials - Consolidated Total')
