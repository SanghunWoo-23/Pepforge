"""Windows manual/self-test checklist for GUI release validation with QA recording."""
from __future__ import annotations
from . import gui_common as state

CHECKS = [
    ('Launch', 'Open main_launcher.py or EXE; title shows current version.'),
    ('Multi-select', 'Ctrl/Shift select several Peptide Items; selected rows stay blue.'),
    ('Duplicate', 'With several rows selected, Duplicate creates all selected copies.'),
    ('Delete', 'With several rows selected, Delete removes all selected rows.'),
    ('Drag reorder', 'Drag selected row/block to another position; order changes.'),
    ('Generate', 'Generate / Update fills Selected Plan, Materials, Operations, Cleavage Cocktail.'),
    ('Export', 'Export creates XLSX/CSV and Excel opens them.'),
    ('Loading columns', 'Exported selected tables contain loading_aa_eq/loading_diea_eq/resin_loading_mmol_g/lot_no.'),
    ('Batch Manager', 'Generate Batch updates progress; Cancel stops before remaining items; Export creates detail and consolidated total.'),
    ('DB Editor', 'Validate, Backup, Merge bundled, Reset bundled buttons respond without crashing.'),
    ('CLI alias', 'CLI accepts --sequence, --scale-mmol, --out.'),
    ('Cache policy', 'Release ZIP has no __pycache__, .pytest_cache, outputs, or *.pyc.'),
]


def _manual_rows(gui):
    rows = getattr(gui, '_manual_qa_rows', None)
    if not rows:
        rows = [{'id': i, 'check': title, 'status': 'PENDING', 'detail': detail, 'note': ''} for i, (title, detail) in enumerate(CHECKS, 1)]
        gui._manual_qa_rows = rows
    return rows


def _write_manual(gui):
    import pandas as pd
    state.write_tree(gui.selftest_manual_tree, pd.DataFrame(_manual_rows(gui)))


def _set_manual_status(gui, status: str):
    try:
        sels = gui.selftest_manual_tree.selection()
        rows = _manual_rows(gui)
        if not sels:
            return
        ids = []
        cols = list(gui.selftest_manual_tree['columns'])
        for item in sels:
            values = gui.selftest_manual_tree.item(item, 'values')
            if values and 'id' in cols:
                ids.append(int(values[cols.index('id')]))
        note = ''
        try:
            note = gui.selftest_note.get('1.0', 'end-1c')
        except Exception:
            note = ''
        for row in rows:
            if int(row.get('id', 0)) in ids:
                row['status'] = status
                if note:
                    row['note'] = note
        _write_manual(gui)
    except Exception:
        pass


def save_qa_report(gui):
    try:
        import pandas as pd
        from datetime import datetime
        state.ensure_app_path()
        from spps_planner.user_paths import user_outputs_dir
        out = user_outputs_dir() / f"windows_selftest_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        pd.DataFrame(_manual_rows(gui)).to_csv(out, index=False, encoding='utf-8-sig')
        try: gui.selftest_status.configure(text=f"QA report saved: {out}")
        except Exception: pass
        try: gui._log(f"Windows QA report saved: {out}\n")
        except Exception: pass
        return out
    except Exception as exc:
        try:
            from tkinter import messagebox
            messagebox.showerror('Save QA report', str(exc))
        except Exception: pass


