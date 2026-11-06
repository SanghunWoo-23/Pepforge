"""V8 sequence-risk inspection window; never mutates the peptide or synthesis plan."""
from __future__ import annotations

import csv
import json
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from suite_gui.sequence_risk_map_v8 import build_sequence_risk_map
from suite_gui.v8_decision_support import decision_report_from_risk, export_experiment_record


def export_risk_report(report: dict, path: str | Path) -> Path:
    """Export an auditable immutable snapshot; no lab history or private datasets."""
    destination = Path(path)
    if destination.suffix.lower() == '.csv':
        with destination.open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['sequence','rule_id','severity','positions_N_to_C','title','reason','operator_consideration','source_class','experimental_observation'])
            for finding in report['findings']:
                writer.writerow([report['sequence'], finding['rule_id'], finding['severity'],
                    ','.join(map(str,finding['positions'])), finding['title'], finding['reason'],
                    finding['operator_consideration'], finding['provenance']['source_class'], False])
    elif destination.suffix.lower() == '.json':
        destination.write_text(json.dumps(report, ensure_ascii=False, indent=2),encoding='utf-8')
    else:
        raise ValueError('Supported exports: .json and .csv')
    return destination


def open_sequence_risk_window(gui):
    """Read current unsaved editor input, not a potentially stale generated plan."""
    window = tk.Toplevel(gui)
    window.title('V8 Sequence Risk Map | Rule-based review')
    window.geometry('1080x690')
    window.minsize(780,480)
    holder = ttk.Frame(window, padding=10)
    holder.pack(fill='both', expand=True)
    headline = tk.StringVar()
    ttk.Label(holder, textvariable=headline, font=('Segoe UI', 11, 'bold')).pack(anchor='w')
    ttk.Label(holder,text='N→C residue numbers | Rule-based heuristic (not experimental success probability). No plan changes are applied.',wraplength=950).pack(anchor='w',pady=(3,8))
    residue_frame=ttk.LabelFrame(holder,text='Residue map (select a row to inspect findings)')
    residue_frame.pack(fill='x',pady=4)
    position_tree=ttk.Treeview(residue_frame,columns=('position','residue','severity','rules'),show='headings',height=7,selectmode='browse')
    for key,label,width in [('position','N→C position',110),('residue','Residue / token',160),('severity','Risk',100),('rules','Rule IDs',590)]:
        position_tree.heading(key,text=label);position_tree.column(key,width=width,stretch=key=='rules')
    position_tree.pack(fill='x',expand=True)
    for level in ('HIGH','CRITICAL','WARNING','INFO'):
        position_tree.tag_configure(level,foreground={'HIGH':'#9b2500','CRITICAL':'#9b2500','WARNING':'#855b00','INFO':'#17598b'}[level])
    findings_frame=ttk.LabelFrame(holder,text='Triggered rules and considerations')
    findings_frame.pack(fill='both',expand=True,pady=5)
    rules_tree=ttk.Treeview(findings_frame,columns=('severity','rule','positions','title'),show='headings',height=5,selectmode='browse')
    for key,label,width in [('severity','Severity',90),('rule','Rule ID',165),('positions','Positions',120),('title','Reason / warning',600)]:
        rules_tree.heading(key,text=label); rules_tree.column(key,width=width,stretch=key=='title')
    rules_tree.pack(fill='both',expand=True)
    detail=tk.Text(holder,height=8,wrap='word',state='disabled',font=('Segoe UI',10))
    detail.pack(fill='both',pady=5)
    state={'report':None,'findings':[],'indexed_ids':{}}
    def show_detail(_event=None):
        selected=rules_tree.selection()
        if not selected:return
        finding=state['findings'][int(selected[0])]
        content=(f"{finding['title']} [{finding['severity']}]\nRule: {finding['rule_id']} | N→C positions: {finding['positions']}\n"
                 f"Why: {finding['reason']}\nPotential impact: {finding['potential_impact']}\n"
                 f"Operator consideration: {finding['operator_consideration']}\n"
                 f"Evidence: Rule-based; no experimental evidence or measured confidence. No action applied.")
        detail.configure(state='normal');detail.delete('1.0','end');detail.insert('1.0',content);detail.configure(state='disabled')
    rules_tree.bind('<<TreeviewSelect>>',show_detail)
    def position_select(_event=None):
        selected=position_tree.selection()
        if not selected:return
        index=int(selected[0]);refs=state['report']['residues'][index-1]['finding_refs']
        for ref in refs:
            i=state['indexed_ids'].get(ref['finding_id'])
            if i is not None:
                rules_tree.selection_set(str(i));rules_tree.see(str(i));show_detail();return
    position_tree.bind('<<TreeviewSelect>>',position_select)
    def refresh():
        try:report=build_sequence_risk_map(gui.pm_sequence.get())
        except Exception as exc:
            messagebox.showerror('Risk Map',str(exc),parent=window);return
        state['report']=report;state['findings']=report['findings']
        state['indexed_ids']={item['id']:i for i,item in enumerate(report['findings'])}
        headline.set(f"{report['residue_count']} residues | {len(report['findings'])} heuristic findings | Rule score: {report['score']} (not a probability)")
        for tree in (position_tree,rules_tree):
            for item in tree.get_children():tree.delete(item)
        for row in report['residues']:
            position_tree.insert('','end',iid=str(row['position']),values=(row['position'],row['token'],row['risk_level'],', '.join(sorted({r['rule_id'] for r in row['finding_refs']}))),tags=(row['risk_level'],))
        for i,row in enumerate(report['findings']):
            rules_tree.insert('','end',iid=str(i),values=(row['severity'],row['rule_id'],', '.join(map(str,row['positions'])),row['title']))
        detail.configure(state='normal');detail.delete('1.0','end')
        detail.insert('1.0',('Parser warnings: '+ '; '.join(map(str,report['parser_warnings']))+'\n' if report['parser_warnings'] else '')+'Select a rule to review its reasoning and optional action. No recipe modifications are made.')
        detail.configure(state='disabled')
        if state['findings']:
            rules_tree.selection_set('0');show_detail()
    def export():
        if state['report'] is None:
            return
        if str(gui.pm_sequence.get()) != state['report']['sequence']:
            messagebox.showwarning('Refresh required', 'Sequence changed. Refresh Risk Map before exporting.', parent=window)
            return
        chosen=filedialog.asksaveasfilename(parent=window,title='Export sequence risk evidence',defaultextension='.json',filetypes=[('JSON report','*.json'),('CSV findings','*.csv')])
        if not chosen:return
        try:export_risk_report(state['report'],chosen)
        except Exception as exc:messagebox.showerror('Export failed',str(exc),parent=window)
    def show_recommendations():
        if state['report'] is None or str(gui.pm_sequence.get()) != state['report']['sequence']:
            refresh()
            if state['report'] is None or str(gui.pm_sequence.get()) != state['report']['sequence']:
                return
        data = decision_report_from_risk(state['report'])
        child = tk.Toplevel(window); child.title('V8 operator review | No automatic changes')
        child.geometry('880x510')
        frame=ttk.Frame(child,padding=10);frame.pack(fill='both',expand=True)
        ttk.Label(frame,text='Rule-based recommendations (not experimentally validated)',font=('Segoe UI',11,'bold')).pack(anchor='w')
        ttk.Label(frame,text='Coupling, loading and cleavage values are not changed. Review approved SOP and analytical evidence.',wraplength=820).pack(anchor='w')
        area=tk.Text(frame,wrap='word',font=('Segoe UI',10))
        area.pack(fill='both',expand=True,pady=8)
        groups = {}
        for action in data['review_actions']:
            groups.setdefault(action['topic'], []).append(action)
        for topic, actions in groups.items():
            area.insert('end',f'{topic} ({len(actions)} findings)\n')
            for action in actions:
                area.insert('end',f"  [{action['severity']}] {action['rule_id']} | N→C {action['positions']}\n  {action['suggestion']}\n")
            area.insert('end','  Evidence: rule-based, no measured success probability.\n\n')
        if not data['review_actions']:area.insert('end','No triggered review rules for this input. This does not establish synthesis success.')
        area.configure(state='disabled')
        ttk.Button(frame,text='Close',command=child.destroy).pack(anchor='e')
    def record_experiment():
        child=tk.Toplevel(window);child.title('V8 experimental evidence — structured export')
        child.geometry('720x670')
        frame=ttk.Frame(child,padding=10);frame.pack(fill='both',expand=True)
        ttk.Label(frame,text='Record only real laboratory observations. Unreviewed records never change recommendations.',wraplength=660).pack(anchor='w')
        fields={};defaults={'sequence':gui.pm_sequence.get(),'recorded_at':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),'outcome':'Inconclusive'}
        for key in ('sequence','batch_id','recorded_at','outcome','analytical_method','operator','conditions','observations','data_reference','reviewer','reviewed_at'):
            line=ttk.Frame(frame);line.pack(fill='x',pady=3)
            ttk.Label(line,text=key,width=19).pack(side='left')
            var=tk.StringVar(value=defaults.get(key,''));fields[key]=var
            if key == 'outcome':
                ttk.Combobox(line,textvariable=var,values=('Pass','Fail','Inconclusive'),state='readonly').pack(side='left',fill='x',expand=True)
            else:
                ttk.Entry(line,textvariable=var).pack(side='left',fill='x',expand=True)
        def save():
            target=filedialog.asksaveasfilename(parent=child,defaultextension='.json',filetypes=[('JSON evidence','*.json')])
            if not target:return
            try:export_experiment_record({key:var.get() for key,var in fields.items()},target)
            except Exception as exc:messagebox.showerror('Evidence validation',str(exc),parent=child);return
            messagebox.showinfo('Evidence exported','New structured evidence file saved. No model or plan changes applied.',parent=child)
        ttk.Button(frame,text='Validate and export NEW JSON evidence',command=save).pack(anchor='e',pady=8)
    commands=ttk.Frame(holder);commands.pack(fill='x')
    ttk.Button(commands,text='Refresh from current Sequence',command=refresh).pack(side='left',padx=3)
    ttk.Button(commands,text='Export JSON / CSV',command=export).pack(side='left',padx=3)
    ttk.Button(commands,text='Review recommendations',command=show_recommendations).pack(side='left',padx=3)
    ttk.Button(commands,text='Record experiment',command=record_experiment).pack(side='left',padx=3)
    ttk.Button(commands,text='Close',command=window.destroy).pack(side='right',padx=3)
    refresh()
    return window
