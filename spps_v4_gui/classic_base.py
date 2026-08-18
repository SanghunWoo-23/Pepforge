from __future__ import annotations
import os
import sys
import re
import json
import csv
from datetime import datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
for _p in [ROOT, ROOT / 'apps' / 'spps_planner_app']:
    _sp = str(_p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from peptiforg_core.ui_helpers import set_pepforge_icon
import pandas as pd
from spps_v4_gui.gui_primitives import EditableTree, StaticValue as _StaticValue, bind_combobox_first_letter_jump, const_var as _v225_const_var, open_path
from spps_v4_gui import catalogs as _catalogs
from spps_v4_gui.session_state import SessionStateMixin
APP_VERSION = 'V4.0.0'
APP = ROOT / 'apps' / 'spps_planner_app'
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))
from spps_planner.engine import PlanInput, plan_summary, generate_excel_like_synthesis_table
from spps_planner.parser import tokenize_core_sequence
try:
    from spps_planner.export import export_csvs
except Exception:
    export_csvs = None

class ClassicBaseCore(SessionStateMixin, tk.Tk):
    PLAN_COLUMNS = _catalogs.PLAN_COLUMNS
    MATERIAL_COLUMNS = _catalogs.MATERIAL_COLUMNS
    RESIN_VALUES = _catalogs.RESIN_VALUES
    REAGENT_VALUES = _catalogs.REAGENT_VALUES
    CATALYST_VALUES = _catalogs.CATALYST_VALUES
    BASE_VALUES = _catalogs.BASE_VALUES
    DEPRO_VALUES = _catalogs.DEPRO_VALUES
    RATIO_VALUES = _catalogs.RATIO_VALUES
    SOLVENT_VALUES = _catalogs.SOLVENT_VALUES
    UNIT_VALUES = _catalogs.UNIT_VALUES
    FMOC_LINKER_VALUES = _catalogs.FMOC_LINKER_VALUES
    MW_FALLBACK = _catalogs.MW_FALLBACK

    def __init__(self):
        super().__init__()
        self.title('SPPS Planner')
        set_pepforge_icon(self)
        self.geometry('1920x1080')
        self.minsize(1550, 900)
        self.last_outdir: Path | None = None
        self._row_meta_by_no = {}
        self._build()
        self.bind_all_combobox_typeahead()
        # Startup must not invoke the synthesis core before the operator has
        # entered a sequence.  Empty editor fields are a valid idle state.
        startup_sequence = ""
        for attr in ("pm_sequence", "seq"):
            try:
                value = getattr(self, attr, None)
                text = value.get() if hasattr(value, "get") else value
                if str(text or "").strip():
                    startup_sequence = str(text).strip()
                    break
            except Exception:
                continue
        if startup_sequence:
            self.rebuild_table()
            self.after(300, self.refresh_outputs_from_tree)

    def _build(self):
        style = ttk.Style(self)
        style.configure('Treeview', rowheight=28, font=('Segoe UI', 10))
        style.configure('Treeview.Heading', font=('Segoe UI', 10, 'bold'))
        style.configure('TNotebook.Tab', padding=(24, 10), font=('Segoe UI', 11, 'bold'))
        main = ttk.Frame(self, padding=10)
        main.pack(fill='both', expand=True)
        ttk.Label(main, text='SPPS Planner V4.0.0 - Modern / Classic Hybrid', font=('Segoe UI', 18, 'bold')).pack(anchor='w')
        self.project_name = tk.StringVar(value='')
        self.seq = tk.StringVar(value='')
        # Retained as an empty compatibility field for legacy calculation and
        # project schemas. Pepforge does not expose or generate LOT identifiers.
        self.lot_no = tk.StringVar(value='')
        project_bar = ttk.Labelframe(main, text='Project', padding=8)
        project_bar.pack(fill='x', pady=(0, 8))
        ttk.Label(project_bar, text='Project name', width=16).grid(row=0, column=0, sticky='w', padx=(0, 4))
        ttk.Entry(project_bar, textvariable=self.project_name).grid(row=0, column=1, sticky='ew', padx=(0, 10))
        ttk.Label(project_bar, text='Sequence', width=12).grid(row=0, column=2, sticky='w', padx=(0, 4))
        ttk.Entry(project_bar, textvariable=self.seq).grid(row=0, column=3, sticky='ew', padx=(0, 10))
        project_bar.columnconfigure(1, weight=1)
        project_bar.columnconfigure(3, weight=1)
        project_bar.columnconfigure(5, weight=0)
        project_bar.pack_forget()
        form = ttk.Labelframe(main, text='Resin / Coupling / Base / Solvent Defaults', padding=8)
        self.setup_form = form
        form.pack(fill='x')
        self.resin = tk.StringVar(value='Amide')
        self.scale = tk.DoubleVar(value=400.0)
        self.loading = tk.DoubleVar(value=0.8)
        self.coupling_eq = tk.StringVar(value='5')
        self.modifier_eq = tk.DoubleVar(value=3.0)
        self.coupling_repeats = tk.IntVar(value=1)
        self.coupling_time_h = tk.StringVar(value='0.5')
        self.modifier_repeats = tk.IntVar(value=1)
        self.default_reagent = tk.StringVar(value='DIC')
        self.default_reagent_eq = tk.DoubleVar(value=5.0)
        self.default_reagent_count = tk.IntVar(value=1)
        self.default_catalyst = tk.StringVar(value='HOBt')
        self.default_catalyst_eq = tk.DoubleVar(value=5.0)
        self.default_catalyst_count = tk.IntVar(value=1)
        self.default_base = tk.StringVar(value='')
        self.default_base_eq = tk.DoubleVar(value=5.0)
        self.default_base_count = tk.IntVar(value=1)
        self.default_depro = tk.StringVar(value='Piperidine')
        self.default_depro_ratio = tk.StringVar(value='20% in DMF')
        self.default_depro_count = tk.IntVar(value=2)
        self.default_solvent1 = tk.StringVar(value='DMF')
        self.default_solvent1_count = tk.IntVar(value=6)
        self.default_solvent2 = tk.StringVar(value='DCM')
        self.default_solvent2_count = tk.IntVar(value=3)
        self.final_meoh_count = tk.IntVar(value=0)
        self.branch_mode = tk.BooleanVar(value=False)
        self.branch_point = tk.StringVar(value='K5')
        self.branch_arm = tk.StringVar(value='RGD')
        self.branch_pg = tk.StringVar(value='Mtt')
        self.branch_depro_condition = tk.StringVar(value='Mtt: dilute TFA/TIS/DCM')
        # One canonical working-volume model.  These variables back the
        # Solvents / Wash controls and replace the removed global mL/mmol field.
        self.solvent_volume_mode = tk.StringVar(value='resin_factor')
        self.amide_ml_per_mmol = tk.StringVar(value='10')
        self.ctc_ml_per_mmol = tk.StringVar(value='5')
        self.solvent_molarity_m = tk.StringVar(value='0.2')
        self.default_coupling_solution_solvent = tk.StringVar(value='DMF')
        self.default_loading_dissolve_solvent = tk.StringVar(value='90% DCM / 10% DMF')
        self.outdir = tk.StringVar(value=str(ROOT / 'outputs' / 'spps_editable_run'))

        def add_card_field(parent, label, widget, r, c, span=1, label_width=22):
            """Place one SPPS setup field inside a compact vertical card.

            The public v1.0.1 UI intentionally groups chemically related inputs
            in vertical blocks instead of one very long horizontal row. This is
            easier to read on a bench laptop and mirrors the way chemists think:
            resin properties, amino-acid/unit settings, reagent 1, reagent 2 or
            catalyst, base/deprotection, and solvents.
            """
            ttk.Label(parent, text=label, width=label_width).grid(row=r, column=c * 2, sticky='w', padx=(0, 8), pady=3)
            try:
                if isinstance(widget, ttk.Entry):
                    widget.configure(width=18)
                elif isinstance(widget, ttk.Combobox):
                    bind_combobox_first_letter_jump(widget)
                    current = int(widget.cget('width') or 0)
                    widget.configure(width=max(current, 22))
            except Exception:
                pass
            widget.grid(row=r, column=c * 2 + 1, sticky='ew', padx=(0, 8), pady=3, columnspan=span)
            try:
                parent.columnconfigure(c * 2 + 1, weight=1)
            except Exception:
                pass

        def make_card(parent, title, row, col, colspan=1):
            card = ttk.Labelframe(parent, text=title, padding=(10, 8))
            card.grid(row=row, column=col, columnspan=colspan, sticky='nsew', padx=6, pady=6)
            for i in range(4):
                card.columnconfigure(i, weight=1)
            return card
        action_bar = ttk.Frame(form)
        action_bar.grid(row=0, column=0, columnspan=4, sticky='ew', padx=(2, 2), pady=(0, 6))
        ttk.Button(action_bar, text='Generate', width=22, command=self.generate_update_plan).pack(side='left', padx=3)
        ttk.Button(action_bar, text='Use DIC/HOBt', width=14, command=self.apply_dic_hobt_preset).pack(side='left', padx=3)
        ttk.Button(action_bar, text='Use HBTU/NMP 10eq', width=18, command=self.apply_hbtu_nmp_preset).pack(side='left', padx=3)
        ttk.Button(action_bar, text='Load Project', width=14, command=self.load_project).pack(side='left', padx=3)
        ttk.Button(action_bar, text='Import Output', width=14, command=self.load_output_folder).pack(side='left', padx=3)
        ttk.Button(action_bar, text='Export', width=12, command=self.export_outputs).pack(side='left', padx=3)
        self._setup_visible = tk.BooleanVar(value=False)
        self.setup_toggle_btn = ttk.Button(action_bar, text='Show setup', width=14, command=self.toggle_setup_panel)
        self.setup_toggle_btn.pack(side='left', padx=(12, 3))
        ttk.Label(action_bar, text='Setup is tabbed; hide it to maximize Plan/Materials visibility.').pack(side='left', padx=(6, 0))
        action_bar.grid_remove()
        for i in range(4):
            form.columnconfigure(i, weight=1)
        setup_tabs = ttk.Notebook(form)
        self.setup_tabs = setup_tabs
        setup_tabs.grid(row=1, column=0, columnspan=4, sticky='ew', padx=2, pady=(2, 4))
        setup_tabs.grid_remove()
        tab_resin = ttk.Frame(setup_tabs, padding=4)
        tab_reagents = ttk.Frame(setup_tabs, padding=4)
        tab_solvents = ttk.Frame(setup_tabs, padding=4)
        tab_output = ttk.Frame(setup_tabs, padding=4)
        setup_tabs.add(tab_resin, text='Resin / Unit')
        setup_tabs.add(tab_reagents, text='Reagents / Base')
        setup_tabs.add(tab_solvents, text='Solvents / Wash')
        setup_tabs.add(tab_output, text='Output')
        for _tab in (tab_resin, tab_reagents, tab_solvents, tab_output):
            _tab.columnconfigure(0, weight=1)
            _tab.columnconfigure(1, weight=1)
        resin_card = make_card(tab_resin, 'Resin properties', 0, 0)
        unit_card = make_card(tab_resin, 'Amino acid / unit defaults', 0, 1)
        reagent1_card = make_card(tab_reagents, 'Reagent 1 / activator', 0, 0)
        reagent2_card = make_card(tab_reagents, 'Reagent 2 / catalyst', 0, 1)
        base_card = make_card(tab_reagents, 'Base / deprotection', 1, 0, colspan=2)
        solvent_card = make_card(tab_solvents, 'Solvent / wash settings', 0, 0, colspan=2)
        output_card = make_card(tab_output, 'Output', 0, 0, colspan=2)
        add_card_field(resin_card, 'Resin family', ttk.Combobox(resin_card, textvariable=self.resin, values=self.RESIN_VALUES, state='normal', width=30), 0, 0)
        add_card_field(resin_card, 'Scale', ttk.Entry(resin_card, textvariable=self.scale), 1, 0)
        ttk.Label(resin_card, text='mmol', width=8).grid(row=1, column=2, sticky='w')
        add_card_field(resin_card, 'Loading', ttk.Entry(resin_card, textvariable=self.loading), 2, 0)
        ttk.Label(resin_card, text='mmol/g', width=8).grid(row=2, column=2, sticky='w')
        add_card_field(unit_card, 'Default unit eq', ttk.Entry(unit_card, textvariable=self.coupling_eq), 0, 0)
        ttk.Label(unit_card, text='eq', width=8).grid(row=0, column=2, sticky='w')
        add_card_field(unit_card, 'Default unit repeat', ttk.Spinbox(unit_card, from_=1, to=20, textvariable=self.coupling_repeats), 1, 0)
        add_card_field(unit_card, 'Coupling time', ttk.Entry(unit_card, textvariable=self.coupling_time_h), 2, 0)
        ttk.Label(unit_card, text='h', width=8).grid(row=2, column=2, sticky='w')
        add_card_field(unit_card, 'Modifier / label eq', ttk.Entry(unit_card, textvariable=self.modifier_eq), 2, 0)
        ttk.Label(unit_card, text='eq', width=8).grid(row=2, column=2, sticky='w')
        add_card_field(unit_card, 'Modifier repeat', ttk.Spinbox(unit_card, from_=1, to=20, textvariable=self.modifier_repeats), 4, 0)
        add_card_field(reagent1_card, 'Reagent 1', ttk.Combobox(reagent1_card, textvariable=self.default_reagent, values=self.REAGENT_VALUES, state='normal', width=26), 0, 0)
        add_card_field(reagent1_card, 'Equivalent', ttk.Entry(reagent1_card, textvariable=self.default_reagent_eq), 1, 0)
        ttk.Label(reagent1_card, text='eq', width=8).grid(row=1, column=2, sticky='w')
        add_card_field(reagent1_card, 'Count', ttk.Spinbox(reagent1_card, from_=0, to=30, textvariable=self.default_reagent_count), 2, 0)
        add_card_field(reagent1_card, 'Cocktail solvent', ttk.Combobox(reagent1_card, textvariable=self.default_coupling_solution_solvent, values=self.SOLVENT_VALUES, state='normal', width=26), 3, 0)
        add_card_field(reagent2_card, 'Reagent 2 / catalyst', ttk.Combobox(reagent2_card, textvariable=self.default_catalyst, values=self.CATALYST_VALUES, state='normal', width=26), 0, 0)
        add_card_field(reagent2_card, 'Equivalent', ttk.Entry(reagent2_card, textvariable=self.default_catalyst_eq), 1, 0)
        ttk.Label(reagent2_card, text='eq', width=8).grid(row=1, column=2, sticky='w')
        add_card_field(reagent2_card, 'Count', ttk.Spinbox(reagent2_card, from_=0, to=30, textvariable=self.default_catalyst_count), 2, 0)
        ttk.Label(reagent2_card, text='Use this block for HOBt, Oxyma, DMAP, HOAt, NHS, or similar additives.', wraplength=460, foreground='#555555').grid(row=3, column=0, columnspan=4, sticky='w', pady=(4, 0))
        add_card_field(base_card, 'Coupling base', ttk.Combobox(base_card, textvariable=self.default_base, values=self.BASE_VALUES, state='normal', width=26), 0, 0)
        add_card_field(base_card, 'Base equivalent', ttk.Entry(base_card, textvariable=self.default_base_eq), 1, 0)
        ttk.Label(base_card, text='eq', width=8).grid(row=1, column=2, sticky='w')
        add_card_field(base_card, 'Base count', ttk.Spinbox(base_card, from_=0, to=30, textvariable=self.default_base_count), 2, 0)
        add_card_field(base_card, 'Deprotection base', ttk.Combobox(base_card, textvariable=self.default_depro, values=self.DEPRO_VALUES, state='normal', width=26), 3, 0)
        add_card_field(base_card, 'Deprotection ratio', ttk.Combobox(base_card, textvariable=self.default_depro_ratio, values=self.RATIO_VALUES, state='normal', width=26), 4, 0)
        add_card_field(base_card, 'Deprotection count', ttk.Spinbox(base_card, from_=0, to=20, textvariable=self.default_depro_count), 5, 0)
        add_card_field(solvent_card, 'Solvent 1', ttk.Combobox(solvent_card, textvariable=self.default_solvent1, values=self.SOLVENT_VALUES, state='normal', width=26), 0, 0)
        add_card_field(solvent_card, 'Solvent 1 count', ttk.Spinbox(solvent_card, from_=0, to=30, textvariable=self.default_solvent1_count), 1, 0)
        add_card_field(solvent_card, 'Solvent 2', ttk.Combobox(solvent_card, textvariable=self.default_solvent2, values=self.SOLVENT_VALUES, state='normal', width=26), 2, 0)
        add_card_field(solvent_card, 'Solvent 2 count', ttk.Spinbox(solvent_card, from_=0, to=30, textvariable=self.default_solvent2_count), 3, 0)
        add_card_field(solvent_card, 'Loading solvent', ttk.Combobox(solvent_card, textvariable=self.default_loading_dissolve_solvent, values=self.SOLVENT_VALUES, state='normal', width=26), 4, 0)
        add_card_field(solvent_card, 'Final MeOH wash', ttk.Spinbox(solvent_card, from_=0, to=30, textvariable=self.final_meoh_count), 5, 0)
        output_card.columnconfigure(1, weight=1)
        ttk.Label(output_card, text='Output folder', width=18).grid(row=0, column=0, sticky='w', padx=(0, 8), pady=3)
        ttk.Entry(output_card, textvariable=self.outdir).grid(row=0, column=1, sticky='ew', padx=(0, 8), pady=3)
        ttk.Button(output_card, text='Browse', command=self.browse_outdir).grid(row=0, column=2, sticky='ew', padx=4)
        ttk.Button(output_card, text='Open Folder', command=self.open_output).grid(row=0, column=3, sticky='ew', padx=4)
        form.pack_forget()
        branch_box = ttk.Labelframe(main, text='Branch mode / side-chain arm', padding=8)
        branch_box.pack(fill='x', pady=(8, 2))
        ttk.Checkbutton(branch_box, text='Enable branch mode', variable=self.branch_mode, command=self.generate_update_plan).grid(row=0, column=0, sticky='w', padx=(0, 10))
        ttk.Label(branch_box, text='Branch point').grid(row=0, column=1, sticky='w')
        ttk.Entry(branch_box, textvariable=self.branch_point, width=12).grid(row=0, column=2, sticky='w', padx=(4, 12))
        ttk.Label(branch_box, text='Branch arm sequence').grid(row=0, column=3, sticky='w')
        ttk.Entry(branch_box, textvariable=self.branch_arm, width=24).grid(row=0, column=4, sticky='ew', padx=(4, 12))
        ttk.Label(branch_box, text='Protecting group').grid(row=0, column=5, sticky='w')
        ttk.Combobox(branch_box, textvariable=self.branch_pg, values=['Mtt', 'ivDde', 'Dde', 'Alloc', 'Manual'], state='normal', width=14).grid(row=0, column=6, sticky='w', padx=(4, 12))
        ttk.Label(branch_box, text='Branch deprotection').grid(row=0, column=7, sticky='w')
        ttk.Combobox(branch_box, textvariable=self.branch_depro_condition, values=['Mtt: dilute TFA/TIS/DCM', 'ivDde/Dde: hydrazine/DMF', 'Alloc: Pd(PPh3)4/phenylsilane/DCM', 'Manual'], state='normal', width=34).grid(row=0, column=8, sticky='ew', padx=(4, 0))
        branch_box.columnconfigure(4, weight=1)
        branch_box.columnconfigure(8, weight=1)
        self.branch_box = branch_box
        branch_box.pack_forget()
        btns = ttk.Frame(main)
        btns.pack(fill='x', pady=8)
        ttk.Button(btns, text='Append row', command=self.append_blank_row).pack(side='left', padx=4)
        ttk.Button(btns, text='Delete selected row', command=self.delete_selected).pack(side='left', padx=4)
        ttk.Button(btns, text='Reset table widths', command=self.reset_column_widths).pack(side='left', padx=4)
        ttk.Label(btns, text='Drag column borders/pane dividers. Double-click cells to edit.').pack(side='left', padx=12)
        self.legacy_table_tools = btns
        btns.pack_forget()
        self.tabs = ttk.Notebook(main)
        self.tabs.pack(fill='both', expand=True)
        self._build_project_manager_tab()
        plan_frame = ttk.Frame(self.tabs)
        self.tabs.add(plan_frame, text='Plan')
        plan_frame.rowconfigure(0, weight=0)
        plan_frame.rowconfigure(1, weight=1)
        plan_frame.columnconfigure(0, weight=1)
        horiz = ttk.PanedWindow(plan_frame, orient='vertical')
        self.plan_paned = horiz
        horiz.grid(row=1, column=0, sticky='nsew')
        pane_controls = ttk.Frame(plan_frame)
        pane_controls.grid(row=0, column=0, sticky='ew', padx=2, pady=(0, 4))
        ttk.Label(pane_controls, text='Plan view').pack(side='left', padx=(0, 4))
        self.plan_view_mode = tk.StringVar(value='Balanced')
        plan_view = ttk.Combobox(pane_controls, textvariable=self.plan_view_mode, values=['Balanced', 'Plan full', 'Live materials full'], state='readonly', width=20)
        plan_view.pack(side='left', padx=3)
        plan_view.bind('<<ComboboxSelected>>', lambda e: self._set_plan_pane({'Plan full': 'plan', 'Live materials full': 'materials', 'Balanced': 'balanced'}.get(self.plan_view_mode.get(), 'balanced')))
        table_frame = ttk.Frame(horiz)
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        self.spps_combo_values = {'Unit name': self.UNIT_VALUES, 'Coupling reagent 1': self.REAGENT_VALUES, 'Coupling reagent 2 / catalyst': self.CATALYST_VALUES, 'Coupling base': self.BASE_VALUES, 'Coupling cocktail solvent': self.SOLVENT_VALUES, 'Deprotection base': self.DEPRO_VALUES, 'Deprotection ratio': self.RATIO_VALUES, 'Solvent 1': self.SOLVENT_VALUES, 'Solvent 2': self.SOLVENT_VALUES}
        self.tree = EditableTree(table_frame, self.PLAN_COLUMNS, on_edit=self.on_tree_edit, combo_values=self.spps_combo_values)
        y = ttk.Scrollbar(table_frame, orient='vertical', command=self.tree.yview)
        x = ttk.Scrollbar(table_frame, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        self.tree.grid(row=0, column=0, sticky='nsew')
        y.grid(row=0, column=1, sticky='ns')
        x.grid(row=1, column=0, sticky='ew')
        horiz.add(table_frame, weight=5)
        usage_frame = ttk.Labelframe(horiz, text='Live Material Usage Table')
        usage_frame.rowconfigure(0, weight=1)
        usage_frame.columnconfigure(0, weight=1)
        self.live_usage_tree = ttk.Treeview(usage_frame, columns=self.MATERIAL_COLUMNS, show='headings')
        for c in self.MATERIAL_COLUMNS:
            self.live_usage_tree.heading(c, text=c)
            self.live_usage_tree.column(c, width=240 if c in ('material', 'note', 'source') else 190, minwidth=140, anchor='w', stretch=True)
        uy = ttk.Scrollbar(usage_frame, orient='vertical', command=self.live_usage_tree.yview)
        ux = ttk.Scrollbar(usage_frame, orient='horizontal', command=self.live_usage_tree.xview)
        self.live_usage_tree.configure(yscrollcommand=uy.set, xscrollcommand=ux.set)
        self.live_usage_tree.grid(row=0, column=0, sticky='nsew')
        uy.grid(row=0, column=1, sticky='ns')
        ux.grid(row=1, column=0, sticky='ew')
        horiz.add(usage_frame, weight=3)
        self.plan_width_map = {'No': 90, 'Unit name': 520, 'Unit eq': 135, 'Unit amount(g)': 210, 'Coupling reagent 1': 240, 'Coupling reagent 1 eq': 135, 'Coupling reagent 1 count': 145, 'Coupling reagent 2 / catalyst': 340, 'Coupling reagent 2 / catalyst eq': 180, 'Coupling reagent 2 / catalyst count': 195, 'Coupling base': 140, 'Coupling base eq': 135, 'Coupling base count': 150, 'Coupling cocktail solvent': 330, 'Coupling cocktail volume(mL)': 245, 'Coupling base volume(mL)': 170, 'Deprotection base': 160, 'Deprotection ratio': 260, 'Deprotection count': 160, 'Solvent 1': 155, 'Solvent 1 count': 130, 'Solvent 2': 155, 'Solvent 2 count': 130, 'Repeat': 80}
        existing_plan_columns = set(self.tree['columns'])
        self._load_column_widths()
        for k, v in self.plan_width_map.items():
            if k in existing_plan_columns:
                self.tree.column(k, width=v, minwidth=80, stretch=True)
        self.tree.bind('<ButtonRelease-1>', lambda e: self._save_column_widths())
        self._build_usage_summary_tab()
        self._build_project_sheet_tab()
        self._build_checklist_tab()
        self.tabs.bind('<<NotebookTabChanged>>', self._on_tab_changed_refresh, add='+')
        self.after_idle(self.refresh_outputs_from_tree)

    def _on_tab_changed_refresh(self, event=None):
        """Keep Materials/Checklist/Log populated when the user opens the tab."""
        try:
            selected = self.tabs.tab(self.tabs.select(), 'text')
            try:
                self.pm_live_sync_selected()
            except Exception:
                pass
            if selected in {'Materials', 'Plan', 'Project', 'Checklist'}:
                self.after_idle(self.refresh_outputs_from_tree)
        except Exception:
            pass

    def toggle_setup_panel(self):
        """Show/hide the Project Manager setup panel under the selected peptide editor.

        V1.0.19: the setup controls no longer occupy the top of the app. They
        live directly under the editor action buttons and collapse completely so
        the result tables move back up when hidden.
        """
        try:
            visible = bool(self._setup_visible.get())
            panel = getattr(self, 'pm_setup_panel', None)
            if panel is None:
                return
            if visible:
                panel.grid_remove()
                self._setup_visible.set(False)
                new_text = 'Show setup'
            else:
                panel.grid(row=5, column=0, columnspan=10, sticky='ew', pady=(6, 0))
                self._setup_visible.set(True)
                new_text = 'Hide setup'
            for btn in [getattr(self, 'setup_toggle_btn', None)] + list(getattr(self, 'setup_toggle_buttons', [])):
                if btn is not None:
                    try:
                        btn.configure(text=new_text)
                    except Exception:
                        pass
            try:
                self.update_idletasks()
                if hasattr(self, 'pm_paned'):
                    self.pm_paned.update_idletasks()
            except Exception:
                pass
        except Exception as exc:
            try:
                self.log(f'Setup toggle error: {exc}')
            except Exception:
                pass

    def _set_plan_pane(self, mode: str):
        """Let one Plan pane visually dominate the other without deleting data."""
        try:
            self.plan_paned.update_idletasks()
            h = max(300, self.plan_paned.winfo_height())
            if mode == 'plan':
                pos = max(260, int(h * 0.92))
            elif mode == 'materials':
                pos = max(42, int(h * 0.06))
            else:
                pos = int(h * 0.62)
            self.plan_paned.sashpos(0, pos)
        except Exception as e:
            self._log(f'Pane resize warning: {e}\n')

    def _on_row_height_var_changed(self, *_):
        """Apply row height immediately when the user clicks +/-/slider/spinbox arrows."""
        try:
            if getattr(self, '_row_height_trace_after_id', None):
                self.after_cancel(self._row_height_trace_after_id)
            self._row_height_trace_after_id = self.after_idle(self.apply_table_row_height)
        except Exception:
            pass

    def adjust_table_row_height(self, delta: int):
        """One-click row-height adjustment for bench use."""
        try:
            h = int(float(self.table_row_height.get()))
        except Exception:
            h = 42
        self.table_row_height.set(max(24, min(160, h + int(delta))))
        self.apply_table_row_height()

    def _on_tree_row_height_wheel(self, event):
        """Ctrl + mouse wheel over any table changes global Treeview row height."""
        delta = 4 if getattr(event, 'delta', 0) > 0 else -4
        self.adjust_table_row_height(delta)
        return 'break'

    def _bind_row_height_controls(self, tree):
        try:
            tree.bind('<Control-MouseWheel>', self._on_tree_row_height_wheel, add='+')
            tree.bind('<Control-Button-4>', lambda e: (self.adjust_table_row_height(4), 'break'), add='+')
            tree.bind('<Control-Button-5>', lambda e: (self.adjust_table_row_height(-4), 'break'), add='+')
        except Exception:
            pass

    def apply_table_row_height(self):
        """Apply a readable row height to all SPPS tables without rebuilding data."""
        try:
            h = int(self.table_row_height.get())
        except Exception:
            h = 28
        h = max(24, min(160, h))
        try:
            ttk.Style(self).configure('Treeview', rowheight=h)
            for tree_name in ('tree', 'live_usage_tree', 'material_tree', 'aa_summary_tree', 'reagent_summary_tree', 'solvent_summary_tree', 'progress_tree'):
                tree = getattr(self, tree_name, None)
                if tree is not None:
                    tree.update_idletasks()
        except Exception as e:
            self._log('Row height update failed: ' + str(e) + '\n')

    def reset_column_widths(self):
        """Restore readable editable-table column widths after manual resizing.

        This does not rebuild the table and does not change any edited values.
        It only restores the visible heading/column widths.
        """
        try:
            existing_plan_columns = set(self.tree['columns'])
            for k, v in getattr(self, 'plan_width_map', {}).items():
                if k in existing_plan_columns:
                    self.tree.column(k, width=v, minwidth=80, stretch=True)
            for tree_name in ('live_usage_tree', 'material_tree', 'aa_summary_tree', 'reagent_summary_tree', 'solvent_summary_tree', 'progress_tree'):
                tree = getattr(self, tree_name, None)
                if tree is not None:
                    for col in tree['columns']:
                        tree.column(col, width=220 if col in ('material', 'note', 'source') else 170, minwidth=120, stretch=True)
            self.tree.update_idletasks()
            self._save_column_widths()
        except Exception as e:
            self._log('Column width reset failed: ' + str(e) + '\n')

    def _text_tab(self, name):
        fr = ttk.Frame(self.tabs)
        self.tabs.add(fr, text=name)
        fr.rowconfigure(0, weight=1)
        fr.columnconfigure(0, weight=1)
        txt = tk.Text(fr, wrap='none')
        y = ttk.Scrollbar(fr, orient='vertical', command=txt.yview)
        x = ttk.Scrollbar(fr, orient='horizontal', command=txt.xview)
        txt.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        txt.grid(row=0, column=0, sticky='nsew')
        y.grid(row=0, column=1, sticky='ns')
        x.grid(row=1, column=0, sticky='ew')
        return txt

    def _tree_tab(self, name, columns):
        fr = ttk.Frame(self.tabs)
        self.tabs.add(fr, text=name)
        fr.rowconfigure(0, weight=1)
        fr.columnconfigure(0, weight=1)
        tree = ttk.Treeview(fr, columns=columns, show='headings')
        for c in columns:
            tree.heading(c, text=c)
            tree.column(c, width=120, anchor='w', stretch=True)
        y = ttk.Scrollbar(fr, orient='vertical', command=tree.yview)
        x = ttk.Scrollbar(fr, orient='horizontal', command=tree.xview)
        tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        tree.grid(row=0, column=0, sticky='nsew')
        y.grid(row=0, column=1, sticky='ns')
        x.grid(row=1, column=0, sticky='ew')
        return tree

    def _tree_in_frame(self, parent, columns):
        tree = ttk.Treeview(parent, columns=columns, show='headings', height=18)
        for c in columns:
            tree.heading(c, text=c)
            w = 340 if c in ('material', 'note', 'source', 'operation', 'next_step') else 170
            if c in ('actual_used', 'actual_used_g'):
                w = 210
            tree.column(c, width=w, anchor='w', stretch=True, minwidth=95)
        y = ttk.Scrollbar(parent, orient='vertical', command=tree.yview)
        x = ttk.Scrollbar(parent, orient='horizontal', command=tree.xview)
        tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        tree.grid(row=0, column=0, sticky='nsew')
        y.grid(row=0, column=1, sticky='ns')
        x.grid(row=1, column=0, sticky='ew')
        return tree

    def _text_in_frame(self, parent):
        txt = tk.Text(parent, wrap='none', font=('Consolas', 10))
        y = ttk.Scrollbar(parent, orient='vertical', command=txt.yview)
        x = ttk.Scrollbar(parent, orient='horizontal', command=txt.xview)
        txt.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        txt.grid(row=0, column=0, sticky='nsew')
        y.grid(row=0, column=1, sticky='ns')
        x.grid(row=1, column=0, sticky='ew')
        return txt

    def _build_usage_summary_tab(self):
        fr = ttk.Frame(self.tabs)
        self.tabs.add(fr, text='Materials')
        fr.rowconfigure(1, weight=1)
        fr.columnconfigure(0, weight=1)
        top = ttk.Frame(fr, padding=(4, 4))
        top.grid(row=0, column=0, sticky='ew')
        ttk.Label(top, text='Materials update automatically from the editable Plan.').pack(side='left', padx=(0, 10))
        ttk.Label(top, text='View').pack(side='left', padx=(0, 4))
        self.material_view_mode = tk.StringVar(value='Balanced')
        material_view = ttk.Combobox(top, textvariable=self.material_view_mode, values=['Balanced', 'Step full', 'AA full', 'Reagent full', 'Solvent full'], state='readonly', width=18)
        material_view.pack(side='left', padx=3)
        material_view.bind('<<ComboboxSelected>>', lambda e: self._set_material_pane({'Step full': 'step', 'AA full': 'aa', 'Reagent full': 'reagent', 'Solvent full': 'solvent', 'Balanced': 'balanced'}.get(self.material_view_mode.get(), 'balanced')))
        paned = ttk.PanedWindow(fr, orient='vertical')
        self.material_paned = paned
        paned.grid(row=1, column=0, sticky='nsew', padx=4, pady=3)
        step_box = ttk.Labelframe(paned, text='Step Material Usage', padding=6)
        aa_box = ttk.Labelframe(paned, text='Amino Acid / Unit Usage', padding=6)
        reagent_box = ttk.Labelframe(paned, text='Reagent / Base / Catalyst Usage', padding=6)
        solvent_box = ttk.Labelframe(paned, text='Solvent Usage', padding=6)
        for box in (step_box, aa_box, reagent_box, solvent_box):
            box.rowconfigure(0, weight=1)
            box.columnconfigure(0, weight=1)
        self.material_tree = self._tree_in_frame(step_box, self.MATERIAL_COLUMNS)
        self.aa_summary_tree = self._tree_in_frame(aa_box, ['material', 'planned_mmol', 'MW', 'calculated_g', 'actual_used_g'])
        self.reagent_summary_tree = self._tree_in_frame(reagent_box, ['material', 'class', 'MW', 'density_g_per_mL', 'planned_mmol', 'planned_g', 'planned_mL', 'actual_used'])
        self.solvent_summary_tree = self._tree_in_frame(solvent_box, ['solvent', 'planned_mL', 'use_count', 'note'])
        paned.add(step_box, weight=5)
        paned.add(aa_box, weight=2)
        paned.add(reagent_box, weight=2)
        paned.add(solvent_box, weight=2)

    def _set_material_pane(self, mode: str):
        try:
            self.material_paned.update_idletasks()
            h = max(420, self.material_paned.winfo_height())
            layouts = {'step': (0.86, 0.91, 0.96), 'aa': (0.06, 0.86, 0.93), 'reagent': (0.06, 0.13, 0.88), 'solvent': (0.05, 0.1, 0.18), 'balanced': (0.38, 0.6, 0.8)}
            a, b, c = layouts.get(mode, layouts['balanced'])
            self.material_paned.sashpos(0, int(h * a))
            self.material_paned.sashpos(1, int(h * b))
            self.material_paned.sashpos(2, int(h * c))
        except Exception as e:
            self._log(f'Material pane resize warning: {e}\n')

    def _build_project_sheet_tab(self):
        fr = ttk.PanedWindow(self.tabs, orient='vertical')
        self.tabs.add(fr, text='Project')
        calc_box = ttk.Labelframe(fr, text='Calculators', padding=4)
        sheet_box = ttk.Labelframe(fr, text='Project Sheets', padding=4)
        calc_box.rowconfigure(0, weight=1)
        calc_box.rowconfigure(1, weight=1)
        calc_box.columnconfigure(0, weight=1)
        sheet_box.rowconfigure(0, weight=1)
        sheet_box.columnconfigure(0, weight=1)
        load_box = ttk.Labelframe(calc_box, text='Loading Calculator', padding=4)
        cleave_box = ttk.Labelframe(calc_box, text='Cleavage Calculator', padding=4)
        for box in (load_box, cleave_box):
            box.rowconfigure(0, weight=1)
            box.columnconfigure(0, weight=1)
        load_box.grid(row=0, column=0, sticky='nsew', padx=2, pady=2)
        cleave_box.grid(row=1, column=0, sticky='nsew', padx=2, pady=2)
        self.loading_text = self._text_in_frame(load_box)
        self.cleavage_text = self._text_in_frame(cleave_box)
        sheets = ttk.Notebook(sheet_box)
        sheets.grid(row=0, column=0, sticky='nsew')
        transfer_box = ttk.Frame(sheets)
        production_box = ttk.Frame(sheets)
        operation_box = ttk.Frame(sheets)
        for box in (transfer_box, production_box, operation_box):
            box.rowconfigure(0, weight=1)
            box.columnconfigure(0, weight=1)
        sheets.add(transfer_box, text='Transfer')
        sheets.add(production_box, text='Production')
        sheets.add(operation_box, text='Operation')
        self.transfer_text = self._text_in_frame(transfer_box)
        self.production_text = self._text_in_frame(production_box)
        self.form_text = self._text_in_frame(operation_box)
        fr.add(calc_box, weight=1)
        fr.add(sheet_box, weight=2)

    def _build_checklist_tab(self):
        fr = ttk.Frame(self.tabs)
        self.tabs.add(fr, text='Checklist')
        fr.rowconfigure(1, weight=2)
        fr.rowconfigure(2, weight=1)
        fr.columnconfigure(0, weight=1)
        top = ttk.Frame(fr, padding=(4, 3))
        top.grid(row=0, column=0, sticky='ew')
        self.checklist_progress_var = tk.DoubleVar(value=0.0)
        self.checklist_progress_label = ttk.Label(top, text='Progress: 0/0 (0%)')
        self.checklist_progress_label.pack(side='left', padx=(0, 10))
        self.checklist_progress_bar = ttk.Progressbar(top, variable=self.checklist_progress_var, maximum=100, length=280)
        self.checklist_progress_bar.pack(side='left', padx=(0, 10))
        ttk.Label(top, text='Toggle rows with double-click or Space').pack(side='left', padx=(0, 10))
        ttk.Button(top, text='All Done', command=self.select_all_progress_rows).pack(side='left', padx=3)
        ttk.Button(top, text='Selected Done', command=self.selected_progress_rows_yes).pack(side='left', padx=3)
        ttk.Button(top, text='Done Until Selected', command=self.mark_until_selected_progress_row).pack(side='left', padx=3)
        ttk.Button(top, text='Clear', command=self.clear_all_progress_rows).pack(side='left', padx=3)
        ttk.Label(top, text='View').pack(side='left', padx=(12, 4))
        self.checklist_view_mode = tk.StringVar(value='Balanced')
        checklist_view = ttk.Combobox(top, textvariable=self.checklist_view_mode, values=['Balanced', 'Progress full', 'Sheet full'], state='readonly', width=16)
        checklist_view.pack(side='left', padx=3)
        checklist_view.bind('<<ComboboxSelected>>', lambda e: self._set_checklist_pane({'Progress full': 'progress', 'Sheet full': 'sheet', 'Balanced': 'balanced'}.get(self.checklist_view_mode.get(), 'balanced')))
        progress_box = ttk.Labelframe(fr, text='Bench Checklist Progress', padding=4)
        progress_box.grid(row=1, column=0, sticky='nsew', padx=4, pady=3)
        progress_box.rowconfigure(0, weight=1)
        progress_box.columnconfigure(0, weight=1)
        self.progress_tree = self._tree_in_frame(progress_box, ['line', 'done', 'checked_at', 'operation', 'unit', 'next_step', 'note'])
        self.progress_tree.bind('<Double-1>', self.toggle_progress_row)
        self.progress_tree.bind('<space>', self.toggle_progress_row)
        printable_box = ttk.Labelframe(fr, text='Printable Bench Sheet / Short Step', padding=4)
        printable_box.grid(row=2, column=0, sticky='nsew', padx=4, pady=3)
        printable_box.rowconfigure(0, weight=1)
        printable_box.columnconfigure(0, weight=1)
        check_tabs = ttk.Notebook(printable_box)
        check_tabs.grid(row=0, column=0, sticky='nsew')
        full_box = ttk.Frame(check_tabs)
        short_box = ttk.Frame(check_tabs)
        for box in (full_box, short_box):
            box.rowconfigure(0, weight=1)
            box.columnconfigure(0, weight=1)
        check_tabs.add(full_box, text='Full checklist')
        check_tabs.add(short_box, text='Short step')
        self.check_text = self._text_in_frame(full_box)
        self.short_step_text = self._text_in_frame(short_box)
        self.next_text = self.check_text

    def _set_checklist_pane(self, mode: str):
        try:
            if mode == 'progress':
                self.tabs.nametowidget(self.tabs.select()).rowconfigure(1, weight=8)
                self.tabs.nametowidget(self.tabs.select()).rowconfigure(2, weight=1)
            elif mode == 'sheet':
                self.tabs.nametowidget(self.tabs.select()).rowconfigure(1, weight=1)
                self.tabs.nametowidget(self.tabs.select()).rowconfigure(2, weight=6)
            else:
                self.tabs.nametowidget(self.tabs.select()).rowconfigure(1, weight=2)
                self.tabs.nametowidget(self.tabs.select()).rowconfigure(2, weight=1)
        except Exception as e:
            self._log(f'Checklist pane resize warning: {e}\n')

    def _build_log_tab(self):
        fr = ttk.Frame(self.tabs)
        self.tabs.add(fr, text='Log')
        fr.rowconfigure(1, weight=1)
        fr.columnconfigure(0, weight=1)
        top = ttk.Frame(fr, padding=(4, 3))
        top.grid(row=0, column=0, sticky='ew')
        ttk.Label(top, text='Log view').pack(side='left', padx=(0, 4))
        self.log_view_mode = tk.StringVar(value='Balanced')
        log_view = ttk.Combobox(top, textvariable=self.log_view_mode, values=['Balanced', 'ML log full', 'App log full'], state='readonly', width=16)
        log_view.pack(side='left', padx=3)
        log_view.bind('<<ComboboxSelected>>', lambda e: self._set_log_pane({'ML log full': 'ml', 'App log full': 'app', 'Balanced': 'balanced'}.get(self.log_view_mode.get(), 'balanced')))
        paned = ttk.PanedWindow(fr, orient='vertical')
        self.log_paned = paned
        paned.grid(row=1, column=0, sticky='nsew')
        ml_box = ttk.Labelframe(paned, text='ML-ready Log', padding=4)
        log_box = ttk.Labelframe(paned, text='Application Log', padding=4)
        for box in (ml_box, log_box):
            box.rowconfigure(0, weight=1)
            box.columnconfigure(0, weight=1)
        self.ml_text = self._text_in_frame(ml_box)
        self.log_text = self._text_in_frame(log_box)
        paned.add(ml_box, weight=1)
        paned.add(log_box, weight=1)

    def _build_project_manager_tab(self):
        """First-screen peptide item manager for multi-peptide SPPS work."""
        fr = ttk.Frame(self.tabs)
        self.tabs.add(fr, text='Project Manager')
        fr.rowconfigure(0, weight=1)
        fr.columnconfigure(0, weight=1)
        paned = tk.PanedWindow(fr, orient='horizontal', sashwidth=10, sashrelief='raised', showhandle=True, bd=1, relief='groove')
        self.pm_paned = paned
        paned.grid(row=0, column=0, sticky='nsew', padx=4, pady=4)
        left = ttk.Labelframe(paned, text='Peptide items  (drag ↔ divider)', padding=6)
        left.configure(width=180)
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)
        btns = ttk.Frame(left)
        btns.grid(row=0, column=0, sticky='ew', pady=(0, 4))
        ttk.Button(btns, text='Add', command=self.pm_add_peptide).pack(side='left', padx=2)
        ttk.Button(btns, text='Duplicate', command=self.pm_duplicate_peptide).pack(side='left', padx=2)
        ttk.Button(btns, text='Delete', command=self.pm_delete_peptide).pack(side='left', padx=2)
        self.pm_list = tk.Listbox(left, height=24, exportselection=False, selectmode=tk.EXTENDED, font=('Segoe UI', 10))
        self.pm_list.grid(row=1, column=0, sticky='nsew')
        sy = ttk.Scrollbar(left, orient='vertical', command=self.pm_list.yview)
        self.pm_list.configure(yscrollcommand=sy.set)
        sy.grid(row=1, column=1, sticky='ns')
        self.pm_list.bind('<<ListboxSelect>>', self.pm_on_select)
        self.pm_list.bind('<Double-Button-1>', self.pm_on_double_click)
        self.pm_list.bind('<Return>', self.pm_on_double_click)
        paned.add(left, minsize=130, width=190)
        right = ttk.Frame(paned)
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)
        edit = ttk.Labelframe(right, text='Selected peptide editor', padding=8)
        edit.grid(row=0, column=0, sticky='ew', padx=4, pady=(0, 4))
        for i in range(10):
            edit.columnconfigure(i, weight=1)
        self.pm_project = tk.StringVar(value='')
        self.pm_peptide = tk.StringVar(value='')
        self.pm_sequence = tk.StringVar(value='')
        self.pm_scale = tk.StringVar(value='0.2')
        self.pm_resin = tk.StringVar(value='Rink Amide AM')
        self.pm_loading = tk.StringVar(value='0.8')
        self.pm_lot = tk.StringVar(value='')
        self.pm_chemistry = tk.StringVar(value='DIC/HOBt')
        self.pm_copies = tk.StringVar(value='1')
        self._pm_loading_editor = False
        for _v in [self.pm_project, self.pm_peptide, self.pm_sequence, self.pm_scale, self.pm_resin, self.pm_loading, self.pm_lot, self.pm_chemistry, self.pm_copies]:
            try:
                _v.trace_add('write', lambda *_: self.after_idle(self.pm_live_sync_selected))
            except Exception:
                pass

        def lab(row, col, text):
            ttk.Label(edit, text=text).grid(row=row, column=col, sticky='w', padx=(2, 4), pady=2)

        def ent(row, col, var, width=18):
            ttk.Entry(edit, textvariable=var, width=width).grid(row=row, column=col + 1, sticky='ew', padx=(0, 8), pady=2)
        lab(0, 0, 'Project')
        ent(0, 0, self.pm_project, 18)
        lab(0, 2, 'Peptide name')
        ent(0, 2, self.pm_peptide, 20)
        lab(1, 0, 'Sequence')
        ttk.Entry(edit, textvariable=self.pm_sequence).grid(row=1, column=1, columnspan=5, sticky='ew', padx=(0, 8), pady=2)
        lab(1, 6, 'Copies')
        ent(1, 6, self.pm_copies, 8)
        lab(2, 0, 'Scale mmol')
        ent(2, 0, self.pm_scale, 10)
        lab(2, 2, 'Resin')
        ttk.Combobox(edit, textvariable=self.pm_resin, values=self.RESIN_VALUES, state='normal', width=22).grid(row=2, column=3, sticky='ew', padx=(0, 8), pady=2)
        lab(2, 4, 'Loading')
        ent(2, 4, self.pm_loading, 10)
        lab(2, 6, 'Chemistry')
        pm_chem_combo = ttk.Combobox(edit, textvariable=self.pm_chemistry, values=['DIC/HOBt', 'DIC/Oxyma', 'HBTU/NMP 10eq', 'HBTU/HOBt/DIPEA', 'HBTU/DIEA', 'HATU/DIPEA', 'HCTU/DIPEA', 'PyBOP/DIPEA', 'Current single-plan settings', 'Manual'], state='readonly', width=20)
        bind_combobox_first_letter_jump(pm_chem_combo)
        pm_chem_combo.grid(row=2, column=7, sticky='ew', padx=(0, 8), pady=2)
        actions = ttk.Frame(edit)
        actions.grid(row=3, column=0, columnspan=10, sticky='ew', pady=(6, 0))
        ttk.Button(actions, text='Generate', command=self.pm_generate_selected).pack(side='left', padx=3)
        ttk.Button(actions, text='Save Session Now', command=self.save_autosave_state).pack(side='left', padx=3)
        moved_actions = ttk.Frame(edit)
        moved_actions.grid(row=4, column=0, columnspan=10, sticky='ew', pady=(5, 0))
        ttk.Label(moved_actions, text='Global actions:').pack(side='left', padx=(0, 4))
        ttk.Button(moved_actions, text='Use DIC/HOBt', command=self.apply_dic_hobt_preset).pack(side='left', padx=3)
        ttk.Button(moved_actions, text='Use HBTU/NMP 10eq', command=self.apply_hbtu_nmp_preset).pack(side='left', padx=3)
        ttk.Button(moved_actions, text='Load Project', command=self.load_project).pack(side='left', padx=3)
        ttk.Button(moved_actions, text='Import Output', command=self.load_output_folder).pack(side='left', padx=3)
        ttk.Button(moved_actions, text='Export', command=self.export_outputs).pack(side='left', padx=3)
        setup_btn = ttk.Button(moved_actions, text='Show setup', command=self.toggle_setup_panel)
        setup_btn.pack(side='left', padx=(10, 3))
        self.setup_toggle_buttons = getattr(self, 'setup_toggle_buttons', []) + [setup_btn]
        self._build_pm_setup_panel(edit)
        results = ttk.Notebook(right)
        results.grid(row=1, column=0, sticky='nsew', padx=4, pady=4)
        sel_plan = ttk.Frame(results)
        sel_mat = ttk.Frame(results)
        sel_check = ttk.Frame(results)
        total = ttk.Frame(results)
        summary = ttk.Frame(results)
        for box in (sel_plan, sel_mat, sel_check, total, summary):
            box.rowconfigure(0, weight=1)
            box.columnconfigure(0, weight=1)
        results.add(sel_plan, text='Selected Plan')
        results.add(sel_mat, text='Selected Materials')
        results.add(sel_check, text='Selected Checklist')
        results.add(total, text='Batch Total Materials')
        results.add(summary, text='Batch Summary')
        self.pm_selected_plan_tree = self._tree_in_frame(sel_plan, ['No', 'Unit name', 'Unit eq', 'Unit amount(g)', 'Coupling reagent 1', 'Coupling cocktail solvent', 'Solvent 1', 'Solvent 1 count', 'Solvent 2', 'Solvent 2 count'])
        self.pm_selected_material_tree = self._tree_in_frame(sel_mat, self.MATERIAL_COLUMNS)
        self.pm_selected_check_text = self._text_in_frame(sel_check)
        self.pm_total_tree = self._tree_in_frame(total, ['material', 'total_g', 'total_mL', 'count', 'note'])
        self.pm_summary_tree = self._tree_in_frame(summary, ['no', 'project', 'peptide', 'sequence', 'scale_mmol', 'resin', 'chemistry', 'status'])
        paned.add(right, minsize=700)
        self.after_idle(lambda: self._set_pm_sash_default())
        self.pm_items = []

    def _build_pm_setup_panel(self, parent):
        """Compact setup panel placed under the selected peptide editor.

        Resin family, scale, and loading are edited only in the selected peptide
        editor above.  This panel only keeps shared synthesis defaults, so the
        same values are not shown twice.
        """
        panel = ttk.Labelframe(parent, text='Setup defaults', padding=6)
        self.pm_setup_panel = panel
        nb = ttk.Notebook(panel)
        nb.pack(fill='x', expand=False)
        tabs = {}
        for name in ['Unit defaults', 'Reagents', 'Solvents / Wash', 'Branch / Tools', 'Output']:
            fr = ttk.Frame(nb, padding=6)
            nb.add(fr, text=name)
            tabs[name] = fr
            for i in range(8):
                fr.columnconfigure(i, weight=1)

        def row(parent, r, c, label, widget, unit=''):
            ttk.Label(parent, text=label).grid(row=r, column=c, sticky='w', padx=(2, 4), pady=2)
            widget.grid(row=r, column=c + 1, sticky='ew', padx=(0, 10), pady=2)
            if unit:
                ttk.Label(parent, text=unit).grid(row=r, column=c + 2, sticky='w', padx=(0, 12), pady=2)
        unit_tab = tabs['Unit defaults']
        row(unit_tab, 0, 0, 'Default AA eq', ttk.Entry(unit_tab, textvariable=self.coupling_eq, width=18), 'eq')
        row(unit_tab, 1, 0, 'Default AA repeat', ttk.Spinbox(unit_tab, from_=1, to=30, textvariable=self.coupling_repeats, width=18))
        row(unit_tab, 0, 4, 'Modifier/label eq', ttk.Entry(unit_tab, textvariable=self.modifier_eq, width=18), 'eq')
        row(unit_tab, 1, 4, 'Modifier repeat', ttk.Spinbox(unit_tab, from_=1, to=30, textvariable=self.modifier_repeats, width=18))
        reagent_tab = tabs['Reagents']
        row(reagent_tab, 0, 0, 'Reagent 1', ttk.Combobox(reagent_tab, textvariable=self.default_reagent, values=self.REAGENT_VALUES, state='normal', width=24))
        row(reagent_tab, 1, 0, 'Reagent 1 eq', ttk.Entry(reagent_tab, textvariable=self.default_reagent_eq, width=18), 'eq')
        row(reagent_tab, 2, 0, 'Reagent 1 count', ttk.Spinbox(reagent_tab, from_=0, to=30, textvariable=self.default_reagent_count, width=18))
        row(reagent_tab, 0, 4, 'Catalyst/additive', ttk.Combobox(reagent_tab, textvariable=self.default_catalyst, values=self.CATALYST_VALUES, state='normal', width=24))
        row(reagent_tab, 1, 4, 'Catalyst eq', ttk.Entry(reagent_tab, textvariable=self.default_catalyst_eq, width=18), 'eq')
        row(reagent_tab, 2, 4, 'Catalyst count', ttk.Spinbox(reagent_tab, from_=0, to=30, textvariable=self.default_catalyst_count, width=18))
        row(reagent_tab, 3, 0, 'Coupling base', ttk.Combobox(reagent_tab, textvariable=self.default_base, values=self.BASE_VALUES, state='normal', width=24))
        row(reagent_tab, 4, 0, 'Base eq', ttk.Entry(reagent_tab, textvariable=self.default_base_eq, width=18), 'eq')
        row(reagent_tab, 5, 0, 'Base count', ttk.Spinbox(reagent_tab, from_=0, to=30, textvariable=self.default_base_count, width=18))
        solvent_tab = tabs['Solvents / Wash']
        row(solvent_tab, 0, 0, 'Cocktail solvent', ttk.Combobox(solvent_tab, textvariable=self.default_coupling_solution_solvent, values=self.SOLVENT_VALUES, state='normal', width=24))
        row(solvent_tab, 1, 0, 'Solvent 1', ttk.Combobox(solvent_tab, textvariable=self.default_solvent1, values=self.SOLVENT_VALUES, state='normal', width=24))
        row(solvent_tab, 2, 0, 'Solvent 1 count', ttk.Spinbox(solvent_tab, from_=0, to=30, textvariable=self.default_solvent1_count, width=18))
        row(solvent_tab, 1, 4, 'Solvent 2', ttk.Combobox(solvent_tab, textvariable=self.default_solvent2, values=self.SOLVENT_VALUES, state='normal', width=24))
        row(solvent_tab, 2, 4, 'Solvent 2 count', ttk.Spinbox(solvent_tab, from_=0, to=30, textvariable=self.default_solvent2_count, width=18))
        row(solvent_tab, 3, 0, 'Loading solvent', ttk.Combobox(solvent_tab, textvariable=self.default_loading_dissolve_solvent, values=self.SOLVENT_VALUES, state='normal', width=24))
        row(solvent_tab, 4, 0, 'Final MeOH wash', ttk.Spinbox(solvent_tab, from_=0, to=30, textvariable=self.final_meoh_count, width=18))
        row(solvent_tab, 0, 4, 'Deprotection base', ttk.Combobox(solvent_tab, textvariable=self.default_depro, values=self.DEPRO_VALUES, state='normal', width=24))
        row(solvent_tab, 3, 4, 'Deprotection ratio', ttk.Combobox(solvent_tab, textvariable=self.default_depro_ratio, values=self.RATIO_VALUES, state='normal', width=24))
        row(solvent_tab, 4, 4, 'Deprotection count', ttk.Spinbox(solvent_tab, from_=0, to=20, textvariable=self.default_depro_count, width=18))
        branch_tab = tabs['Branch / Tools']
        ttk.Checkbutton(branch_tab, text='Enable branch mode', variable=self.branch_mode, command=self.generate_update_plan).grid(row=0, column=0, sticky='w', padx=2, pady=2)
        row(branch_tab, 1, 0, 'Branch point', ttk.Entry(branch_tab, textvariable=self.branch_point, width=18))
        row(branch_tab, 1, 4, 'Branch arm seq', ttk.Entry(branch_tab, textvariable=self.branch_arm, width=24))
        row(branch_tab, 2, 0, 'Protecting group', ttk.Combobox(branch_tab, textvariable=self.branch_pg, values=['Mtt', 'ivDde', 'Dde', 'Alloc', 'Manual'], state='normal', width=18))
        row(branch_tab, 2, 4, 'Deprotection', ttk.Combobox(branch_tab, textvariable=self.branch_depro_condition, values=['Mtt: dilute TFA/TIS/DCM', 'ivDde/Dde: hydrazine/DMF', 'Alloc: Pd(PPh3)4/phenylsilane/DCM', 'Manual'], state='normal', width=34))
        output_tab = tabs['Output']
        output_tab.columnconfigure(1, weight=1)
        ttk.Label(output_tab, text='Output folder').grid(row=0, column=0, sticky='w', padx=2, pady=2)
        ttk.Entry(output_tab, textvariable=self.outdir).grid(row=0, column=1, sticky='ew', padx=(0, 8), pady=2)
        ttk.Button(output_tab, text='Browse', command=self.browse_outdir).grid(row=0, column=2, padx=3, pady=2)
        ttk.Button(output_tab, text='Open Folder', command=self.open_output).grid(row=0, column=3, padx=3, pady=2)
        panel.grid(row=5, column=0, columnspan=10, sticky='ew', pady=(6, 0))
        panel.grid_remove()

    def _set_pm_sash_default(self):
        """Default Project Manager list width; user can resize with the ↔ sash."""
        try:
            if hasattr(self, 'pm_paned'):
                self.pm_paned.sash_place(0, 185, 1)
        except Exception:
            try:
                self.pm_paned.sashpos(0, 185)
            except Exception:
                pass

    def pm_display_name(self, item):
        return f"{item.get('project', '')} | {item.get('peptide', '')} | {item.get('lot', '')}"

    def pm_refresh_list(self, keep_index=None, reload_editor=True):
        if not hasattr(self, 'pm_list'):
            return
        cur = self.pm_list.curselection()
        keep = keep_index if keep_index is not None else cur[0] if cur else 0
        self.pm_list.delete(0, 'end')
        for item in getattr(self, 'pm_items', []):
            self.pm_list.insert('end', self.pm_display_name(item))
        if self.pm_items:
            idx = min(max(int(keep or 0), 0), len(self.pm_items) - 1)
            self.pm_list.selection_set(idx)
            self.pm_list.activate(idx)
            if reload_editor:
                self.pm_load_to_editor(idx)
        self.pm_update_summary()

    def pm_current_index(self):
        if not hasattr(self, 'pm_list'):
            return None
        sel = self.pm_list.curselection()
        if not sel:
            return None
        idx = int(sel[0])
        return idx if 0 <= idx < len(getattr(self, 'pm_items', [])) else None

    def pm_add_peptide(self, item=None):
        if not hasattr(self, 'pm_items'):
            self.pm_items = []
        n = len(self.pm_items) + 1
        item = item or {'project': f'Project-{n:03d}', 'peptide': f'Peptide-{n:03d}', 'sequence': '', 'copies': '1', 'scale': '0.2', 'resin': 'Rink Amide AM', 'loading': '0.8', 'lot': f"SPPS-{datetime.now().strftime('%y%m%d')}-{n:02d}", 'chemistry': 'DIC/HOBt', 'status': 'Ready'}
        self.pm_items.append(dict(item))
        self.pm_refresh_list()
        self.schedule_autosave()

    def pm_duplicate_peptide(self):
        idx = self.pm_current_index()
        if idx is None:
            return
        item = dict(self.pm_items[idx])
        item['peptide'] = str(item.get('peptide', 'Peptide')) + '_copy'
        item['lot'] = f"SPPS-{datetime.now().strftime('%y%m%d')}-{len(self.pm_items) + 1:02d}"
        self.pm_items.append(item)
        self.pm_refresh_list()
        self.schedule_autosave()

    def pm_delete_peptide(self):
        idx = self.pm_current_index()
        if idx is None:
            return
        del self.pm_items[idx]
        if not self.pm_items:
            self.pm_add_peptide()
        self.pm_refresh_list()
        self.schedule_autosave()

    def pm_on_select(self, _event=None):
        idx = self.pm_current_index()
        if idx is not None:
            self.pm_load_to_editor(idx)

    def pm_on_double_click(self, _event=None):
        """Open the peptide item as the active working peptide.

        A single click only loads the editor fields. A double-click is intentionally
        stronger: it applies the stored project/sequence/resin/chemistry/LOT values
        to the main working plan, regenerates the selected Plan/Materials/Checklist,
        and refreshes the batch summary so every red-area result panel matches the
        peptide clicked in the left Peptide items list.
        """
        try:
            idx = self.pm_current_index()
            if idx is None:
                return 'break'
            self.pm_live_sync_selected()
            self.pm_load_to_editor(idx)
            seq = str(self.pm_items[idx].get('sequence', '')).strip()
            if not seq:
                self.pm_clear_selected_outputs()
                self.pm_update_summary()
                self.schedule_autosave()
                return 'break'
            self.pm_generate_selected()
            return 'break'
        except Exception as e:
            try:
                messagebox.showerror('Project Manager', f'Failed to open selected peptide:\n{e}')
            except Exception:
                pass
            return 'break'

    def pm_clear_selected_outputs(self):
        """Clear stale selected-result panels when an item has no sequence yet."""
        for tree_name in ('pm_selected_plan_tree', 'pm_selected_material_tree'):
            tree = getattr(self, tree_name, None)
            if tree is not None:
                for iid in tree.get_children():
                    tree.delete(iid)
        txt = getattr(self, 'pm_selected_check_text', None)
        if txt is not None:
            try:
                txt.delete('1.0', 'end')
            except Exception:
                pass

    def pm_load_to_editor(self, idx):
        item = self.pm_items[idx]
        self._pm_loading_editor = True
        try:
            self.pm_project.set(item.get('project', ''))
            self.pm_peptide.set(item.get('peptide', ''))
            self.pm_sequence.set(item.get('sequence', ''))
            self.pm_scale.set(str(item.get('scale', '0.2')))
            self.pm_resin.set(item.get('resin', 'Rink Amide AM'))
            self.pm_loading.set(str(item.get('loading', '0.8')))
            self.pm_lot.set('')
            self.pm_chemistry.set(item.get('chemistry', 'DIC/HOBt'))
            self.pm_copies.set(str(item.get('copies', '1')))
        finally:
            self._pm_loading_editor = False
        self.pm_update_summary()

    def pm_live_sync_selected(self):
        if getattr(self, '_pm_loading_editor', False):
            return
        idx = self.pm_current_index() if hasattr(self, 'pm_list') else None
        if idx is None or idx < 0 or idx >= len(getattr(self, 'pm_items', [])):
            return
        try:
            self.pm_items[idx].update({'project': self.pm_project.get().strip(), 'peptide': self.pm_peptide.get().strip(), 'sequence': self.pm_sequence.get().strip(), 'scale': self.pm_scale.get().strip(), 'resin': self.pm_resin.get().strip(), 'loading': self.pm_loading.get().strip(), 'lot': '', 'lot_no': '', 'chemistry': self.pm_chemistry.get().strip(), 'copies': self.pm_copies.get().strip(), 'status': self.pm_items[idx].get('status', 'Ready')})
            self.pm_refresh_list(keep_index=idx, reload_editor=False)
            self.pm_update_summary()
            if hasattr(self, 'batch_tree'):
                self.refresh_batch_workspace_preview()
            self.schedule_autosave()
        except Exception:
            pass

    def pm_save_selected(self):
        idx = self.pm_current_index()
        if idx is None:
            return
        self.pm_items[idx].update({'project': self.pm_project.get().strip(), 'peptide': self.pm_peptide.get().strip(), 'sequence': self.pm_sequence.get().strip(), 'scale': self.pm_scale.get().strip(), 'resin': self.pm_resin.get().strip(), 'loading': self.pm_loading.get().strip(), 'lot': '', 'lot_no': '', 'chemistry': self.pm_chemistry.get().strip(), 'copies': self.pm_copies.get().strip(), 'status': self.pm_items[idx].get('status', 'Ready')})
        self.pm_refresh_list()
        self.schedule_autosave()

    def pm_apply_item_to_single_plan(self, item):
        self.seq.set(str(item.get('sequence', '')))
        self.scale.set(float(self._to_float(item.get('scale'), 0.2)))
        self.resin.set(str(item.get('resin', 'Rink Amide AM')))
        self.loading.set(float(self._to_float(item.get('loading'), 0.8)))
        if hasattr(self, 'lot_no'):
            self.lot_no.set('')

    def pm_tree_to_df(self, tree):
        cols = list(tree['columns'])
        rows = []
        for iid in tree.get_children():
            vals = list(tree.item(iid, 'values'))
            vals += [''] * max(0, len(cols) - len(vals))
            rows.append(dict(zip(cols, vals)))
        return pd.DataFrame(rows, columns=cols)

    def pm_generate_selected(self):
        self.pm_save_selected()
        idx = self.pm_current_index()
        if idx is None:
            return
        item = self.pm_items[idx]
        try:
            self.pm_apply_item_to_single_plan(item)
            self.generate_update_plan()
            item['status'] = 'Calculated'
            self._write_tree(self.pm_selected_plan_tree, self.pm_tree_to_df(self.tree), list(self.pm_selected_plan_tree['columns']))
            self._write_tree(self.pm_selected_material_tree, self.pm_tree_to_df(self.live_usage_tree), list(self.pm_selected_material_tree['columns']))
            try:
                self.pm_selected_check_text.delete('1.0', 'end')
                self.pm_selected_check_text.insert('end', self.short_step_text.get('1.0', 'end'))
            except Exception:
                pass
            self.pm_refresh_list()
            self.pm_update_summary()
        except Exception as e:
            item['status'] = 'Error'
            messagebox.showerror('Project Manager', str(e))

    def pm_calculate_all(self):
        self.pm_save_selected()
        total_rows = []
        summary_rows = []
        for idx, item in enumerate(list(self.pm_items), start=1):
            try:
                self.pm_apply_item_to_single_plan(item)
                self.generate_update_plan()
                item['status'] = 'Calculated'
                mats = self.pm_tree_to_df(self.live_usage_tree)
                copies = max(1, int(round(self._to_float(item.get('copies'), 1))))
                for _, r in mats.iterrows():
                    material = str(r.get('material', '')).strip()
                    if not material or material.startswith('No material'):
                        continue
                    total_rows.append({'material': material, 'total_g': self._to_float(r.get('planned_g'), 0) * copies, 'total_mL': self._to_float(r.get('planned_mL'), 0) * copies, 'count': self._to_float(r.get('use_count'), 0) * copies, 'note': r.get('note', '')})
                summary_rows.append({'no': idx, 'project': item.get('project', ''), 'peptide': item.get('peptide', ''), 'sequence': item.get('sequence', ''), 'scale_mmol': item.get('scale', ''), 'resin': item.get('resin', ''), 'chemistry': item.get('chemistry', ''), 'status': item.get('status', '')})
            except Exception:
                item['status'] = 'Error'
        if total_rows:
            df = pd.DataFrame(total_rows)
            total = df.groupby('material', as_index=False).agg({'total_g': 'sum', 'total_mL': 'sum', 'count': 'sum', 'note': 'first'})
            for col in ['total_g', 'total_mL', 'count']:
                total[col] = total[col].round(4)
        else:
            total = pd.DataFrame(columns=['material', 'total_g', 'total_mL', 'count', 'note'])
        self._write_tree(self.pm_total_tree, total, ['material', 'total_g', 'total_mL', 'count', 'note'])
        self._write_tree(self.pm_summary_tree, pd.DataFrame(summary_rows), ['no', 'project', 'peptide', 'sequence', 'scale_mmol', 'resin', 'chemistry', 'status'])
        self.pm_refresh_list()

    def pm_update_summary(self):
        if not hasattr(self, 'pm_summary_tree'):
            return
        rows = [{'no': i, 'project': item.get('project', ''), 'peptide': item.get('peptide', ''), 'sequence': item.get('sequence', ''), 'scale_mmol': item.get('scale', ''), 'resin': item.get('resin', ''), 'chemistry': item.get('chemistry', ''), 'status': item.get('status', '')} for i, item in enumerate(getattr(self, 'pm_items', []), start=1)]
        self._write_tree(self.pm_summary_tree, pd.DataFrame(rows), ['no', 'project', 'peptide', 'sequence', 'scale_mmol', 'resin', 'chemistry', 'status'])

    def pm_send_to_batch_manager(self):
        try:
            if not hasattr(self, 'batch_tree'):
                return
            for item_id in list(self.batch_tree.get_children()):
                self.batch_tree.delete(item_id)
            for item in getattr(self, 'pm_items', []):
                self.batch_add_row({'Project': item.get('project', ''), 'Peptide name': item.get('peptide', ''), 'Form': 'linear', 'Copies': item.get('copies', '1'), 'N-term': 'Ac' if self._sequence_has_nterm_ac(item.get('sequence', '')) else '', 'Region 1 seq': item.get('sequence', ''), 'Region 1 eq': '1', 'Linker': '', 'Region 2 seq': '', 'Region 2 eq': '', 'Tag': '', 'Label': '', 'C-term': 'NH2', 'D/non-natural notes': '', 'Chemistry': item.get('chemistry', 'DIC/HOBt'), 'Scale mmol': item.get('scale', '0.2'), 'AA conc M': getattr(self, 'batch_solution_conc', _v225_const_var('0.25')).get(), 'AA coupling eq': getattr(self, 'batch_coupling_eq', _v225_const_var('10')).get(), 'Resin': item.get('resin', 'Rink Amide AM'), 'Loading': item.get('loading', '0.8'), 'LOT No': item.get('lot', ''), 'Status': item.get('status', 'Ready')})
            self.tabs.select(self.tabs.index('end') - 1)
            self.schedule_autosave()
        except Exception as e:
            messagebox.showerror('Send to Batch Manager', str(e))

    def _build_batch_tab(self):
        """Build the synthesizer-oriented batch manager.

        This tab is for real synthesizer operation: multiple projects/peptides are kept
        in one editable table, each row can be calculated in parallel, and total AA/
        reagent/solvent use is summarized for weighing and solution preparation.
        """
        fr = ttk.Frame(self.tabs)
        self.tabs.add(fr, text='Batch Manager')
        fr.rowconfigure(2, weight=1)
        fr.rowconfigure(3, weight=2)
        fr.columnconfigure(0, weight=1)
        top = ttk.Frame(fr, padding=(4, 3))
        top.grid(row=0, column=0, sticky='ew')
        ttk.Button(top, text='Add peptide', command=self.batch_add_row).pack(side='left', padx=3)
        ttk.Button(top, text='Delete selected', command=self.batch_delete_selected).pack(side='left', padx=3)
        ttk.Button(top, text='Generate Batch Workspace', command=self.run_batch_plans).pack(side='left', padx=3)
        ttk.Button(top, text='Load CSV', command=self.load_batch_csv).pack(side='left', padx=3)
        ttk.Button(top, text='Save CSV', command=self.save_batch_csv).pack(side='left', padx=3)
        ttk.Button(top, text='Open Batch Folder', command=self.open_batch_output).pack(side='left', padx=3)
        ttk.Button(top, text='Sync from Project Manager', command=self.pm_send_to_batch_manager).pack(side='left', padx=3)
        ttk.Button(top, text='Save Session Now', command=self.save_autosave_state).pack(side='left', padx=3)
        defaults = ttk.Labelframe(fr, text='Synthesizer solution defaults', padding=4)
        defaults.grid(row=1, column=0, sticky='ew', padx=4, pady=3)
        self.batch_solution_conc = tk.StringVar(value='0.25')
        self.batch_coupling_eq = tk.StringVar(value='10')
        self.batch_actual_round_ml = tk.StringVar(value='10')
        self.batch_actual_extra_ml = tk.StringVar(value='10')
        self.batch_default_scale = tk.StringVar(value='0.2')
        self.batch_default_resin = tk.StringVar(value='Rink Amide AM')
        self.batch_default_loading = tk.StringVar(value='0.8')
        self.batch_hbtu_eq = tk.StringVar(value='10')
        self.batch_hbtu_conc = tk.StringVar(value='0.4')
        self.batch_hbtu_mw = tk.StringVar(value='379.25')
        self.batch_nmp_density = tk.StringVar(value='1.03')
        fields = [('Scale / column (mmol)', self.batch_default_scale), ('AA solution conc. (M)', self.batch_solution_conc), ('AA coupling eq', self.batch_coupling_eq), ('Actual round mL', self.batch_actual_round_ml), ('Extra mL', self.batch_actual_extra_ml), ('Default resin', self.batch_default_resin), ('Loading mmol/g', self.batch_default_loading), ('HBTU eq', self.batch_hbtu_eq), ('HBTU conc M', self.batch_hbtu_conc)]
        for i, (label, var) in enumerate(fields):
            ttk.Label(defaults, text=label).grid(row=0, column=i * 2, sticky='w', padx=(2, 3))
            width = 11 if i < 5 else 18
            ttk.Entry(defaults, textvariable=var, width=width).grid(row=0, column=i * 2 + 1, sticky='ew', padx=(0, 8))
        defaults.columnconfigure(11, weight=1)
        for _v in [self.batch_solution_conc, self.batch_coupling_eq, self.batch_actual_round_ml, self.batch_actual_extra_ml, self.batch_default_scale, self.batch_default_resin, self.batch_default_loading, self.batch_hbtu_eq, self.batch_hbtu_conc, self.batch_hbtu_mw, self.batch_nmp_density]:
            try:
                _v.trace_add('write', lambda *_: self.after_idle(self.refresh_batch_workspace_preview))
            except Exception:
                pass
        input_box = ttk.Labelframe(fr, text='Batch peptide/project table', padding=4)
        input_box.grid(row=2, column=0, sticky='nsew', padx=4, pady=3)
        input_box.rowconfigure(0, weight=1)
        input_box.columnconfigure(0, weight=1)
        self.batch_columns = ['No', 'Project', 'Peptide name', 'Form', 'Copies', 'N-term', 'Region 1 seq', 'Region 1 eq', 'Linker', 'Region 2 seq', 'Region 2 eq', 'Tag', 'Label', 'C-term', 'Chemistry', 'Scale mmol', 'AA conc M', 'AA coupling eq', 'Resin', 'Loading', 'LOT No', 'Status']
        combo = {'Form': ['linear', 'branched', 'cyclic', 'bivalent', 'manual'], 'N-term': ['', 'Ac', 'Pal', 'Myr', 'Gal', 'Nic', 'Caf', 'Biotin', 'FITC', 'FAM', 'TAMRA', 'CY3', 'CY5', 'DOTA', 'NOTA', 'Manual'], 'Linker': ['', *self.FMOC_LINKER_VALUES, 'Manual'], 'Tag': ['', 'His6', 'His8', 'His10', 'FLAG', 'HA', 'Myc', 'StrepII', 'TwinStrep', 'V5', 'T7', 'ALFA', 'AviTag', 'SpyTag', 'Manual'], 'Label': ['', 'Biotin', 'Biotin-NHS', 'FITC', 'FAM', 'TAMRA', 'ROX', 'CY3', 'CY5', 'CY5.5', 'CY7', 'Alexa488', 'Dabcyl', 'BHQ1', 'BHQ2', 'Manual'], 'C-term': ['NH2', 'OH', 'COOH', 'acid', 'amide', 'Manual'], 'Chemistry': ['DIC/HOBt', 'DIC/Oxyma', 'HBTU/NMP 10eq', 'HBTU/HOBt/DIPEA', 'HBTU/DIEA', 'HATU/DIPEA', 'Manual'], 'Resin': self.RESIN_VALUES}
        self.batch_tree = EditableTree(input_box, self.batch_columns, on_edit=self.batch_on_edit, combo_values=combo)
        by = ttk.Scrollbar(input_box, orient='vertical', command=self.batch_tree.yview)
        bx = ttk.Scrollbar(input_box, orient='horizontal', command=self.batch_tree.xview)
        self.batch_tree.configure(yscrollcommand=by.set, xscrollcommand=bx.set)
        self.batch_tree.grid(row=0, column=0, sticky='nsew')
        by.grid(row=0, column=1, sticky='ns')
        bx.grid(row=1, column=0, sticky='ew')
        widths = {'No': 45, 'Project': 120, 'Peptide name': 150, 'Form': 85, 'Copies': 65, 'N-term': 95, 'Region 1 seq': 190, 'Region 1 eq': 80, 'Linker': 230, 'Region 2 seq': 150, 'Region 2 eq': 80, 'Tag': 100, 'Label': 110, 'C-term': 80, 'Chemistry': 140, 'Scale mmol': 85, 'AA conc M': 85, 'AA coupling eq': 95, 'Resin': 140, 'Loading': 80, 'LOT No': 150, 'Status': 120}
        for c, w in widths.items():
            self.batch_tree.column(c, width=w, minwidth=50, stretch=True)
        preview = ttk.PanedWindow(fr, orient='horizontal')
        preview.grid(row=3, column=0, sticky='nsew', padx=4, pady=3)
        layout_box = ttk.Labelframe(preview, text='Synthesizer layout / peptide columns', padding=4)
        totals_box = ttk.Labelframe(preview, text='Batch total usage dashboard', padding=4)
        project_box = ttk.Labelframe(preview, text='Project summary', padding=4)
        for box in (layout_box, totals_box, project_box):
            box.rowconfigure(0, weight=1)
            box.columnconfigure(0, weight=1)
        self.batch_layout_text = self._text_in_frame(layout_box)
        self.batch_total_notebook = ttk.Notebook(totals_box)
        self.batch_total_notebook.grid(row=0, column=0, sticky='nsew')

        def _tot_tab(title, cols):
            frame = ttk.Frame(self.batch_total_notebook)
            frame.rowconfigure(0, weight=1)
            frame.columnconfigure(0, weight=1)
            self.batch_total_notebook.add(frame, text=title)
            return self._tree_in_frame(frame, cols)
        common_cols = ['item', 'purpose', 'count', 'eq', 'conc_M', 'calculated', 'actual', 'unit', 'MW', 'density', 'weight_g', 'volume_mL', 'note']
        self.batch_aa_tree = _tot_tab('AA prep', ['AA', 'count', 'eq', 'conc_M', 'calc_mL', 'actual_mL', 'MW', 'weight_g', 'note'])
        self.batch_coupling_reagent_tree = _tot_tab('Coupling prep', common_cols)
        self.batch_catalyst_tree = _tot_tab('Catalyst/Additive', common_cols)
        self.batch_base_tree = _tot_tab('Base/Deprotection', common_cols)
        self.batch_solvent_tree = _tot_tab('Solvent/Wash', common_cols)
        self.batch_modifier_tree = _tot_tab('Modifier/Tag/Label/Linker', common_cols)
        self.batch_project_tree = self._tree_in_frame(project_box, ['no', 'project', 'peptide_name', 'lot_no', 'copies', 'sequence', 'scale_mmol', 'resin', 'output_folder'])
        self.batch_material_tree = self.batch_aa_tree
        self.batch_hbtu_tree = self.batch_coupling_reagent_tree
        self.batch_cap_tree = self.batch_modifier_tree
        preview.add(layout_box, weight=2)
        preview.add(totals_box, weight=4)
        preview.add(project_box, weight=2)
        self.last_batch_outdir = None
        self.refresh_batch_workspace_preview()

    def batch_add_row(self, values=None):
        values = values or {}
        if not hasattr(self, 'batch_tree'):
            return
        no = len(self.batch_tree.get_children()) + 1
        lot = values.get('LOT No') or f"SPPS-{datetime.now().strftime('%y%m%d')}-{no:02d}"
        row = {'No': no, 'Project': values.get('Project', ''), 'Peptide name': values.get('Peptide name', ''), 'Form': values.get('Form', 'linear'), 'Copies': values.get('Copies', '1'), 'N-term': values.get('N-term', 'Ac' if self._sequence_has_nterm_ac(values.get('Region 1 seq', '')) else ''), 'Region 1 seq': values.get('Region 1 seq', ''), 'Region 1 eq': values.get('Region 1 eq', '1'), 'Linker': values.get('Linker', ''), 'Region 2 seq': values.get('Region 2 seq', ''), 'Region 2 eq': values.get('Region 2 eq', ''), 'Tag': values.get('Tag', ''), 'Label': values.get('Label', ''), 'C-term': values.get('C-term', 'NH2'), 'Chemistry': values.get('Chemistry', 'DIC/HOBt'), 'Scale mmol': values.get('Scale mmol', getattr(self, 'batch_default_scale', _v225_const_var('0.2')).get()), 'AA conc M': values.get('AA conc M', getattr(self, 'batch_solution_conc', _v225_const_var('0.25')).get()), 'AA coupling eq': values.get('AA coupling eq', getattr(self, 'batch_coupling_eq', _v225_const_var('10')).get()), 'Resin': values.get('Resin', getattr(self, 'batch_default_resin', _v225_const_var('Rink Amide AM')).get()), 'Loading': values.get('Loading', getattr(self, 'batch_default_loading', _v225_const_var('0.8')).get()), 'LOT No': lot, 'Status': values.get('Status', 'Ready')}
        self.batch_tree.insert('', 'end', values=[row[c] for c in self.batch_columns])
        self.refresh_batch_workspace_preview()
        self.schedule_autosave()

    def batch_on_edit(self, *_):
        try:
            self.refresh_batch_workspace_preview()
            self.schedule_autosave()
        except Exception:
            pass

    def batch_delete_selected(self):
        for item in list(self.batch_tree.selection()):
            self.batch_tree.delete(item)
        self._renumber_batch_rows()
        self.refresh_batch_workspace_preview()
        self.schedule_autosave()

    def _renumber_batch_rows(self):
        if not hasattr(self, 'batch_tree'):
            return
        for i, item in enumerate(self.batch_tree.get_children(), start=1):
            vals = list(self.batch_tree.item(item, 'values'))
            if vals:
                vals[0] = i
                self.batch_tree.item(item, values=vals)

    def _batch_rows_from_tree(self):
        rows = []
        if not hasattr(self, 'batch_tree'):
            return rows
        for item in self.batch_tree.get_children():
            vals = list(self.batch_tree.item(item, 'values'))
            vals += [''] * (len(self.batch_columns) - len(vals))
            d = dict(zip(self.batch_columns, vals))
            if not str(d.get('Region 1 seq', '')).strip() and (not str(d.get('Peptide name', '')).strip()):
                continue
            rows.append(d)
        return rows

    def _aa_letters_from_sequence(self, seq: str) -> list[str]:
        """Return synthesizer solution tokens from a user sequence.

        Caps/linkers/tags are ignored here because those are handled in the
        modifier table. D-amino acids and non-natural amino acids are kept as
        solution-prep items instead of being shown as a separate meaningless
        category.
        """
        s = str(seq or '')
        if not s or s.strip() in {'-', '_'}:
            return []
        ignore = {'AC', 'NH', 'NH2', 'COOH', 'OH', 'PAL', 'MYR', 'GAL', 'NIC', 'CAF', 'AEEA', 'AHX', 'PEG', 'PEG1', 'PEG3', 'PEG4', 'PEG6', 'PEG8', 'BALA', 'GALA', 'BIOTIN', 'FITC', 'FAM', 'TAMRA', 'CY', 'CY3', 'CY5', 'CY7', 'DOTA', 'NOTA'}
        d3 = {'DALA': 'D-Ala', 'DARG': 'D-Arg', 'DASN': 'D-Asn', 'DASP': 'D-Asp', 'DCYS': 'D-Cys', 'DGLN': 'D-Gln', 'DGLU': 'D-Glu', 'DHIS': 'D-His', 'DILE': 'D-Ile', 'DLEU': 'D-Leu', 'DLYS': 'D-Lys', 'DPHE': 'D-Phe', 'DPRO': 'D-Pro', 'DSER': 'D-Ser', 'DTYR': 'D-Tyr', 'DVAL': 'D-Val'}
        specials = {'HYP': 'Hyp', 'NLE': 'Nle', 'NVA': 'Nva', 'ORN': 'Orn', 'DAP': 'Dap', 'DAB': 'Dab', 'AIB': 'Aib', 'SAR': 'Sar', 'BPA': 'Bpa', 'CHA': 'Cha', 'CIT': 'Cit', 'HARG': 'hArg', 'HLYS': 'hLys', 'PEN': 'Pen'}
        tokens = []
        try:
            raw_tokens = list(tokenize_core_sequence(s))
        except Exception:
            raw_tokens = re.split('[-_\\s,;/()]+', s)
        for raw in raw_tokens:
            t = str(raw).strip()
            if not t:
                continue
            if re.match('^D[-_][A-Za-z]{1,3}$', t):
                base = re.sub('^D[-_]', '', t, flags=re.I).upper()
                one = {'A': 'Ala', 'R': 'Arg', 'N': 'Asn', 'D': 'Asp', 'C': 'Cys', 'Q': 'Gln', 'E': 'Glu', 'G': 'Gly', 'H': 'His', 'I': 'Ile', 'L': 'Leu', 'K': 'Lys', 'M': 'Met', 'F': 'Phe', 'P': 'Pro', 'S': 'Ser', 'T': 'Thr', 'W': 'Trp', 'Y': 'Tyr', 'V': 'Val'}.get(base, base.title())
                tokens.append('D-' + one)
                continue
            key = re.sub('[^A-Za-z0-9]', '', t).upper()
            if key in ignore:
                continue
            if key in d3:
                tokens.append(d3[key])
                continue
            if key in specials:
                tokens.append(specials[key])
                continue
            if len(key) == 1 and key in set('ARNDCQEGHILKMFPSTWYV'):
                tokens.append(key)
                continue
        if tokens:
            return tokens
        cleaned = re.sub('(?i)Ac|NH2|COOH|OH', '', s)
        return [c.upper() for c in cleaned if c.upper() in set('ARNDCQEGHILKMFPSTWYV')]

    def _sequence_has_nterm_ac(self, seq: str) -> bool:
        s = str(seq or '').strip()
        return bool(re.match('^\\s*Ac(?:[-_]|$)', s, flags=re.IGNORECASE))

    def _batch_ac_cap_count_by_rows(self, rows=None) -> float:
        rows = rows if rows is not None else self._batch_rows_from_tree()
        total = 0.0
        for r in rows:
            copies = int(round(self._to_float(r.get('Copies'), 1))) or 1
            if self._sequence_has_nterm_ac(r.get('Region 1 seq')):
                total += copies
        return total

    def _batch_ac_cap_summary(self, rows=None) -> pd.DataFrame:
        rows = rows if rows is not None else self._batch_rows_from_tree()
        count = self._batch_ac_cap_count_by_rows(rows)
        if count <= 0:
            return pd.DataFrame(columns=['material', 'count', 'calc_mL', 'actual_mL', 'MW', 'weight_g', 'note'])
        round_ml = max(self._to_float(getattr(self, 'batch_actual_round_ml', _v225_const_var('10')).get(), 10), 1)
        extra_ml = max(self._to_float(getattr(self, 'batch_actual_extra_ml', _v225_const_var('10')).get(), 10), 0)
        mw = 102.09
        density = 1.08
        total_mmol = 0.0
        for r in rows:
            copies = int(round(self._to_float(r.get('Copies'), 1))) or 1
            if not self._sequence_has_nterm_ac(r.get('Region 1 seq')):
                continue
            scale = self._to_float(r.get('Scale mmol'), self._to_float(getattr(self, 'batch_default_scale', _v225_const_var('0.2')).get(), 0.2))
            ac_eq = self._to_float(getattr(self, 'modifier_eq', _v225_const_var('3')).get(), 3.0)
            total_mmol += copies * scale * ac_eq
        calc_g = total_mmol * mw / 1000.0
        calc_ml = calc_g / density if density else 0.0
        actual_ml = int((calc_ml + round_ml - 1) // round_ml) * round_ml + extra_ml if calc_ml else 0.0
        actual_g = actual_ml * density if actual_ml else calc_g
        return pd.DataFrame([{'material': 'Acetic anhydride (Ac2O) for Ac', 'count': int(count) if float(count).is_integer() else round(count, 3), 'calc_mL': round(calc_ml, 3), 'actual_mL': round(actual_ml, 2), 'MW': mw, 'weight_g': round(actual_g, 3), 'note': 'Detected N-terminal Ac-. Reagent MW 102.09, density 1.08 g/mL; peptide mass contribution is +42.04 Da.'}], columns=['material', 'count', 'calc_mL', 'actual_mL', 'MW', 'weight_g', 'note'])

    def _normalize_batch_modifier(self, value: str) -> str:
        v = str(value or '').strip()
        if not v or v.lower() in {'none', '-', 'manual'}:
            return ''
        aliases = {'ac': 'Ac', 'acetyl': 'Ac', 'acetylation': 'Ac', 'pal': 'Pal', 'palmitic': 'Pal', 'palmitic acid': 'Pal', 'myr': 'Myr', 'myristic': 'Myr', 'myristic acid': 'Myr', 'gal': 'Gal', 'gallic': 'Gal', 'gallic acid': 'Gal', 'nic': 'Nic', 'nicotinic': 'Nic', 'nicotinic acid': 'Nic', 'caf': 'Caf', 'caffeic': 'Caf', 'caffeic acid': 'Caf', 'biotin-nhs': 'Biotin-NHS', 'biotin nhs': 'Biotin-NHS', 'cy3': 'CY3', 'cy5': 'CY5', 'cy5.5': 'CY5.5', 'cy7': 'CY7', 'fitc': 'FITC', 'fam': 'FAM', 'tamra': 'TAMRA', 'rox': 'ROX', 'ahx': 'Ahx', 'aeea': 'AEEA', 'peg1': 'PEG1', 'peg3': 'PEG3', 'peg4': 'PEG4', 'peg6': 'PEG6', 'peg8': 'PEG8', 'bala': 'bAla', 'b-ala': 'bAla', 'beta-ala': 'bAla', 'gala': 'gAla', 'g-ala': 'gAla', 'gamma-ala': 'gAla', 'his6': 'His6', 'his8': 'His8', 'his10': 'His10', 'flag': 'FLAG', 'ha': 'HA', 'myc': 'Myc', 'strepii': 'StrepII', 'twinstrep': 'TwinStrep'}
        return aliases.get(v.lower(), v)

    def _extract_sequence_special_tokens(self, seq: str) -> list[str]:
        specials = []
        for raw in re.split('[-_\\s,;/]+', str(seq or '')):
            t = raw.strip()
            if not t:
                continue
            low = t.lower()
            if low.startswith('d') and len(low) > 1 and (low.startswith('d-') or low in {'dala', 'darg', 'dasn', 'dasp', 'dcys', 'dgln', 'dglu', 'dhis', 'dile', 'dleu', 'dlys', 'dphe', 'dpro', 'dser', 'dtyr', 'dval'}):
                specials.append(t)
            norm = self._normalize_batch_modifier(t)
            if norm and norm not in set('ARNDCQEGHILKMFPSTWYV') and (norm not in {'NH2', 'COOH', 'OH'}):
                if norm not in specials:
                    specials.append(norm)
            if low in {'hyp', 'nle', 'nva', 'orn', 'dap', 'dab', 'aib', 'sar', 'bpa', 'cha', 'cit', 'harg', 'hlys', 'pen'}:
                if t not in specials:
                    specials.append(t)
        return specials

    def _batch_modifier_summary(self, rows=None) -> pd.DataFrame:
        rows = rows if rows is not None else self._batch_rows_from_tree()
        round_ml = max(self._to_float(getattr(self, 'batch_actual_round_ml', _v225_const_var('10')).get(), 10), 1)
        extra_ml = max(self._to_float(getattr(self, 'batch_actual_extra_ml', _v225_const_var('10')).get(), 10), 0)
        mod_eq = self._to_float(getattr(self, 'modifier_eq', _v225_const_var('3')).get(), 3.0)
        records = {}

        def add_record(material, typ, copies, scale, eq=None, note=''):
            mat = self._normalize_batch_modifier(material)
            if not mat:
                return
            key = (mat, typ)
            rec = records.setdefault(key, {'material': mat, 'type': typ, 'count': 0.0, 'mmol': 0.0, 'note': note})
            rec['count'] += copies
            rec['mmol'] += copies * scale * (mod_eq if eq is None else eq)
            if note and note not in rec.get('note', ''):
                rec['note'] = (rec.get('note', '') + '; ' + note).strip('; ')
        for r in rows:
            copies = int(round(self._to_float(r.get('Copies'), 1))) or 1
            scale = self._to_float(r.get('Scale mmol'), self._to_float(getattr(self, 'batch_default_scale', _v225_const_var('0.2')).get(), 0.2))
            nterm = self._normalize_batch_modifier(r.get('N-term'))
            if not nterm and self._sequence_has_nterm_ac(r.get('Region 1 seq')):
                nterm = 'Ac'
            if nterm:
                add_record('Acetic anhydride (Ac2O)' if nterm == 'Ac' else nterm, 'N-term', copies, scale, note='N-terminal modifier/cap')
            for col, typ in [('Linker', 'linker'), ('Tag', 'tag'), ('Label', 'label')]:
                val = self._normalize_batch_modifier(r.get(col))
                if val:
                    add_record(val, typ, copies, scale, note=f'{typ}; verify reagent form/vendor MW if exact weighing is needed')
            for seq_col in ['Region 1 seq', 'Region 2 seq']:
                for sp in self._extract_sequence_special_tokens(r.get(seq_col)):
                    mat = self._normalize_batch_modifier(sp)
                    if mat in {'Ac'}:
                        continue
                    add_record(mat, 'sequence special', copies, scale, note='Detected in sequence; verify AA derivative/protecting group')
            note = str(r.get('D/non-natural notes', '')).strip()
            if note:
                add_record(note, 'D/non-natural note', copies, scale, eq=0, note='manual note only')
        out = []
        for rec in records.values():
            material = rec['material']
            mw = 102.09 if 'Ac2O' in material else self._mw_for_token(material) or self.MW_FALLBACK.get(material, 0.0)
            density = 1.08 if 'Ac2O' in material else 0.0
            mmol = rec.get('mmol', 0.0)
            calc_g = mmol * mw / 1000.0 if mw else 0.0
            calc_ml = calc_g / density if density else 0.0
            actual_ml = int((calc_ml + round_ml - 1) // round_ml) * round_ml + extra_ml if calc_ml else ''
            weight_g = actual_ml * density if isinstance(actual_ml, (int, float)) and density else round(calc_g, 4) if calc_g else ''
            out.append({'material': material, 'type': rec.get('type', ''), 'count': int(rec['count']) if float(rec['count']).is_integer() else round(rec['count'], 3), 'calc_mL': round(calc_ml, 3) if calc_ml else '', 'actual_mL': round(actual_ml, 2) if isinstance(actual_ml, (int, float)) else '', 'MW': round(mw, 2) if mw else 'manual', 'weight_g': round(weight_g, 3) if isinstance(weight_g, (int, float)) else weight_g, 'note': rec.get('note', '')})
        return pd.DataFrame(out, columns=['material', 'type', 'count', 'calc_mL', 'actual_mL', 'MW', 'weight_g', 'note'])

    def _batch_aa_synthesizer_summary(self, rows=None) -> pd.DataFrame:
        rows = rows if rows is not None else self._batch_rows_from_tree()
        counts = {}
        calc_ml_by_aa = {}
        mmol_by_aa = {}
        conc_by_aa = {}
        for r in rows:
            copies = int(round(self._to_float(r.get('Copies'), 1))) or 1
            scale = self._to_float(r.get('Scale mmol'), self._to_float(getattr(self, 'batch_default_scale', _v225_const_var('0.2')).get(), 0.2))
            conc = self._to_float(r.get('AA conc M'), self._to_float(getattr(self, 'batch_solution_conc', _v225_const_var('0.25')).get(), 0.25))
            aa_eq = self._to_float(r.get('AA coupling eq'), self._to_float(getattr(self, 'batch_coupling_eq', _v225_const_var('10')).get(), 10))
            regions = [(r.get('Region 1 seq'), r.get('Region 1 eq')), (r.get('Region 2 seq'), r.get('Region 2 eq'))]
            for seq, eq in regions:
                region_eq = self._to_float(eq, 0)
                if region_eq <= 0:
                    continue
                for aa in self._aa_letters_from_sequence(seq):
                    count_add = copies * region_eq
                    mmol_add = count_add * scale * aa_eq
                    ml_add = mmol_add / conc if conc else 0.0
                    counts[aa] = counts.get(aa, 0.0) + count_add
                    mmol_by_aa[aa] = mmol_by_aa.get(aa, 0.0) + mmol_add
                    calc_ml_by_aa[aa] = calc_ml_by_aa.get(aa, 0.0) + ml_add
                    conc_by_aa.setdefault(aa, conc)
        round_ml = max(self._to_float(getattr(self, 'batch_actual_round_ml', _v225_const_var('10')).get(), 10), 1)
        extra_ml = max(self._to_float(getattr(self, 'batch_actual_extra_ml', _v225_const_var('10')).get(), 10), 0)
        default_conc = self._to_float(getattr(self, 'batch_solution_conc', _v225_const_var('0.25')).get(), 0.25)
        rows_out = []
        for aa in sorted(counts.keys()):
            count = counts[aa]
            calc_ml = calc_ml_by_aa.get(aa, 0.0)
            actual_ml = int((calc_ml + round_ml - 1) // round_ml) * round_ml + extra_ml if calc_ml else 0
            mw = self._mw_for_token(aa) or self.MW_FALLBACK.get(aa, 0.0)
            conc_for_weight = conc_by_aa.get(aa, default_conc) or default_conc
            weight_g = actual_ml / 1000.0 * conc_for_weight * mw if mw and conc_for_weight else 0
            rows_out.append({'AA': aa, 'count': int(count) if float(count).is_integer() else round(count, 3), 'calc_mL': round(calc_ml, 2), 'eq': aa_eq if 'aa_eq' in locals() else self._to_float(getattr(self, 'batch_coupling_eq', _v225_const_var('10')).get(), 10), 'conc_M': round(conc_for_weight, 3), 'calc_mL': round(calc_ml, 2), 'actual_mL': round(actual_ml, 2), 'MW': round(mw, 2) if mw else '', 'weight_g': round(weight_g, 2), 'note': 'actual mL is rounded up + reserve for synthesizer prep'})
        return pd.DataFrame(rows_out, columns=['AA', 'count', 'eq', 'conc_M', 'calc_mL', 'actual_mL', 'MW', 'weight_g', 'note'])

    def _batch_coupling_count_by_rows(self, rows=None) -> float:
        rows = rows if rows is not None else self._batch_rows_from_tree()
        total = 0.0
        for r in rows:
            copies = int(round(self._to_float(r.get('Copies'), 1))) or 1
            for seq, eq in [(r.get('Region 1 seq'), r.get('Region 1 eq')), (r.get('Region 2 seq'), r.get('Region 2 eq'))]:
                region_eq = self._to_float(eq, 0)
                if region_eq <= 0:
                    continue
                total += copies * region_eq * len(self._aa_letters_from_sequence(seq))
        return total

    def _batch_hbtu_nmp_summary(self, rows=None) -> pd.DataFrame:
        rows = rows if rows is not None else self._batch_rows_from_tree()
        count = self._batch_coupling_count_by_rows(rows)
        if count <= 0:
            return pd.DataFrame(columns=['material', 'count', 'calc_mL', 'actual_mL', 'MW', 'weight_g', 'note'])
        hbtu_eq = self._to_float(getattr(self, 'batch_hbtu_eq', _v225_const_var('10')).get(), 10)
        hbtu_conc = self._to_float(getattr(self, 'batch_hbtu_conc', _v225_const_var('0.4')).get(), 0.4)
        hbtu_mw = self._to_float(getattr(self, 'batch_hbtu_mw', _v225_const_var('379.25')).get(), 379.25)
        round_ml = max(self._to_float(getattr(self, 'batch_actual_round_ml', _v225_const_var('10')).get(), 10), 1)
        extra_ml = max(self._to_float(getattr(self, 'batch_actual_extra_ml', _v225_const_var('10')).get(), 10), 0)
        calc_ml = 0.0
        for r in rows:
            copies = int(round(self._to_float(r.get('Copies'), 1))) or 1
            scale = self._to_float(r.get('Scale mmol'), self._to_float(getattr(self, 'batch_default_scale', _v225_const_var('0.2')).get(), 0.2))
            for seq, eq in [(r.get('Region 1 seq'), r.get('Region 1 eq')), (r.get('Region 2 seq'), r.get('Region 2 eq'))]:
                region_eq = self._to_float(eq, 0)
                if region_eq <= 0:
                    continue
                local_count = copies * region_eq * len(self._aa_letters_from_sequence(seq))
                calc_ml += local_count * scale * hbtu_eq / hbtu_conc if hbtu_conc else 0.0
        actual_ml = int((calc_ml + round_ml - 1) // round_ml) * round_ml + extra_ml if calc_ml else 0.0
        hbtu_g = actual_ml / 1000.0 * hbtu_conc * hbtu_mw if actual_ml and hbtu_conc and hbtu_mw else 0.0
        rows_out = [{'material': 'HBTU', 'count': int(count) if float(count).is_integer() else round(count, 3), 'calc_mL': round(calc_ml, 2), 'actual_mL': round(actual_ml, 2), 'MW': round(hbtu_mw, 2), 'weight_g': round(hbtu_g, 2), 'note': f'{hbtu_eq} eq, {hbtu_conc} M in NMP'}, {'material': 'NMP', 'count': int(count) if float(count).is_integer() else round(count, 3), 'calc_mL': round(calc_ml, 2), 'actual_mL': round(actual_ml, 2), 'MW': round(self.MW_FALLBACK.get('NMP', 99.13), 2), 'weight_g': '', 'note': 'solvent volume for HBTU solution'}]
        return pd.DataFrame(rows_out, columns=['material', 'count', 'calc_mL', 'actual_mL', 'MW', 'weight_g', 'note'])

    def _batch_project_index_df(self, rows=None) -> pd.DataFrame:
        rows = rows if rows is not None else self._batch_rows_from_tree()
        out = []
        for i, r in enumerate(rows, start=1):
            seq_parts = []
            if str(r.get('Region 1 seq', '')).strip():
                seq_parts.append(str(r.get('Region 1 seq', '')).strip())
            if str(r.get('Linker', '')).strip():
                seq_parts.append(f"[{r.get('Linker')}]")
            if str(r.get('Region 2 seq', '')).strip():
                seq_parts.append(str(r.get('Region 2 seq', '')).strip())
            for _k in ['Tag', 'Label']:
                if str(r.get(_k, '')).strip():
                    seq_parts.append(f'[{r.get(_k)}]')
            out.append({'no': i, 'project': r.get('Project', ''), 'peptide_name': r.get('Peptide name', ''), 'lot_no': r.get('LOT No', ''), 'form': r.get('Form', ''), 'copies': r.get('Copies', ''), 'sequence': ' / '.join(seq_parts), 'scale_mmol': r.get('Scale mmol', ''), 'resin': r.get('Resin', ''), 'loading_mmol_g': r.get('Loading', ''), 'output_folder': ''})
        return pd.DataFrame(out)

    def refresh_batch_workspace_preview(self):
        try:
            rows = self._batch_rows_from_tree()
            aa_df = self._batch_aa_synthesizer_summary(rows)
            index_df = self._batch_project_index_df(rows)
            if hasattr(self, 'batch_material_tree'):
                self._write_tree(self.batch_material_tree, aa_df, ['AA', 'count', 'calc_mL', 'actual_mL', 'MW', 'weight_g'])
            if hasattr(self, 'batch_project_tree'):
                self._write_tree(self.batch_project_tree, index_df, ['no', 'project', 'peptide_name', 'lot_no', 'copies', 'sequence', 'scale_mmol', 'resin', 'output_folder'])
            if hasattr(self, 'batch_hbtu_tree'):
                self._write_tree(self.batch_hbtu_tree, self._batch_hbtu_nmp_summary(rows), ['material', 'count', 'calc_mL', 'actual_mL', 'MW', 'weight_g', 'note'])
            if hasattr(self, 'batch_cap_tree'):
                self._write_tree(self.batch_cap_tree, self._batch_modifier_summary(rows), ['material', 'type', 'count', 'calc_mL', 'actual_mL', 'MW', 'weight_g', 'note'])
            if hasattr(self, 'batch_layout_text'):
                self.batch_layout_text.delete('1.0', 'end')
                self.batch_layout_text.insert('end', self._batch_layout_text(rows))
        except Exception as e:
            try:
                self._log(f'Batch preview warning: {e}\n')
            except Exception:
                pass

    def _batch_layout_text(self, rows) -> str:
        lines = []
        lines.append('peptide name / synthesizer columns')
        lines.append('=' * 70)
        col_no = 1
        for r in rows:
            copies = int(round(self._to_float(r.get('Copies'), 1))) or 1
            name = r.get('Peptide name') or r.get('Project') or f'Peptide_{col_no}'
            lot = r.get('LOT No', '')
            form = r.get('Form', 'linear')
            cols = [str(i) for i in range(col_no, col_no + copies)]
            lines.append(f"Columns {', '.join(cols)} | {name} | {lot} | {form}")
            if str(r.get('Region 1 seq', '')).strip():
                lines.append(f"  1구역 ({r.get('Region 1 eq', '1')}eq): " + ' '.join(self._aa_letters_from_sequence(r.get('Region 1 seq'))))
            if str(r.get('Region 2 seq', '')).strip():
                lines.append(f"  2구역 ({r.get('Region 2 eq', '')}eq): " + ' '.join(self._aa_letters_from_sequence(r.get('Region 2 seq'))))
            lines.append('')
            col_no += copies
        lines.append('Combined AA table uses: count × scale × AA coupling eq / concentration.')
        lines.append('HBTU/NMP table uses: coupling count × scale × HBTU eq / HBTU concentration.')
        lines.append('N-term Ac table detects Ac- at the start of Region 1 and calculates Ac2O separately.')
        lines.append('Actual mL = round up to selected mL increment + extra mL reserve.')
        return '\n'.join(lines)

    def _roundup_actual_amount(self, calc_value, unit='mL'):
        """Return practical production amount: rounded up + reserve.
        mL values use the Batch Manager round/extra fields. Gram values get a 10% reserve
        and are rounded to 0.01 g. This keeps synthesizer prep slightly generous.
        """
        try:
            calc_value = float(calc_value or 0)
        except Exception:
            calc_value = 0.0
        if calc_value <= 0:
            return 0.0
        if str(unit).lower() == 'ml':
            round_ml = max(self._to_float(getattr(self, 'batch_actual_round_ml', _v225_const_var('10')).get(), 10), 1)
            extra_ml = max(self._to_float(getattr(self, 'batch_actual_extra_ml', _v225_const_var('10')).get(), 10), 0)
            return int((calc_value + round_ml - 1) // round_ml) * round_ml + extra_ml
        return round(calc_value * 1.1 + 0.0049, 2)

    def _density_for_token(self, token):
        t = self._normalize_batch_modifier(token) if token else ''
        aliases = {'DIC': 0.815, 'DIEA': 0.742, 'DIPEA': 0.742, 'TEA': 0.726, 'Piperidine': 0.862, 'DMF': 0.944, 'NMP': 1.03, 'DCM': 1.33, 'TFA': 1.49, 'TIS': 0.773, 'Acetic anhydride (Ac2O)': 1.08, 'Ac2O': 1.08}
        return aliases.get(t, aliases.get(str(token or ''), 0.0))

    def _add_total_record(self, records, item, purpose, count=0, eq=0, conc=0, amount=0, unit_hint='g', note=''):
        item = str(item or '').strip()
        if not item or item.lower() in {'manual', 'none', '-'}:
            return
        key = (item, purpose, eq, conc, unit_hint)
        rec = records.setdefault(key, {'item': item, 'purpose': purpose, 'count': 0.0, 'eq': eq, 'conc_M': conc, 'amount': 0.0, 'unit_hint': unit_hint, 'note': note})
        rec['count'] += float(count or 0)
        rec['amount'] += float(amount or 0)
        if note and note not in rec.get('note', ''):
            rec['note'] = (rec.get('note', '') + '; ' + note).strip('; ')

    def _records_to_usage_df(self, records):
        """Convert category totals into a synthesizer-prep table.

        amount meaning by unit_hint:
        - mmol: reagent mmol, converted to g and/or neat mL by MW/density
        - solution_mL: amount is mmol of solute, converted to solution mL by conc_M
        - direct_mL: amount is already mL, rounded up for actual prep volume
        """
        out = []
        for rec in records.values():
            item = rec['item']
            purpose = rec.get('purpose', '')
            eq = rec.get('eq', '')
            conc = rec.get('conc_M', '')
            amount = float(rec.get('amount', 0) or 0)
            unit_hint = rec.get('unit_hint', 'g')
            mw = self._mw_for_token(item) or self.MW_FALLBACK.get(item, 0.0)
            density = self._density_for_token(item)
            calc_g = 0.0
            calc_ml = 0.0
            if unit_hint == 'solution_mL':
                c = float(conc or 0)
                calc_ml = amount / c if c else 0.0
                calc_g = amount * mw / 1000.0 if mw else 0.0
            elif unit_hint == 'direct_mL':
                calc_ml = amount
                calc_g = calc_ml * density if density else 0.0
            else:
                calc_g = amount * mw / 1000.0 if mw else 0.0
                calc_ml = calc_g / density if density else 0.0
            actual_ml = self._roundup_actual_amount(calc_ml, 'mL') if calc_ml else ''
            actual_g = self._roundup_actual_amount(calc_g, 'g') if calc_g and (not calc_ml) else round(actual_ml * density, 3) if actual_ml != '' and density else self._roundup_actual_amount(calc_g, 'g') if calc_g else ''
            if unit_hint == 'direct_mL' and (not density):
                actual_g = ''
            out.append({'item': item, 'purpose': purpose, 'count': int(rec['count']) if float(rec['count']).is_integer() else round(rec['count'], 3), 'eq': eq, 'conc_M': conc, 'calculated': round(calc_ml if calc_ml else calc_g, 3) if calc_ml or calc_g else '', 'actual': round(actual_ml if actual_ml != '' else actual_g, 3) if actual_ml != '' or actual_g != '' else '', 'unit': 'mL' if calc_ml else 'g' if calc_g else 'manual', 'MW': round(mw, 2) if mw else 'manual', 'density': round(density, 3) if density else '', 'weight_g': round(actual_g, 3) if isinstance(actual_g, (int, float)) else actual_g, 'volume_mL': round(actual_ml, 3) if isinstance(actual_ml, (int, float)) else actual_ml, 'note': rec.get('note', '')})
        cols = ['item', 'purpose', 'count', 'eq', 'conc_M', 'calculated', 'actual', 'unit', 'MW', 'density', 'weight_g', 'volume_mL', 'note']
        return pd.DataFrame(out, columns=cols)

    def _batch_total_usage_by_category(self, rows=None):
        rows = rows if rows is not None else self._batch_rows_from_tree()
        coupling = {}
        catalyst = {}
        base = {}
        solvent = {}
        modifier = {}
        for r in rows:
            copies = int(round(self._to_float(r.get('Copies'), 1))) or 1
            scale = self._to_float(r.get('Scale mmol'), self._to_float(getattr(self, 'batch_default_scale', _v225_const_var('0.2')).get(), 0.2))
            chem = str(r.get('Chemistry', '') or 'DIC/HOBt')
            local_steps = 0.0
            for seq, eq in [(r.get('Region 1 seq'), r.get('Region 1 eq')), (r.get('Region 2 seq'), r.get('Region 2 eq'))]:
                region_eq = self._to_float(eq, 0)
                if region_eq <= 0:
                    continue
                local_steps += copies * region_eq * len(self._aa_letters_from_sequence(seq))
            total_step_mmol = local_steps * scale
            volume_factor = self._volume_factor_for_resin(r.get('Resin'))
            if local_steps:
                if 'HBTU/NMP' in chem:
                    hbtu_eq = self._to_float(getattr(self, 'batch_hbtu_eq', _v225_const_var('10')).get(), 10)
                    hbtu_conc = self._to_float(getattr(self, 'batch_hbtu_conc', _v225_const_var('0.4')).get(), 0.4)
                    hbtu_mmol = total_step_mmol * hbtu_eq
                    hbtu_solution_ml = hbtu_mmol / hbtu_conc if hbtu_conc else 0.0
                    self._add_total_record(coupling, 'HBTU', 'activation solution', local_steps, hbtu_eq, hbtu_conc, hbtu_mmol, 'solution_mL', 'Prepare HBTU solution in NMP')
                    self._add_total_record(solvent, 'NMP', 'HBTU cocktail solvent', local_steps, '', '', hbtu_solution_ml, 'direct_mL', 'Solvent volume for HBTU/NMP cocktail')
                elif 'HBTU' in chem:
                    self._add_total_record(coupling, 'HBTU', 'coupling reagent', local_steps, 5.0, '', total_step_mmol * 5.0, 'mmol', 'solid HBTU total + reserve')
                    self._add_total_record(catalyst, 'HOBt', 'additive', local_steps, 5.0, '', total_step_mmol * 5.0, 'mmol', 'if selected chemistry uses HOBt')
                    self._add_total_record(base, 'DIPEA', 'coupling base', local_steps, 10.0, '', total_step_mmol * 10.0, 'mmol', 'liquid base by density')
                    self._add_total_record(solvent, 'DMF', 'coupling solvent', local_steps, '', '', total_step_mmol * volume_factor, 'direct_mL', 'cocktail solvent')
                else:
                    self._add_total_record(coupling, 'DIC', 'coupling reagent', local_steps, 5.0, '', total_step_mmol * 5.0, 'mmol', 'liquid DIC by density')
                    add = 'Oxyma' if 'Oxyma' in chem else 'HOBt'
                    self._add_total_record(catalyst, add, 'additive', local_steps, 5.0, '', total_step_mmol * 5.0, 'mmol', 'solid additive + reserve')
                    self._add_total_record(solvent, 'DMF', 'coupling solvent', local_steps, '', '', total_step_mmol * volume_factor, 'direct_mL', 'coupling cocktail solvent')
                self._add_total_record(base, 'Piperidine', 'deprotection base', local_steps * 2, '20%', '', total_step_mmol * volume_factor * 2 * 0.2, 'direct_mL', '20% piperidine/DMF, 2 cycles')
                self._add_total_record(solvent, 'DMF', 'deprotection/wash solvent', local_steps * 8, '', '', total_step_mmol * volume_factor * 8, 'direct_mL', 'DMF deprotection/wash practical reserve')
                self._add_total_record(solvent, 'DCM', 'final wash solvent', copies, '', '', copies * scale * volume_factor * 3, 'direct_mL', 'DCM final wash reserve')
            mod_eq = self._to_float(getattr(self, 'modifier_eq', _v225_const_var(3.0)).get(), 3.0)
            nterm = self._normalize_batch_modifier(r.get('N-term'))
            if not nterm and self._sequence_has_nterm_ac(r.get('Region 1 seq')):
                nterm = 'Ac'
            if nterm:
                mat = 'Acetic anhydride (Ac2O)' if nterm == 'Ac' else nterm
                self._add_total_record(modifier, mat, 'N-term modifier', copies, mod_eq, '', copies * scale * mod_eq, 'mmol', 'N-terminal cap/modifier reagent')
            for col, purpose in [('Linker', 'linker reagent'), ('Tag', 'tag reagent'), ('Label', 'label reagent')]:
                val = self._normalize_batch_modifier(r.get(col))
                if val:
                    self._add_total_record(modifier, val, purpose, copies, mod_eq, '', copies * scale * mod_eq, 'mmol', 'verify vendor form/MW before weighing')
        return {'coupling': self._records_to_usage_df(coupling), 'catalyst': self._records_to_usage_df(catalyst), 'base': self._records_to_usage_df(base), 'solvent': self._records_to_usage_df(solvent), 'modifier': self._records_to_usage_df(modifier)}

    def refresh_batch_workspace_preview(self):
        try:
            rows = self._batch_rows_from_tree()
            aa_df = self._batch_aa_synthesizer_summary(rows)
            index_df = self._batch_project_index_df(rows)
            totals = self._batch_total_usage_by_category(rows)
            if hasattr(self, 'batch_aa_tree'):
                self._write_tree(self.batch_aa_tree, aa_df, ['AA', 'count', 'eq', 'conc_M', 'calc_mL', 'actual_mL', 'MW', 'weight_g', 'note'] if 'eq' in aa_df.columns else ['AA', 'count', 'calc_mL', 'actual_mL', 'MW', 'weight_g'])
            elif hasattr(self, 'batch_material_tree'):
                self._write_tree(self.batch_material_tree, aa_df, ['AA', 'count', 'calc_mL', 'actual_mL', 'MW', 'weight_g'])
            if hasattr(self, 'batch_project_tree'):
                self._write_tree(self.batch_project_tree, index_df, ['no', 'project', 'peptide_name', 'lot_no', 'copies', 'sequence', 'scale_mmol', 'resin', 'output_folder'])
            cols = ['item', 'purpose', 'count', 'eq', 'conc_M', 'calculated', 'actual', 'unit', 'MW', 'density', 'weight_g', 'volume_mL', 'note']
            mapping = [('batch_coupling_reagent_tree', totals['coupling']), ('batch_catalyst_tree', totals['catalyst']), ('batch_base_tree', totals['base']), ('batch_solvent_tree', totals['solvent']), ('batch_modifier_tree', totals['modifier'])]
            for attr, df in mapping:
                if hasattr(self, attr):
                    self._write_tree(getattr(self, attr), df, cols)
            if hasattr(self, 'batch_layout_text'):
                self.batch_layout_text.delete('1.0', 'end')
                self.batch_layout_text.insert('end', self._batch_layout_text(rows))
        except Exception as e:
            try:
                self._log(f'Batch preview warning: {e}\n')
            except Exception:
                pass

    def load_batch_csv(self):
        path = filedialog.askopenfilename(filetypes=[('CSV/TSV', '*.csv *.tsv *.txt'), ('All files', '*.*')])
        if not path:
            return
        try:
            text = Path(path).read_text(encoding='utf-8-sig')
        except UnicodeDecodeError:
            text = Path(path).read_text(encoding='cp949')
        rows = []
        lines = [line for line in text.splitlines() if line.strip()]
        if not lines:
            return
        reader = csv.DictReader(lines) if any((h in lines[0].lower() for h in ['project', 'peptide', 'region'])) else None
        if reader:
            for r in reader:
                rows.append({'Project': r.get('Project') or r.get('project') or r.get('project_name') or '', 'Peptide name': r.get('Peptide name') or r.get('peptide_name') or r.get('peptide') or '', 'Form': r.get('Form') or r.get('form') or 'linear', 'Copies': r.get('Copies') or r.get('copies') or '1', 'N-term': r.get('N-term') or r.get('n_term') or r.get('nterm') or '', 'Region 1 seq': r.get('Region 1 seq') or r.get('region1') or r.get('sequence') or '', 'Region 1 eq': r.get('Region 1 eq') or r.get('region1_eq') or '1', 'Linker': r.get('Linker') or r.get('linker') or '', 'Region 2 seq': r.get('Region 2 seq') or r.get('region2') or '', 'Region 2 eq': r.get('Region 2 eq') or r.get('region2_eq') or '', 'Tag': r.get('Tag') or r.get('tag') or '', 'Label': r.get('Label') or r.get('label') or '', 'C-term': r.get('C-term') or r.get('c_term') or r.get('cterm') or 'NH2', 'D/non-natural notes': r.get('D/non-natural notes') or r.get('notes') or '', 'Chemistry': r.get('Chemistry') or r.get('chemistry') or 'DIC/HOBt', 'Scale mmol': r.get('Scale mmol') or r.get('scale_mmol') or self.batch_default_scale.get(), 'AA conc M': r.get('AA conc M') or r.get('aa_conc_m') or self.batch_solution_conc.get(), 'AA coupling eq': r.get('AA coupling eq') or r.get('aa_coupling_eq') or self.batch_coupling_eq.get(), 'Resin': r.get('Resin') or r.get('resin') or self.batch_default_resin.get(), 'Loading': r.get('Loading') or r.get('loading') or self.batch_default_loading.get(), 'LOT No': r.get('LOT No') or r.get('lot_no') or '', 'Status': r.get('Status') or r.get('status') or 'Ready'})
        else:
            for line in lines:
                parts = next(csv.reader([line], delimiter='\t' if '\t' in line else ','))
                parts = [str(x).strip() for x in parts]
                parts += [''] * 15
                rows.append({'Project': parts[0], 'Peptide name': parts[1], 'Form': parts[2] or 'linear', 'Copies': parts[3] or '1', 'Region 1 seq': parts[4], 'Region 1 eq': parts[5] or '1', 'Region 2 seq': parts[6], 'Region 2 eq': parts[7], 'Scale mmol': parts[8] or self.batch_default_scale.get(), 'AA conc M': parts[9] or self.batch_solution_conc.get(), 'AA coupling eq': parts[10] or self.batch_coupling_eq.get(), 'Resin': parts[11] or self.batch_default_resin.get(), 'Loading': parts[12] or self.batch_default_loading.get(), 'LOT No': parts[13], 'Status': parts[14] or 'Ready'})
        for item in list(self.batch_tree.get_children()):
            self.batch_tree.delete(item)
        for r in rows:
            self.batch_add_row(r)
        self.refresh_batch_workspace_preview()

    def save_batch_csv(self):
        path = filedialog.asksaveasfilename(defaultextension='.csv', filetypes=[('CSV', '*.csv')])
        if not path:
            return
        rows = self._batch_rows_from_tree()
        pd.DataFrame(rows).to_csv(path, index=False, encoding='utf-8-sig')
        self._log(f'Batch CSV saved: {path}\n')

    def open_batch_output(self):
        p = getattr(self, 'last_batch_outdir', None)
        if p and Path(p).exists():
            open_path(Path(p))
        else:
            base = Path(self.outdir.get() or ROOT / 'outputs')
            if base.exists():
                open_path(base)

    def _parse_batch_input(self):
        out = []
        for r in self._batch_rows_from_tree():
            seq1 = str(r.get('Region 1 seq', '')).strip()
            seq2 = str(r.get('Region 2 seq', '')).strip()
            seq = seq1 if not seq2 else seq1 + '-' + seq2
            if not seq:
                continue
            out.append({'project_name': r.get('Project') or r.get('Peptide name') or 'SPPS', 'peptide_name': r.get('Peptide name') or r.get('Project') or 'SPPS', 'sequence': seq, 'scale_mmol': self._to_float(r.get('Scale mmol'), self._to_float(getattr(self, 'batch_default_scale', _v225_const_var('0.2')).get(), 0.2)), 'resin': r.get('Resin') or getattr(self, 'batch_default_resin', _v225_const_var('Rink Amide AM')).get(), 'loading_mmol_g': self._to_float(r.get('Loading'), self._to_float(getattr(self, 'batch_default_loading', _v225_const_var('0.8')).get(), 0.8)), 'lot_no': r.get('LOT No') or '', 'copies': int(round(self._to_float(r.get('Copies'), 1))) or 1, 'form': r.get('Form') or 'linear', 'region1_seq': seq1, 'region1_eq': r.get('Region 1 eq') or '1', 'region2_seq': seq2, 'region2_eq': r.get('Region 2 eq') or ''})
        return out

    def _export_current_outputs_to_dir(self, outdir: Path):
        outdir.mkdir(parents=True, exist_ok=True)
        plan = pd.DataFrame(self.tree_rows())
        materials = self.materials_from_rows(plan)
        if (materials is None or materials.empty) and (not plan.empty):
            materials = self._minimal_materials_from_plan(plan)
        ml = self.ml_log_from_rows(plan)
        ops = self.operation_form_from_rows(plan)
        checklist = self.checklist_from_rows(plan)
        loading_df = self.loading_calculator_df()
        cleavage_df = self.cleavage_calculator_df()
        transfer_df = self.manufacturing_transfer_df(materials, plan)
        production_df = self.production_tracking_df(plan)
        bench_df = self.bench_checklist_layout_df(plan, materials)
        progress_df = self.progress_df()
        next_df = self.next_step_df()
        self.save_project_state(outdir / 'project_state.json')
        plan.to_csv(outdir / 'editable_spps_plan.csv', index=False, encoding='utf-8-sig')
        materials.to_csv(outdir / 'material_usage_from_editable_plan.csv', index=False, encoding='utf-8-sig')
        ops.to_csv(outdir / 'operation_form_from_editable_plan.csv', index=False, encoding='utf-8-sig')
        checklist.to_csv(outdir / 'printable_synthesis_checklist.csv', index=False, encoding='utf-8-sig')
        ml.to_csv(outdir / 'spps_ml_ready_log_from_editable_plan.csv', index=False, encoding='utf-8-sig')
        progress_df.to_csv(outdir / 'checklist_progress.csv', index=False, encoding='utf-8-sig')
        next_df.to_csv(outdir / 'next_step.csv', index=False, encoding='utf-8-sig')
        aa_df = self.amino_acid_usage_summary(materials)
        reagent_df = self.reagent_usage_summary(materials)
        solvent_df = self.solvent_usage_summary(materials)
        aa_df.to_csv(outdir / 'total_amino_acid_usage.csv', index=False, encoding='utf-8-sig')
        reagent_df.to_csv(outdir / 'total_reagent_base_usage.csv', index=False, encoding='utf-8-sig')
        solvent_df.to_csv(outdir / 'total_solvent_usage.csv', index=False, encoding='utf-8-sig')
        with pd.ExcelWriter(outdir / 'spps_plan.xlsx', engine='openpyxl') as writer:
            plan.to_excel(writer, index=False, sheet_name='00_EDITABLE_PLAN')
            materials.to_excel(writer, index=False, sheet_name='01_MATERIAL_USAGE')
            checklist.to_excel(writer, index=False, sheet_name='02_PRINT_CHECKLIST')
            ops.to_excel(writer, index=False, sheet_name='03_OPERATION_FORM')
            ml.to_excel(writer, index=False, sheet_name='04_ML_READY_LOG')
            loading_df.to_excel(writer, index=False, sheet_name='06_LOADING_CALC')
            cleavage_df.to_excel(writer, index=False, sheet_name='07_CLEAVAGE_CALC')
            transfer_df.to_excel(writer, index=False, sheet_name='08_TRANSFER_SHEET')
            production_df.to_excel(writer, index=False, sheet_name='09_PRODUCTION_TRACKING')
            bench_df.to_excel(writer, index=False, sheet_name='10_BENCH_CHECKLIST')
            progress_df.to_excel(writer, index=False, sheet_name='11_CHECKLIST_PROGRESS')
            next_df.to_excel(writer, index=False, sheet_name='12_NEXT_STEP')
            try:
                pd.DataFrame([plan_summary(self._input())]).to_excel(writer, index=False, sheet_name='05_SUMMARY')
            except Exception:
                pass
        return (plan, materials, aa_df, reagent_df, solvent_df)

    def _write_synthesizer_excel(self, writer, rows, aa_prep_df, index_df):
        pd.DataFrame(rows).to_excel(writer, index=False, sheet_name='00_BATCH_INPUT')
        index_df.to_excel(writer, index=False, sheet_name='01_PROJECT_PEPTIDES')
        aa_prep_df.to_excel(writer, index=False, sheet_name='02_AA_PREP_TOTAL')
        layout_rows = []
        layout_rows.append(['peptide name'])
        max_cols = 0
        peptide_cols = []
        for r in rows:
            copies = int(round(self._to_float(r.get('Copies'), 1))) or 1
            for _ in range(copies):
                peptide_cols.append(r)
        max_cols = max(len(peptide_cols), 1)
        header1 = ['peptide name'] + [c.get('Peptide name') or c.get('Project') or '' for c in peptide_cols]
        header2 = [''] + [c.get('LOT No') or '' for c in peptide_cols]
        header3 = [''] + [c.get('Form') or 'linear' for c in peptide_cols]
        layout_rows = [header1, header2, header3, ['Loading'] + ['-' for _ in peptide_cols]]
        max_r1 = max([len(self._aa_letters_from_sequence(c.get('Region 1 seq'))) for c in peptide_cols] + [0])
        layout_rows.append(['1구역 (1eq)'] + ['' for _ in peptide_cols])
        for i in range(max_r1):
            layout_rows.append([''] + [self._aa_letters_from_sequence(c.get('Region 1 seq'))[i] if i < len(self._aa_letters_from_sequence(c.get('Region 1 seq'))) else '' for c in peptide_cols])
        layout_rows.append(['2구역'] + ['' for _ in peptide_cols])
        max_r2 = max([len(self._aa_letters_from_sequence(c.get('Region 2 seq'))) for c in peptide_cols] + [0])
        for i in range(max_r2):
            layout_rows.append([''] + [self._aa_letters_from_sequence(c.get('Region 2 seq'))[i] if i < len(self._aa_letters_from_sequence(c.get('Region 2 seq'))) else '' for c in peptide_cols])
        pd.DataFrame(layout_rows).to_excel(writer, index=False, header=False, sheet_name='03_SYNTHESIZER_LAYOUT')

    def run_batch_plans(self):
        try:
            batch_rows = self._parse_batch_input()
            raw_rows = self._batch_rows_from_tree()
            if not batch_rows:
                messagebox.showwarning('Batch', 'No batch rows found.')
                return
            original = {'project_name': self.project_name.get(), 'sequence': self.seq.get(), 'lot_no': self.lot_no.get(), 'scale': self.scale.get(), 'resin': self.resin.get(), 'loading': self.loading.get()}
            batch_root = Path(self.outdir.get() or ROOT / 'outputs') / ('batch_workspace_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
            batch_root.mkdir(parents=True, exist_ok=True)
            index_rows = []
            all_materials = []
            all_aa = []
            all_reagents = []
            all_solvents = []
            for i, item in enumerate(batch_rows, start=1):
                self.project_name.set(item['project_name'])
                self.seq.set(item['sequence'])
                self.scale.set(item['scale_mmol'])
                self.resin.set(item['resin'])
                self.loading.set(item['loading_mmol_g'])
                self.lot_no.set(item['lot_no'] or self._generate_lot_no())
                self.rebuild_table()
                self.refresh_outputs_from_tree()
                folder_name = f"{i:02d}_{self._safe_name(item.get('project_name'))}_{self._safe_name(item.get('peptide_name'))}_{self._safe_name(self.lot_no.get())}"
                outdir = batch_root / folder_name
                plan, materials, aa_df, reagent_df, solvent_df = self._export_current_outputs_to_dir(outdir)
                plan_steps = len(plan.index) if plan is not None else 0
                idx_row = {'no': i, 'project_name': item.get('project_name'), 'peptide_name': item.get('peptide_name'), 'lot_no': self.lot_no.get(), 'form': item.get('form'), 'copies': item.get('copies', 1), 'region1_seq': item.get('region1_seq'), 'region1_eq': item.get('region1_eq'), 'region2_seq': item.get('region2_seq'), 'region2_eq': item.get('region2_eq'), 'sequence': self.seq.get(), 'scale_mmol': self.scale.get(), 'resin': self.resin.get(), 'loading_mmol_g': self.loading.get(), 'plan_steps': plan_steps, 'output_folder': str(outdir)}
                index_rows.append(idx_row)
                if materials is not None and (not materials.empty):
                    tmp = materials.copy()
                    tmp.insert(0, 'batch_no', i)
                    tmp.insert(1, 'project_name', item.get('project_name'))
                    tmp.insert(2, 'peptide_name', item.get('peptide_name'))
                    tmp.insert(3, 'lot_no', self.lot_no.get())
                    all_materials.append(tmp)
                if aa_df is not None and (not aa_df.empty):
                    tmp = aa_df.copy()
                    tmp.insert(0, 'batch_no', i)
                    tmp.insert(1, 'project_name', item.get('project_name'))
                    tmp.insert(2, 'peptide_name', item.get('peptide_name'))
                    tmp.insert(3, 'lot_no', self.lot_no.get())
                    all_aa.append(tmp)
                if reagent_df is not None and (not reagent_df.empty):
                    tmp = reagent_df.copy()
                    tmp.insert(0, 'batch_no', i)
                    tmp.insert(1, 'project_name', item.get('project_name'))
                    tmp.insert(2, 'peptide_name', item.get('peptide_name'))
                    tmp.insert(3, 'lot_no', self.lot_no.get())
                    all_reagents.append(tmp)
                if solvent_df is not None and (not solvent_df.empty):
                    tmp = solvent_df.copy()
                    tmp.insert(0, 'batch_no', i)
                    tmp.insert(1, 'project_name', item.get('project_name'))
                    tmp.insert(2, 'peptide_name', item.get('peptide_name'))
                    tmp.insert(3, 'lot_no', self.lot_no.get())
                    all_solvents.append(tmp)
            index_df = pd.DataFrame(index_rows)
            index_df.to_csv(batch_root / 'BATCH_PROJECT_INDEX.csv', index=False, encoding='utf-8-sig')
            materials_all = pd.concat(all_materials, ignore_index=True) if all_materials else pd.DataFrame()
            aa_all = pd.concat(all_aa, ignore_index=True) if all_aa else pd.DataFrame()
            reag_all = pd.concat(all_reagents, ignore_index=True) if all_reagents else pd.DataFrame()
            solv_all = pd.concat(all_solvents, ignore_index=True) if all_solvents else pd.DataFrame()
            for df, filename in [(materials_all, 'BATCH_ALL_MATERIALS.csv'), (aa_all, 'BATCH_AA_USAGE_BY_PROJECT.csv'), (reag_all, 'BATCH_REAGENT_USAGE_BY_PROJECT.csv'), (solv_all, 'BATCH_SOLVENT_USAGE_BY_PROJECT.csv')]:
                df.to_csv(batch_root / filename, index=False, encoding='utf-8-sig')
            total_materials = self._batch_total_materials(materials_all)
            total_aa = self._batch_total_aa(aa_all)
            total_reagents = self._batch_total_reagents(reag_all)
            total_solvents = self._batch_total_solvents(solv_all)
            aa_prep_df = self._batch_aa_synthesizer_summary(raw_rows)
            hbtu_prep_df = self._batch_hbtu_nmp_summary(raw_rows)
            ac_prep_df = self._batch_ac_cap_summary(raw_rows)
            total_materials.to_csv(batch_root / 'BATCH_TOTAL_MATERIALS.csv', index=False, encoding='utf-8-sig')
            total_aa.to_csv(batch_root / 'BATCH_TOTAL_AA_USAGE.csv', index=False, encoding='utf-8-sig')
            total_reagents.to_csv(batch_root / 'BATCH_TOTAL_REAGENT_USAGE.csv', index=False, encoding='utf-8-sig')
            total_solvents.to_csv(batch_root / 'BATCH_TOTAL_SOLVENT_USAGE.csv', index=False, encoding='utf-8-sig')
            aa_prep_df.to_csv(batch_root / 'SYNTHESIZER_AA_PREP_TOTAL.csv', index=False, encoding='utf-8-sig')
            hbtu_prep_df.to_csv(batch_root / 'SYNTHESIZER_HBTU_NMP_PREP_TOTAL.csv', index=False, encoding='utf-8-sig')
            ac_prep_df.to_csv(batch_root / 'SYNTHESIZER_NTERM_CAP_PREP_TOTAL.csv', index=False, encoding='utf-8-sig')
            with pd.ExcelWriter(batch_root / 'BATCH_WORKSPACE.xlsx', engine='openpyxl') as writer:
                self._write_synthesizer_excel(writer, raw_rows, aa_prep_df, index_df)
                hbtu_prep_df.to_excel(writer, index=False, sheet_name='04_HBTU_NMP_PREP_TOTAL')
                total_materials.to_excel(writer, index=False, sheet_name='10_TOTAL_MATERIALS')
                total_aa.to_excel(writer, index=False, sheet_name='11_TOTAL_AA_ENGINE')
                total_reagents.to_excel(writer, index=False, sheet_name='12_TOTAL_REAGENTS')
                total_solvents.to_excel(writer, index=False, sheet_name='13_TOTAL_SOLVENTS')
                materials_all.to_excel(writer, index=False, sheet_name='20_ALL_MATERIALS')
            (batch_root / 'BATCH_MANIFEST.txt').write_text('SPPS Planner batch workspace\nCreated: ' + datetime.now().isoformat(timespec='seconds') + '\n', encoding='utf-8')
            self.last_batch_outdir = batch_root
            self.project_name.set(original['project_name'])
            self.seq.set(original['sequence'])
            self.lot_no.set(original['lot_no'])
            self.scale.set(original['scale'])
            self.resin.set(original['resin'])
            self.loading.set(original['loading'])
            self.rebuild_table()
            self.refresh_outputs_from_tree()
            self.refresh_batch_workspace_preview()
            if hasattr(self, 'batch_project_tree'):
                idx_preview = index_df.copy()
                self._write_tree(self.batch_project_tree, idx_preview, ['no', 'project_name', 'peptide_name', 'lot_no', 'copies', 'sequence', 'scale_mmol', 'resin', 'output_folder'])
            self._log(f'Batch workspace exported: {batch_root}\n')
            messagebox.showinfo('Batch complete', f'Batch workspace exported to:\n{batch_root}')
        except Exception as e:
            messagebox.showerror('Batch error', str(e))
            self._log('ERROR batch: ' + str(e) + '\n')

    def _batch_total_materials(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()
        tmp = df.copy()
        for c in ['planned_mmol', 'planned_g', 'planned_mL', 'use_count']:
            if c in tmp.columns:
                tmp[c] = pd.to_numeric(tmp[c], errors='coerce').fillna(0)
        keys = [c for c in ['material', 'class', 'MW', 'phase'] if c in tmp.columns]
        agg = {c: 'sum' for c in ['planned_mmol', 'planned_g', 'planned_mL', 'use_count'] if c in tmp.columns}
        if not keys or not agg:
            return tmp
        return tmp.groupby(keys, dropna=False).agg(agg).reset_index()

    def _batch_total_aa(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()
        tmp = df.copy()
        for c in ['planned_mmol', 'calculated_g']:
            if c in tmp.columns:
                tmp[c] = pd.to_numeric(tmp[c], errors='coerce').fillna(0)
        return tmp.groupby(['material', 'MW'], dropna=False).agg({'planned_mmol': 'sum', 'calculated_g': 'sum'}).reset_index()

    def _batch_total_reagents(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()
        tmp = df.copy()
        for c in ['planned_mmol', 'planned_g', 'planned_mL']:
            if c in tmp.columns:
                tmp[c] = pd.to_numeric(tmp[c], errors='coerce').fillna(0)
        keys = [c for c in ['material', 'class', 'MW', 'density_g_per_mL'] if c in tmp.columns]
        return tmp.groupby(keys, dropna=False).agg({'planned_mmol': 'sum', 'planned_g': 'sum', 'planned_mL': 'sum'}).reset_index()

    def _batch_total_solvents(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()
        tmp = df.copy()
        for c in ['planned_mL', 'use_count']:
            if c in tmp.columns:
                tmp[c] = pd.to_numeric(tmp[c], errors='coerce').fillna(0)
        return tmp.groupby(['solvent'], dropna=False).agg({'planned_mL': 'sum', 'use_count': 'sum'}).reset_index()

    def _set_log_pane(self, mode: str):
        try:
            self.log_paned.update_idletasks()
            h = max(300, self.log_paned.winfo_height())
            pos = int(h * (0.82 if mode == 'ml' else 0.18 if mode == 'app' else 0.5))
            self.log_paned.sashpos(0, pos)
        except Exception as e:
            self._log(f'Log pane resize warning: {e}\n')

    def bind_all_combobox_typeahead(self):
        """Apply first-letter jump to all existing drop-down/combobox widgets only."""

        def walk(w):
            try:
                if isinstance(w, ttk.Combobox):
                    bind_combobox_first_letter_jump(w)
                for child in w.winfo_children():
                    walk(child)
            except Exception:
                pass
        walk(self)

    def apply_dic_hobt_preset(self):
        """Restore the classic DIC/HOBt SPPS coupling preset."""
        try:
            self.default_reagent.set('DIC')
            self.default_reagent_eq.set(5.0)
            self.default_reagent_count.set(1)
            self.default_catalyst.set('HOBt')
            self.default_catalyst_eq.set(5.0)
            self.default_catalyst_count.set(1)
            self.default_base.set('')
            self.default_base_eq.set(0.0)
            self.default_base_count.set(0)
            self.default_coupling_solution_solvent.set('DMF')
            self.coupling_eq.set(5.0)
            self.rebuild_table()
            self.refresh_outputs_from_tree()
            if hasattr(self, 'refresh_batch_workspace_preview'):
                self.refresh_batch_workspace_preview()
            self._log('Applied DIC/HOBt preset: DIC 5 eq + HOBt 5 eq in DMF. HBTU/NMP and manual options are still available.\n')
        except Exception as e:
            messagebox.showerror('DIC/HOBt preset', str(e))

    def apply_chemistry_preset_from_string(self, chemistry: str):
        c = str(chemistry or '').upper().replace(' ', '')
        if c.startswith('HBTU') or 'HBTU/NMP' in c:
            self.apply_hbtu_nmp_preset()
        elif c.startswith('DIC') or 'DIC/HOBT' in c:
            self.apply_dic_hobt_preset()

    def apply_hbtu_nmp_preset(self):
        """Apply the bench HBTU/NMP chemistry preset without deleting existing functions."""
        try:
            self.default_reagent.set('HBTU')
            self.default_reagent_eq.set(10.0)
            self.default_reagent_count.set(1)
            self.default_catalyst.set('')
            self.default_catalyst_eq.set(0.0)
            self.default_catalyst_count.set(0)
            self.default_coupling_solution_solvent.set('NMP')
            self.coupling_eq.set(10.0)
            if hasattr(self, 'batch_hbtu_eq'):
                self.batch_hbtu_eq.set('10')
            if hasattr(self, 'batch_hbtu_conc'):
                self.batch_hbtu_conc.set('0.4')
            self.rebuild_table()
            self.refresh_outputs_from_tree()
            if hasattr(self, 'refresh_batch_workspace_preview'):
                self.refresh_batch_workspace_preview()
            self._log('Applied HBTU/NMP preset: HBTU 10 eq, 0.4 M in NMP. Existing DIC/HOBt/manual options are still available.\n')
        except Exception as e:
            messagebox.showerror('HBTU/NMP preset', str(e))

    def _input(self):
        return PlanInput(sequence=self.seq.get().strip(), resin=self.resin.get(), scale_mmol=float(self.scale.get()), resin_loading_mmol_g=float(self.loading.get()), coupling_eq=float(self.coupling_eq.get()), ac_eq=float(self.modifier_eq.get()), default_coupling_repeats=int(self.coupling_repeats.get()), default_modifier_repeats=int(self.modifier_repeats.get()), default_coupling_reagent=self.default_reagent.get().strip(), default_catalyst=self.default_catalyst.get().strip(), default_base=self.default_base.get().strip(), default_reaction_solvent=self.default_solvent1.get().strip(), step_overrides_text='')

    def _compound_row_for_unit(self, token: str):
        """Return compound DB row for standard AA / modifier token when available."""
        try:
            if not hasattr(self, '_compound_lookup_cache'):
                p = APP / 'data' / 'compounds.csv'
                df = pd.read_csv(p, encoding='utf-8-sig')
                cache = {}
                df.columns = [str(c).replace('\ufeff', '').strip() for c in df.columns]
                for _, row in df.iterrows():
                    key = str(row.get('Token', '')).strip()
                    if key:
                        d = row.to_dict()
                        cache[key.upper()] = d
                        reagent_name = str(row.get('Reagent/protected form', '')).strip()
                        if reagent_name:
                            cache[reagent_name.upper()] = d
                self._compound_lookup_cache = cache
            return self._compound_lookup_cache.get(str(token or '').strip().upper(), {})
        except Exception:
            return {}

    def _protected_name_for_token(self, token: str) -> str:
        row = self._compound_row_for_unit(token)
        return str(row.get('Reagent/protected form') or token).strip()

    def _mw_for_token(self, token: str) -> float:
        tok = str(token or '').strip()
        row = self._compound_row_for_unit(tok)
        try:
            mw = float(row.get('Reagent MW (g/mol)') or 0)
            if mw:
                return mw
        except Exception:
            pass
        d_map = {'D-Ala': 'A', 'D-Arg': 'R', 'D-Asn': 'N', 'D-Asp': 'D', 'D-Cys': 'C', 'D-Gln': 'Q', 'D-Glu': 'E', 'D-His': 'H', 'D-Ile': 'I', 'D-Leu': 'L', 'D-Lys': 'K', 'D-Met': 'M', 'D-Phe': 'F', 'D-Pro': 'P', 'D-Ser': 'S', 'D-Thr': 'T', 'D-Trp': 'W', 'D-Tyr': 'Y', 'D-Val': 'V'}
        if tok in d_map:
            return float(self.MW_FALLBACK.get(d_map[tok], 0.0) or 0.0)
        return float(self.MW_FALLBACK.get(tok, 0.0) or 0.0)

    def _swell_solvent_for_resin(self) -> str:
        """Swell solvent follows loading solvent family.

        - 2-CTC/trityl: DCM swell/loading.
        - Amide/Wang/Rink-type Fmoc resin: DMF swell/loading by default.
        """
        return 'DCM' if self._resin_family_text() == 'CTC/Trityl' else 'DMF'

    def _resin_family_text(self) -> str:
        r = str(self.resin.get() or '').lower()
        if 'ctc' in r or 'trityl' in r:
            return 'CTC/Trityl'
        return 'Amide'

    def _volume_factor_for_resin(self, resin=None, unit_eq=None) -> float:
        """Return the single active working-volume basis in mL/mmol.

        Resin-factor mode reads the retained Amide/Rink or 2-CTC/Trityl
        control.  Molarity mode converts the selected coupling equivalents to
        an equivalent mL/mmol factor.  The removed global ``ml_per_mmol``
        variable is intentionally not consulted.
        """
        if resin is None:
            for name in ('pm_resin', 'resin'):
                variable = getattr(self, name, None)
                try:
                    current = str(variable.get() or '').strip()
                except Exception:
                    current = ''
                if current:
                    resin = current
                    break
        resin_text = str(resin or '').lower()
        is_ctc = 'ctc' in resin_text or 'trityl' in resin_text
        mode = str(getattr(self, 'solvent_volume_mode', _v225_const_var('resin_factor')).get() or 'resin_factor').strip().lower()
        if mode == 'molarity':
            molarity = max(self._to_float(getattr(self, 'solvent_molarity_m', _v225_const_var('0.2')).get(), 0.2), 1e-12)
            if unit_eq is None:
                unit_eq = self._to_float(getattr(self, 'coupling_eq', _v225_const_var('1')).get(), 1.0)
            return max(0.0, self._to_float(unit_eq, 1.0) / molarity)
        variable = getattr(
            self,
            'ctc_ml_per_mmol' if is_ctc else 'amide_ml_per_mmol',
            _v225_const_var('5' if is_ctc else '10'),
        )
        return max(0.0, self._to_float(variable.get(), 5.0 if is_ctc else 10.0))

    def _working_volume_for_scale(self, scale=None, resin=None, unit_eq=None) -> float:
        if scale is None:
            scale = self._to_float(getattr(self, 'scale', _v225_const_var('0')).get(), 0.0)
        return max(0.0, self._to_float(scale, 0.0) * self._volume_factor_for_resin(resin, unit_eq))

    def _loading_dissolve_solvent_for_resin(self) -> str:
        """Default solvent system used to dissolve the loading amino acid.

        2-CTC/trityl loading often uses a DCM-rich system; this planner exposes
        the default as 90% DCM / 10% DMF because users may dissolve the amino acid
        in a small DMF fraction while keeping the loading condition DCM-rich.
        Amide/Rink/Wang workflows default to DMF.
        """
        if self._resin_family_text() == 'CTC/Trityl':
            return str(getattr(self, 'default_loading_dissolve_solvent', _v225_const_var('90% DCM / 10% DMF')).get() or '90% DCM / 10% DMF')
        return str(getattr(self, 'default_coupling_solution_solvent', _v225_const_var('DMF')).get() or 'DMF')

    def _is_solid_reagent_name(self, name: str) -> bool:
        """True for solid reagents that should show a dissolve solvent/volume."""
        n = str(name or '').strip()
        if not n:
            return False
        return not self._is_liquid_like(n)

    def _default_dissolve_volume(self, name: str, phase: str='') -> float:
        """Default preparation volume for dissolving solid units/reagents.

        This uses the same retained resin-factor or molarity basis as the
        reaction/wash model, so preparation and working-volume tables cannot
        diverge through a second hidden setting.
        """
        try:
            return round(self._working_volume_for_scale(), 4)
        except Exception:
            return 0.0

    def _split_solution_name(self, solvent_name: str, total_ml: float):
        """Return component solvent rows for a solution string.

        Supports common 2-CTC loading notation such as '90% DCM / 10% DMF' or
        '10% DMF/DCM'. If the composition cannot be parsed, returns the original
        solvent as a single component.
        """
        s = str(solvent_name or '').strip()
        if not s or total_ml <= 0:
            return []
        u = s.upper().replace(' ', '')
        if '90%DCM' in u and '10%DMF' in u:
            return [('DCM', total_ml * 0.9, '90% of DCM-rich loading solution'), ('DMF', total_ml * 0.1, '10% of DCM-rich loading solution')]
        if '10%DMF' in u and 'DCM' in u:
            return [('DCM', total_ml * 0.9, '90% of DCM-rich loading solution'), ('DMF', total_ml * 0.1, '10% of DCM-rich loading solution')]
        return [(s, total_ml, 'dissolution/solution preparation solvent')]

    def _default_counts_for_row(self, step: int, total_steps: int, phase: str, unit_name: str, needs_depro: bool | None=None) -> tuple[str, int, str, int]:
        """Return post-coupling wash defaults for one editable row.

        Pepforge separates the SPPS process into loading, standard cycles, last
        coupling, and final modifier steps. The deprotection wash (DMF x6) is
        generated in the operation/checklist/material tables, not stored in the
        post-coupling solvent columns.

        Defaults:
        - Loading on 2-CTC/trityl: DCM-family condition.
        - Intermediate Fmoc-AA coupling: DMF wash x2 before next cycle.
        - Last Fmoc-AA coupling: DMF wash x2 before final deprotection.
        - Final Ac/chemical/label/modifier: no post-coupling solvent count here;
          final wash is generated separately.
        """
        is_last = int(step) == int(total_steps)
        phase_l = str(phase or '').lower()
        unit_u = str(unit_name or '').upper()
        is_non_fmoc_final = self._is_ac_unit(unit_name) or self._is_chemical_label_like_unit(unit_name)
        if 'branch first' in phase_l:
            return ('DMF', 2, '', 0)
        if 'loading' in phase_l and self._resin_family_text() == 'CTC/Trityl':
            return ('DCM', 1, '', 0)
        if is_last and is_non_fmoc_final:
            return ('', 0, '', 0)
        return ('DMF', 2, '', 0)

    def _final_wash_specs(self):
        """Return final wash sequence after last deprotection or final modifier.

        Default lab practice: DMF x3 and DCM x3. Some labs additionally use
        MeOH x3; this is controlled by the Final MeOH wash count field.
        """
        specs = [('DMF', 3), ('DCM', 3)]
        meoh_count = self._to_int(getattr(self, 'final_meoh_count', _v225_const_var(0)).get(), 0)
        if meoh_count > 0:
            specs.append(('MeOH', meoh_count))
        return specs

    def _last_fmoc_step_no(self, plan_df: pd.DataFrame):
        last = None
        for _, r in plan_df.iterrows():
            step = str(r.get('No', ''))
            meta = self._row_meta_by_no.get(step, {})
            row_dict = r.to_dict() if hasattr(r, 'to_dict') else dict(r)
            if self._is_non_fmoc_modifier_row(row_dict, meta):
                continue
            if self._needs_deprotection_for_row(row_dict, meta):
                last = step
        return last

    def _last_non_fmoc_final_step_no(self, plan_df: pd.DataFrame):
        for _, r in list(plan_df.iterrows())[::-1]:
            step = str(r.get('No', ''))
            meta = self._row_meta_by_no.get(step, {})
            if self._is_non_fmoc_modifier_row(r.to_dict() if hasattr(r, 'to_dict') else dict(r), meta):
                return step
        return None

    def generate_update_plan(self):
        """Single user-facing update action.

        This replaces duplicated build/update controls.
        It rebuilds the editable plan from the current setup fields, then refreshes
        material usage, project sheets, checklist, short steps, and logs.
        """
        try:
            self.rebuild_table()
            self.refresh_outputs_from_tree()
            self._log('Plan generated/updated.\n')
        except Exception as e:
            messagebox.showerror('Generate / Update Plan error', str(e))
            self._log('ERROR generate/update: ' + str(e) + '\n')

    def rebuild_table(self):
        try:
            inp = self._input()
            df = generate_excel_like_synthesis_table(inp)
            self.tree.delete(*self.tree.get_children())
            self._row_meta_by_no = {}
            total_steps = len(df.index) if df is not None else 0
            for _, row in df.iterrows():
                step = int(row.get('step', len(self.tree.get_children()) + 1))
                unit = str(row.get('unit', ''))
                phase = str(row.get('phase', ''))
                is_mod = any((x in phase.lower() for x in ['modifier', 'n-term', 'label', 'chemical']))
                eq = float(row.get('reagent_eq', self.coupling_eq.get()) or 0)
                repeat = int(float(row.get('coupling_repeat', self.coupling_repeats.get()) or 1))
                mw = float(row.get('reagent_mw', 0) or 0)
                calc_mmol = float(self.scale.get()) * eq * repeat
                name = self._normalize_unit_display_name(str(row.get('protected_reagent', '')) or unit)
                amount_basis_name, amount_basis_mw, amount_basis_hint = self._amount_basis_for_unit(name, phase, str(row.get('coupling_reagent', '')), mw)
                if amount_basis_mw:
                    mw = amount_basis_mw
                amount_display, calc_g, calc_ml, amount_unit = self._format_unit_amount(calc_mmol, mw, name, amount_basis_hint)
                note = str(row.get('note', ''))
                if is_mod:
                    note = (note + ' | terminal chemical/label/tag/cap step; chemical modifier row after final Fmoc removal and DMF x6; no post-coupling deprotection or default DCM final wash').strip(' |')
                if any((x in unit.upper() for x in ['FITC', 'BIOTIN', 'CY', 'FAM', 'TAMRA'])):
                    note = (note + ' | label reagent form must be verified; edit eq/reagent/base manually').strip(' |')
                temp_row_for_logic = {'No': step, 'Unit name': name}
                temp_meta_for_logic = {'Phase': phase, 'Note': note}
                needs_depro = self._needs_deprotection_for_row(temp_row_for_logic, temp_meta_for_logic)
                if not needs_depro:
                    if self._is_first_synthesis_row(temp_row_for_logic) and (not self._is_non_fmoc_modifier_row(temp_row_for_logic, temp_meta_for_logic)):
                        note = (note + ' | trityl/2-CTC first loading row; no initial Fmoc deprotection').strip(' |')
                solvent_defaults = self._default_counts_for_row(step, total_steps, phase, name, needs_depro=needs_depro)
                item = {'No': step, 'Unit name': name, 'Unit eq': eq, 'Unit amount(g)': round(calc_g, 4) if calc_g else '', 'Unit volume(mL)': round(calc_ml, 4) if calc_ml else '', 'Coupling reagent 1': '' if self._is_ac_unit(name) else row.get('coupling_reagent', self.default_reagent.get()), 'Coupling reagent 1 eq': '' if self._is_ac_unit(name) else self.default_reagent_eq.get(), 'Coupling reagent 1 count': 0 if self._is_ac_unit(name) else self.default_reagent_count.get(), 'Coupling reagent 2 / catalyst': '' if self._is_ac_unit(name) else row.get('catalyst', self.default_catalyst.get()), 'Coupling reagent 2 / catalyst eq': '' if self._is_ac_unit(name) else self.default_catalyst_eq.get() if row.get('catalyst', self.default_catalyst.get()) else '', 'Coupling reagent 2 / catalyst count': 0 if self._is_ac_unit(name) else self.default_catalyst_count.get(), 'Coupling base': row.get('base', self.default_base.get()), 'Coupling base eq': self.default_base_eq.get() if row.get('base', self.default_base.get()) else '', 'Coupling base count': self.default_base_count.get() if row.get('base', self.default_base.get()) else 0, 'Coupling cocktail solvent': self._loading_dissolve_solvent_for_resin() if 'loading' in phase.lower() else self.default_coupling_solution_solvent.get(), 'Coupling cocktail volume(mL)': self._default_dissolve_volume(name, phase), 'Deprotection base': self.default_depro.get() if needs_depro else '', 'Deprotection ratio': self.default_depro_ratio.get() if needs_depro else '', 'Deprotection count': self.default_depro_count.get() if needs_depro else 0, 'Solvent 1': solvent_defaults[0], 'Solvent 1 count': solvent_defaults[1], 'Solvent 2': solvent_defaults[2], 'Solvent 2 count': solvent_defaults[3], 'Repeat': repeat, 'MW': round(mw, 3) if mw else '', 'calculated mmol': round(calc_mmol, 4), 'calculated g': round(calc_g, 4), 'Phase': phase, 'Note': note}
                self._row_meta_by_no[str(step)] = {'MW': round(mw, 3) if mw else '', 'calculated mmol': round(calc_mmol, 4), 'calculated g': round(calc_g, 4), 'calculated mL': round(calc_ml, 4), 'amount_unit': amount_unit, 'Phase': phase, 'Note': note}
                self.tree.insert('', 'end', values=[item.get(c, '') for c in self.PLAN_COLUMNS])
            self._append_branch_rows_if_enabled()
            self.refresh_outputs_from_tree()
            self._log('Parsed sequence and built editable SPPS table.\n')
        except Exception as e:
            messagebox.showerror('Parse error', str(e))
            self._log('ERROR parse: ' + str(e) + '\n')

    def _append_branch_rows_if_enabled(self):
        """Append a simple branch workflow block after the main linear plan.

        Linear mode remains the default. When branch mode is enabled, the planner
        adds a branch protecting-group removal row followed by branch-arm coupling
        rows in C-term to N-term order. This keeps branch steps visibly separated
        while preserving the existing editable SPPS table and material usage logic.
        """
        try:
            if not bool(self.branch_mode.get()):
                return
            arm_raw = str(self.branch_arm.get() or '').strip()
            tokens = tokenize_core_sequence(arm_raw)
            if not tokens:
                return
            start_no = len(self.tree.get_children()) + 1
            pg = str(self.branch_pg.get() or 'Mtt')
            point = str(self.branch_point.get() or '').strip() or 'branch point'
            condition = str(self.branch_depro_condition.get() or '').strip()
            cond_u = condition.upper()
            if 'HYDRAZINE' in cond_u:
                depro_base, ratio, solv1 = ('Hydrazine', 'hydrazine/DMF', 'DMF')
            elif 'PD' in cond_u or 'ALLOC' in cond_u:
                depro_base, ratio, solv1 = ('Pd/phenylsilane', 'Alloc removal in DCM', 'DCM')
            else:
                depro_base, ratio, solv1 = ('TFA/TIS', 'dilute TFA/TIS/DCM', 'DCM')
            d = {c: '' for c in self.PLAN_COLUMNS}
            d.update({'No': start_no, 'Unit name': f'Branch PG removal ({pg} @ {point})', 'Unit eq': 0, 'Unit amount(g)': '', 'Unit volume(mL)': '', 'Coupling reagent 1': '', 'Coupling reagent 1 eq': '', 'Coupling reagent 1 count': 0, 'Coupling reagent 2 / catalyst': '', 'Coupling reagent 2 / catalyst eq': '', 'Coupling reagent 2 / catalyst count': 0, 'Coupling base': '', 'Coupling base eq': '', 'Coupling base count': 0, 'Deprotection base': depro_base, 'Deprotection ratio': ratio, 'Deprotection count': 1, 'Solvent 1': solv1, 'Solvent 1 count': 3, 'Solvent 2': '', 'Solvent 2 count': 0, 'Repeat': 1})
            self._row_meta_by_no[str(start_no)] = {'MW': '', 'calculated mmol': 0, 'calculated g': 0, 'calculated mL': 0, 'amount_unit': '', 'Phase': 'Branch deprotection', 'Note': f'Selective side-chain protecting group removal before branch arm coupling; {condition}'}
            self.tree.insert('', 'end', values=[d.get(c, '') for c in self.PLAN_COLUMNS])
            step_no = start_no + 1
            for branch_i, tok in enumerate(reversed(tokens), start=1):
                protected = self._protected_name_for_token(tok)
                mw = self._mw_for_token(tok)
                eq = float(self.coupling_eq.get())
                repeat = int(self.coupling_repeats.get())
                mmol = float(self.scale.get()) * eq * repeat
                amount_display, calc_g, calc_ml, amount_unit = self._format_unit_amount(mmol, mw, protected, protected)
                is_first_branch_coupling = branch_i == 1
                phase_label = 'Branch first coupling' if is_first_branch_coupling else 'Branch coupling'
                row = {c: '' for c in self.PLAN_COLUMNS}
                row.update({'No': step_no, 'Unit name': protected, 'Unit eq': eq, 'Unit amount(g)': round(calc_g, 4) if calc_g else '', 'Unit volume(mL)': round(calc_ml, 4) if calc_ml else '', 'Coupling reagent 1': self.default_reagent.get(), 'Coupling reagent 1 eq': self.default_reagent_eq.get(), 'Coupling reagent 1 count': self.default_reagent_count.get(), 'Coupling reagent 2 / catalyst': self.default_catalyst.get(), 'Coupling reagent 2 / catalyst eq': self.default_catalyst_eq.get(), 'Coupling reagent 2 / catalyst count': self.default_catalyst_count.get(), 'Coupling base': self.default_base.get(), 'Coupling base eq': self.default_base_eq.get() if self.default_base.get() else '', 'Coupling base count': self.default_base_count.get() if self.default_base.get() else 0, 'Coupling cocktail solvent': self.default_coupling_solution_solvent.get(), 'Coupling cocktail volume(mL)': self._default_dissolve_volume(protected, phase_label), 'Deprotection base': '' if is_first_branch_coupling else self.default_depro.get(), 'Deprotection ratio': '' if is_first_branch_coupling else self.default_depro_ratio.get(), 'Deprotection count': 0 if is_first_branch_coupling else self.default_depro_count.get(), 'Solvent 1': self.default_solvent1.get(), 'Solvent 1 count': 2, 'Solvent 2': '', 'Solvent 2 count': 0, 'Repeat': repeat})
                note = f'Branch arm coupling at {point}; branch arm={arm_raw}; protecting group={pg}'
                if is_first_branch_coupling:
                    note += '; first branch residue couples to deprotected side-chain handle without extra Fmoc deprotection'
                self._row_meta_by_no[str(step_no)] = {'MW': round(mw, 3) if mw else '', 'calculated mmol': round(mmol, 4), 'calculated g': round(calc_g, 4), 'calculated mL': round(calc_ml, 4), 'amount_unit': amount_unit, 'Phase': phase_label, 'Note': note}
                self.tree.insert('', 'end', values=[row.get(c, '') for c in self.PLAN_COLUMNS])
                step_no += 1
        except Exception as e:
            self._log('Branch mode append warning: ' + str(e) + '\n')

    def tree_rows(self) -> list[dict]:
        rows = []
        for child in self.tree.get_children():
            vals = list(self.tree.item(child, 'values'))
            rows.append({col: vals[i] if i < len(vals) else '' for i, col in enumerate(self.PLAN_COLUMNS)})
        return rows

    def on_tree_edit(self, row_id, col_name, new_value):
        self.recalculate_row(row_id)
        self.refresh_outputs_from_tree()

    def _to_float(self, v, default=0.0):
        return self._amount_numeric(v, default)

    def _to_int(self, v, default=0):
        try:
            return int(float(str(v).replace(',', '')))
        except Exception:
            return default
    LIQUID_DENSITY = _catalogs.LIQUID_DENSITY

    def _amount_numeric(self, value, default=0.0):
        """Parse numeric value from a cell that may contain 'g' or 'mL'."""
        try:
            if value is None or str(value).strip() == '':
                return default
            m = re.search('[-+]?\\d*\\.?\\d+(?:[eE][-+]?\\d+)?', str(value).replace(',', ''))
            return float(m.group(0)) if m else default
        except Exception:
            return default

    def _is_amount_ml(self, value) -> bool:
        return 'ml' in str(value or '').lower()

    def _is_liquid_like(self, name: str) -> bool:
        s = str(name or '').upper()
        if not s:
            return False
        liquid_markers = ['AC2O', 'ACOH', 'ACETIC', 'DIC', 'DIEA', 'DIPEA', 'NMM', 'TEA', 'PYRIDINE', 'COLLIDINE', 'LUTIDINE', 'PIPERIDINE', 'DBU', 'DMF', 'NMP', 'DCM', 'MEOH', 'ETOH', 'I-PROH', 'ACN', 'THF', 'DMSO', 'TFA', 'TIS', 'WATER', 'ETHER', 'MTBE']
        return any((m in s for m in liquid_markers))

    def _density_for(self, name: str) -> float:
        s = str(name or '').upper()
        for key, dens in self.LIQUID_DENSITY.items():
            if key in s:
                return dens
        return 1.0

    def _is_ac_unit(self, name: str) -> bool:
        u = str(name or '').strip().upper()
        key = self._unit_key(name) if hasattr(self, '_unit_key') else re.sub('[^A-Za-z0-9]', '', u)
        return u in {'AC', 'AC-', 'ACETYL', 'ACETYL CAP', 'AC / ACETYL CAP'} or key in {'AC', 'ACETYL', 'ACETYLCAP', 'ACETICANHYDRIDEAC2OFORNTERMINALACETYLATION', 'ACETICANHYDRIDE', 'AC2O'} or 'ACETIC ANHYDRIDE' in u

    def _amount_basis_for_unit(self, display_name: str, phase: str, coupling_reagent: str, mw: float):
        """Return calculation basis for the unit row.

        The editable row should show the user-facing unit such as 'Ac', but
        N-terminal acetylation is calculated from the actual liquid reagent
        Acetic anhydride (Ac2O) by default. Ac2O/AcOH must not appear in the
        coupling reagent columns.
        """
        if self._is_ac_unit(display_name):
            return ('Ac2O', 102.09, 'Ac2O')
        return (display_name, mw, display_name)

    def _format_unit_amount(self, mmol: float, mw: float, display_name: str, coupling_reagent: str=''):
        """Return display amount, g, mL, and unit for editable plan.

        Solid Fmoc-AA/modifier reagents are reported as g. Liquid/solution-like
        reagents such as Ac2O/AcOH are reported as mL using density.
        """
        reagent_hint = coupling_reagent or display_name
        grams = float(mmol) * float(mw) / 1000.0 if mw else 0.0
        if self._is_liquid_like(reagent_hint):
            dens = self._density_for(reagent_hint)
            ml = grams / dens if dens else 0.0
            return (f'{ml:.4f} mL', 0.0, ml, 'mL')
        return (round(grams, 4), grams, 0.0, 'g')
    AA_LIKE_LINKER_TOKENS = _catalogs.AA_LIKE_LINKER_TOKENS
    CHEMICAL_LABEL_TOKENS = _catalogs.CHEMICAL_LABEL_TOKENS
    CHEMICAL_DISPLAY_NAMES = _catalogs.CHEMICAL_DISPLAY_NAMES

    @staticmethod
    def _unit_key(name: str) -> str:
        return re.sub('[^A-Za-z0-9]', '', str(name or '')).upper()

    def _normalize_unit_display_name(self, name: str) -> str:
        s = str(name or '').strip()
        u = self._unit_key(s)
        if u in {'AC', 'ACETYL', 'ACETYL CAP'.replace(' ', ''), 'ACETICACID'}:
            return 'Ac'
        if u in self.CHEMICAL_DISPLAY_NAMES:
            return self.CHEMICAL_DISPLAY_NAMES[u]
        return s

    def _is_linker_like_unit(self, name: str) -> bool:
        u = str(name or '').strip().upper()
        return u in self.AA_LIKE_LINKER_TOKENS or u.startswith('PEG') or u.startswith('G4S')

    def _is_chemical_label_like_unit(self, name: str) -> bool:
        u = str(name or '').strip().upper()
        key = self._unit_key(name)
        if u in self.CHEMICAL_LABEL_TOKENS or key in self.CHEMICAL_LABEL_TOKENS:
            return True
        if any((x in u for x in ['FITC', 'FAM', 'TAMRA', 'BIOTIN', 'CY3', 'CY5', 'CY7', 'DOTA', 'NOTA', 'PAL', 'MYR', 'NHS'])):
            return not self._is_linker_like_unit(u)
        return False

    def _resin_needs_initial_deprotection(self) -> bool:
        """Return whether the selected resin requires an initial Fmoc deprotection.

        Practical rule used in this planner:
        - Trityl / 2-CTC loading does not have an initial Fmoc handle on resin.
        - Wang and amide/Rink-type resins are treated as Fmoc resins and require
          initial deprotection before the first coupling.
        """
        r = str(self.resin.get() or '').lower()
        if 'trityl' in r or '2-ctc' in r or 'ctc' in r:
            return False
        return True

    def _is_first_synthesis_row(self, row_dict: dict) -> bool:
        try:
            return int(float(str(row_dict.get('No', '0')))) == 1
        except Exception:
            return False

    def _needs_deprotection_for_row(self, row_dict: dict, meta: dict | None=None) -> bool:
        """Return whether a pre-reaction Fmoc deprotection is scheduled.

        Important distinction:
        - Final Ac/chemical/label/modifier rows do not need a *post-coupling*
          deprotection, but they usually need a pre-reaction Fmoc deprotection to
          expose the N-terminus before the final non-Fmoc reaction.
        - 2-CTC/trityl first loading and the first branch arm coupling start from an
          already available attachment point and skip this initial Fmoc deprotection.
        """
        meta = meta or {}
        phase = str(meta.get('Phase', row_dict.get('Phase', ''))).lower()
        if 'branch first' in phase or 'branch deprotection' in phase:
            return False
        if self._is_non_fmoc_modifier_row(row_dict, meta):
            return True
        if self._is_first_synthesis_row(row_dict) and (not self._resin_needs_initial_deprotection()):
            return False
        return True

    def _is_non_fmoc_modifier_row(self, row_dict: dict, meta: dict | None=None) -> bool:
        """Return True only for terminal chemical/label/cap modifier rows.

        Linkers such as Ahx, AEEA, PEGn, Cha and G4S are amino-acid-like
        synthesis units.  They must keep ordinary AA-cycle behavior: deprotection
        before coupling, coupling reaction, post-coupling DMF transition wash, and
        final deprotection/final wash when they are the last core unit.

        Chemical labels/caps such as Ac, FITC, FAM, TAMRA, Biotin, Pal/Myr and
        activated NHS labels are non-Fmoc terminal modifier rows. They need the
        preceding Fmoc removed before the modifier reaction, but they must not get
        a deprotection after the modifier reaction.
        """
        meta = meta or {}
        phase = str(meta.get('Phase', row_dict.get('Phase', ''))).lower()
        name = str(row_dict.get('Unit name', '')).strip()
        if self._is_linker_like_unit(name):
            return False
        if self._is_ac_unit(name) or self._is_chemical_label_like_unit(name):
            return True
        if any((m in phase for m in ['modifier', 'label', 'chemical', 'n-term', 'terminal', 'cap'])):
            return not self._is_linker_like_unit(name)
        return False

    def recalculate_row(self, row_id):
        cols = self.PLAN_COLUMNS
        vals = list(self.tree.item(row_id, 'values'))
        d = {cols[i]: vals[i] if i < len(vals) else '' for i in range(len(cols))}
        no_key = str(d.get('No', ''))
        meta = self._row_meta_by_no.get(no_key, {})
        eq = self._to_float(d.get('Unit eq'), self._to_float(d.get('Coupling reagent 1 eq'), 1.0))
        repeat = max(1, self._to_int(d.get('Repeat'), 1))
        mw = self._to_float(meta.get('MW'), 0.0)
        calc_mmol = self._to_float(self.scale.get(), 0.0) * eq * repeat
        amount_basis_name, amount_basis_mw, amount_basis_hint = self._amount_basis_for_unit(d.get('Unit name', ''), meta.get('Phase', ''), d.get('Coupling reagent 1', ''), mw)
        if amount_basis_mw:
            mw = amount_basis_mw
        amount_display, calc_g, calc_ml, amount_unit = self._format_unit_amount(calc_mmol, mw, d.get('Unit name', ''), amount_basis_hint)
        if not mw:
            calc_g = self._amount_numeric(d.get('Unit amount(g)', ''), 0.0)
            calc_ml = self._amount_numeric(d.get('Unit volume(mL)', ''), 0.0)
            amount_unit = 'mL' if calc_ml else 'g'
        d['Unit amount(g)'] = round(calc_g, 4) if calc_g else ''
        d['Unit volume(mL)'] = round(calc_ml, 4) if calc_ml else ''
        if not self._needs_deprotection_for_row(d, meta):
            d['Deprotection count'] = 0
            d['Deprotection base'] = ''
            d['Deprotection ratio'] = ''
            if not meta.get('Note'):
                if 'branch' in str(meta.get('Phase', '')).lower():
                    meta['Note'] = 'first branch-arm coupling starts from the deprotected side-chain handle; no extra pre-coupling Fmoc deprotection'
                else:
                    meta['Note'] = 'trityl/2-CTC first loading row; no initial Fmoc deprotection'
        elif self._is_non_fmoc_modifier_row(d, meta):
            if not meta.get('Note'):
                meta['Note'] = 'non-Fmoc Ac/chemical/tag/label/modifier row; no deprotection is assigned to this row'
        meta.update({'MW': round(mw, 3) if mw else meta.get('MW', ''), 'calculated mmol': round(calc_mmol, 4), 'calculated g': round(calc_g, 4), 'calculated mL': round(calc_ml, 4), 'amount_unit': amount_unit, 'Phase': meta.get('Phase', d.get('Phase', '')), 'Note': meta.get('Note', d.get('Note', ''))})
        self._row_meta_by_no[no_key] = meta
        self.tree.item(row_id, values=[d.get(c, '') for c in cols])

    def refresh_outputs_from_tree(self):
        for child in list(self.tree.get_children()):
            self.recalculate_row(child)
        rows = self.tree_rows()
        if not rows:
            self.rebuild_table()
            rows = self.tree_rows()
        plan_df = pd.DataFrame(rows)
        materials = self.materials_from_rows(plan_df)
        if (materials is None or materials.empty) and (not plan_df.empty):
            materials = self._minimal_materials_from_plan(plan_df)
        aa_summary = self.amino_acid_usage_summary(materials)
        reagent_summary = self.reagent_usage_summary(materials)
        solvent_summary = self.solvent_usage_summary(materials)
        ml = self.ml_log_from_rows(plan_df)
        ops = self.operation_form_from_rows(plan_df)
        checklist = self.checklist_from_rows(plan_df)
        loading_df = self.loading_calculator_df()
        cleavage_df = self.cleavage_calculator_df()
        transfer_df = self.manufacturing_transfer_df(materials, plan_df)
        production_df = self.production_tracking_df(plan_df)
        self._write_tree(self.live_usage_tree, materials, self.MATERIAL_COLUMNS)
        self._write_tree(self.material_tree, materials, self.MATERIAL_COLUMNS)
        self._write_tree(self.aa_summary_tree, aa_summary, ['material', 'planned_mmol', 'MW', 'calculated_g', 'actual_used_g'])
        self._write_tree(self.reagent_summary_tree, reagent_summary, ['material', 'class', 'MW', 'density_g_per_mL', 'planned_mmol', 'planned_g', 'planned_mL', 'actual_used'])
        self._write_tree(self.solvent_summary_tree, solvent_summary, ['solvent', 'planned_mL', 'use_count', 'note'])
        self._write_df(self.loading_text, loading_df)
        self._write_df(self.cleavage_text, cleavage_df)
        self._write_df(self.transfer_text, transfer_df)
        self._write_df(self.production_text, production_df)
        if hasattr(self, 'ml_text'):
            self._write_df(self.ml_text, ml)
        self._write_df(self.form_text, ops)
        self._write_df(self.check_text, checklist)
        if hasattr(self, 'short_step_text'):
            self._write_df(self.short_step_text, self.short_step_checklist_df(plan_df))
        self._populate_progress_tree(checklist)
        self._write_df(self.next_text, self.next_step_df())

    def amino_acid_usage_summary(self, materials: pd.DataFrame) -> pd.DataFrame:
        """Aggregate solid amino-acid / AA-like unit usage separately from solvents and reagents."""
        cols = ['material', 'planned_mmol', 'MW', 'calculated_g', 'actual_used_g']
        if materials is None or materials.empty:
            return pd.DataFrame(columns=cols)
        df = materials.copy()
        cls = df.get('class', '').astype(str).str.lower()
        mask = cls.str.contains('aa/chemical|amino|modifier|label|tag|linker', regex=True, na=False)
        mask &= pd.to_numeric(df.get('planned_g', 0), errors='coerce').fillna(0) > 0
        if not mask.any():
            return pd.DataFrame(columns=cols)
        out = df.loc[mask].groupby('material', dropna=False).agg({'planned_mmol': 'sum', 'MW': 'first', 'planned_g': 'sum'}).reset_index()
        out = out.rename(columns={'planned_g': 'calculated_g'})
        out['actual_used_g'] = ''
        for c in ['planned_mmol', 'calculated_g']:
            out[c] = pd.to_numeric(out[c], errors='coerce').fillna(0).round(4)
        return out[cols]

    def reagent_usage_summary(self, materials: pd.DataFrame) -> pd.DataFrame:
        """Aggregate coupling reagents, bases, catalysts/additives, capping and deprotection reagents."""
        cols = ['material', 'class', 'MW', 'density_g_per_mL', 'planned_mmol', 'planned_g', 'planned_mL', 'actual_used']
        if materials is None or materials.empty:
            return pd.DataFrame(columns=cols)
        df = materials.copy()
        cls = df.get('class', '').astype(str).str.lower()
        excl = cls.str.contains('solvent|wash', regex=True, na=False)
        incl = cls.str.contains('reagent|base|catalyst|additive|deprotection|modifier', regex=True, na=False) & ~excl
        incl |= df.get('material', '').astype(str).str.contains('Ac2O|DIC|HOBt|HBTU|HATU|DIEA|DIPEA|Piperidine|TFA|TIS', case=False, regex=True, na=False)
        if not incl.any():
            return pd.DataFrame(columns=cols)
        tmp = df.loc[incl].copy()
        grouped = tmp.groupby(['material', 'class'], dropna=False).agg({'MW': 'first', 'planned_mmol': 'sum', 'planned_g': 'sum', 'planned_mL': 'sum'}).reset_index()
        grouped['density_g_per_mL'] = grouped['material'].apply(lambda x: self._density_for(x) if self._density_for(x) else '')
        grouped['actual_used'] = ''
        for c in ['planned_mmol', 'planned_g', 'planned_mL']:
            grouped[c] = pd.to_numeric(grouped[c], errors='coerce').fillna(0).round(4)
        return grouped[cols]

    def solvent_usage_summary(self, materials: pd.DataFrame) -> pd.DataFrame:
        """Aggregate solvent consumption independently from reagent/material rows."""
        cols = ['solvent', 'planned_mL', 'use_count', 'note']
        if materials is None or materials.empty:
            return pd.DataFrame(columns=cols)
        df = materials.copy()
        cls = df.get('class', '').astype(str).str.lower()
        mask = cls.str.contains('solvent|wash', regex=True, na=False)
        if not mask.any():
            return pd.DataFrame(columns=cols)
        tmp = df.loc[mask].copy()
        tmp['planned_mL'] = pd.to_numeric(tmp.get('planned_mL', 0), errors='coerce').fillna(0)
        tmp['_use_count_num'] = pd.to_numeric(tmp.get('use_count', 0), errors='coerce').fillna(0)
        out = tmp.groupby('material', dropna=False).agg({'planned_mL': 'sum', '_use_count_num': 'sum', 'note': 'first'}).reset_index()
        out = out.rename(columns={'material': 'solvent', '_use_count_num': 'use_count'})
        out['planned_mL'] = out['planned_mL'].round(4)
        out['use_count'] = out['use_count'].round(4)
        return out[cols]

    def _estimate_reagent_g(self, name, mmol):
        mw = self.MW_FALLBACK.get(str(name).strip(), 0.0)
        return mmol * mw / 1000 if mw else 0.0

    def materials_from_rows(self, plan_df: pd.DataFrame) -> pd.DataFrame:
        """Build a process-ordered material usage table from the editable plan.

        Important SPPS rules enforced here:
        - A coupling row uses one coupling cocktail solvent for unit + reagent 1 + reagent 2/catalyst + base.
        - Final N-terminal Ac/chemical/tag/label/linker/modifier rows are treated like practical coupling units.
        - Their own row carries the required final Fmoc removal and DMF wash x6 before terminal reaction.
        - Terminal chemical/label/tag/cap reaction is followed by the same Last wash as final workup: DMF x3 then DCM x3.
        - Without an N-terminal modifier, final deprotection is followed by final wash DMF x3 then DCM x3.
        """
        scale = self._to_float(self.scale.get(), 0.0)
        loading = self._to_float(self.loading.get(), 0.0)
        per_use_ml = self._working_volume_for_scale(scale)
        rows = []

        def mw_for(name: str):
            n = str(name or '').strip()
            if not n:
                return ''
            if n in self.MW_FALLBACK:
                return self.MW_FALLBACK[n]
            u = n.upper()
            for k, v in self.MW_FALLBACK.items():
                if k.upper() == u or k.upper() in u:
                    return v
            return ''

        def add(step='', material='', cls='', mmol=0, g=0, ml=0, count='', repeat='', phase='', note='', src='', mw=''):
            material = str(material or '').strip()
            if not material:
                return
            rows.append({'step': step, 'material': material, 'class': cls, 'MW': mw if mw != '' else mw_for(material), 'planned_mmol': round(self._to_float(mmol, 0.0), 4), 'planned_g': round(self._to_float(g, 0.0), 4), 'planned_mL': round(self._to_float(ml, 0.0), 4), 'use_count': count, 'repeat': repeat, 'phase': phase, 'note': note, 'source': src})

        def add_solution_components(step, solvent_name, total_ml, cls, phase, note, src, count=1):
            for solv_name, solv_ml, split_note in self._split_solution_name(solvent_name, total_ml):
                add(step=step, material=solv_name, cls=cls, ml=solv_ml, count=count, phase=phase, note=(note + '; ' + split_note).strip('; '), src=src)
        resin_g = scale / loading if loading else 0.0
        add(material='Resin', cls=self.resin.get(), mmol=scale, g=resin_g, phase='resin', note='calculated from scale/loading', src='scale/loading')
        swell_solvent = self._swell_solvent_for_resin()
        add(step='swell', material=swell_solvent, cls='resin swell solvent', ml=per_use_ml, count=1, repeat=1, phase='resin swell', note='Swell solvent follows resin/loading family: DCM for 2-CTC/trityl; DMF for amide/Wang/Rink-type resin.', src='resin swell')
        final_non_fmoc_step = self._last_non_fmoc_final_step_no(plan_df)
        last_fmoc_step = self._last_fmoc_step_no(plan_df)
        final_depro_added = False

        def add_final_depro_before(step_for_depro, before_step_note=''):
            nonlocal final_depro_added
            if final_depro_added or not step_for_depro:
                return
            try:
                last_row = plan_df[plan_df['No'].astype(str) == str(step_for_depro)].iloc[0]
            except Exception:
                return
            final_depro_count = self._to_int(last_row.get('Deprotection count'), self.default_depro_count.get())
            final_depro_base = last_row.get('Deprotection base', self.default_depro.get())
            final_depro_ratio = last_row.get('Deprotection ratio', self.default_depro_ratio.get())
            if final_depro_count > 0 and str(final_depro_base or '').strip():
                label = f'{step_for_depro}; final Fmoc removal'
                phase = 'pre-modifier Fmoc removal' if before_step_note else 'final deprotection'
                note = 'Final Fmoc removal assigned to the last Fmoc-AA row; non-Fmoc Ac/chemical/tag/label/modifier rows do not receive deprotection.'
                if not before_step_note:
                    note = 'Final deprotection after the last Fmoc-AA coupling; followed only by final wash DMF x3 / DCM x3 / optional MeOH.'
                add(step=label, material=final_depro_base, cls='final deprotection base', ml=per_use_ml * final_depro_count, count=final_depro_count, phase=phase, note=note, src=f'step {step_for_depro}; final deprotection; ratio={final_depro_ratio}', mw=mw_for(final_depro_base))
                if before_step_note:
                    add(step=f'{step_for_depro}; final Fmoc removal wash', material='DMF', cls='final deprotection wash solvent', ml=per_use_ml * 6, count=6, phase='pre-modifier final deprotection wash', note='Before N-terminal Ac/modifier reaction: DMF wash x6 after final Fmoc removal; DCM is not used before Ac.', src=f'step {step_for_depro}; pre-modifier final deprotection wash')
                final_depro_added = True
        for _, r in plan_df.iterrows():
            step = str(r.get('No', ''))
            meta = self._row_meta_by_no.get(str(step), {})
            name = str(r.get('Unit name', '') or '')
            eq = self._to_float(r.get('Unit eq'), 0)
            repeat = max(1, self._to_int(r.get('Repeat'), 1))
            mmol = scale * eq * repeat
            amount_g_cell = r.get('Unit amount(g)')
            amount_ml_cell = r.get('Unit volume(mL)')
            phase = meta.get('Phase', '')
            note = meta.get('Note', '')
            row_dict = r.to_dict() if hasattr(r, 'to_dict') else dict(r)
            is_non_fmoc_final = str(step) == str(final_non_fmoc_step)
            is_last_fmoc = str(step) == str(last_fmoc_step)
            needs_pre_depro = self._needs_deprotection_for_row(row_dict, meta)
            depro_count = self._to_int(r.get('Deprotection count'), 0)
            if needs_pre_depro and depro_count > 0:
                depro = r.get('Deprotection base', self.default_depro.get())
                ratio = r.get('Deprotection ratio', self.default_depro_ratio.get())
                add(step=f'{step}; pre-coupling deprotection', material=depro, cls='deprotection base', ml=per_use_ml * depro_count, count=depro_count, phase='pre-coupling deprotection', note='STD cycle: deprotection x2 before Fmoc-AA coupling', src=f'step {step}; ratio={ratio}', mw=mw_for(depro))
                add(step=f'{step}; deprotection wash', material='DMF', cls='deprotection wash solvent', ml=per_use_ml * 6, count=6, phase='pre-coupling deprotection wash', note='STD cycle: DMF wash x6 after deprotection and before coupling', src=f'step {step}; pre-coupling deprotection wash')
            if self._is_ac_unit(name):
                ac_mw = 102.09
                ac_g = mmol * ac_mw / 1000.0
                ac_ml = ac_g / self._density_for('Ac2O')
                add(step=step, material='Acetic anhydride (Ac2O) for Ac', cls='N-terminal modifier reagent', mmol=mmol, ml=ac_ml, repeat=repeat, phase=phase, note='N-terminal Ac is calculated from Acetic anhydride (Ac2O, MW 102.09, density 1.08 g/mL); no post-Ac deprotection.', src=f'step {step}', mw=ac_mw)
            else:
                mw_unit = meta.get('MW', '')
                if self._amount_numeric(amount_ml_cell, 0.0) > 0:
                    add(step=step, material=name, cls='AA/Chemical/label/tag/linker', mmol=mmol, ml=self._amount_numeric(amount_ml_cell, 0.0), repeat=repeat, phase=phase, note=note, src=f'step {step}', mw=mw_unit)
                else:
                    g = self._amount_numeric(amount_g_cell, self._to_float(meta.get('calculated g'), 0))
                    add(step=step, material=name, cls='AA/Chemical/label/tag/linker', mmol=mmol, g=g, repeat=repeat, phase=phase, note=note, src=f'step {step}', mw=mw_unit)
            csolv = str(r.get('Coupling cocktail solvent', '') or '')
            cvol = self._to_float(r.get('Coupling cocktail volume(mL)'), 0)
            if csolv and cvol > 0 and str(r.get('Unit name', '') or '').strip():
                components = [x for x in [r.get('Unit name', ''), r.get('Coupling reagent 1', ''), r.get('Coupling reagent 2 / catalyst', ''), r.get('Coupling base', '')] if str(x or '').strip()]
                comp_txt = ' + '.join(map(str, components))
                add_solution_components(step=f'{step}; coupling cocktail', solvent_name=csolv, total_ml=cvol, cls='coupling cocktail solvent', phase=phase, note=f'Single cocktail solvent for: {comp_txt}', src=f'step {step}; coupling cocktail', count=1)
            r1_name = r.get('Coupling reagent 1')
            r1eq = self._to_float(r.get('Coupling reagent 1 eq'), 0)
            r1count = self._to_float(r.get('Coupling reagent 1 count'), repeat)
            r1mmol = scale * r1eq * r1count
            r1_mw = mw_for(r1_name)
            r1_g = r1mmol * self._to_float(r1_mw, 0) / 1000.0 if r1_mw else 0.0
            if self._is_liquid_like(r1_name):
                add(step=step, material=r1_name, cls='coupling reagent', mmol=r1mmol, ml=r1_g / self._density_for(r1_name) if r1_g else 0, count=r1count, repeat=repeat, src=f'step {step}', mw=r1_mw)
            else:
                add(step=step, material=r1_name, cls='coupling reagent', mmol=r1mmol, g=r1_g, count=r1count, repeat=repeat, src=f'step {step}', mw=r1_mw)
            c2_name = r.get('Coupling reagent 2 / catalyst')
            c2eq = self._to_float(r.get('Coupling reagent 2 / catalyst eq'), 0)
            c2count = self._to_float(r.get('Coupling reagent 2 / catalyst count'), repeat)
            c2mmol = scale * c2eq * c2count
            c2_mw = mw_for(c2_name)
            c2_g = c2mmol * self._to_float(c2_mw, 0) / 1000.0 if c2_mw else 0.0
            if self._is_liquid_like(c2_name):
                add(step=step, material=c2_name, cls='catalyst/additive', mmol=c2mmol, ml=c2_g / self._density_for(c2_name) if c2_g else 0, count=c2count, repeat=repeat, src=f'step {step}', mw=c2_mw)
            else:
                add(step=step, material=c2_name, cls='catalyst/additive', mmol=c2mmol, g=c2_g, count=c2count, repeat=repeat, src=f'step {step}', mw=c2_mw)
            base_name = r.get('Coupling base')
            beq = self._to_float(r.get('Coupling base eq'), 0)
            bcount = self._to_float(r.get('Coupling base count'), repeat)
            bmmol = scale * beq * bcount
            base_mw = mw_for(base_name)
            base_g = bmmol * self._to_float(base_mw, 0) / 1000.0 if base_mw else 0.0
            if self._is_liquid_like(base_name):
                add(step=step, material=base_name, cls='base', mmol=bmmol, ml=base_g / self._density_for(base_name) if base_g else 0, count=bcount, repeat=repeat, src=f'step {step}', mw=base_mw)
            else:
                add(step=step, material=base_name, cls='base', mmol=bmmol, g=base_g, count=bcount, repeat=repeat, src=f'step {step}', mw=base_mw)
            skip_transition_wash = bool(is_non_fmoc_final or (is_last_fmoc and (not final_non_fmoc_step)))
            if not skip_transition_wash:
                s1_count = self._to_int(r.get('Solvent 1 count'), 0)
                s2_count = self._to_int(r.get('Solvent 2 count'), 0)
                if s1_count > 0:
                    add(step=f'{step}; post-coupling wash', material=r.get('Solvent 1'), cls='post-coupling wash solvent', ml=per_use_ml * s1_count, count=s1_count, phase='post-coupling wash', note='Default transition wash after coupling is DMF x2 unless edited', src=f'step {step}')
                if s2_count > 0:
                    add(step=f'{step}; post-coupling wash', material=r.get('Solvent 2'), cls='post-coupling wash solvent', ml=per_use_ml * s2_count, count=s2_count, phase='post-coupling wash', note='Special/user-edited post-coupling wash', src=f'step {step}')
            if is_last_fmoc and (not final_non_fmoc_step):
                add_final_depro_before(last_fmoc_step)
                for solvent_name, wash_count in self._final_wash_specs():
                    if wash_count > 0:
                        add(step=f'{step}; final wash', material=solvent_name, cls='final wash solvent', ml=per_use_ml * wash_count, count=wash_count, phase='final wash', note='Final wash after final Fmoc deprotection: DMF x3 / DCM x3 / optional MeOH', src=f'step {step}; final wash')
            if is_non_fmoc_final:
                for solvent_name, wash_count in self._final_wash_specs():
                    if wash_count > 0:
                        add(step=f'{step}; final wash', material=solvent_name, cls='final wash solvent', ml=per_use_ml * wash_count, count=wash_count, phase='final wash', note='Last wash after terminal chemical/label/tag/cap reaction: DMF x3 first, then DCM x3', src=f'step {step}; final wash')
        df = pd.DataFrame(rows)
        if not df.empty:
            for col in ['planned_mmol', 'planned_g', 'planned_mL']:
                if col in df.columns:
                    df[col] = df[col].apply(lambda x: round(float(x), 4) if str(x) not in ['', 'nan'] else x)
        return df

    def _minimal_materials_from_plan(self, plan_df: pd.DataFrame) -> pd.DataFrame:
        """Fallback material renderer used when the full process table returns empty.

        It prevents a blank Materials tab and makes SPPS Planner usable while the
        user edits custom rows. The full calculator is still used whenever it
        returns rows.
        """
        rows = []
        scale = self._to_float(self.scale.get(), 0.0)

        def add(step, material, cls, mmol=0, g=0, ml=0, note='fallback'):
            if str(material or '').strip():
                rows.append({'step': step, 'material': material, 'class': cls, 'MW': '', 'planned_mmol': round(self._to_float(mmol, 0), 4), 'planned_g': round(self._to_float(g, 0), 4), 'planned_mL': round(self._to_float(ml, 0), 4), 'use_count': '', 'repeat': '', 'phase': 'fallback', 'note': note, 'source': 'editable plan fallback'})
        add('resin', 'Resin', self.resin.get(), mmol=scale, g=scale / self._to_float(self.loading.get(), 1) if self._to_float(self.loading.get(), 0) else 0, note='scale/loading')
        for _, r in plan_df.iterrows():
            step = r.get('No', '')
            unit = r.get('Unit name', '')
            eq = self._to_float(r.get('Unit eq'), 0)
            rep = max(1, self._to_int(r.get('Repeat'), 1))
            mmol = scale * eq * rep
            add(step, unit, 'AA/chemical/linker', mmol=mmol, g=self._to_float(r.get('Unit amount(g)'), 0), ml=self._to_float(r.get('Unit volume(mL)'), 0), note='unit from editable plan')
            for col, cls in [('Coupling reagent 1', 'coupling reagent'), ('Coupling reagent 2 / catalyst', 'catalyst/additive'), ('Coupling base', 'base'), ('Deprotection base', 'deprotection base'), ('Coupling cocktail solvent', 'coupling solvent'), ('Solvent 1', 'wash solvent'), ('Solvent 2', 'wash solvent')]:
                add(step, r.get(col, ''), cls, note=col)
        return pd.DataFrame(rows, columns=self.MATERIAL_COLUMNS)

    def ml_log_from_rows(self, plan_df: pd.DataFrame) -> pd.DataFrame:
        out = plan_df.copy()
        out.insert(0, 'project_name', self.project_name.get())
        out.insert(1, 'lot_no', self.lot_no.get())
        out.insert(2, 'sequence', self.seq.get())
        out.insert(1, 'resin', self.resin.get())
        out.insert(2, 'scale_mmol', self.scale.get())
        out.insert(3, 'loading_mmol_g', self.loading.get())
        out.insert(4, 'solvent_volume_mode', self.solvent_volume_mode.get())
        out.insert(5, 'amide_ml_per_mmol', self.amide_ml_per_mmol.get())
        out.insert(6, 'ctc_ml_per_mmol', self.ctc_ml_per_mmol.get())
        out.insert(7, 'solvent_molarity_m', self.solvent_molarity_m.get())
        out.insert(8, 'branch_mode', bool(self.branch_mode.get()))
        out.insert(9, 'branch_point', self.branch_point.get())
        out.insert(10, 'branch_arm', self.branch_arm.get())
        out.insert(11, 'branch_protecting_group', self.branch_pg.get())
        out['actual_yield'] = ''
        out['purity'] = ''
        out['lcms_result'] = ''
        out['hplc_method'] = ''
        out['operator_note'] = ''
        return out

    def operation_form_from_rows(self, plan_df: pd.DataFrame) -> pd.DataFrame:
        ops = []
        line = 1
        swell_solvent = self._swell_solvent_for_resin()
        loading_family = 'DCM-family loading' if self._resin_family_text() == 'CTC/Trityl' else 'DMF-family loading / preloaded Fmoc resin handling'
        ops.append({'line': line, 'step': 'swell', 'operation': 'resin swell', 'unit': self.resin.get(), 'solution': swell_solvent, 'repeat/count': 1, 'date': '', 'operator': '', 'note': f'Swell before loading; {loading_family}'})
        line += 1
        final_non_fmoc_step = self._last_non_fmoc_final_step_no(plan_df)
        last_fmoc_step = self._last_fmoc_step_no(plan_df)
        for _, r in plan_df.iterrows():
            step = str(r.get('No', ''))
            unit = r.get('Unit name', '')
            rep = max(1, self._to_int(r.get('Repeat'), 1))
            depro = r.get('Deprotection base', self.default_depro.get())
            ratio = r.get('Deprotection ratio', self.default_depro_ratio.get())
            dcount = self._to_int(r.get('Deprotection count'), self.default_depro_count.get())
            row_dict = r.to_dict() if hasattr(r, 'to_dict') else dict(r)
            meta = self._row_meta_by_no.get(str(step), {})
            needs_pre_depro = self._needs_deprotection_for_row(row_dict, meta)
            is_last_fmoc = str(step) == str(last_fmoc_step)
            is_final_non_fmoc = str(step) == str(final_non_fmoc_step)
            phase_text = str(meta.get('Phase', ''))
            is_loading = 'loading' in phase_text.lower()
            if dcount > 0 and needs_pre_depro:
                ops.append({'line': line, 'step': step, 'operation': 'deprotection', 'unit': unit, 'solution': f'{depro} ({ratio})', 'repeat/count': dcount, 'date': '', 'operator': '', 'note': 'Pre-coupling Fmoc deprotection'})
                line += 1
                ops.append({'line': line, 'step': step, 'operation': 'DMF wash after deprotection', 'unit': unit, 'solution': 'DMF', 'repeat/count': 6, 'date': '', 'operator': '', 'note': 'STD cycle: DMF wash x6 after deprotection before coupling'})
                line += 1
            for i in range(rep):
                if is_loading:
                    op_name = 'resin loading / first unit attachment'
                    note_extra = 'Loading is distinct from regular coupling; solvent follows resin family'
                elif is_last_fmoc:
                    op_name = 'last coupling step'
                    note_extra = 'After this Fmoc-AA coupling: DMF wash x2 -> next terminal row or final deprotection'
                elif is_final_non_fmoc:
                    op_name = 'final chemical / label / modifier coupling'
                    note_extra = 'Terminal chemical/label/tag/cap coupling after Fmoc removal + DMF x6; followed by last wash DMF x3 then DCM x3'
                else:
                    op_name = 'coupling reaction'
                    note_extra = 'STD cycle: coupling -> DMF wash x2 -> next cycle'
                ops.append({'line': line, 'step': step, 'operation': op_name, 'unit': unit, 'solution': f"Prepare coupling cocktail: {unit} + {r.get('Coupling reagent 1', '')} + {r.get('Coupling reagent 2 / catalyst', '')} + {r.get('Coupling base', '')} in {r.get('Coupling cocktail solvent', r.get('Solvent 1', ''))} ({r.get('Coupling cocktail volume(mL)', '')} mL); add to resin", 'repeat/count': i + 1, 'date': '', 'operator': '', 'note': (str(meta.get('Note', r.get('Note', ''))) + ' | ' + note_extra).strip(' |')})
                line += 1
            s1 = r.get('Solvent 1', '')
            c1 = self._to_int(r.get('Solvent 1 count'), 0)
            s2 = r.get('Solvent 2', '')
            c2 = self._to_int(r.get('Solvent 2 count'), 0)
            skip_transition_wash = bool(is_final_non_fmoc or (is_last_fmoc and (not final_non_fmoc_step)))
            if (c1 > 0 or c2 > 0) and (not skip_transition_wash):
                ops.append({'line': line, 'step': step, 'operation': 'post-coupling wash', 'unit': unit, 'solution': f'{s1} x {c1} / {s2} x {c2}', 'repeat/count': '', 'date': '', 'operator': '', 'note': 'Default transition wash is DMF x2; DCM is not used between ordinary coupling cycles unless edited by the user'})
                line += 1
            if is_last_fmoc and (not final_non_fmoc_step) and (dcount > 0) and needs_pre_depro:
                ops.append({'line': line, 'step': step, 'operation': 'final deprotection', 'unit': unit, 'solution': f'{depro} ({ratio})', 'repeat/count': dcount, 'date': '', 'operator': '', 'note': 'Final Fmoc deprotection after the last Fmoc-AA coupling'})
                line += 1
            if is_last_fmoc and (not final_non_fmoc_step):
                for solvent_name, wash_count in self._final_wash_specs():
                    ops.append({'line': line, 'step': step, 'operation': 'final wash', 'unit': unit, 'solution': solvent_name, 'repeat/count': wash_count, 'date': '', 'operator': '', 'note': 'Final wash after final deprotection: DMF x3 then DCM x3'})
                    line += 1
            elif is_final_non_fmoc:
                for solvent_name, wash_count in self._final_wash_specs():
                    ops.append({'line': line, 'step': step, 'operation': 'final wash', 'unit': unit, 'solution': solvent_name, 'repeat/count': wash_count, 'date': '', 'operator': '', 'note': 'Last wash after terminal chemical/label/tag/cap reaction: DMF x3 first, then DCM x3'})
                    line += 1
        return pd.DataFrame(ops)

    def checklist_from_rows(self, plan_df: pd.DataFrame) -> pd.DataFrame:
        """Printable checklist with one row per practical SPPS operation."""
        rows = []
        line = 1
        swell_solvent = self._swell_solvent_for_resin()
        loading_family = 'DCM-family loading' if self._resin_family_text() == 'CTC/Trityl' else 'DMF-family loading / preloaded Fmoc resin handling'
        rows.append({'Line': line, 'Step': 'swell', 'Operation': 'Resin swell', 'AA/Chemical/label/tag/linker': self.resin.get(), 'Reagent/Solution': swell_solvent, 'Eq/Count': 1, 'Amount(g or mL)': '', 'Date': '', 'Checked': 'No', 'Operator': '', 'Note': f'Swell before loading; {loading_family}'})
        line += 1
        final_non_fmoc_step = self._last_non_fmoc_final_step_no(plan_df)
        last_fmoc_step = self._last_fmoc_step_no(plan_df)
        for _, r in plan_df.iterrows():
            step = str(r.get('No', ''))
            unit = r.get('Unit name', '')
            rep = max(1, self._to_int(r.get('Repeat'), 1))
            depro = r.get('Deprotection base', self.default_depro.get())
            ratio = r.get('Deprotection ratio', self.default_depro_ratio.get())
            dcount = self._to_int(r.get('Deprotection count'), self.default_depro_count.get())
            row_dict = r.to_dict() if hasattr(r, 'to_dict') else dict(r)
            meta = self._row_meta_by_no.get(str(step), {})
            needs_pre_depro = self._needs_deprotection_for_row(row_dict, meta)
            is_last_fmoc = str(step) == str(last_fmoc_step)
            is_final_non_fmoc = str(step) == str(final_non_fmoc_step)
            phase_text = str(meta.get('Phase', ''))
            is_loading = 'loading' in phase_text.lower()
            if dcount > 0 and needs_pre_depro:
                for i in range(dcount):
                    rows.append({'Line': line, 'Step': step, 'Operation': 'Deprotection', 'AA/Chemical/label/tag/linker': unit, 'Reagent/Solution': f'{depro} ({ratio})', 'Eq/Count': i + 1, 'Amount(g or mL)': '', 'Date': '', 'Checked': 'No', 'Operator': '', 'Note': 'Pre-coupling Fmoc deprotection'})
                    line += 1
                for i in range(6):
                    rows.append({'Line': line, 'Step': step, 'Operation': 'DMF wash after deprotection', 'AA/Chemical/label/tag/linker': unit, 'Reagent/Solution': 'DMF', 'Eq/Count': i + 1, 'Amount(g or mL)': '', 'Date': '', 'Checked': 'No', 'Operator': '', 'Note': 'STD cycle: DMF wash x6 before coupling'})
                    line += 1
            for i in range(rep):
                op = 'Resin loading / first unit attachment' if is_loading else 'Last coupling step' if is_last_fmoc else 'Final chemical / label / modifier coupling' if is_final_non_fmoc else 'Coupling reaction'
                rows.append({'Line': line, 'Step': step, 'Operation': op, 'AA/Chemical/label/tag/linker': unit, 'Reagent/Solution': f"Coupling cocktail: {unit} + {r.get('Coupling reagent 1', '')} + {r.get('Coupling reagent 2 / catalyst', '')} + {r.get('Coupling base', '')} in {r.get('Coupling cocktail solvent', r.get('Solvent 1', ''))} ({r.get('Coupling cocktail volume(mL)', '')} mL)", 'Eq/Count': f"repeat {i + 1}/{rep}; unit eq={r.get('Unit eq', '')}", 'Amount(g or mL)': r.get('Unit amount(g)', '') or r.get('Unit volume(mL)', ''), 'Date': '', 'Checked': 'No', 'Operator': '', 'Note': str(meta.get('Note', ''))})
                line += 1
            s1 = r.get('Solvent 1', '')
            c1 = self._to_int(r.get('Solvent 1 count'), 0)
            s2 = r.get('Solvent 2', '')
            c2 = self._to_int(r.get('Solvent 2 count'), 0)
            skip_transition_wash = bool(is_final_non_fmoc or (is_last_fmoc and (not final_non_fmoc_step)))
            if not skip_transition_wash:
                for i in range(c1):
                    rows.append({'Line': line, 'Step': step, 'Operation': 'Post-coupling wash', 'AA/Chemical/label/tag/linker': unit, 'Reagent/Solution': s1, 'Eq/Count': i + 1, 'Amount(g or mL)': '', 'Date': '', 'Checked': 'No', 'Operator': '', 'Note': 'Default transition wash is DMF x2'})
                    line += 1
                for i in range(c2):
                    rows.append({'Line': line, 'Step': step, 'Operation': 'Post-coupling wash', 'AA/Chemical/label/tag/linker': unit, 'Reagent/Solution': s2, 'Eq/Count': i + 1, 'Amount(g or mL)': '', 'Date': '', 'Checked': 'No', 'Operator': '', 'Note': 'User-edited/special wash'})
                    line += 1
            if is_last_fmoc and (not final_non_fmoc_step) and (dcount > 0) and needs_pre_depro:
                for i in range(dcount):
                    rows.append({'Line': line, 'Step': step, 'Operation': 'Final deprotection', 'AA/Chemical/label/tag/linker': unit, 'Reagent/Solution': f'{depro} ({ratio})', 'Eq/Count': i + 1, 'Amount(g or mL)': '', 'Date': '', 'Checked': 'No', 'Operator': '', 'Note': 'After last Fmoc-AA coupling'})
                    line += 1
            if is_last_fmoc and (not final_non_fmoc_step):
                for solvent_name, wash_count in self._final_wash_specs():
                    for i in range(wash_count):
                        rows.append({'Line': line, 'Step': step, 'Operation': 'Final wash', 'AA/Chemical/label/tag/linker': unit, 'Reagent/Solution': solvent_name, 'Eq/Count': i + 1, 'Amount(g or mL)': '', 'Date': '', 'Checked': 'No', 'Operator': '', 'Note': 'Final wash order: first DMF x3, then DCM x3'})
                        line += 1
            elif is_final_non_fmoc:
                for solvent_name, wash_count in self._final_wash_specs():
                    for i in range(wash_count):
                        rows.append({'Line': line, 'Step': step, 'Operation': 'Final wash', 'AA/Chemical/label/tag/linker': unit, 'Reagent/Solution': solvent_name, 'Eq/Count': i + 1, 'Amount(g or mL)': '', 'Date': '', 'Checked': 'No', 'Operator': '', 'Note': 'Last wash order after terminal chemical/label/tag/cap: first DMF x3, then DCM x3'})
                        line += 1
        return pd.DataFrame(rows)

    def _sanitize_display_value(self, value):
        """Return compact, Treeview-safe display text.

        V7.4 accidentally called this helper without defining it, which made
        all Material tables render blank.  Keep it intentionally small: remove
        decorative glyphs/control characters and round noisy floats, but never
        alter the underlying exported DataFrame.
        """
        try:
            if value is None:
                return ''
            try:
                if pd.isna(value):
                    return ''
            except Exception:
                pass
            if isinstance(value, float):
                return f'{value:.4f}'.rstrip('0').rstrip('.')
            text = str(value)
            for bad in ('♪', '♫', '♬', '♩', '♭', '♯'):
                text = text.replace(bad, '')
            text = re.sub('[\\x00-\\x08\\x0b\\x0c\\x0e-\\x1f]', ' ', text)
            return text.strip()
        except Exception:
            return str(value) if value is not None else ''

    def _write_tree(self, tree: ttk.Treeview, df: pd.DataFrame, columns):
        """Write a DataFrame into a Treeview safely.

        This keeps the live Material Usage and Material Usage tab in sync without
        relying on any Tk root-level helper. Missing columns are rendered as blank
        cells, and previous rows are cleared before writing.
        """
        try:
            for item in tree.get_children():
                tree.delete(item)
            existing = list(tree['columns'])
            if list(existing) != list(columns):
                tree.configure(columns=list(columns))
                for col in columns:
                    tree.heading(col, text=col)
                    tree.column(col, width=130, minwidth=60, anchor='w', stretch=True)
            if df is None or df.empty:
                if tree in (getattr(self, 'live_usage_tree', None), getattr(self, 'material_tree', None)):
                    blank = {c: '' for c in columns}
                    if 'material' in blank:
                        blank['material'] = 'No material rows calculated yet'
                    if 'note' in blank:
                        blank['note'] = 'Click Generate / Update Plan; verify sequence, scale, resin, and coupling settings.'
                    tree.insert('', 'end', values=[blank.get(c, '') for c in columns])
                return
            for _, row in df.iterrows():
                vals = [self._sanitize_display_value(row.get(c, '')) for c in columns]
                tree.insert('', 'end', values=vals)
        except Exception as e:
            try:
                for item in tree.get_children():
                    tree.delete(item)
                blank = {c: '' for c in columns}
                if 'material' in blank:
                    blank['material'] = 'Material table render warning'
                if 'note' in blank:
                    blank['note'] = str(e)
                tree.insert('', 'end', values=[blank.get(c, '') for c in columns])
            except Exception:
                pass
            self._log(f'Tree render warning: {e}\n')

    def _write_df(self, widget: tk.Text, df: pd.DataFrame):
        if widget is None:
            return
        try:
            widget.delete('1.0', 'end')
            if df is None or df.empty:
                return
            widget.insert('1.0', df.to_csv(index=False, sep='\t'))
        except Exception:
            return

    def append_blank_row(self):
        no = len(self.tree.get_children()) + 1
        d = {c: '' for c in self.PLAN_COLUMNS}
        d['No'] = no
        d['Unit eq'] = self.coupling_eq.get()
        d['Repeat'] = 1
        d['Coupling reagent 1'] = self.default_reagent.get()
        d['Coupling reagent 1 eq'] = self.default_reagent_eq.get()
        d['Coupling reagent 1 count'] = self.default_reagent_count.get()
        d['Coupling reagent 2 / catalyst'] = self.default_catalyst.get()
        d['Coupling reagent 2 / catalyst eq'] = self.default_catalyst_eq.get()
        d['Coupling reagent 2 / catalyst count'] = self.default_catalyst_count.get()
        d['Coupling base'] = self.default_base.get()
        d['Coupling base eq'] = self.default_base_eq.get() if self.default_base.get() else ''
        d['Coupling base count'] = self.default_base_count.get() if self.default_base.get() else 0
        d['Coupling cocktail solvent'] = self.default_coupling_solution_solvent.get()
        d['Coupling cocktail volume(mL)'] = self._default_dissolve_volume('manual', 'manual')
        d['Deprotection base'] = self.default_depro.get()
        d['Deprotection ratio'] = self.default_depro_ratio.get()
        d['Deprotection count'] = self.default_depro_count.get()
        d['Solvent 1'] = self.default_solvent1.get()
        d['Solvent 1 count'] = self.default_solvent1_count.get()
        d['Solvent 2'] = self.default_solvent2.get()
        d['Solvent 2 count'] = self.default_solvent2_count.get()
        self._row_meta_by_no[str(no)] = {'MW': '', 'calculated mmol': '', 'calculated g': '', 'Phase': 'manual', 'Note': 'manual row'}
        self.tree.insert('', 'end', values=[d.get(c, '') for c in self.PLAN_COLUMNS])
        self.refresh_outputs_from_tree()

    def delete_selected(self):
        for item in self.tree.selection():
            self.tree.delete(item)
        for i, item in enumerate(self.tree.get_children(), start=1):
            vals = list(self.tree.item(item, 'values'))
            vals[0] = i
            self.tree.item(item, values=vals)
        self.refresh_outputs_from_tree()

    def loading_calculator_df(self) -> pd.DataFrame:
        """Resin loading calculator sheet.

        Required resin mass is calculated from target scale and resin loading.
        This sheet is designed to mirror the kind of loading calculation usually
        tracked in laboratory Excel workbooks while keeping the values editable
        after export.
        """
        scale = self._to_float(self.scale.get(), 0.0)
        loading = self._to_float(self.loading.get(), 0.0)
        resin_g = scale / loading if loading else 0.0
        loading_solvent = self._loading_dissolve_solvent_for_resin()
        loading_volume = self._working_volume_for_scale(scale)
        rows = [{'field': 'project_name', 'value': self.project_name.get(), 'unit': '', 'note': 'user-defined project/run name'}, {'field': 'lot_no', 'value': self.lot_no.get(), 'unit': '', 'note': 'auto-generated or manually edited lot number'}, {'field': 'sequence', 'value': self.seq.get(), 'unit': '', 'note': 'input peptide sequence'}, {'field': 'resin_type', 'value': self.resin.get(), 'unit': '', 'note': 'selected resin family'}, {'field': 'target_scale', 'value': round(scale, 4), 'unit': 'mmol', 'note': 'target synthesis scale'}, {'field': 'resin_loading', 'value': round(loading, 4), 'unit': 'mmol/g', 'note': 'resin substitution/loading'}, {'field': 'required_resin', 'value': round(resin_g, 4), 'unit': 'g', 'note': 'target_scale / resin_loading'}, {'field': 'swell_solvent', 'value': self._swell_solvent_for_resin(), 'unit': '', 'note': 'DCM for CTC/trityl; DMF for amide/Rink/Wang'}, {'field': 'loading_cocktail_solvent', 'value': loading_solvent, 'unit': '', 'note': 'default loading solution solvent'}, {'field': 'estimated_loading_solution_volume', 'value': round(loading_volume, 4), 'unit': 'mL', 'note': 'canonical Solvents / Wash volume basis'}]
        return pd.DataFrame(rows)

    def cleavage_calculator_df(self) -> pd.DataFrame:
        """Cleavage planning scaffold.

        This is intentionally editable after export. It uses the current Pepforge
        resin/scale defaults and the user's empirical rules can be adjusted in Excel.
        """
        scale = self._to_float(self.scale.get(), 0.0)
        seq = str(self.seq.get() or '')
        core = re.sub('[^A-Za-z]', '', seq.replace('Ac', '').replace('NH2', ''))
        length = len(core)
        cys_count = core.upper().count('C')
        base_tfa_eq = 30 if length <= 7 else 80 if length <= 15 else 100
        tfa_eq = base_tfa_eq + 100 * cys_count
        tfa_mmol_equiv = scale * tfa_eq
        tfa_mL = tfa_mmol_equiv * 114.02 / 1000.0 / self._density_for('TFA') if scale else 0
        rows = [{'component': 'TFA', 'ratio_percent': 'editable', 'equiv': tfa_eq, 'estimated_mL': round(tfa_mL, 4), 'note': 'base rule: short 30 eq, 15mer 80 eq, 22mer 100 eq, +100 eq per Cys; verify lab protocol'}, {'component': 'TIS', 'ratio_percent': 'editable', 'equiv': '', 'estimated_mL': '', 'note': 'scavenger; fill according to cleavage cocktail'}, {'component': 'Water', 'ratio_percent': 'editable', 'equiv': '', 'estimated_mL': '', 'note': 'scavenger; fill according to cleavage cocktail'}, {'component': 'EDT', 'ratio_percent': 'editable', 'equiv': '', 'estimated_mL': '', 'note': 'optional Cys scavenger; use only when protocol requires'}]
        return pd.DataFrame(rows)

    def manufacturing_transfer_df(self, materials: pd.DataFrame, plan: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame([{'project_name': self.project_name.get(), 'lot_no': self.lot_no.get(), 'sequence': self.seq.get(), 'resin': self.resin.get(), 'scale_mmol': self.scale.get(), 'resin_loading_mmol_g': self.loading.get(), 'current_status': '', 'completed_step': '', 'next_step': '', 'critical_note': '', 'operator': '', 'date': '', 'company_contact': '', 'handover_note': 'Use this sheet to communicate synthesis progress, material status, and next operation to an external company or collaborator.'}])

    def production_tracking_df(self, plan: pd.DataFrame) -> pd.DataFrame:
        rows = []
        for _, r in plan.iterrows():
            rows.append({'project_name': self.project_name.get(), 'lot_no': self.lot_no.get(), 'sequence': self.seq.get(), 'step': r.get('No', ''), 'unit': r.get('Unit name', ''), 'phase': self._row_meta_by_no.get(str(r.get('No', '')), {}).get('Phase', ''), 'status': 'Not started', 'date': '', 'operator': '', 'note': ''})
        return pd.DataFrame(rows)

    def short_step_checklist_df(self, plan: pd.DataFrame) -> pd.DataFrame:
        """Compact SPPS step view placed next to the checklist."""
        rows = []
        rows.append({'No': 'LOT', 'step': 'LOT No.', 'short_work': '', 'check': '', 'note': self.lot_no.get()})
        for _, r in plan.iterrows():
            no = r.get('No', '')
            unit = r.get('Unit name', '')
            meta = self._row_meta_by_no.get(str(no), {})
            dcount = self._to_int(r.get('Deprotection count'), 0)
            rep = self._to_int(r.get('Repeat'), 1)
            s1 = r.get('Solvent 1', '')
            c1 = self._to_int(r.get('Solvent 1 count'), 0)
            s2 = r.get('Solvent 2', '')
            c2 = self._to_int(r.get('Solvent 2 count'), 0)
            parts = []
            if dcount:
                parts.append(f'Depro x{dcount}')
            parts.append(f'Couple x{rep}')
            wash = []
            if s1 and c1:
                wash.append(f'{s1} x{c1}')
            if s2 and c2:
                wash.append(f'{s2} x{c2}')
            if wash:
                parts.append('Wash ' + ' / '.join(wash))
            rows.append({'No': no, 'step': unit, 'short_work': ' -> '.join(parts), 'check': 'No', 'note': meta.get('Phase', '')})
        return pd.DataFrame(rows)

    def bench_checklist_layout_df(self, plan: pd.DataFrame, materials: pd.DataFrame) -> pd.DataFrame:
        """Bench-sheet style checklist separated from material usage.

        The top section is a step/date/check grid. The lower sections are intended
        for AA usage and reagent/base/capping usage. It is exported to Excel as a
        standalone practical checklist sheet.
        """
        rows = []
        rows.append({'section': 'STEP_TRACKING', 'item': 'Project', 'value': self.project_name.get(), 'unit': '', 'date': '', 'check': '', 'note': ''})
        rows.append({'section': 'STEP_TRACKING', 'item': 'LOT No.', 'value': self.lot_no.get(), 'unit': '', 'date': '', 'check': '', 'note': ''})
        rows.append({'section': 'STEP_TRACKING', 'item': 'Sequence', 'value': self.seq.get(), 'unit': '', 'date': '', 'check': '', 'note': ''})
        for _, r in plan.iterrows():
            rows.append({'section': 'STEP_TRACKING', 'item': r.get('Unit name', ''), 'value': '', 'unit': '', 'date': '', 'check': 'No', 'note': self._row_meta_by_no.get(str(r.get('No', '')), {}).get('Phase', '')})
        aa = self.amino_acid_usage_summary(materials)
        for _, r in aa.iterrows():
            rows.append({'section': 'AA_USAGE', 'item': r.get('material', ''), 'value': r.get('calculated_g', ''), 'unit': 'g', 'date': '', 'check': '', 'note': f"mmol={r.get('planned_mmol', '')}; MW={r.get('MW', '')}"})
        reag = self.reagent_usage_summary(materials)
        for _, r in reag.iterrows():
            rows.append({'section': 'REAGENT_BASE_CAPPING', 'item': r.get('material', ''), 'value': r.get('planned_mL', '') if r.get('planned_mL', 0) else r.get('planned_g', ''), 'unit': 'mL/g', 'date': '', 'check': '', 'note': f"MW={r.get('MW', '')}; density={r.get('density_g_per_mL', '')}"})
        return pd.DataFrame(rows)

    def _safe_name(self, value: str) -> str:
        raw = str(value or '').strip() or 'Pepforge_Project'
        raw = re.sub('[<>:"/\\\\|?*]+', '_', raw)
        raw = re.sub('\\s+', ' ', raw).strip()
        return raw[:120] if len(raw) > 120 else raw

    def _project_export_dir(self) -> Path:
        base = Path(self.outdir.get())
        chosen = self.project_name.get().strip() or self.seq.get().strip() or 'Pepforge_Project'
        folder = self._safe_name(chosen) + '_' + datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        return base / folder

    def _column_width_file(self) -> Path:
        p = ROOT / 'outputs'
        p.mkdir(parents=True, exist_ok=True)
        return p / 'spps_column_widths.json'

    def _save_column_widths(self):
        try:
            data = {c: int(self.tree.column(c, 'width')) for c in self.tree['columns']}
            self._column_width_file().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception:
            pass

    def _load_column_widths(self):
        try:
            p = self._column_width_file()
            if p.exists():
                self.plan_width_map.update(json.loads(p.read_text(encoding='utf-8')))
        except Exception:
            pass

    def progress_df(self) -> pd.DataFrame:
        rows = []
        for iid in self.progress_tree.get_children():
            vals = list(self.progress_tree.item(iid, 'values'))
            cols = list(self.progress_tree['columns'])
            rows.append({c: vals[i] if i < len(vals) else '' for i, c in enumerate(cols)})
        return pd.DataFrame(rows)

    def _progress_key(self, row: dict) -> str:
        return f"{row.get('line', '')}|{row.get('operation', '')}|{row.get('unit', '')}"

    def _populate_progress_tree(self, checklist: pd.DataFrame):
        old = {}
        for iid in self.progress_tree.get_children():
            vals = list(self.progress_tree.item(iid, 'values'))
            if len(vals) >= 5:
                key = f'{vals[0]}|{vals[3]}|{vals[4]}'
                old[key] = vals
        self.progress_tree.delete(*self.progress_tree.get_children())
        if checklist is None or checklist.empty:
            return
        rows = []
        for i, r in checklist.iterrows():
            operation = r.get('Operation', '')
            unit = r.get('AA/Chemical/label/tag/linker', '')
            line = r.get('Line', i + 1)
            key = f'{line}|{operation}|{unit}'
            next_step = ''
            if i + 1 < len(checklist.index):
                nr = checklist.iloc[i + 1]
                next_step = f"{nr.get('Operation', '')} / {nr.get('AA/Chemical/label/tag/linker', '')}"
            if key in old:
                vals = old[key]
            else:
                vals = [line, 'No', '', operation, unit, next_step, r.get('Note', '')]
            self.progress_tree.insert('', 'end', values=vals)
        self._update_progress_widgets()

    def _update_progress_widgets(self):
        try:
            total = len(self.progress_tree.get_children())
            done = sum((1 for x in self.progress_tree.get_children() if list(self.progress_tree.item(x, 'values'))[1] == 'Yes'))
            pct = round(done / total * 100, 1) if total else 0.0
            if hasattr(self, 'checklist_progress_var'):
                self.checklist_progress_var.set(pct)
            if hasattr(self, 'checklist_progress_label'):
                self.checklist_progress_label.configure(text=f'Progress: {done}/{total} ({pct}%)')
        except Exception:
            pass

    def toggle_progress_row(self, event=None):
        item = self.progress_tree.focus() or (self.progress_tree.selection()[0] if self.progress_tree.selection() else '')
        if not item:
            return
        vals = list(self.progress_tree.item(item, 'values'))
        if len(vals) < 7:
            return
        if vals[1] == 'Yes':
            vals[1] = 'No'
            vals[2] = ''
        else:
            vals[1] = 'Yes'
            vals[2] = datetime.now().strftime('%Y-%m-%d %H:%M')
        self.progress_tree.item(item, values=vals)
        self._update_progress_widgets()
        self._write_df(self.next_text, self.next_step_df())

    def _set_progress_item_done(self, item, done: bool):
        vals = list(self.progress_tree.item(item, 'values'))
        if len(vals) < 7:
            return
        if done:
            vals[1] = 'Yes'
            if not vals[2]:
                vals[2] = datetime.now().strftime('%Y-%m-%d %H:%M')
        else:
            vals[1] = 'No'
            vals[2] = ''
        self.progress_tree.item(item, values=vals)

    def select_all_progress_rows(self):
        for item in self.progress_tree.get_children():
            self._set_progress_item_done(item, True)
        self._update_progress_widgets()
        self._write_df(self.next_text, self.next_step_df())

    def clear_all_progress_rows(self):
        for item in self.progress_tree.get_children():
            self._set_progress_item_done(item, False)
        self._update_progress_widgets()
        self._write_df(self.next_text, self.next_step_df())

    def selected_progress_rows_yes(self):
        selected = self.progress_tree.selection()
        if not selected:
            focused = self.progress_tree.focus()
            selected = (focused,) if focused else ()
        for item in selected:
            self._set_progress_item_done(item, True)
        self._update_progress_widgets()
        self._write_df(self.next_text, self.next_step_df())

    def mark_until_selected_progress_row(self):
        children = list(self.progress_tree.get_children())
        if not children:
            return
        target = self.progress_tree.focus() or (self.progress_tree.selection()[0] if self.progress_tree.selection() else '')
        if not target or target not in children:
            target = children[-1]
        end = children.index(target)
        for item in children[:end + 1]:
            self._set_progress_item_done(item, True)
        self._update_progress_widgets()
        self._write_df(self.next_text, self.next_step_df())

    def next_step_df(self) -> pd.DataFrame:
        for iid in self.progress_tree.get_children():
            vals = list(self.progress_tree.item(iid, 'values'))
            if len(vals) >= 7 and vals[1] != 'Yes':
                total = len(self.progress_tree.get_children())
                done = sum((1 for x in self.progress_tree.get_children() if list(self.progress_tree.item(x, 'values'))[1] == 'Yes'))
                return pd.DataFrame([{'progress': f'{done}/{total}', 'percent': round(done / total * 100, 1) if total else 0, 'next_line': vals[0], 'next_operation': vals[3], 'next_unit': vals[4], 'next_step_after_that': vals[5], 'note': vals[6]}])
        total = len(self.progress_tree.get_children())
        return pd.DataFrame([{'progress': f'{total}/{total}', 'percent': 100 if total else 0, 'next_line': '', 'next_operation': 'Complete', 'next_unit': '', 'next_step_after_that': '', 'note': 'All checklist rows are checked.'}])

    def save_project_state(self, path: Path):
        data = {'project_name': self.project_name.get(), 'lot_no': self.lot_no.get(), 'sequence': self.seq.get(), 'resin': self.resin.get(), 'scale_mmol': self.scale.get(), 'loading_mmol_g': self.loading.get(), 'outdir': self.outdir.get(), 'plan_rows': self.tree_rows(), 'row_meta': self._row_meta_by_no, 'progress_rows': self.progress_df().to_dict('records'), 'saved_at': datetime.now().isoformat(timespec='seconds')}
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

    def load_project(self):
        p = filedialog.askopenfilename(filetypes=[('Pepforge project state', 'project_state.json *.json'), ('All files', '*.*')])
        if not p:
            return
        try:
            data = json.loads(Path(p).read_text(encoding='utf-8'))
            self.project_name.set(data.get('project_name', ''))
            self.lot_no.set(data.get('lot_no', self.lot_no.get()))
            self.seq.set(data.get('sequence', self.seq.get()))
            self.resin.set(data.get('resin', self.resin.get()))
            self.scale.set(float(data.get('scale_mmol', self.scale.get())))
            self.loading.set(float(data.get('loading_mmol_g', self.loading.get())))
            self.outdir.set(data.get('outdir', self.outdir.get()))
            self.tree.delete(*self.tree.get_children())
            self._row_meta_by_no = data.get('row_meta', {})
            for row in data.get('plan_rows', []):
                self.tree.insert('', 'end', values=[row.get(c, '') for c in self.PLAN_COLUMNS])
            self.refresh_outputs_from_tree()
            progress_rows = data.get('progress_rows', [])
            if progress_rows:
                by_key = {f"{r.get('line', '')}|{r.get('operation', '')}|{r.get('unit', '')}": r for r in progress_rows}
                for iid in self.progress_tree.get_children():
                    vals = list(self.progress_tree.item(iid, 'values'))
                    key = f'{vals[0]}|{vals[3]}|{vals[4]}'
                    r = by_key.get(key)
                    if r:
                        vals[1] = r.get('done', vals[1])
                        vals[2] = r.get('checked_at', vals[2])
                        self.progress_tree.item(iid, values=vals)
            self._write_df(self.next_text, self.next_step_df())
            self._log(f'Loaded project state: {p}\n')
        except Exception as e:
            messagebox.showerror('Load error', str(e))

    def load_output_folder(self):
        folder = filedialog.askdirectory(title='Select a Pepforge SPPS output folder')
        if not folder:
            return
        try:
            base = Path(folder)
            plan_path = base / 'editable_spps_plan.csv'
            xlsx_path = base / 'spps_plan.xlsx'
            if plan_path.exists():
                plan = pd.read_csv(plan_path)
            elif xlsx_path.exists():
                plan = pd.read_excel(xlsx_path, sheet_name='00_EDITABLE_PLAN')
            else:
                raise FileNotFoundError('No editable_spps_plan.csv or spps_plan.xlsx found in selected folder.')
            self.tree.delete(*self.tree.get_children())
            self._row_meta_by_no = {}
            for _, row in plan.iterrows():
                d = {c: row.get(c, '') for c in self.PLAN_COLUMNS}
                no = str(d.get('No', len(self.tree.get_children()) + 1))
                self._row_meta_by_no[no] = {'Phase': row.get('Phase', 'loaded output'), 'Note': row.get('Note', 'loaded from output folder')}
                self.tree.insert('', 'end', values=[d.get(c, '') for c in self.PLAN_COLUMNS])
            state_path = base / 'project_state.json'
            if state_path.exists():
                try:
                    data = json.loads(state_path.read_text(encoding='utf-8'))
                    self.project_name.set(data.get('project_name', self.project_name.get()))
                    self.seq.set(data.get('sequence', self.seq.get()))
                    self.resin.set(data.get('resin', self.resin.get()))
                    self.scale.set(float(data.get('scale_mmol', self.scale.get())))
                    self.loading.set(float(data.get('loading_mmol_g', self.loading.get())))
                except Exception:
                    pass
            self.last_outdir = base
            self.outdir.set(str(base.parent))
            self.refresh_outputs_from_tree()
            self._log(f'Loaded output folder: {base}\n')
        except Exception as e:
            messagebox.showerror('Load output error', str(e))

    def export_outputs(self):
        try:
            outdir = self._project_export_dir()
            outdir.mkdir(parents=True, exist_ok=True)
            plan = pd.DataFrame(self.tree_rows())
            materials = self.materials_from_rows(plan)
            ml = self.ml_log_from_rows(plan)
            ops = self.operation_form_from_rows(plan)
            checklist = self.checklist_from_rows(plan)
            loading_df = self.loading_calculator_df()
            cleavage_df = self.cleavage_calculator_df()
            transfer_df = self.manufacturing_transfer_df(materials, plan)
            production_df = self.production_tracking_df(plan)
            bench_df = self.bench_checklist_layout_df(plan, materials)
            progress_df = self.progress_df()
            next_df = self.next_step_df()
            self.save_project_state(outdir / 'project_state.json')
            plan.to_csv(outdir / 'editable_spps_plan.csv', index=False, encoding='utf-8-sig')
            materials.to_csv(outdir / 'material_usage_from_editable_plan.csv', index=False, encoding='utf-8-sig')
            ops.to_csv(outdir / 'operation_form_from_editable_plan.csv', index=False, encoding='utf-8-sig')
            checklist.to_csv(outdir / 'printable_synthesis_checklist.csv', index=False, encoding='utf-8-sig')
            ml.to_csv(outdir / 'spps_ml_ready_log_from_editable_plan.csv', index=False, encoding='utf-8-sig')
            progress_df.to_csv(outdir / 'checklist_progress.csv', index=False, encoding='utf-8-sig')
            next_df.to_csv(outdir / 'next_step.csv', index=False, encoding='utf-8-sig')
            self.amino_acid_usage_summary(materials).to_csv(outdir / 'total_amino_acid_usage.csv', index=False, encoding='utf-8-sig')
            self.reagent_usage_summary(materials).to_csv(outdir / 'total_reagent_base_usage.csv', index=False, encoding='utf-8-sig')
            self.solvent_usage_summary(materials).to_csv(outdir / 'total_solvent_usage.csv', index=False, encoding='utf-8-sig')
            if export_csvs is not None:
                try:
                    export_csvs(self._input(), outdir)
                except Exception as e:
                    self._log(f'Classic export warning: {e}\n')
            xlsx = outdir / 'spps_plan.xlsx'
            with pd.ExcelWriter(xlsx, engine='openpyxl') as writer:
                plan.to_excel(writer, index=False, sheet_name='00_EDITABLE_PLAN')
                materials.to_excel(writer, index=False, sheet_name='01_MATERIAL_USAGE')
                checklist.to_excel(writer, index=False, sheet_name='02_PRINT_CHECKLIST')
                ops.to_excel(writer, index=False, sheet_name='03_OPERATION_FORM')
                ml.to_excel(writer, index=False, sheet_name='04_ML_READY_LOG')
                loading_df.to_excel(writer, index=False, sheet_name='06_LOADING_CALC')
                cleavage_df.to_excel(writer, index=False, sheet_name='07_CLEAVAGE_CALC')
                transfer_df.to_excel(writer, index=False, sheet_name='08_TRANSFER_SHEET')
                production_df.to_excel(writer, index=False, sheet_name='09_PRODUCTION_TRACKING')
                bench_df.to_excel(writer, index=False, sheet_name='10_BENCH_CHECKLIST')
                progress_df.to_excel(writer, index=False, sheet_name='11_CHECKLIST_PROGRESS')
                next_df.to_excel(writer, index=False, sheet_name='12_NEXT_STEP')
                try:
                    pd.DataFrame([plan_summary(self._input())]).to_excel(writer, index=False, sheet_name='05_SUMMARY')
                except Exception:
                    pass
            with pd.ExcelWriter(outdir / 'bench_checklist.xlsx', engine='openpyxl') as cw:
                progress_df.to_excel(cw, index=False, sheet_name='CHECKLIST_PROGRESS')
                bench_df.to_excel(cw, index=False, sheet_name='BENCH_SHEET')
                self.amino_acid_usage_summary(materials).to_excel(cw, index=False, sheet_name='AA_USAGE')
                self.reagent_usage_summary(materials).to_excel(cw, index=False, sheet_name='REAGENT_BASE')
                self.solvent_usage_summary(materials).to_excel(cw, index=False, sheet_name='SOLVENT_TOTAL')
            (outdir / 'OUTPUT_MANIFEST.txt').write_text('Pepforge SPPS output folder\n' + 'Created: ' + datetime.now().isoformat(timespec='seconds') + '\n' + 'Open this folder from SPPS Planner with Load Output or Open Output.\n', encoding='utf-8')
            self.last_outdir = outdir
            self._log(f'Exported: {outdir}\n')
            messagebox.showinfo('Export complete', f'CSV/XLSX exported to:\n{outdir}')
        except Exception as e:
            messagebox.showerror('Export error', str(e))
            self._log('ERROR export: ' + str(e) + '\n')

    def browse_outdir(self):
        p = filedialog.askdirectory()
        if p:
            self.outdir.set(p)

    def open_output(self):
        p = self.last_outdir or Path(self.outdir.get())
        if p.exists():
            open_path(p)
        else:
            messagebox.showinfo('Not found', str(p))

    def _log(self, msg):
        self.log_text.insert('end', msg)
        self.log_text.see('end')

def _v23_roundup_ml(self, calc_ml: float) -> float:
    try:
        calc_ml = float(calc_ml or 0)
    except Exception:
        calc_ml = 0.0
    if calc_ml <= 0:
        return 0.0
    try:
        step = max(float(self.batch_actual_round_ml.get()), 1.0)
    except Exception:
        step = 10.0
    try:
        extra = max(float(self.batch_actual_extra_ml.get()), 0.0)
    except Exception:
        extra = 10.0
    import math
    return math.ceil(calc_ml / step) * step + extra

def _v23_project_rows(self):
    rows = []
    for item in list(getattr(self, 'pm_items', [])):
        seq = str(item.get('sequence', '') or '').strip()
        if not seq:
            continue
        rows.append({'Project': item.get('project', ''), 'Peptide name': item.get('peptide', ''), 'Sequence': seq, 'Copies': item.get('copies', '1') or '1', 'Scale mmol': item.get('scale', '0.2') or '0.2', 'Resin': item.get('resin', ''), 'Loading': item.get('loading', ''), 'LOT No': item.get('lot', ''), 'Chemistry': item.get('chemistry', 'DIC/HOBt') or 'DIC/HOBt'})
    return rows

def _v23_aa_calculator_df(self, rows=None):
    rows = rows if rows is not None else self._v23_project_rows()
    try:
        conc = float(self.batch_solution_conc.get())
    except Exception:
        conc = 0.25
    try:
        aa_eq = float(self.batch_coupling_eq.get())
    except Exception:
        aa_eq = 10.0
    totals = {}
    for r in rows:
        try:
            copies = max(int(float(r.get('Copies', 1) or 1)), 1)
        except Exception:
            copies = 1
        try:
            scale = float(r.get('Scale mmol', 0.2) or 0.2)
        except Exception:
            scale = 0.2
        for aa in self._aa_letters_from_sequence(r.get('Sequence', '')):
            totals.setdefault(aa, {'count': 0, 'mmol': 0.0})
            totals[aa]['count'] += copies
            totals[aa]['mmol'] += copies * scale * aa_eq
    out = []
    for aa in sorted(totals):
        count = totals[aa]['count']
        mmol = totals[aa]['mmol']
        calc_ml = mmol / conc if conc else 0.0
        actual_ml = self._v23_roundup_ml(calc_ml)
        mw = self._mw_for_token(aa) or self.MW_FALLBACK.get(aa, 0.0)
        weight_g = actual_ml / 1000.0 * conc * mw if actual_ml and conc and mw else 0.0
        out.append({'AA': aa, 'count': count, 'eq': aa_eq, 'solvent': 'DMF', 'conc_M': conc, 'calculated_mL': round(calc_ml, 2), 'actual_mL': round(actual_ml, 2), 'MW': round(mw, 2) if mw else 'manual', 'weight_g': round(weight_g, 2), 'note': 'synthesizer AA stock; actual includes transfer/dead-volume reserve'})
    return pd.DataFrame(out, columns=['AA', 'count', 'eq', 'solvent', 'conc_M', 'calculated_mL', 'actual_mL', 'MW', 'weight_g', 'note'])

def _v23_add_solution_record(self, d, item, purpose, count, eq, solvent, conc, mmol, note=''):
    item = str(item or '').strip()
    if not item:
        return
    key = (item, purpose, solvent, str(eq), str(conc))
    rec = d.setdefault(key, {'item': item, 'purpose': purpose, 'count': 0.0, 'eq': eq, 'solvent': solvent, 'conc_M': conc, 'mmol': 0.0, 'note': note})
    rec['count'] += float(count or 0)
    rec['mmol'] += float(mmol or 0)

def _v23_solution_records_to_df(self, d):
    out = []
    for rec in d.values():
        item = rec['item']
        conc = float(rec.get('conc_M') or 0) if str(rec.get('conc_M', '')).strip() else 0.0
        mmol = float(rec.get('mmol') or 0)
        mw = self._mw_for_token(item) or self.MW_FALLBACK.get(item, 0.0)
        density = self._density_for_token(item)
        calc_ml = mmol / conc if conc else 0.0
        actual_ml = self._v23_roundup_ml(calc_ml) if calc_ml else 0.0
        if not conc:
            calc_g = mmol * mw / 1000.0 if mw else 0.0
            actual_g = round(calc_g * 1.1 + 0.004, 2) if calc_g else 0.0
            volume_ml = actual_g / density if density else ''
            out.append({'item': item, 'purpose': rec['purpose'], 'count': int(rec['count']) if float(rec['count']).is_integer() else round(rec['count'], 2), 'eq': rec['eq'], 'solvent': rec.get('solvent', ''), 'conc_M': '', 'calculated': '', 'actual': '', 'unit': 'g' if not density else 'g/mL', 'MW': round(mw, 2) if mw else 'manual', 'density': round(density, 3) if density else '', 'weight_g': actual_g if actual_g else '', 'volume_mL': round(volume_ml, 2) if isinstance(volume_ml, float) else volume_ml, 'note': rec.get('note', '')})
        else:
            weight_g = actual_ml / 1000.0 * conc * mw if actual_ml and mw else 0.0
            out.append({'item': item, 'purpose': rec['purpose'], 'count': int(rec['count']) if float(rec['count']).is_integer() else round(rec['count'], 2), 'eq': rec['eq'], 'solvent': rec.get('solvent', ''), 'conc_M': conc, 'calculated': round(calc_ml, 2), 'actual': round(actual_ml, 2), 'unit': 'mL', 'MW': round(mw, 2) if mw else 'manual', 'density': round(density, 3) if density else '', 'weight_g': round(weight_g, 2) if weight_g else '', 'volume_mL': round(actual_ml, 2), 'note': rec.get('note', '')})
    cols = ['item', 'purpose', 'count', 'eq', 'solvent', 'conc_M', 'calculated', 'actual', 'unit', 'MW', 'density', 'weight_g', 'volume_mL', 'note']
    return pd.DataFrame(out, columns=cols)

def _v23_batch_totals(self, rows=None):
    rows = rows if rows is not None else self._v23_project_rows()
    coupling = {}
    catalyst = {}
    solvent = {}
    modifier = {}
    try:
        aa_eq = float(self.batch_coupling_eq.get())
    except Exception:
        aa_eq = 10.0
    try:
        hbtu_eq = float(self.batch_hbtu_eq.get())
    except Exception:
        hbtu_eq = 10.0
    try:
        hbtu_conc = float(self.batch_hbtu_conc.get())
    except Exception:
        hbtu_conc = 0.4
    for r in rows:
        try:
            copies = max(int(float(r.get('Copies', 1) or 1)), 1)
        except Exception:
            copies = 1
        try:
            scale = float(r.get('Scale mmol', 0.2) or 0.2)
        except Exception:
            scale = 0.2
        aas = self._aa_letters_from_sequence(r.get('Sequence', ''))
        steps = len(aas) * copies
        chem = str(r.get('Chemistry', 'DIC/HOBt') or 'DIC/HOBt')
        step_mmol = steps * scale
        if steps:
            if 'HBTU/NMP' in chem:
                self._v23_add_solution_record(coupling, 'HBTU', 'coupling reagent stock', steps, hbtu_eq, 'NMP', hbtu_conc, step_mmol * hbtu_eq, 'prepare HBTU/NMP stock for synthesizer bottle')
                calc_ml = step_mmol * hbtu_eq / hbtu_conc if hbtu_conc else 0.0
                self._v23_add_solution_record(solvent, 'NMP', 'HBTU stock solvent', steps, '', '', 0, calc_ml, 'mL of NMP needed before reserve shown as volume')
            else:
                self._v23_add_solution_record(coupling, 'DIC', 'coupling reagent', steps, 5.0, 'neat/DMF', 0, step_mmol * 5.0, 'DIC amount for synthesizer coupling preparation')
                add = 'Oxyma' if 'Oxyma' in chem else 'HOBt'
                self._v23_add_solution_record(catalyst, add, 'catalyst/additive', steps, 5.0, 'DMF', 0, step_mmol * 5.0, 'solid catalyst/additive for coupling bottle')
                self._v23_add_solution_record(solvent, 'DMF', 'coupling solvent reservoir', steps, '', '', 0, step_mmol * 10.0, 'DMF used for coupling/cocktail transfer; practical reserve applied')
            self._v23_add_solution_record(solvent, 'DMF', 'AA stock solvent', steps, '', '', 0, 0, 'AA stock solvent volume is listed in AA table')
            self._v23_add_solution_record(solvent, 'DMF', 'wash/deprotection reservoir', steps, '', '', 0, step_mmol * 8.0 * 10.0, 'DMF wash/deprotection reservoir estimate')
            self._v23_add_solution_record(solvent, 'DCM', 'final wash reservoir', steps, '', '', 0, copies * scale * 3.0 * 10.0, 'DCM final wash reservoir estimate')
        seq = str(r.get('Sequence', '') or '')
        if self._sequence_has_nterm_ac(seq):
            self._v23_add_solution_record(modifier, 'Acetic anhydride (Ac2O)', 'N-terminal Ac cap', copies, 3.0, 'neat/DMF', 0, copies * scale * 3.0, 'Ac detected from sequence prefix Ac-')
    return {'coupling': self._v23_solution_records_to_df(coupling), 'catalyst': self._v23_solution_records_to_df(catalyst), 'solvent': self._v23_solution_records_to_df(solvent), 'modifier': self._v23_solution_records_to_df(modifier)}

def _v23_project_summary_df(self, rows=None):
    rows = rows if rows is not None else self._v23_project_rows()
    out = []
    for i, r in enumerate(rows, 1):
        out.append({'no': i, 'project': r.get('Project', ''), 'peptide_name': r.get('Peptide name', ''), 'lot_no': r.get('LOT No', ''), 'sequence': r.get('Sequence', ''), 'copies': r.get('Copies', ''), 'scale_mmol': r.get('Scale mmol', ''), 'resin': r.get('Resin', ''), 'chemistry': r.get('Chemistry', '')})
    return pd.DataFrame(out)

def _v23_build_batch_tab(self):
    fr = ttk.Frame(self.tabs)
    self.tabs.add(fr, text='Batch Manager')
    fr.rowconfigure(2, weight=1)
    fr.columnconfigure(0, weight=1)
    top = ttk.Frame(fr, padding=(4, 3))
    top.grid(row=0, column=0, sticky='ew')
    ttk.Label(top, text='Synthesizer stock/cocktail calculator: automatically uses Project Manager peptide items.').pack(side='left', padx=(2, 12))
    ttk.Button(top, text='Refresh totals', command=self.refresh_batch_workspace_preview).pack(side='left', padx=3)
    ttk.Button(top, text='Export batch calculator', command=self._v23_export_batch_calculator).pack(side='left', padx=3)
    ttk.Button(top, text='Save Session Now', command=self.save_autosave_state).pack(side='left', padx=3)
    defaults = ttk.Labelframe(fr, text='Solution prep defaults', padding=5)
    defaults.grid(row=1, column=0, sticky='ew', padx=4, pady=3)
    self.batch_solution_conc = tk.StringVar(value='0.25')
    self.batch_coupling_eq = tk.StringVar(value='10')
    self.batch_actual_round_ml = tk.StringVar(value='10')
    self.batch_actual_extra_ml = tk.StringVar(value='10')
    self.batch_hbtu_eq = tk.StringVar(value='10')
    self.batch_hbtu_conc = tk.StringVar(value='0.4')
    self.batch_default_scale = tk.StringVar(value='0.2')
    self.batch_default_resin = tk.StringVar(value='Rink Amide AM')
    self.batch_default_loading = tk.StringVar(value='0.8')
    self.batch_hbtu_mw = tk.StringVar(value='379.25')
    self.batch_nmp_density = tk.StringVar(value='1.03')
    fields = [('AA conc M', self.batch_solution_conc), ('AA eq', self.batch_coupling_eq), ('Round-up mL', self.batch_actual_round_ml), ('Extra reserve mL', self.batch_actual_extra_ml), ('HBTU eq', self.batch_hbtu_eq), ('HBTU conc M', self.batch_hbtu_conc)]
    for i, (lab, var) in enumerate(fields):
        ttk.Label(defaults, text=lab).grid(row=0, column=i * 2, sticky='w', padx=(2, 3))
        ttk.Entry(defaults, textvariable=var, width=10).grid(row=0, column=i * 2 + 1, sticky='ew', padx=(0, 8))
        try:
            var.trace_add('write', lambda *_: self.after_idle(self.refresh_batch_workspace_preview))
        except Exception:
            pass
    nb = ttk.Notebook(fr)
    nb.grid(row=2, column=0, sticky='nsew', padx=4, pady=4)

    def tab(title, cols):
        frame = ttk.Frame(nb)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        nb.add(frame, text=title)
        return self._tree_in_frame(frame, cols)
    self.batch_aa_tree = tab('AA stock solutions', ['AA', 'count', 'eq', 'solvent', 'conc_M', 'calculated_mL', 'actual_mL', 'MW', 'weight_g', 'note'])
    common = ['item', 'purpose', 'count', 'eq', 'solvent', 'conc_M', 'calculated', 'actual', 'unit', 'MW', 'density', 'weight_g', 'volume_mL', 'note']
    self.batch_coupling_reagent_tree = tab('Coupling reagents', common)
    self.batch_catalyst_tree = tab('Catalyst / additive', common)
    self.batch_solvent_tree = tab('Solvents / reservoirs', common)
    self.batch_modifier_tree = tab('Chemicals / caps', common)
    self.batch_project_tree = tab('Project summary', ['no', 'project', 'peptide_name', 'lot_no', 'sequence', 'copies', 'scale_mmol', 'resin', 'chemistry'])
    self.batch_material_tree = self.batch_aa_tree
    self.batch_hbtu_tree = self.batch_coupling_reagent_tree
    self.batch_cap_tree = self.batch_modifier_tree
    self.refresh_batch_workspace_preview()

def _v23_refresh_batch_workspace_preview(self):
    try:
        rows = self._v23_project_rows()
        aa_df = self._v23_aa_calculator_df(rows)
        totals = self._v23_batch_totals(rows)
        self._write_tree(self.batch_aa_tree, aa_df, ['AA', 'count', 'eq', 'solvent', 'conc_M', 'calculated_mL', 'actual_mL', 'MW', 'weight_g', 'note'])
        cols = ['item', 'purpose', 'count', 'eq', 'solvent', 'conc_M', 'calculated', 'actual', 'unit', 'MW', 'density', 'weight_g', 'volume_mL', 'note']
        self._write_tree(self.batch_coupling_reagent_tree, totals['coupling'], cols)
        self._write_tree(self.batch_catalyst_tree, totals['catalyst'], cols)
        self._write_tree(self.batch_solvent_tree, totals['solvent'], cols)
        self._write_tree(self.batch_modifier_tree, totals['modifier'], cols)
        self._write_tree(self.batch_project_tree, self._v23_project_summary_df(rows), ['no', 'project', 'peptide_name', 'lot_no', 'sequence', 'copies', 'scale_mmol', 'resin', 'chemistry'])
    except Exception as e:
        print('Batch refresh warning:', e)

def _v23_export_batch_calculator(self):
    path = filedialog.asksaveasfilename(defaultextension='.xlsx', filetypes=[('Excel', '*.xlsx')])
    if not path:
        return
    rows = self._v23_project_rows()
    totals = self._v23_batch_totals(rows)
    with pd.ExcelWriter(path, engine='openpyxl') as writer:
        self._v23_project_summary_df(rows).to_excel(writer, index=False, sheet_name='00_PROJECT_SUMMARY')
        self._v23_aa_calculator_df(rows).to_excel(writer, index=False, sheet_name='01_AA_STOCK')
        totals['coupling'].to_excel(writer, index=False, sheet_name='02_COUPLING')
        totals['catalyst'].to_excel(writer, index=False, sheet_name='03_CATALYST')
        totals['solvent'].to_excel(writer, index=False, sheet_name='04_SOLVENTS')
        totals['modifier'].to_excel(writer, index=False, sheet_name='05_CHEMICALS')
    messagebox.showinfo('Export complete', f'Batch calculator saved:\n{path}')

def _v23_pm_live_sync_selected(self):
    if getattr(self, '_pm_loading_editor', False):
        return
    idx = self.pm_current_index() if hasattr(self, 'pm_list') else None
    if idx is None or idx < 0 or idx >= len(getattr(self, 'pm_items', [])):
        return
    try:
        self.pm_items[idx].update({'project': self.pm_project.get().strip(), 'peptide': self.pm_peptide.get().strip(), 'sequence': self.pm_sequence.get().strip(), 'scale': self.pm_scale.get().strip(), 'resin': self.pm_resin.get().strip(), 'loading': self.pm_loading.get().strip(), 'lot': self.pm_lot.get().strip(), 'chemistry': self.pm_chemistry.get().strip(), 'copies': self.pm_copies.get().strip(), 'status': self.pm_items[idx].get('status', 'Ready')})
        self.pm_refresh_list(keep_index=idx, reload_editor=False)
        self.pm_update_summary()
        if hasattr(self, 'batch_aa_tree'):
            self.refresh_batch_workspace_preview()
        self.schedule_autosave()
    except Exception:
        pass

def _v23_log(self, msg):
    try:
        if hasattr(self, 'log_text'):
            self.log_text.insert('end', msg)
            self.log_text.see('end')
        else:
            print(str(msg), end='')
    except Exception:
        pass

def _v25_is_blank(value):
    try:
        if value is None:
            return True
        try:
            if pd.isna(value):
                return True
        except Exception:
            pass
        return str(value).strip() == ''
    except Exception:
        return False

def _v25_to_float(value):
    try:
        if _v25_is_blank(value):
            return None
        if isinstance(value, str):
            cleaned = value.replace(',', '').replace('mL', '').replace('g', '').strip()
            if cleaned.lower() in {'manual', 'nan', 'none'}:
                return None
            return float(cleaned)
        return float(value)
    except Exception:
        return None

def _v25_format_display_value(self, value, column=''):
    try:
        if _v25_is_blank(value):
            return ''
        col = str(column or '').lower()
        text_value = str(value).strip()
        if text_value.lower() in {'manual', 'manual required', 'n/a'}:
            return text_value
        number = _v25_to_float(value)
        if number is None:
            text = text_value
            for bad in ('♪', '♫', '♬', '♩', '♭', '♯'):
                text = text.replace(bad, '')
            text = re.sub('[\\x00-\\x08\\x0b\\x0c\\x0e-\\x1f]', ' ', text)
            return text.strip()
        if col in {'no', 'line', 'step', 'count', 'copies', 'use_count', 'repeat'}:
            return str(int(round(number))) if abs(number - round(number)) < 1e-09 else f'{number:.2f}'
        volume_markers = ['ml', 'volume', 'actual', 'calculated', 'planned_ml', 'calc_ml', 'reservoir']
        unit_markers = ['unit volume']
        if any((m in col for m in volume_markers + unit_markers)):
            if 'g' not in col and 'weight' not in col:
                return f'{number:.1f}'
        return f'{number:.2f}'
    except Exception:
        return str(value) if value is not None else ''

def _v25_write_tree(self, tree: ttk.Treeview, df: pd.DataFrame, columns):
    try:
        for item in tree.get_children():
            tree.delete(item)
        existing = list(tree['columns'])
        if list(existing) != list(columns):
            tree.configure(columns=list(columns))
            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=130, minwidth=60, anchor='w', stretch=True)
        if df is None or df.empty:
            if tree in (getattr(self, 'live_usage_tree', None), getattr(self, 'material_tree', None)):
                blank = {c: '' for c in columns}
                if 'material' in blank:
                    blank['material'] = 'No material rows calculated yet'
                if 'note' in blank:
                    blank['note'] = 'Click Generate / Update Plan; verify sequence, scale, resin, and coupling settings.'
                tree.insert('', 'end', values=[blank.get(c, '') for c in columns])
            return
        for _, row in df.iterrows():
            vals = [_v25_format_display_value(self, row.get(c, ''), c) for c in columns]
            tree.insert('', 'end', values=vals)
    except Exception as e:
        try:
            for item in tree.get_children():
                tree.delete(item)
            blank = {c: '' for c in columns}
            if 'material' in blank:
                blank['material'] = 'Material table render warning'
            if 'note' in blank:
                blank['note'] = str(e)
            tree.insert('', 'end', values=[blank.get(c, '') for c in columns])
        except Exception:
            pass

def _v26_pm_items_to_batch_rows(self):
    rows = []
    for item in list(getattr(self, 'pm_items', []) or []):
        seq = str(item.get('sequence', '') or '').strip()
        pep = str(item.get('peptide', '') or '').strip()
        if not seq and (not pep):
            continue
        rows.append({'Project': item.get('project', ''), 'Peptide name': item.get('peptide', ''), 'Form': item.get('form', 'linear'), 'Copies': item.get('copies', '1'), 'N-term': 'Ac' if self._sequence_has_nterm_ac(seq) else item.get('n_term', ''), 'Region 1 seq': seq, 'Region 1 eq': '1', 'Linker': item.get('linker', ''), 'Region 2 seq': item.get('region2_seq', ''), 'Region 2 eq': item.get('region2_eq', ''), 'Tag': item.get('tag', ''), 'Label': item.get('label', ''), 'C-term': item.get('c_term', 'NH2'), 'D/non-natural notes': item.get('notes', ''), 'Chemistry': item.get('chemistry', 'DIC/HOBt'), 'Scale mmol': item.get('scale', getattr(self, 'batch_default_scale', _v225_const_var('0.2')).get()), 'AA conc M': getattr(self, 'batch_solution_conc', _v225_const_var('0.25')).get(), 'AA coupling eq': getattr(self, 'batch_coupling_eq', _v225_const_var('10')).get(), 'Resin': item.get('resin', getattr(self, 'batch_default_resin', _v225_const_var('Rink Amide AM')).get()), 'Loading': item.get('loading', getattr(self, 'batch_default_loading', _v225_const_var('0.8')).get()), 'LOT No': item.get('lot', ''), 'Status': item.get('status', 'Ready')})
    return rows

def _v26_batch_rows_from_tree(self):
    pm_rows = _v26_pm_items_to_batch_rows(self)
    if pm_rows:
        return pm_rows
    rows = []
    if not hasattr(self, 'batch_tree'):
        return rows
    for item in self.batch_tree.get_children():
        vals = list(self.batch_tree.item(item, 'values'))
        vals += [''] * (len(self.batch_columns) - len(vals))
        d = dict(zip(self.batch_columns, vals))
        if not str(d.get('Region 1 seq', '')).strip() and (not str(d.get('Peptide name', '')).strip()):
            continue
        rows.append(d)
    return rows

def _v26_pm_generate_selected(self):
    try:
        self.pm_save_selected()
        idx = self.pm_current_index()
        if idx is None:
            return
        item = self.pm_items[idx]
        self.pm_apply_item_to_single_plan(item)
        self.generate_update_plan()
        item['status'] = 'Calculated'
        self._write_tree(self.pm_selected_plan_tree, self.pm_tree_to_df(self.tree), list(self.pm_selected_plan_tree['columns']))
        self._write_tree(self.pm_selected_material_tree, self.pm_tree_to_df(self.live_usage_tree), list(self.pm_selected_material_tree['columns']))
        try:
            self.pm_selected_check_text.delete('1.0', 'end')
            self.pm_selected_check_text.insert('end', self.short_step_text.get('1.0', 'end'))
        except Exception:
            pass
        self.pm_refresh_list(keep_index=idx, reload_editor=False)
        self.pm_update_summary()
        self.refresh_batch_workspace_preview()
        self.schedule_autosave()
    except Exception as e:
        try:
            item['status'] = 'Error'
        except Exception:
            pass
        messagebox.showerror('Project Manager', str(e))

def _v26_bind_setup_live_update(self):
    if getattr(self, '_v26_setup_bound', False):
        return
    self._v26_setup_bound = True
    vars_to_watch = ['coupling_eq', 'coupling_time_h', 'coupling_repeats', 'modifier_eq', 'modifier_repeats', 'solvent_volume_mode', 'amide_ml_per_mmol', 'ctc_ml_per_mmol', 'solvent_molarity_m', 'default_reagent', 'default_reagent_eq', 'default_reagent_count', 'default_catalyst', 'default_catalyst_eq', 'default_catalyst_count', 'default_base', 'default_base_eq', 'default_base_count', 'default_coupling_solution_solvent', 'default_solvent1', 'default_solvent1_count', 'default_solvent2', 'default_solvent2_count', 'default_loading_dissolve_solvent', 'final_meoh_count', 'default_depro', 'default_depro_ratio', 'default_depro_count', 'batch_solution_conc', 'batch_coupling_eq', 'batch_actual_round_ml', 'batch_actual_extra_ml', 'batch_hbtu_eq', 'batch_hbtu_conc', 'batch_hbtu_mw', 'batch_nmp_density']

    def _changed(*_):
        try:
            from spps_v4_gui import batch_workflow
            batch_workflow.invalidate_and_refresh_if_visible(self)
            self.pm_update_summary()
            self.schedule_autosave()
        except Exception:
            pass
    for name in vars_to_watch:
        var = getattr(self, name, None)
        if hasattr(var, 'trace_add'):
            try:
                var.trace_add('write', lambda *_: self.after_idle(_changed))
            except Exception:
                pass
_old_v26_build_pm_setup_panel = ClassicBaseCore._build_pm_setup_panel

def _v26_build_pm_setup_panel(self, parent):
    _old_v26_build_pm_setup_panel(self, parent)
    try:
        _v26_bind_setup_live_update(self)
    except Exception:
        pass

def _v26_pm_live_sync_selected(self):
    if (getattr(self, '_pm_loading_editor', False)
            or getattr(self, '_v229_switching', False)
            or getattr(self, '_v2212_switching', False)):
        return
    idx = self.pm_current_index() if hasattr(self, 'pm_list') else None
    if idx is None or idx < 0 or idx >= len(getattr(self, 'pm_items', [])):
        return
    try:
        self.pm_items[idx].update({'project': self.pm_project.get().strip(), 'peptide': self.pm_peptide.get().strip(), 'sequence': self.pm_sequence.get().strip(), 'scale': self.pm_scale.get().strip(), 'resin': self.pm_resin.get().strip(), 'loading': self.pm_loading.get().strip(), 'lot': self.pm_lot.get().strip(), 'chemistry': self.pm_chemistry.get().strip(), 'copies': self.pm_copies.get().strip(), 'status': self.pm_items[idx].get('status', 'Ready')})
        self.pm_refresh_list(keep_index=idx, reload_editor=False)
        self.pm_update_summary()
        from spps_v4_gui import batch_workflow
        batch_workflow.invalidate_and_refresh_if_visible(self)
        self.schedule_autosave()
    except Exception:
        pass

class ClassicControllerBase(ClassicBaseCore):
    """Static accepted Classic UI base. Methods are resolved once in source, never rebound at runtime."""
    __init__ = ClassicBaseCore.__init__
    _aa_letters_from_sequence = ClassicBaseCore._aa_letters_from_sequence
    _add_total_record = ClassicBaseCore._add_total_record
    _amount_basis_for_unit = ClassicBaseCore._amount_basis_for_unit
    _amount_numeric = ClassicBaseCore._amount_numeric
    _append_branch_rows_if_enabled = ClassicBaseCore._append_branch_rows_if_enabled
    _batch_aa_synthesizer_summary = ClassicBaseCore._batch_aa_synthesizer_summary
    _batch_ac_cap_count_by_rows = ClassicBaseCore._batch_ac_cap_count_by_rows
    _batch_ac_cap_summary = ClassicBaseCore._batch_ac_cap_summary
    _batch_coupling_count_by_rows = ClassicBaseCore._batch_coupling_count_by_rows
    _batch_hbtu_nmp_summary = ClassicBaseCore._batch_hbtu_nmp_summary
    _batch_layout_text = ClassicBaseCore._batch_layout_text
    _batch_modifier_summary = ClassicBaseCore._batch_modifier_summary
    _batch_project_index_df = ClassicBaseCore._batch_project_index_df
    _batch_rows_from_tree = _v26_batch_rows_from_tree
    _batch_total_aa = ClassicBaseCore._batch_total_aa
    _batch_total_materials = ClassicBaseCore._batch_total_materials
    _batch_total_reagents = ClassicBaseCore._batch_total_reagents
    _batch_total_solvents = ClassicBaseCore._batch_total_solvents
    _batch_total_usage_by_category = ClassicBaseCore._batch_total_usage_by_category
    _bind_row_height_controls = ClassicBaseCore._bind_row_height_controls
    _build = ClassicBaseCore._build
    # Keep the accepted V2 Project-driven calculator as the default Batch UI.
    # V3's canonical calculation engine populates these compact tables, so
    # chemical/linker/tag support remains available without a duplicate editor.
    _build_batch_tab = _v23_build_batch_tab
    _build_checklist_tab = ClassicBaseCore._build_checklist_tab
    _build_log_tab = ClassicBaseCore._build_log_tab
    _build_pm_setup_panel = _v26_build_pm_setup_panel
    _build_project_manager_tab = ClassicBaseCore._build_project_manager_tab
    _build_project_sheet_tab = ClassicBaseCore._build_project_sheet_tab
    _build_usage_summary_tab = ClassicBaseCore._build_usage_summary_tab
    _column_width_file = ClassicBaseCore._column_width_file
    _compound_row_for_unit = ClassicBaseCore._compound_row_for_unit
    _default_counts_for_row = ClassicBaseCore._default_counts_for_row
    _default_dissolve_volume = ClassicBaseCore._default_dissolve_volume
    _density_for = ClassicBaseCore._density_for
    _density_for_token = ClassicBaseCore._density_for_token
    _estimate_reagent_g = ClassicBaseCore._estimate_reagent_g
    _export_current_outputs_to_dir = ClassicBaseCore._export_current_outputs_to_dir
    _extract_sequence_special_tokens = ClassicBaseCore._extract_sequence_special_tokens
    _final_wash_specs = ClassicBaseCore._final_wash_specs
    _format_unit_amount = ClassicBaseCore._format_unit_amount
    _input = ClassicBaseCore._input
    _is_ac_unit = ClassicBaseCore._is_ac_unit
    _is_amount_ml = ClassicBaseCore._is_amount_ml
    _is_chemical_label_like_unit = ClassicBaseCore._is_chemical_label_like_unit
    _is_first_synthesis_row = ClassicBaseCore._is_first_synthesis_row
    _is_linker_like_unit = ClassicBaseCore._is_linker_like_unit
    _is_liquid_like = ClassicBaseCore._is_liquid_like
    _is_non_fmoc_modifier_row = ClassicBaseCore._is_non_fmoc_modifier_row
    _is_solid_reagent_name = ClassicBaseCore._is_solid_reagent_name
    _last_fmoc_step_no = ClassicBaseCore._last_fmoc_step_no
    _last_non_fmoc_final_step_no = ClassicBaseCore._last_non_fmoc_final_step_no
    _load_column_widths = ClassicBaseCore._load_column_widths
    _loading_dissolve_solvent_for_resin = ClassicBaseCore._loading_dissolve_solvent_for_resin
    _log = _v23_log
    _minimal_materials_from_plan = ClassicBaseCore._minimal_materials_from_plan
    _mw_for_token = ClassicBaseCore._mw_for_token
    _needs_deprotection_for_row = ClassicBaseCore._needs_deprotection_for_row
    _normalize_batch_modifier = ClassicBaseCore._normalize_batch_modifier
    _normalize_unit_display_name = ClassicBaseCore._normalize_unit_display_name
    _on_row_height_var_changed = ClassicBaseCore._on_row_height_var_changed
    _on_tab_changed_refresh = ClassicBaseCore._on_tab_changed_refresh
    _on_tree_row_height_wheel = ClassicBaseCore._on_tree_row_height_wheel
    _parse_batch_input = ClassicBaseCore._parse_batch_input
    _populate_progress_tree = ClassicBaseCore._populate_progress_tree
    _progress_key = ClassicBaseCore._progress_key
    _project_export_dir = ClassicBaseCore._project_export_dir
    _protected_name_for_token = ClassicBaseCore._protected_name_for_token
    _records_to_usage_df = ClassicBaseCore._records_to_usage_df
    _renumber_batch_rows = ClassicBaseCore._renumber_batch_rows
    _resin_family_text = ClassicBaseCore._resin_family_text
    _resin_needs_initial_deprotection = ClassicBaseCore._resin_needs_initial_deprotection
    _roundup_actual_amount = ClassicBaseCore._roundup_actual_amount
    _safe_name = ClassicBaseCore._safe_name
    _sanitize_display_value = ClassicBaseCore._sanitize_display_value
    _save_column_widths = ClassicBaseCore._save_column_widths
    _sequence_has_nterm_ac = ClassicBaseCore._sequence_has_nterm_ac
    _set_checklist_pane = ClassicBaseCore._set_checklist_pane
    _set_log_pane = ClassicBaseCore._set_log_pane
    _set_material_pane = ClassicBaseCore._set_material_pane
    _set_plan_pane = ClassicBaseCore._set_plan_pane
    _set_pm_sash_default = ClassicBaseCore._set_pm_sash_default
    _set_progress_item_done = ClassicBaseCore._set_progress_item_done
    _split_solution_name = ClassicBaseCore._split_solution_name
    _swell_solvent_for_resin = ClassicBaseCore._swell_solvent_for_resin
    _text_in_frame = ClassicBaseCore._text_in_frame
    _text_tab = ClassicBaseCore._text_tab
    _to_float = ClassicBaseCore._to_float
    _to_int = ClassicBaseCore._to_int
    _tree_in_frame = ClassicBaseCore._tree_in_frame
    _tree_tab = ClassicBaseCore._tree_tab
    _update_progress_widgets = ClassicBaseCore._update_progress_widgets
    _v23_aa_calculator_df = _v23_aa_calculator_df
    _v23_add_solution_record = _v23_add_solution_record
    _v23_batch_totals = _v23_batch_totals
    _v23_export_batch_calculator = _v23_export_batch_calculator
    _v23_project_rows = _v23_project_rows
    _v23_project_summary_df = _v23_project_summary_df
    _v23_roundup_ml = _v23_roundup_ml
    _v23_solution_records_to_df = _v23_solution_records_to_df
    _v25_format_display_value = _v25_format_display_value
    _write_df = ClassicBaseCore._write_df
    _write_synthesizer_excel = ClassicBaseCore._write_synthesizer_excel
    _write_tree = _v25_write_tree
    adjust_table_row_height = ClassicBaseCore.adjust_table_row_height
    amino_acid_usage_summary = ClassicBaseCore.amino_acid_usage_summary
    append_blank_row = ClassicBaseCore.append_blank_row
    apply_chemistry_preset_from_string = ClassicBaseCore.apply_chemistry_preset_from_string
    apply_dic_hobt_preset = ClassicBaseCore.apply_dic_hobt_preset
    apply_hbtu_nmp_preset = ClassicBaseCore.apply_hbtu_nmp_preset
    apply_table_row_height = ClassicBaseCore.apply_table_row_height
    batch_add_row = ClassicBaseCore.batch_add_row
    batch_delete_selected = ClassicBaseCore.batch_delete_selected
    batch_on_edit = ClassicBaseCore.batch_on_edit
    bench_checklist_layout_df = ClassicBaseCore.bench_checklist_layout_df
    bind_all_combobox_typeahead = ClassicBaseCore.bind_all_combobox_typeahead
    browse_outdir = ClassicBaseCore.browse_outdir
    checklist_from_rows = ClassicBaseCore.checklist_from_rows
    clear_all_progress_rows = ClassicBaseCore.clear_all_progress_rows
    cleavage_calculator_df = ClassicBaseCore.cleavage_calculator_df
    delete_selected = ClassicBaseCore.delete_selected
    export_outputs = ClassicBaseCore.export_outputs
    generate_update_plan = ClassicBaseCore.generate_update_plan
    load_batch_csv = ClassicBaseCore.load_batch_csv
    load_output_folder = ClassicBaseCore.load_output_folder
    load_project = ClassicBaseCore.load_project
    loading_calculator_df = ClassicBaseCore.loading_calculator_df
    manufacturing_transfer_df = ClassicBaseCore.manufacturing_transfer_df
    mark_until_selected_progress_row = ClassicBaseCore.mark_until_selected_progress_row
    materials_from_rows = ClassicBaseCore.materials_from_rows
    ml_log_from_rows = ClassicBaseCore.ml_log_from_rows
    next_step_df = ClassicBaseCore.next_step_df
    on_tree_edit = ClassicBaseCore.on_tree_edit
    open_batch_output = ClassicBaseCore.open_batch_output
    open_output = ClassicBaseCore.open_output
    operation_form_from_rows = ClassicBaseCore.operation_form_from_rows
    pm_add_peptide = ClassicBaseCore.pm_add_peptide
    pm_apply_item_to_single_plan = ClassicBaseCore.pm_apply_item_to_single_plan
    pm_calculate_all = _v26_pm_generate_selected
    pm_clear_selected_outputs = ClassicBaseCore.pm_clear_selected_outputs
    pm_current_index = ClassicBaseCore.pm_current_index
    pm_delete_peptide = ClassicBaseCore.pm_delete_peptide
    pm_display_name = ClassicBaseCore.pm_display_name
    pm_duplicate_peptide = ClassicBaseCore.pm_duplicate_peptide
    pm_generate_selected = _v26_pm_generate_selected
    pm_live_sync_selected = _v26_pm_live_sync_selected
    pm_load_to_editor = ClassicBaseCore.pm_load_to_editor
    pm_on_double_click = ClassicBaseCore.pm_on_double_click
    pm_on_select = ClassicBaseCore.pm_on_select
    pm_refresh_list = ClassicBaseCore.pm_refresh_list
    pm_save_selected = ClassicBaseCore.pm_save_selected
    pm_send_to_batch_manager = ClassicBaseCore.pm_send_to_batch_manager
    pm_tree_to_df = ClassicBaseCore.pm_tree_to_df
    pm_update_summary = ClassicBaseCore.pm_update_summary
    production_tracking_df = ClassicBaseCore.production_tracking_df
    progress_df = ClassicBaseCore.progress_df
    reagent_usage_summary = ClassicBaseCore.reagent_usage_summary
    rebuild_table = ClassicBaseCore.rebuild_table
    recalculate_row = ClassicBaseCore.recalculate_row
    refresh_batch_workspace_preview = _v23_refresh_batch_workspace_preview
    refresh_outputs_from_tree = ClassicBaseCore.refresh_outputs_from_tree
    reset_column_widths = ClassicBaseCore.reset_column_widths
    run_batch_plans = ClassicBaseCore.run_batch_plans
    save_batch_csv = ClassicBaseCore.save_batch_csv
    save_project_state = ClassicBaseCore.save_project_state
    select_all_progress_rows = ClassicBaseCore.select_all_progress_rows
    selected_progress_rows_yes = ClassicBaseCore.selected_progress_rows_yes
    short_step_checklist_df = ClassicBaseCore.short_step_checklist_df
    solvent_usage_summary = ClassicBaseCore.solvent_usage_summary
    toggle_progress_row = ClassicBaseCore.toggle_progress_row
    toggle_setup_panel = ClassicBaseCore.toggle_setup_panel
    tree_rows = ClassicBaseCore.tree_rows
__all__ = ['ClassicControllerBase']