def run_selftest(gui):
    import pandas as pd
    rows=[]
    try:
        rows.append({'check':'Project items count','status':'PASS' if len(getattr(gui,'pm_items',[]))>=1 else 'FAIL','detail':str(len(getattr(gui,'pm_items',[])))})
        inp, meta, tables = state.core_tables(gui)
        rows.append({'check':'Core calculation','status':'PASS','detail':inp.sequence})
        for name in ['selected_plan_core','selected_materials_core','cleavage_cocktail','summary']:
            rows.append({'check':name,'status':'PASS' if not tables[name].empty else 'FAIL','detail':f"rows={len(tables[name])}"})
        plan=tables['selected_plan_core']
        cols=set(plan.columns)
        needed={'resin_loading_mmol_g','loading_aa_eq','loading_diea_eq','lot_no','scale_mmol'}
        rows.append({'check':'Loading metadata columns','status':'PASS' if needed.issubset(cols) else 'FAIL','detail':', '.join(sorted(needed-cols))})
        try:
            from spps_planner.database import validate_compounds_dataframe, load_compounds
            issues = validate_compounds_dataframe(load_compounds())
            errors = 0 if issues.empty else int(issues['level'].eq('ERROR').sum())
            rows.append({'check':'DB schema validation','status':'PASS' if errors == 0 else 'FAIL','detail':f'errors={errors}'})
        except Exception as exc:
            rows.append({'check':'DB schema validation','status':'FAIL','detail':str(exc)})
    except Exception as exc:
        rows.append({'check':'Self-test exception','status':'FAIL','detail':str(exc)})
    df=pd.DataFrame(rows)
    state.write_tree(gui.selftest_tree, df)
    try:
        failed = int(df['status'].eq('FAIL').sum())
        gui.selftest_status.configure(text=f"Code self-test complete: {len(df)-failed} pass / {failed} fail")
    except Exception: pass
    return df


def build_selftest_tab(gui, notebook):
    import tkinter as tk
    import tkinter.ttk as ttk
    frame=ttk.Frame(notebook,padding=8); notebook.add(frame,text='Windows Self-Test')
    frame.rowconfigure(1,weight=1); frame.columnconfigure(0,weight=1)
    top=ttk.Frame(frame); top.grid(row=0,column=0,sticky='ew',pady=(0,6))
    ttk.Button(top,text='Run code self-test',command=lambda: run_selftest(gui)).pack(side='left')
    ttk.Button(top,text='Mark PASS',command=lambda: _set_manual_status(gui, 'PASS')).pack(side='left',padx=(8,0))
    ttk.Button(top,text='Mark FAIL',command=lambda: _set_manual_status(gui, 'FAIL')).pack(side='left')
    ttk.Button(top,text='Mark N/A',command=lambda: _set_manual_status(gui, 'N/A')).pack(side='left')
    ttk.Button(top,text='Save QA Report',command=lambda: save_qa_report(gui)).pack(side='left',padx=(8,0))
    gui.selftest_status=ttk.Label(top,text='Run code self-test, then record Windows manual QA results.',foreground='#555')
    gui.selftest_status.pack(side='left',padx=12)
    nb=ttk.Notebook(frame); nb.grid(row=1,column=0,sticky='nsew')
    gui.selftest_tree=gui._add_tree_tab(nb,'Code Self-Test')
    manual=ttk.Frame(nb); manual.rowconfigure(0,weight=1); manual.rowconfigure(1,weight=0); manual.columnconfigure(0,weight=1); nb.add(manual,text='Manual QA Record')
    # Build a tree directly so the tab stays simple and selectable.
    tree=ttk.Treeview(manual, columns=['id','check','status','detail','note'], show='headings', selectmode='extended')
    for c,w in [('id',55),('check',180),('status',90),('detail',620),('note',280)]:
        tree.heading(c, text=c); tree.column(c, width=w, anchor='w')
    tree.grid(row=0,column=0,sticky='nsew')
    sb=ttk.Scrollbar(manual, orient='vertical', command=tree.yview); sb.grid(row=0,column=1,sticky='ns'); tree.configure(yscrollcommand=sb.set)
    gui.selftest_manual_tree=tree
    note_frame=ttk.Frame(manual); note_frame.grid(row=1,column=0,columnspan=2,sticky='ew',pady=(6,0)); note_frame.columnconfigure(1,weight=1)
    ttk.Label(note_frame,text='Note for selected check').grid(row=0,column=0,sticky='w')
    gui.selftest_note=tk.Text(note_frame,height=2,wrap='word'); gui.selftest_note.grid(row=0,column=1,sticky='ew',padx=(8,0))
    _write_manual(gui)
    run_selftest(gui)
