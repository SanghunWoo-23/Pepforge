"""Optional CPU-compatible ensemble docking dialog; never fakes computed poses."""
from __future__ import annotations
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


def open_ensemble_docking_dialog(parent):
    win = tk.Toplevel(parent)
    win.title('Modified Peptide Ensemble Docking')
    win.geometry('900x540')
    win.transient(parent)
    frame = ttk.Frame(win, padding=16)
    frame.pack(fill='both', expand=True)
    values = {key: tk.StringVar() for key in ('Receptor PDB/mmCIF', 'Peptide SDF', 'New output folder')}
    for idx, (label, variable) in enumerate(values.items()):
        ttk.Label(frame, text=label).grid(row=idx, column=0, sticky='w', pady=7)
        ttk.Entry(frame, textvariable=variable, width=72).grid(row=idx, column=1, sticky='ew', padx=6)
        if idx < 2:
            command = lambda v=variable: v.set(filedialog.askopenfilename(parent=win, filetypes=[('Structure files','*.pdb *.cif *.mmcif *.sdf'),('All files','*.*')]) or v.get())
        else:
            command = lambda v=variable: v.set(filedialog.askdirectory(parent=win) or v.get())
        ttk.Button(frame, text='Browse', command=command).grid(row=idx,column=2)
    frame.columnconfigure(1, weight=1)
    ttk.Label(frame, text='SDF must contain the explicit full covalent graph and stereochemistry of the modified peptide.').grid(row=3,column=0,columnspan=3,sticky='w',pady=8)
    ttk.Label(frame, text='CPU native geometry search; docking scores are not binding free energies.').grid(row=4,column=0,columnspan=3,sticky='w')
    status = tk.StringVar(value='Ready')
    ttk.Label(frame, textvariable=status, wraplength=730).grid(row=5,column=0,columnspan=3,sticky='w',pady=12)
    options = ttk.Frame(frame)
    options.grid(row=6,column=0,columnspan=3,sticky='w',pady=8)
    ttk.Label(options,text='Conformers').pack(side='left')
    conf=tk.IntVar(value=12)
    ttk.Spinbox(options,from_=1,to=100,textvariable=conf,width=5).pack(side='left',padx=5)
    ttk.Label(options,text='Max structures').pack(side='left')
    maximum=tk.IntVar(value=8)
    ttk.Spinbox(options,from_=1,to=40,textvariable=maximum,width=5).pack(side='left',padx=5)
    ttk.Label(options,text='Poses').pack(side='left',padx=(12,0))
    poses=tk.IntVar(value=3)
    ttk.Spinbox(options,from_=1,to=20,textvariable=poses,width=5).pack(side='left',padx=5)
    ttk.Label(options,text='Max candidates').pack(side='left',padx=(12,0))
    candidates=tk.IntVar(value=250)
    ttk.Spinbox(options,from_=1,to=200000,textvariable=candidates,width=8).pack(side='left',padx=5)
    strategy = ttk.Frame(frame)
    strategy.grid(row=7,column=0,columnspan=3,sticky='w',pady=7)
    ttk.Label(strategy,text='Docking mode').pack(side='left')
    mode=tk.StringVar(value='blind')
    ttk.Combobox(strategy,textvariable=mode,values=('blind','manual','hotspot'),width=12,state='readonly').pack(side='left',padx=6)
    ttk.Label(strategy,text='Binding residues (manual/hotspot)').pack(side='left',padx=(12,3))
    residue_text=tk.StringVar()
    ttk.Entry(strategy,textvariable=residue_text,width=35).pack(side='left',padx=4)
    ttk.Label(frame,text='Residues: use native engine identifiers separated by commas; blind mode ignores this field.').grid(row=8,column=0,columnspan=3,sticky='w')
    button=ttk.Button(frame,text='Run Ensemble Docking')
    button.grid(row=9,column=0,columnspan=3,pady=8)

    def done(report=None, error=None):
        button.configure(state='normal')
        if error is not None:
            status.set(f'FAILED: {error}')
            messagebox.showerror('Ensemble Docking failed', str(error),parent=win)
        else:
            completed=sum(r.get('status') == 'COMPLETED' for r in report.get('runs', []))
            failed=len(report.get('runs', []))-completed
            status.set(f"{report['status']}: {completed} successful, {failed} unsuccessful; ensemble_docking_report.json in output folder.")
            if report['status'] != 'COMPLETED':
                messagebox.showwarning('Partial run',status.get(),parent=win)

    def start():
        try:
            receptor=Path(values['Receptor PDB/mmCIF'].get()).expanduser()
            peptide=Path(values['Peptide SDF'].get()).expanduser()
            output=Path(values['New output folder'].get()).expanduser()
            if not str(values['New output folder'].get()).strip():
                raise ValueError('Select a new output folder')
            if not receptor.is_file() or not peptide.is_file():
                raise FileNotFoundError('Select both receptor and peptide structure files')
            from peptiforg_core.v6_ensemble_options import parse_binding_residues
            n, m=conf.get(), maximum.get()
            pose_count, candidate_count=poses.get(), candidates.get()
            if not 1 <= n <= 100 or not 1 <= m <= 40 or not 1 <= pose_count <= 20 or not 1 <= candidate_count <= 200000:
                raise ValueError('Conformers, structures, poses or candidate count out of range')
            selected_mode=mode.get()
            selected_residues=parse_binding_residues(residue_text.get(), selected_mode)
        except (ValueError, OSError, tk.TclError) as exc:
            messagebox.showerror('Invalid input',str(exc),parent=win)
            return
        button.configure(state='disabled')
        status.set('Running actual conformer refinement and docking; this may take time...')
        def worker():
            try:
                from peptiforg_core.v6_ensemble_docking import run_ensemble_docking
                result=run_ensemble_docking(receptor,peptide,output,conformers=n,max_structures=m,poses=pose_count,max_candidates=candidate_count,mode=selected_mode,binding_residues=selected_residues)
                win.after(0, lambda: done(report=result))
            except Exception as exc:
                reason=f'{type(exc).__name__}: {exc}'
                win.after(0, lambda: done(error=reason))
        threading.Thread(target=worker,daemon=True).start()
    button.configure(command=start)
    return win
