from __future__ import annotations
import os
import sys
import re
import json
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from peptiforg_core.ui_helpers import set_pepforge_icon

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "apps" / "spps_planner_app"
sys.path.insert(0, str(APP))

from spps_planner.engine import (
    PlanInput,
    plan_summary,
    generate_excel_like_synthesis_table,
)
from spps_planner.parser import tokenize_core_sequence
try:
    from spps_planner.export import export_csvs
except Exception:
    export_csvs = None


def open_path(p: Path):
    if os.name == "nt":
        os.startfile(str(p))
    elif sys.platform == "darwin":
        os.system(f'open "{p}"')
    else:
        os.system(f'xdg-open "{p}"')


class EditableTree(ttk.Treeview):
    """Small Excel-like Treeview with double-click editing.

    Some columns use an editable Combobox so SPPS users can select common
    amino acids, modifiers, coupling reagents, catalysts, bases, and solvents.
    Values remain editable because laboratories often use vendor- or
    protocol-specific reagent names. The SPPS coupling solvent is represented
    as one coupling cocktail solvent for the amino acid/modifier + reagent(s) + base mixture,
    not as separate unit/reagent/base dissolution solvents.
    """
    def __init__(self, master, columns, on_edit=None, combo_values=None, **kwargs):
        super().__init__(master, columns=columns, show="headings", **kwargs)
        self._on_edit = on_edit
        self._edit_entry = None
        self._combo_values = combo_values or {}
        for col in columns:
            self.heading(col, text=col)
            self.column(col, width=180, minwidth=110, anchor="w", stretch=True)
        self.bind("<Double-1>", self._begin_edit)

    def _begin_edit(self, event):
        if self.identify("region", event.x, event.y) != "cell":
            return
        row_id = self.identify_row(event.y)
        col_id = self.identify_column(event.x)
        if not row_id or not col_id:
            return
        col_index = int(col_id.replace("#", "")) - 1
        cols = list(self["columns"])
        if col_index < 0 or col_index >= len(cols):
            return
        col_name = cols[col_index]
        if col_name in {"No"}:
            return
        bbox = self.bbox(row_id, col_id)
        if not bbox:
            return
        x, y, w, h = bbox
        values = list(self.item(row_id, "values"))
        old = values[col_index] if col_index < len(values) else ""
        if self._edit_entry is not None:
            self._edit_entry.destroy()
        choices = self._combo_values.get(col_name)
        if choices:
            e = ttk.Combobox(self, values=choices, state="normal")
            e.set(str(old))
        else:
            e = ttk.Entry(self)
            e.insert(0, str(old))
            e.select_range(0, "end")
        e.focus_set()
        e.place(x=x, y=y, width=w, height=h)
        self._edit_entry = e

        def commit(_event=None):
            new = e.get()
            values[col_index] = new
            self.item(row_id, values=values)
            e.destroy()
            self._edit_entry = None
            if self._on_edit:
                self._on_edit(row_id, col_name, new)

        def cancel(_event=None):
            e.destroy()
            self._edit_entry = None

        e.bind("<Return>", commit)
        e.bind("<FocusOut>", commit)
        e.bind("<Escape>", cancel)


class SPPSGui(tk.Tk):
    PLAN_COLUMNS = [
        "No",
        "Unit name",
        "Unit eq",
        "Unit amount(g)",
        "Unit volume(mL)",
        "Coupling reagent 1",
        "Coupling reagent 1 eq",
        "Coupling reagent 1 count",
        "Coupling reagent 2 / catalyst",
        "Coupling reagent 2 / catalyst eq",
        "Coupling reagent 2 / catalyst count",
        "Coupling base",
        "Coupling base eq",
        "Coupling base count",
        "Coupling cocktail solvent",
        "Coupling cocktail volume(mL)",
        "Deprotection base",
        "Deprotection ratio",
        "Deprotection count",
        "Solvent 1",
        "Solvent 1 count",
        "Solvent 2",
        "Solvent 2 count",
        "Repeat",
    ]

    MATERIAL_COLUMNS = [
        "step", "material", "class", "MW", "planned_mmol", "planned_g", "planned_mL", "use_count", "repeat", "phase", "note", "source"
    ]

    RESIN_VALUES = ["Amide", "Rink Amide", "Rink Amide AM", "Rink Amide MBHA", "Rink Amide ChemMatrix", "Rink Amide Tentagel", "Wang", "HMPB", "Sieber Amide", "PAL resin", "CTC/Trityl", "2-CTC", "2-Chlorotrityl chloride resin", "Trityl chloride resin", "Tentagel", "Manual"]
    # Coupling reagent 1 is for actual coupling/activating reagent only. Labels/modifiers stay in the AA/modifier name column.
    REAGENT_VALUES = ["", "DIC", "DCC", "EDC", "HBTU", "HATU", "HCTU", "TBTU", "PyBOP", "PyAOP", "BOP", "COMU", "T3P", "DMTMM", "TFFH", "BTC", "CDI", "MSNT", "Manual"]
    # Coupling reagent 2 / catalyst is reserved for catalyst/additive-like components.
    CATALYST_VALUES = ["", "HOBt", "Cl-HOBt", "6-Cl-HOBt", "HOAt", "Oxyma", "Oxyma Pure", "K-Oxyma", "DMAP", "NHS", "Sulfo-NHS", "HOSu", "HODhbt", "DHO", "Manual"]
    BASE_VALUES = ["", "DIEA", "DIPEA", "NMM", "TEA", "Pyridine", "2,4,6-collidine", "2,6-lutidine", "DBU", "Piperidine", "TMP", "Manual"]
    DEPRO_VALUES = ["Piperidine", "DBU", "Piperazine", "Morpholine", "4-methylpiperidine", "Manual"]
    RATIO_VALUES = ["20% in DMF", "2% DBU + 2% piperidine in DMF", "20% piperidine + 0.1 M HOBt", "Manual"]
    SOLVENT_VALUES = ["", "DMF", "NMP", "DCM", "90% DCM / 10% DMF", "10% DMF/DCM", "DCM/DMF", "DMF/NMP", "MeOH", "EtOH", "i-PrOH", "ACN", "THF", "DMSO", "TFA", "TIS", "Water", "Ether", "Diethyl ether", "MTBE", "Manual"]

    UNIT_VALUES = [
        "", "A", "R", "N", "D", "C", "Q", "E", "G", "H", "I", "L", "K", "M", "F", "P", "S", "T", "W", "Y", "V",
        "D-Ala", "D-Arg", "D-Asn", "D-Asp", "D-Cys", "D-Gln", "D-Glu", "D-His", "D-Ile", "D-Leu", "D-Lys", "D-Phe", "D-Pro", "D-Ser", "D-Tyr", "D-Val",
        "Hyp", "Nle", "Nva", "Orn", "Dap", "Dab", "Aib", "Sar", "Bpa", "Cha", "Cit", "hArg", "hLys", "Pen",
        "Ac", "FITC", "Biotin", "Biotin-NHS", "Biotin acid", "FAM", "TAMRA", "CY3", "CY5", "CY7", "Dabcyl", "DOTA", "NOTA",
        "Pal", "Myr", "Gal", "Nic", "Caf", "Ahx", "AEEA", "PEG4", "PEG8", "bAla", "gAla", "His6", "FLAG", "HA", "Manual"
    ]

    MW_FALLBACK = {
        # coupling / activation reagents
        "DIC": 126.20, "DCC": 206.33, "EDC": 191.70, "HBTU": 379.25, "HATU": 380.23,
        "HCTU": 413.69, "TBTU": 321.08, "PyBOP": 520.39, "PyAOP": 521.36, "BOP": 442.28,
        "COMU": 427.35, "T3P": 318.18, "DMTMM": 276.72, "TFFH": 226.19, "BTC": 296.75,
        "CDI": 162.15, "MSNT": 284.29,
        # catalysts / additives
        "HOBt": 135.13, "Cl-HOBt": 169.57, "6-Cl-HOBt": 169.57, "HOAt": 136.11,
        "Oxyma": 142.11, "Oxyma Pure": 142.11, "K-Oxyma": 180.20, "DMAP": 122.17,
        "NHS": 115.09, "Sulfo-NHS": 217.13, "HOSu": 115.09, "HODhbt": 151.12, "DHO": 151.12,
        # bases / deprotection reagents
        "DIEA": 129.25, "DIPEA": 129.25, "NMM": 101.15, "TEA": 101.19, "Pyridine": 79.10,
        "2,4,6-collidine": 121.18, "2,6-lutidine": 107.16, "DBU": 152.24, "Piperidine": 85.15,
        "Piperazine": 86.14, "Morpholine": 87.12, "4-methylpiperidine": 99.18, "TMP": 141.25,
        # N-terminal acetylation / common liquids
        "Ac2O": 102.09, "Acetic anhydride": 102.09, "AcOH": 60.05, "Acetic acid": 60.05,
        # common solvents (MW shown only for reference; volume is density/count based)
        "DMF": 73.09, "NMP": 99.13, "DCM": 84.93, "MeOH": 32.04, "EtOH": 46.07,
        "i-PrOH": 60.10, "ACN": 41.05, "THF": 72.11, "DMSO": 78.13, "TFA": 114.02,
        "TIS": 158.36, "Water": 18.02, "Ether": 74.12, "Diethyl ether": 74.12, "MTBE": 88.15,
        # common labels/modifiers: exact reagent form should still be verified by user/vendor
        "FITC": 389.38, "Biotin": 244.31, "Biotin-NHS": 341.38, "FAM": 376.32, "TAMRA": 430.45,
        "DOTA": 404.42, "NOTA": 393.35,
        "Pal": 256.43, "Palmitic acid": 256.43, "Myr": 228.38, "Myristic acid": 228.38,
        "Nic": 123.11, "Nicotinic acid": 123.11, "Caf": 180.16, "Caffeic acid": 180.16,
        "Gal": 170.12, "Gallic acid": 170.12, "Stear": 284.48, "Stearic acid": 284.48,
    }

    def __init__(self):
        super().__init__()
        self.title("SPPS Planner")
        set_pepforge_icon(self)
        self.geometry("1920x1080")
        self.minsize(1550, 900)
        self.last_outdir: Path | None = None
        self._row_meta_by_no = {}
        self._build()
        self.rebuild_table()
        self.after(300, self.refresh_outputs_from_tree)

    def _build(self):
        style = ttk.Style(self)
        style.configure("Treeview", rowheight=28, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        style.configure("TNotebook.Tab", padding=(24, 10), font=("Segoe UI", 11, "bold"))
        main = ttk.Frame(self, padding=10)
        main.pack(fill="both", expand=True)
        ttk.Label(main, text="SPPS Planner - Production Workbench", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(main, text="Project-based SPPS planner with editable tables, material summaries, calculators, checklist progress, and transfer sheets.", wraplength=1500).pack(anchor="w", pady=(4, 10))
        self.project_name = tk.StringVar(value="")
        self.seq = tk.StringVar(value="Ac-EEMQRR-NH2")

        project_bar = ttk.Labelframe(main, text="Project", padding=8)
        project_bar.pack(fill="x", pady=(0,8))
        ttk.Label(project_bar, text="Project name", width=16).grid(row=0, column=0, sticky="w", padx=(0,4))
        ttk.Entry(project_bar, textvariable=self.project_name).grid(row=0, column=1, sticky="ew", padx=(0,10))
        ttk.Label(project_bar, text="Sequence", width=12).grid(row=0, column=2, sticky="w", padx=(0,4))
        ttk.Entry(project_bar, textvariable=self.seq).grid(row=0, column=3, sticky="ew")
        project_bar.columnconfigure(1, weight=1)
        project_bar.columnconfigure(3, weight=1)

        form = ttk.Labelframe(main, text="Resin / Coupling / Base / Solvent Defaults", padding=8)
        form.pack(fill="x")
        self.resin = tk.StringVar(value="Amide")
        self.scale = tk.DoubleVar(value=400.0)
        self.loading = tk.DoubleVar(value=0.8)
        self.coupling_eq = tk.DoubleVar(value=5.0)
        self.modifier_eq = tk.DoubleVar(value=3.0)
        self.coupling_repeats = tk.IntVar(value=1)
        self.modifier_repeats = tk.IntVar(value=1)
        self.default_reagent = tk.StringVar(value="DIC")
        self.default_reagent_eq = tk.DoubleVar(value=5.0)
        self.default_reagent_count = tk.IntVar(value=1)
        self.default_catalyst = tk.StringVar(value="HOBt")
        self.default_catalyst_eq = tk.DoubleVar(value=5.0)
        self.default_catalyst_count = tk.IntVar(value=1)
        self.default_base = tk.StringVar(value="")
        self.default_base_eq = tk.DoubleVar(value=5.0)
        self.default_base_count = tk.IntVar(value=1)
        self.default_depro = tk.StringVar(value="Piperidine")
        self.default_depro_ratio = tk.StringVar(value="20% in DMF")
        self.default_depro_count = tk.IntVar(value=2)
        self.default_solvent1 = tk.StringVar(value="DMF")
        self.default_solvent1_count = tk.IntVar(value=6)
        self.default_solvent2 = tk.StringVar(value="DCM")
        self.default_solvent2_count = tk.IntVar(value=3)
        self.final_meoh_count = tk.IntVar(value=0)
        self.branch_mode = tk.BooleanVar(value=False)
        self.branch_point = tk.StringVar(value="K5")
        self.branch_arm = tk.StringVar(value="RGD")
        self.branch_pg = tk.StringVar(value="Mtt")
        self.branch_depro_condition = tk.StringVar(value="Mtt: dilute TFA/TIS/DCM")
        self.ml_per_mmol = tk.DoubleVar(value=10.0)
        self.default_coupling_solution_solvent = tk.StringVar(value="DMF")
        self.default_loading_dissolve_solvent = tk.StringVar(value="90% DCM / 10% DMF")
        self.outdir = tk.StringVar(value=str(ROOT / "outputs" / "spps_editable_run"))

        def add_card_field(parent, label, widget, r, c, span=1, label_width=22):
            """Place one SPPS setup field inside a compact vertical card.

            The public v1.0.1 UI intentionally groups chemically related inputs
            in vertical blocks instead of one very long horizontal row. This is
            easier to read on a bench laptop and mirrors the way chemists think:
            resin properties, amino-acid/unit settings, reagent 1, reagent 2 or
            catalyst, base/deprotection, and solvents.
            """
            ttk.Label(parent, text=label, width=label_width).grid(row=r, column=c*2, sticky="w", padx=(0, 8), pady=3)
            try:
                if isinstance(widget, ttk.Entry):
                    widget.configure(width=18)
                elif isinstance(widget, ttk.Combobox):
                    current = int(widget.cget("width") or 0)
                    widget.configure(width=max(current, 22))
            except Exception:
                pass
            widget.grid(row=r, column=c*2+1, sticky="ew", padx=(0, 8), pady=3, columnspan=span)
            try:
                parent.columnconfigure(c*2+1, weight=1)
            except Exception:
                pass

        def make_card(parent, title, row, col, colspan=1):
            card = ttk.Labelframe(parent, text=title, padding=(10, 8))
            card.grid(row=row, column=col, columnspan=colspan, sticky="nsew", padx=6, pady=6)
            for i in range(4):
                card.columnconfigure(i, weight=1)
            return card

        # Top action bar: primary workflow buttons remain visible above the setup cards.
        action_bar = ttk.Frame(form)
        action_bar.grid(row=0, column=0, columnspan=4, sticky="ew", padx=(2, 2), pady=(0, 6))
        ttk.Button(action_bar, text="Build/Rebuild", width=16, command=self.rebuild_table).pack(side="left", padx=3)
        ttk.Button(action_bar, text="Load Project", width=14, command=self.load_project).pack(side="left", padx=3)
        ttk.Button(action_bar, text="Load Output", width=14, command=self.load_output_folder).pack(side="left", padx=3)
        ttk.Button(action_bar, text="Recalculate", width=14, command=self.refresh_outputs_from_tree).pack(side="left", padx=3)
        ttk.Button(action_bar, text="Export", width=12, command=self.export_outputs).pack(side="left", padx=3)
        ttk.Button(action_bar, text="Open Output", width=14, command=self.open_output).pack(side="left", padx=3)
        # v2.1.0: keep the work tables large by default. Setup tabs are still available,
        # but hidden until the user needs to edit synthesis defaults.
        self._setup_visible = tk.BooleanVar(value=False)
        self.setup_toggle_btn = ttk.Button(action_bar, text="Show setup", width=14, command=self.toggle_setup_panel)
        self.setup_toggle_btn.pack(side="left", padx=(12, 3))
        ttk.Label(action_bar, text="Setup is tabbed; hide it to maximize Plan/Materials visibility.").pack(side="left", padx=(6, 0))

        for i in range(4):
            form.columnconfigure(i, weight=1)

        # v2.1.0: keep SPPS work tables visible by moving setup cards into a compact tabbed panel.
        setup_tabs = ttk.Notebook(form)
        self.setup_tabs = setup_tabs
        setup_tabs.grid(row=1, column=0, columnspan=4, sticky="ew", padx=2, pady=(2, 4))
        # Default hidden so the lower editable work tables are readable on 1080p screens.
        setup_tabs.grid_remove()
        tab_resin = ttk.Frame(setup_tabs, padding=4)
        tab_reagents = ttk.Frame(setup_tabs, padding=4)
        tab_solvents = ttk.Frame(setup_tabs, padding=4)
        tab_output = ttk.Frame(setup_tabs, padding=4)
        setup_tabs.add(tab_resin, text="Resin / Unit")
        setup_tabs.add(tab_reagents, text="Reagents / Base")
        setup_tabs.add(tab_solvents, text="Solvents / Wash")
        setup_tabs.add(tab_output, text="Output")
        for _tab in (tab_resin, tab_reagents, tab_solvents, tab_output):
            _tab.columnconfigure(0, weight=1)
            _tab.columnconfigure(1, weight=1)

        resin_card = make_card(tab_resin, "Resin properties", 0, 0)
        unit_card = make_card(tab_resin, "Amino acid / unit defaults", 0, 1)
        reagent1_card = make_card(tab_reagents, "Reagent 1 / activator", 0, 0)
        reagent2_card = make_card(tab_reagents, "Reagent 2 / catalyst", 0, 1)
        base_card = make_card(tab_reagents, "Base / deprotection", 1, 0, colspan=2)
        solvent_card = make_card(tab_solvents, "Solvent / wash settings", 0, 0, colspan=2)
        output_card = make_card(tab_output, "Output", 0, 0, colspan=2)

        add_card_field(resin_card, "Resin family", ttk.Combobox(resin_card, textvariable=self.resin, values=self.RESIN_VALUES, state="normal", width=30), 0, 0)
        add_card_field(resin_card, "Scale", ttk.Entry(resin_card, textvariable=self.scale), 1, 0)
        ttk.Label(resin_card, text="mmol", width=8).grid(row=1, column=2, sticky="w")
        add_card_field(resin_card, "Loading", ttk.Entry(resin_card, textvariable=self.loading), 2, 0)
        ttk.Label(resin_card, text="mmol/g", width=8).grid(row=2, column=2, sticky="w")
        add_card_field(resin_card, "mL per mmol", ttk.Entry(resin_card, textvariable=self.ml_per_mmol), 3, 0)

        add_card_field(unit_card, "Default unit eq", ttk.Entry(unit_card, textvariable=self.coupling_eq), 0, 0)
        ttk.Label(unit_card, text="eq", width=8).grid(row=0, column=2, sticky="w")
        add_card_field(unit_card, "Default unit repeat", ttk.Spinbox(unit_card, from_=1, to=20, textvariable=self.coupling_repeats), 1, 0)
        add_card_field(unit_card, "Modifier / label eq", ttk.Entry(unit_card, textvariable=self.modifier_eq), 2, 0)
        ttk.Label(unit_card, text="eq", width=8).grid(row=2, column=2, sticky="w")
        add_card_field(unit_card, "Modifier repeat", ttk.Spinbox(unit_card, from_=1, to=20, textvariable=self.modifier_repeats), 3, 0)

        add_card_field(reagent1_card, "Reagent 1", ttk.Combobox(reagent1_card, textvariable=self.default_reagent, values=self.REAGENT_VALUES, state="normal", width=26), 0, 0)
        add_card_field(reagent1_card, "Equivalent", ttk.Entry(reagent1_card, textvariable=self.default_reagent_eq), 1, 0)
        ttk.Label(reagent1_card, text="eq", width=8).grid(row=1, column=2, sticky="w")
        add_card_field(reagent1_card, "Count", ttk.Spinbox(reagent1_card, from_=0, to=30, textvariable=self.default_reagent_count), 2, 0)
        add_card_field(reagent1_card, "Cocktail solvent", ttk.Combobox(reagent1_card, textvariable=self.default_coupling_solution_solvent, values=self.SOLVENT_VALUES, state="normal", width=26), 3, 0)

        add_card_field(reagent2_card, "Reagent 2 / catalyst", ttk.Combobox(reagent2_card, textvariable=self.default_catalyst, values=self.CATALYST_VALUES, state="normal", width=26), 0, 0)
        add_card_field(reagent2_card, "Equivalent", ttk.Entry(reagent2_card, textvariable=self.default_catalyst_eq), 1, 0)
        ttk.Label(reagent2_card, text="eq", width=8).grid(row=1, column=2, sticky="w")
        add_card_field(reagent2_card, "Count", ttk.Spinbox(reagent2_card, from_=0, to=30, textvariable=self.default_catalyst_count), 2, 0)
        ttk.Label(reagent2_card, text="Use this block for HOBt, Oxyma, DMAP, HOAt, NHS, or similar additives.", wraplength=460, foreground="#555555").grid(row=3, column=0, columnspan=4, sticky="w", pady=(4,0))

        add_card_field(base_card, "Coupling base", ttk.Combobox(base_card, textvariable=self.default_base, values=self.BASE_VALUES, state="normal", width=26), 0, 0)
        add_card_field(base_card, "Base equivalent", ttk.Entry(base_card, textvariable=self.default_base_eq), 1, 0)
        ttk.Label(base_card, text="eq", width=8).grid(row=1, column=2, sticky="w")
        add_card_field(base_card, "Base count", ttk.Spinbox(base_card, from_=0, to=30, textvariable=self.default_base_count), 2, 0)
        add_card_field(base_card, "Deprotection base", ttk.Combobox(base_card, textvariable=self.default_depro, values=self.DEPRO_VALUES, state="normal", width=26), 3, 0)
        add_card_field(base_card, "Deprotection ratio", ttk.Combobox(base_card, textvariable=self.default_depro_ratio, values=self.RATIO_VALUES, state="normal", width=26), 4, 0)
        add_card_field(base_card, "Deprotection count", ttk.Spinbox(base_card, from_=0, to=20, textvariable=self.default_depro_count), 5, 0)

        add_card_field(solvent_card, "Solvent 1", ttk.Combobox(solvent_card, textvariable=self.default_solvent1, values=self.SOLVENT_VALUES, state="normal", width=26), 0, 0)
        add_card_field(solvent_card, "Solvent 1 count", ttk.Spinbox(solvent_card, from_=0, to=30, textvariable=self.default_solvent1_count), 1, 0)
        add_card_field(solvent_card, "Solvent 2", ttk.Combobox(solvent_card, textvariable=self.default_solvent2, values=self.SOLVENT_VALUES, state="normal", width=26), 2, 0)
        add_card_field(solvent_card, "Solvent 2 count", ttk.Spinbox(solvent_card, from_=0, to=30, textvariable=self.default_solvent2_count), 3, 0)
        add_card_field(solvent_card, "Loading solvent", ttk.Combobox(solvent_card, textvariable=self.default_loading_dissolve_solvent, values=self.SOLVENT_VALUES, state="normal", width=26), 4, 0)
        add_card_field(solvent_card, "Final MeOH wash", ttk.Spinbox(solvent_card, from_=0, to=30, textvariable=self.final_meoh_count), 5, 0)

        output_card.columnconfigure(1, weight=1)
        ttk.Label(output_card, text="Output folder", width=18).grid(row=0, column=0, sticky="w", padx=(0,8), pady=3)
        ttk.Entry(output_card, textvariable=self.outdir).grid(row=0, column=1, sticky="ew", padx=(0,8), pady=3)
        ttk.Button(output_card, text="Browse", command=self.browse_outdir).grid(row=0, column=2, sticky="ew", padx=4)
        ttk.Button(output_card, text="Open Folder", command=self.open_output).grid(row=0, column=3, sticky="ew", padx=4)

        branch_box = ttk.Labelframe(main, text="Branch mode / side-chain arm", padding=8)
        branch_box.pack(fill="x", pady=(8, 2))
        ttk.Checkbutton(branch_box, text="Enable branch mode", variable=self.branch_mode, command=self.rebuild_table).grid(row=0, column=0, sticky="w", padx=(0, 10))
        ttk.Label(branch_box, text="Branch point").grid(row=0, column=1, sticky="w")
        ttk.Entry(branch_box, textvariable=self.branch_point, width=12).grid(row=0, column=2, sticky="w", padx=(4, 12))
        ttk.Label(branch_box, text="Branch arm sequence").grid(row=0, column=3, sticky="w")
        ttk.Entry(branch_box, textvariable=self.branch_arm, width=24).grid(row=0, column=4, sticky="ew", padx=(4, 12))
        ttk.Label(branch_box, text="Protecting group").grid(row=0, column=5, sticky="w")
        ttk.Combobox(branch_box, textvariable=self.branch_pg, values=["Mtt", "ivDde", "Dde", "Alloc", "Manual"], state="normal", width=14).grid(row=0, column=6, sticky="w", padx=(4, 12))
        ttk.Label(branch_box, text="Branch deprotection").grid(row=0, column=7, sticky="w")
        ttk.Combobox(branch_box, textvariable=self.branch_depro_condition, values=["Mtt: dilute TFA/TIS/DCM", "ivDde/Dde: hydrazine/DMF", "Alloc: Pd(PPh3)4/phenylsilane/DCM", "Manual"], state="normal", width=34).grid(row=0, column=8, sticky="ew", padx=(4, 0))
        branch_box.columnconfigure(4, weight=1)
        branch_box.columnconfigure(8, weight=1)

        btns = ttk.Frame(main)
        btns.pack(fill="x", pady=8)
        ttk.Button(btns, text="Append row", command=self.append_blank_row).pack(side="left", padx=4)
        ttk.Button(btns, text="Delete selected row", command=self.delete_selected).pack(side="left", padx=4)
        ttk.Button(btns, text="Reset table widths", command=self.reset_column_widths).pack(side="left", padx=4)
        ttk.Label(btns, text="Drag column borders/pane dividers. Double-click cells to edit.").pack(side="left", padx=12)

        self.tabs = ttk.Notebook(main)
        self.tabs.pack(fill="both", expand=True)

        plan_frame = ttk.Frame(self.tabs)
        self.tabs.add(plan_frame, text="Plan")
        plan_frame.rowconfigure(0, weight=0)
        plan_frame.rowconfigure(1, weight=1)
        plan_frame.columnconfigure(0, weight=1)
        horiz = ttk.PanedWindow(plan_frame, orient="vertical")
        self.plan_paned = horiz
        horiz.grid(row=1, column=0, sticky="nsew")
        pane_controls = ttk.Frame(plan_frame)
        pane_controls.grid(row=0, column=0, sticky="ew", padx=2, pady=(0, 4))
        ttk.Button(pane_controls, text="Plan full", command=lambda: self._set_plan_pane("plan")).pack(side="left", padx=3)
        ttk.Button(pane_controls, text="Live materials full", command=lambda: self._set_plan_pane("materials")).pack(side="left", padx=3)
        ttk.Button(pane_controls, text="Balanced", command=lambda: self._set_plan_pane("balanced")).pack(side="left", padx=3)

        table_frame = ttk.Frame(horiz)
        table_frame.rowconfigure(0, weight=1); table_frame.columnconfigure(0, weight=1)
        self.spps_combo_values = {
            "Unit name": self.UNIT_VALUES,
            "Coupling reagent 1": self.REAGENT_VALUES,
            "Coupling reagent 2 / catalyst": self.CATALYST_VALUES,
            "Coupling base": self.BASE_VALUES,
            "Coupling cocktail solvent": self.SOLVENT_VALUES,
            "Deprotection base": self.DEPRO_VALUES,
            "Deprotection ratio": self.RATIO_VALUES,
            "Solvent 1": self.SOLVENT_VALUES,
            "Solvent 2": self.SOLVENT_VALUES,
        }
        self.tree = EditableTree(table_frame, self.PLAN_COLUMNS, on_edit=self.on_tree_edit, combo_values=self.spps_combo_values)
        y = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        x = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        y.grid(row=0, column=1, sticky="ns")
        x.grid(row=1, column=0, sticky="ew")
        horiz.add(table_frame, weight=5)

        usage_frame = ttk.Labelframe(horiz, text="Live Material Usage Table")
        usage_frame.rowconfigure(0, weight=1); usage_frame.columnconfigure(0, weight=1)
        self.live_usage_tree = ttk.Treeview(usage_frame, columns=self.MATERIAL_COLUMNS, show="headings")
        for c in self.MATERIAL_COLUMNS:
            self.live_usage_tree.heading(c, text=c)
            self.live_usage_tree.column(c, width=240 if c in ("material", "note", "source") else 190, minwidth=140, anchor="w", stretch=True)
        uy = ttk.Scrollbar(usage_frame, orient="vertical", command=self.live_usage_tree.yview)
        ux = ttk.Scrollbar(usage_frame, orient="horizontal", command=self.live_usage_tree.xview)
        self.live_usage_tree.configure(yscrollcommand=uy.set, xscrollcommand=ux.set)
        self.live_usage_tree.grid(row=0, column=0, sticky="nsew")
        uy.grid(row=0, column=1, sticky="ns"); ux.grid(row=1, column=0, sticky="ew")
        horiz.add(usage_frame, weight=3)

        self.plan_width_map = {
            "No": 90,
            "Unit name": 520,
            "Unit eq": 135,
            "Unit amount(g)": 210,
            "Coupling reagent 1": 240,
            "Coupling reagent 1 eq": 135,
            "Coupling reagent 1 count": 145,
            "Coupling reagent 2 / catalyst": 340,
            "Coupling reagent 2 / catalyst eq": 180,
            "Coupling reagent 2 / catalyst count": 195,
            "Coupling base": 140,
            "Coupling base eq": 135,
            "Coupling base count": 150,
            "Coupling cocktail solvent": 330,
            "Coupling cocktail volume(mL)": 245,
            "Coupling base volume(mL)": 170,
            "Deprotection base": 160,
            "Deprotection ratio": 260,
            "Deprotection count": 160,
            "Solvent 1": 155,
            "Solvent 1 count": 130,
            "Solvent 2": 155,
            "Solvent 2 count": 130,
            "Repeat": 80,
        }
        existing_plan_columns = set(self.tree["columns"])
        self._load_column_widths()
        for k, v in self.plan_width_map.items():
            if k in existing_plan_columns:
                self.tree.column(k, width=v, minwidth=80, stretch=True)
        self.tree.bind("<ButtonRelease-1>", lambda e: self._save_column_widths())

        # Compact SPPS workbench tabs for bench use. Related views are grouped
        # to avoid notebook overflow glyphs and duplicated checklist views.
        self._build_usage_summary_tab()
        self._build_project_sheet_tab()
        self._build_checklist_tab()
        self._build_log_tab()
        self.tabs.bind("<<NotebookTabChanged>>", self._on_tab_changed_refresh, add="+")
        self.after_idle(self.refresh_outputs_from_tree)

    def _on_tab_changed_refresh(self, event=None):
        """Keep Materials/Checklist/Log populated when the user opens the tab."""
        try:
            selected = self.tabs.tab(self.tabs.select(), "text")
            if selected in {"Materials", "Plan", "Project", "Checklist", "Log"}:
                self.after_idle(self.refresh_outputs_from_tree)
        except Exception:
            pass

    def toggle_setup_panel(self):
        """Show or hide the tabbed synthesis setup panel.

        The SPPS workbench tables are the main working area. On 1080p screens,
        keeping all setup cards visible makes Plan/Materials difficult to read,
        so v2.1.0 defaults to a collapsed setup panel.
        """
        try:
            if self._setup_visible.get():
                self.setup_tabs.grid_remove()
                self._setup_visible.set(False)
                self.setup_toggle_btn.configure(text="Show setup")
            else:
                self.setup_tabs.grid()
                self._setup_visible.set(True)
                self.setup_toggle_btn.configure(text="Hide setup")
        except Exception:
            pass

    def _set_plan_pane(self, mode: str):
        """Let one Plan pane visually dominate the other without deleting data."""
        try:
            self.plan_paned.update_idletasks()
            h = max(300, self.plan_paned.winfo_height())
            if mode == "plan":
                # Make the editable Plan dominate while keeping the live material pane recoverable.
                pos = max(260, int(h * 0.92))
            elif mode == "materials":
                # Make Live Materials dominate, matching the requested "full" behavior.
                pos = max(42, int(h * 0.06))
            else:
                pos = int(h * 0.62)
            self.plan_paned.sashpos(0, pos)
        except Exception as e:
            self._log(f"Pane resize warning: {e}\n")

    def _on_row_height_var_changed(self, *_):
        """Apply row height immediately when the user clicks +/-/slider/spinbox arrows."""
        try:
            if getattr(self, "_row_height_trace_after_id", None):
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
        delta = 4 if getattr(event, "delta", 0) > 0 else -4
        self.adjust_table_row_height(delta)
        return "break"

    def _bind_row_height_controls(self, tree):
        try:
            tree.bind("<Control-MouseWheel>", self._on_tree_row_height_wheel, add="+")
            tree.bind("<Control-Button-4>", lambda e: (self.adjust_table_row_height(4), "break"), add="+")
            tree.bind("<Control-Button-5>", lambda e: (self.adjust_table_row_height(-4), "break"), add="+")
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
            ttk.Style(self).configure("Treeview", rowheight=h)
            for tree_name in ("tree", "live_usage_tree", "material_tree", "aa_summary_tree", "reagent_summary_tree", "solvent_summary_tree", "progress_tree"):
                tree = getattr(self, tree_name, None)
                if tree is not None:
                    tree.update_idletasks()
        except Exception as e:
            self._log("Row height update failed: " + str(e) + "\n")

    def reset_column_widths(self):
        """Restore readable editable-table column widths after manual resizing.

        This does not rebuild the table and does not change any edited values.
        It only restores the visible heading/column widths.
        """
        try:
            existing_plan_columns = set(self.tree["columns"])
            for k, v in getattr(self, "plan_width_map", {}).items():
                if k in existing_plan_columns:
                    self.tree.column(k, width=v, minwidth=80, stretch=True)
            for tree_name in ("live_usage_tree", "material_tree", "aa_summary_tree", "reagent_summary_tree", "solvent_summary_tree", "progress_tree"):
                tree = getattr(self, tree_name, None)
                if tree is not None:
                    for col in tree["columns"]:
                        tree.column(col, width=220 if col in ("material", "note", "source") else 170, minwidth=120, stretch=True)
            # keep the horizontal scrollbar active and preserve user data
            self.tree.update_idletasks()
            self._save_column_widths()
        except Exception as e:
            self._log("Column width reset failed: " + str(e) + "\n")

    def _text_tab(self, name):
        fr = ttk.Frame(self.tabs)
        self.tabs.add(fr, text=name)
        fr.rowconfigure(0, weight=1)
        fr.columnconfigure(0, weight=1)
        txt = tk.Text(fr, wrap="none")
        y = ttk.Scrollbar(fr, orient="vertical", command=txt.yview)
        x = ttk.Scrollbar(fr, orient="horizontal", command=txt.xview)
        txt.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        txt.grid(row=0, column=0, sticky="nsew")
        y.grid(row=0, column=1, sticky="ns")
        x.grid(row=1, column=0, sticky="ew")
        return txt

    def _tree_tab(self, name, columns):
        fr = ttk.Frame(self.tabs)
        self.tabs.add(fr, text=name)
        fr.rowconfigure(0, weight=1)
        fr.columnconfigure(0, weight=1)
        tree = ttk.Treeview(fr, columns=columns, show="headings")
        for c in columns:
            tree.heading(c, text=c)
            tree.column(c, width=120, anchor="w", stretch=True)
        y = ttk.Scrollbar(fr, orient="vertical", command=tree.yview)
        x = ttk.Scrollbar(fr, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        tree.grid(row=0, column=0, sticky="nsew")
        y.grid(row=0, column=1, sticky="ns")
        x.grid(row=1, column=0, sticky="ew")
        return tree

    def _tree_in_frame(self, parent, columns):
        tree = ttk.Treeview(parent, columns=columns, show="headings", height=18)
        for c in columns:
            tree.heading(c, text=c)
            w = 340 if c in ("material", "note", "source", "operation", "next_step") else 170
            if c in ("actual_used", "actual_used_g"):
                w = 210
            tree.column(c, width=w, anchor="w", stretch=True, minwidth=95)
        y = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        x = ttk.Scrollbar(parent, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        tree.grid(row=0, column=0, sticky="nsew")
        y.grid(row=0, column=1, sticky="ns")
        x.grid(row=1, column=0, sticky="ew")
        return tree

    def _text_in_frame(self, parent):
        txt = tk.Text(parent, wrap="none", font=("Consolas", 10))
        y = ttk.Scrollbar(parent, orient="vertical", command=txt.yview)
        x = ttk.Scrollbar(parent, orient="horizontal", command=txt.xview)
        txt.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        txt.grid(row=0, column=0, sticky="nsew")
        y.grid(row=0, column=1, sticky="ns")
        x.grid(row=1, column=0, sticky="ew")
        return txt

    def _build_usage_summary_tab(self):
        fr = ttk.Frame(self.tabs)
        self.tabs.add(fr, text="Materials")
        fr.rowconfigure(1, weight=1)
        fr.columnconfigure(0, weight=1)
        top = ttk.Frame(fr, padding=(4, 4))
        top.grid(row=0, column=0, sticky="ew")
        ttk.Label(top, text="Materials update automatically from the editable Plan.").pack(side="left", padx=(0, 10))
        ttk.Button(top, text="Step full", command=lambda: self._set_material_pane("step")).pack(side="left", padx=3)
        ttk.Button(top, text="AA full", command=lambda: self._set_material_pane("aa")).pack(side="left", padx=3)
        ttk.Button(top, text="Reagent full", command=lambda: self._set_material_pane("reagent")).pack(side="left", padx=3)
        ttk.Button(top, text="Solvent full", command=lambda: self._set_material_pane("solvent")).pack(side="left", padx=3)
        ttk.Button(top, text="Balanced", command=lambda: self._set_material_pane("balanced")).pack(side="left", padx=3)

        paned = ttk.PanedWindow(fr, orient="vertical")
        self.material_paned = paned
        paned.grid(row=1, column=0, sticky="nsew", padx=4, pady=3)

        step_box = ttk.Labelframe(paned, text="Step Material Usage", padding=6)
        aa_box = ttk.Labelframe(paned, text="Amino Acid / Unit Usage", padding=6)
        reagent_box = ttk.Labelframe(paned, text="Reagent / Base / Catalyst Usage", padding=6)
        solvent_box = ttk.Labelframe(paned, text="Solvent Usage", padding=6)
        for box in (step_box, aa_box, reagent_box, solvent_box):
            box.rowconfigure(0, weight=1)
            box.columnconfigure(0, weight=1)
        self.material_tree = self._tree_in_frame(step_box, self.MATERIAL_COLUMNS)
        self.aa_summary_tree = self._tree_in_frame(aa_box, ["material", "planned_mmol", "MW", "calculated_g", "actual_used_g"])
        self.reagent_summary_tree = self._tree_in_frame(reagent_box, ["material", "class", "MW", "density_g_per_mL", "planned_mmol", "planned_g", "planned_mL", "actual_used"])
        self.solvent_summary_tree = self._tree_in_frame(solvent_box, ["solvent", "planned_mL", "use_count", "note"])
        paned.add(step_box, weight=5)
        paned.add(aa_box, weight=2)
        paned.add(reagent_box, weight=2)
        paned.add(solvent_box, weight=2)

    def _set_material_pane(self, mode: str):
        try:
            self.material_paned.update_idletasks()
            h = max(420, self.material_paned.winfo_height())
            layouts = {
                # Full buttons give one material table most of the vertical workspace.
                # The other panes remain visible as thin handles so the user can recover them manually.
                "step": (0.86, 0.91, 0.96),
                "aa": (0.06, 0.86, 0.93),
                "reagent": (0.06, 0.13, 0.88),
                "solvent": (0.05, 0.10, 0.18),
                "balanced": (0.38, 0.60, 0.80),
            }
            a, b, c = layouts.get(mode, layouts["balanced"])
            self.material_paned.sashpos(0, int(h * a))
            self.material_paned.sashpos(1, int(h * b))
            self.material_paned.sashpos(2, int(h * c))
        except Exception as e:
            self._log(f"Material pane resize warning: {e}\n")

    def _build_project_sheet_tab(self):
        fr = ttk.PanedWindow(self.tabs, orient="vertical")
        self.tabs.add(fr, text="Project")
        calc_box = ttk.Labelframe(fr, text="Calculators", padding=4)
        sheet_box = ttk.Labelframe(fr, text="Project Sheets", padding=4)
        calc_box.rowconfigure(0, weight=1); calc_box.rowconfigure(1, weight=1); calc_box.columnconfigure(0, weight=1)
        sheet_box.rowconfigure(0, weight=1); sheet_box.columnconfigure(0, weight=1)

        load_box = ttk.Labelframe(calc_box, text="Loading Calculator", padding=4)
        cleave_box = ttk.Labelframe(calc_box, text="Cleavage Calculator", padding=4)
        for box in (load_box, cleave_box):
            box.rowconfigure(0, weight=1); box.columnconfigure(0, weight=1)
        load_box.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        cleave_box.grid(row=1, column=0, sticky="nsew", padx=2, pady=2)
        self.loading_text = self._text_in_frame(load_box)
        self.cleavage_text = self._text_in_frame(cleave_box)

        sheets = ttk.Notebook(sheet_box)
        sheets.grid(row=0, column=0, sticky="nsew")
        transfer_box = ttk.Frame(sheets); production_box = ttk.Frame(sheets); operation_box = ttk.Frame(sheets)
        for box in (transfer_box, production_box, operation_box):
            box.rowconfigure(0, weight=1); box.columnconfigure(0, weight=1)
        sheets.add(transfer_box, text="Transfer")
        sheets.add(production_box, text="Production")
        sheets.add(operation_box, text="Operation")
        self.transfer_text = self._text_in_frame(transfer_box)
        self.production_text = self._text_in_frame(production_box)
        self.form_text = self._text_in_frame(operation_box)

        fr.add(calc_box, weight=1)
        fr.add(sheet_box, weight=2)

    def _build_checklist_tab(self):
        fr = ttk.Frame(self.tabs)
        self.tabs.add(fr, text="Checklist")
        fr.rowconfigure(1, weight=2); fr.rowconfigure(2, weight=1); fr.columnconfigure(0, weight=1)
        top = ttk.Frame(fr, padding=(4, 3))
        top.grid(row=0, column=0, sticky="ew")
        self.checklist_progress_var = tk.DoubleVar(value=0.0)
        self.checklist_progress_label = ttk.Label(top, text="Progress: 0/0 (0%)")
        self.checklist_progress_label.pack(side="left", padx=(0, 10))
        self.checklist_progress_bar = ttk.Progressbar(top, variable=self.checklist_progress_var, maximum=100, length=280)
        self.checklist_progress_bar.pack(side="left", padx=(0, 10))
        ttk.Label(top, text="Toggle rows with double-click or Space").pack(side="left", padx=(0, 10))
        ttk.Button(top, text="Select All = Yes", command=self.select_all_progress_rows).pack(side="left", padx=3)
        ttk.Button(top, text="Selected = Yes", command=self.selected_progress_rows_yes).pack(side="left", padx=3)
        ttk.Button(top, text="Mark Until Selection", command=self.mark_until_selected_progress_row).pack(side="left", padx=3)
        ttk.Button(top, text="Clear All", command=self.clear_all_progress_rows).pack(side="left", padx=3)
        ttk.Button(top, text="Progress full", command=lambda: self._set_checklist_pane("progress")).pack(side="left", padx=3)
        ttk.Button(top, text="Sheet full", command=lambda: self._set_checklist_pane("sheet")).pack(side="left", padx=3)
        ttk.Button(top, text="Balanced", command=lambda: self._set_checklist_pane("balanced")).pack(side="left", padx=3)
        progress_box = ttk.Labelframe(fr, text="Bench Checklist Progress", padding=4)
        progress_box.grid(row=1, column=0, sticky="nsew", padx=4, pady=3)
        progress_box.rowconfigure(0, weight=1); progress_box.columnconfigure(0, weight=1)
        self.progress_tree = self._tree_in_frame(progress_box, ["line", "done", "checked_at", "operation", "unit", "next_step", "note"])
        self.progress_tree.bind("<Double-1>", self.toggle_progress_row)
        self.progress_tree.bind("<space>", self.toggle_progress_row)
        printable_box = ttk.Labelframe(fr, text="Printable Bench Sheet", padding=4)
        printable_box.grid(row=2, column=0, sticky="nsew", padx=4, pady=3)
        printable_box.rowconfigure(0, weight=1); printable_box.columnconfigure(0, weight=1)
        self.check_text = self._text_in_frame(printable_box)
        self.next_text = self.check_text

    def _set_checklist_pane(self, mode: str):
        try:
            if mode == "progress":
                self.tabs.nametowidget(self.tabs.select()).rowconfigure(1, weight=8)
                self.tabs.nametowidget(self.tabs.select()).rowconfigure(2, weight=1)
            elif mode == "sheet":
                self.tabs.nametowidget(self.tabs.select()).rowconfigure(1, weight=1)
                self.tabs.nametowidget(self.tabs.select()).rowconfigure(2, weight=6)
            else:
                self.tabs.nametowidget(self.tabs.select()).rowconfigure(1, weight=2)
                self.tabs.nametowidget(self.tabs.select()).rowconfigure(2, weight=1)
        except Exception as e:
            self._log(f"Checklist pane resize warning: {e}\n")

    def _build_log_tab(self):
        fr = ttk.Frame(self.tabs)
        self.tabs.add(fr, text="Log")
        fr.rowconfigure(1, weight=1); fr.columnconfigure(0, weight=1)
        top = ttk.Frame(fr, padding=(4, 3))
        top.grid(row=0, column=0, sticky="ew")
        ttk.Button(top, text="ML log full", command=lambda: self._set_log_pane("ml")).pack(side="left", padx=3)
        ttk.Button(top, text="App log full", command=lambda: self._set_log_pane("app")).pack(side="left", padx=3)
        ttk.Button(top, text="Balanced", command=lambda: self._set_log_pane("balanced")).pack(side="left", padx=3)
        paned = ttk.PanedWindow(fr, orient="vertical")
        self.log_paned = paned
        paned.grid(row=1, column=0, sticky="nsew")
        ml_box = ttk.Labelframe(paned, text="ML-ready Log", padding=4)
        log_box = ttk.Labelframe(paned, text="Application Log", padding=4)
        for box in (ml_box, log_box):
            box.rowconfigure(0, weight=1); box.columnconfigure(0, weight=1)
        self.ml_text = self._text_in_frame(ml_box)
        self.log_text = self._text_in_frame(log_box)
        paned.add(ml_box, weight=1); paned.add(log_box, weight=1)

    def _set_log_pane(self, mode: str):
        try:
            self.log_paned.update_idletasks()
            h = max(300, self.log_paned.winfo_height())
            pos = int(h * (0.82 if mode == "ml" else 0.18 if mode == "app" else 0.50))
            self.log_paned.sashpos(0, pos)
        except Exception as e:
            self._log(f"Log pane resize warning: {e}\n")

    def _input(self):
        return PlanInput(
            sequence=self.seq.get().strip(),
            resin=self.resin.get(),
            scale_mmol=float(self.scale.get()),
            resin_loading_mmol_g=float(self.loading.get()),
            coupling_eq=float(self.coupling_eq.get()),
            ac_eq=float(self.modifier_eq.get()),
            default_coupling_repeats=int(self.coupling_repeats.get()),
            default_modifier_repeats=int(self.modifier_repeats.get()),
            default_coupling_reagent=self.default_reagent.get().strip(),
            default_catalyst=self.default_catalyst.get().strip(),
            default_base=self.default_base.get().strip(),
            default_reaction_solvent=self.default_solvent1.get().strip(),
            step_overrides_text="",
        )


    def _compound_row_for_unit(self, token: str):
        """Return compound DB row for standard AA / modifier token when available."""
        try:
            if not hasattr(self, "_compound_lookup_cache"):
                p = APP / "data" / "compounds.csv"
                df = pd.read_csv(p, encoding="utf-8-sig")
                cache = {}
                for _, row in df.iterrows():
                    key = str(row.get("Token", "")).strip()
                    if key:
                        cache[key.upper()] = row.to_dict()
                self._compound_lookup_cache = cache
            return self._compound_lookup_cache.get(str(token or "").strip().upper(), {})
        except Exception:
            return {}

    def _protected_name_for_token(self, token: str) -> str:
        row = self._compound_row_for_unit(token)
        return str(row.get("Reagent/protected form") or token).strip()

    def _mw_for_token(self, token: str) -> float:
        row = self._compound_row_for_unit(token)
        try:
            return float(row.get("Reagent MW (g/mol)") or 0)
        except Exception:
            return 0.0

    def _swell_solvent_for_resin(self) -> str:
        """Swell solvent follows loading solvent family.

        - 2-CTC/trityl: DCM swell/loading.
        - Amide/Wang/Rink-type Fmoc resin: DMF swell/loading by default.
        """
        return "DCM" if self._resin_family_text() == "CTC/Trityl" else "DMF"

    def _resin_family_text(self) -> str:
        r = str(self.resin.get() or "").lower()
        if "ctc" in r or "trityl" in r:
            return "CTC/Trityl"
        return "Amide"

    def _loading_dissolve_solvent_for_resin(self) -> str:
        """Default solvent system used to dissolve the loading amino acid.

        2-CTC/trityl loading often uses a DCM-rich system; this planner exposes
        the default as 90% DCM / 10% DMF because users may dissolve the amino acid
        in a small DMF fraction while keeping the loading condition DCM-rich.
        Amide/Rink/Wang workflows default to DMF.
        """
        if self._resin_family_text() == "CTC/Trityl":
            return str(getattr(self, "default_loading_dissolve_solvent", tk.StringVar(value="90% DCM / 10% DMF")).get() or "90% DCM / 10% DMF")
        return str(getattr(self, "default_coupling_solution_solvent", tk.StringVar(value="DMF")).get() or "DMF")

    def _is_solid_reagent_name(self, name: str) -> bool:
        """True for solid reagents that should show a dissolve solvent/volume."""
        n = str(name or "").strip()
        if not n:
            return False
        return not self._is_liquid_like(n)

    def _default_dissolve_volume(self, name: str, phase: str = "") -> float:
        """Default preparation volume for dissolving solid units/reagents.

        This is intentionally editable. It uses the same mL/mmol scale basis as
        the reaction/wash model so the table always shows a visible preparation
        volume for amino acids, coupling reagents, catalysts, labels, and loading
        units.
        """
        try:
            return round(float(self.scale.get()) * float(self.ml_per_mmol.get()), 4)
        except Exception:
            return 0.0

    def _split_solution_name(self, solvent_name: str, total_ml: float):
        """Return component solvent rows for a solution string.

        Supports common 2-CTC loading notation such as '90% DCM / 10% DMF' or
        '10% DMF/DCM'. If the composition cannot be parsed, returns the original
        solvent as a single component.
        """
        s = str(solvent_name or "").strip()
        if not s or total_ml <= 0:
            return []
        u = s.upper().replace(" ", "")
        if "90%DCM" in u and "10%DMF" in u:
            return [("DCM", total_ml * 0.90, "90% of DCM-rich loading solution"), ("DMF", total_ml * 0.10, "10% of DCM-rich loading solution")]
        if "10%DMF" in u and "DCM" in u:
            return [("DCM", total_ml * 0.90, "90% of DCM-rich loading solution"), ("DMF", total_ml * 0.10, "10% of DCM-rich loading solution")]
        return [(s, total_ml, "dissolution/solution preparation solvent")]

    def _default_counts_for_row(self, step: int, total_steps: int, phase: str, unit_name: str, needs_depro: bool | None = None) -> tuple[str, int, str, int]:
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
        phase_l = str(phase or "").lower()
        unit_u = str(unit_name or "").upper()
        is_non_fmoc_final = self._is_ac_unit(unit_name) or self._is_chemical_label_like_unit(unit_name)
        if "branch first" in phase_l:
            return "DMF", 2, "", 0
        if "loading" in phase_l and self._resin_family_text() == "CTC/Trityl":
            return "DCM", 1, "", 0
        if is_last and is_non_fmoc_final:
            return "", 0, "", 0
        return "DMF", 2, "", 0

    def _final_wash_specs(self):
        """Return final wash sequence after last deprotection or final modifier.

        Default lab practice: DMF x3 and DCM x3. Some labs additionally use
        MeOH x3; this is controlled by the Final MeOH wash count field.
        """
        specs = [("DMF", 3), ("DCM", 3)]
        meoh_count = self._to_int(getattr(self, "final_meoh_count", tk.IntVar(value=0)).get(), 0)
        if meoh_count > 0:
            specs.append(("MeOH", meoh_count))
        return specs

    def _last_fmoc_step_no(self, plan_df: pd.DataFrame):
        last = None
        for _, r in plan_df.iterrows():
            step = str(r.get("No", ""))
            meta = self._row_meta_by_no.get(step, {})
            row_dict = r.to_dict() if hasattr(r, "to_dict") else dict(r)
            if self._is_non_fmoc_modifier_row(row_dict, meta):
                continue
            if self._needs_deprotection_for_row(row_dict, meta):
                last = step
        return last

    def _last_non_fmoc_final_step_no(self, plan_df: pd.DataFrame):
        for _, r in list(plan_df.iterrows())[::-1]:
            step = str(r.get("No", ""))
            meta = self._row_meta_by_no.get(step, {})
            if self._is_non_fmoc_modifier_row(r.to_dict() if hasattr(r, "to_dict") else dict(r), meta):
                return step
        return None

    def rebuild_table(self):
        try:
            inp = self._input()
            df = generate_excel_like_synthesis_table(inp)
            self.tree.delete(*self.tree.get_children())
            self._row_meta_by_no = {}
            total_steps = len(df.index) if df is not None else 0
            for _, row in df.iterrows():
                step = int(row.get("step", len(self.tree.get_children())+1))
                unit = str(row.get("unit", ""))
                phase = str(row.get("phase", ""))
                is_mod = any(x in phase.lower() for x in ["modifier", "n-term", "label", "chemical"])
                eq = float(row.get("reagent_eq", self.coupling_eq.get()) or 0)
                repeat = int(float(row.get("coupling_repeat", self.coupling_repeats.get()) or 1))
                mw = float(row.get("reagent_mw", 0) or 0)
                calc_mmol = float(self.scale.get()) * eq * repeat
                name = self._normalize_unit_display_name(str(row.get("protected_reagent", "")) or unit)
                amount_basis_name, amount_basis_mw, amount_basis_hint = self._amount_basis_for_unit(name, phase, str(row.get("coupling_reagent", "")), mw)
                if amount_basis_mw:
                    mw = amount_basis_mw
                amount_display, calc_g, calc_ml, amount_unit = self._format_unit_amount(calc_mmol, mw, name, amount_basis_hint)
                note = str(row.get("note", ""))
                if is_mod:
                    note = (note + " | terminal chemical/label/tag/cap step; chemical modifier row after final Fmoc removal and DMF x6; no post-coupling deprotection or default DCM final wash").strip(" |")
                if any(x in unit.upper() for x in ["FITC", "BIOTIN", "CY", "FAM", "TAMRA"]):
                    note = (note + " | label reagent form must be verified; edit eq/reagent/base manually").strip(" |")
                temp_row_for_logic = {"No": step, "Unit name": name}
                temp_meta_for_logic = {"Phase": phase, "Note": note}
                needs_depro = self._needs_deprotection_for_row(temp_row_for_logic, temp_meta_for_logic)
                if not needs_depro:
                    if self._is_first_synthesis_row(temp_row_for_logic) and not self._is_non_fmoc_modifier_row(temp_row_for_logic, temp_meta_for_logic):
                        note = (note + " | trityl/2-CTC first loading row; no initial Fmoc deprotection").strip(" |")
                solvent_defaults = self._default_counts_for_row(step, total_steps, phase, name, needs_depro=needs_depro)
                item = {
                    "No": step,
                    "Unit name": name,
                    "Unit eq": eq,
                    "Unit amount(g)": round(calc_g, 4) if calc_g else "",
                    "Unit volume(mL)": round(calc_ml, 4) if calc_ml else "",
                    "Coupling reagent 1": "" if self._is_ac_unit(name) else row.get("coupling_reagent", self.default_reagent.get()),
                    "Coupling reagent 1 eq": "" if self._is_ac_unit(name) else self.default_reagent_eq.get(),
                    "Coupling reagent 1 count": 0 if self._is_ac_unit(name) else self.default_reagent_count.get(),
                    "Coupling reagent 2 / catalyst": "" if self._is_ac_unit(name) else row.get("catalyst", self.default_catalyst.get()),
                    "Coupling reagent 2 / catalyst eq": "" if self._is_ac_unit(name) else (self.default_catalyst_eq.get() if row.get("catalyst", self.default_catalyst.get()) else ""),
                    "Coupling reagent 2 / catalyst count": 0 if self._is_ac_unit(name) else self.default_catalyst_count.get(),
                    "Coupling base": row.get("base", self.default_base.get()),
                    "Coupling base eq": self.default_base_eq.get() if row.get("base", self.default_base.get()) else "",
                    "Coupling base count": self.default_base_count.get() if row.get("base", self.default_base.get()) else 0,
                    "Coupling cocktail solvent": self._loading_dissolve_solvent_for_resin() if "loading" in phase.lower() else self.default_coupling_solution_solvent.get(),
                    "Coupling cocktail volume(mL)": self._default_dissolve_volume(name, phase),
                    "Deprotection base": self.default_depro.get() if needs_depro else "",
                    "Deprotection ratio": self.default_depro_ratio.get() if needs_depro else "",
                    "Deprotection count": self.default_depro_count.get() if needs_depro else 0,
                    "Solvent 1": solvent_defaults[0],
                    "Solvent 1 count": solvent_defaults[1],
                    "Solvent 2": solvent_defaults[2],
                    "Solvent 2 count": solvent_defaults[3],
                    "Repeat": repeat,
                    "MW": round(mw, 3) if mw else "",
                    "calculated mmol": round(calc_mmol, 4),
                    "calculated g": round(calc_g, 4),
                    "Phase": phase,
                    "Note": note,
                }
                self._row_meta_by_no[str(step)] = {"MW": round(mw, 3) if mw else "", "calculated mmol": round(calc_mmol, 4), "calculated g": round(calc_g, 4), "calculated mL": round(calc_ml, 4), "amount_unit": amount_unit, "Phase": phase, "Note": note}
                self.tree.insert("", "end", values=[item.get(c, "") for c in self.PLAN_COLUMNS])
            self._append_branch_rows_if_enabled()
            self.refresh_outputs_from_tree()
            self._log("Parsed sequence and built editable SPPS table.\n")
        except Exception as e:
            messagebox.showerror("Parse error", str(e))
            self._log("ERROR parse: " + str(e) + "\n")


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
            arm_raw = str(self.branch_arm.get() or "").strip()
            tokens = tokenize_core_sequence(arm_raw)
            if not tokens:
                return
            start_no = len(self.tree.get_children()) + 1
            pg = str(self.branch_pg.get() or "Mtt")
            point = str(self.branch_point.get() or "").strip() or "branch point"
            condition = str(self.branch_depro_condition.get() or "").strip()
            cond_u = condition.upper()
            if "HYDRAZINE" in cond_u:
                depro_base, ratio, solv1 = "Hydrazine", "hydrazine/DMF", "DMF"
            elif "PD" in cond_u or "ALLOC" in cond_u:
                depro_base, ratio, solv1 = "Pd/phenylsilane", "Alloc removal in DCM", "DCM"
            else:
                depro_base, ratio, solv1 = "TFA/TIS", "dilute TFA/TIS/DCM", "DCM"
            d = {c: "" for c in self.PLAN_COLUMNS}
            d.update({
                "No": start_no,
                "Unit name": f"Branch PG removal ({pg} @ {point})",
                "Unit eq": 0,
                "Unit amount(g)": "",
                "Unit volume(mL)": "",
                "Coupling reagent 1": "",
                "Coupling reagent 1 eq": "",
                "Coupling reagent 1 count": 0,
                "Coupling reagent 2 / catalyst": "",
                "Coupling reagent 2 / catalyst eq": "",
                "Coupling reagent 2 / catalyst count": 0,
                "Coupling base": "",
                "Coupling base eq": "",
                "Coupling base count": 0,
                "Deprotection base": depro_base,
                "Deprotection ratio": ratio,
                "Deprotection count": 1,
                "Solvent 1": solv1,
                "Solvent 1 count": 3,
                "Solvent 2": "",
                "Solvent 2 count": 0,
                "Repeat": 1,
            })
            self._row_meta_by_no[str(start_no)] = {"MW": "", "calculated mmol": 0, "calculated g": 0, "calculated mL": 0, "amount_unit": "", "Phase": "Branch deprotection", "Note": f"Selective side-chain protecting group removal before branch arm coupling; {condition}"}
            self.tree.insert("", "end", values=[d.get(c, "") for c in self.PLAN_COLUMNS])
            step_no = start_no + 1
            for branch_i, tok in enumerate(reversed(tokens), start=1):
                protected = self._protected_name_for_token(tok)
                mw = self._mw_for_token(tok)
                eq = float(self.coupling_eq.get())
                repeat = int(self.coupling_repeats.get())
                mmol = float(self.scale.get()) * eq * repeat
                amount_display, calc_g, calc_ml, amount_unit = self._format_unit_amount(mmol, mw, protected, protected)
                is_first_branch_coupling = branch_i == 1
                phase_label = "Branch first coupling" if is_first_branch_coupling else "Branch coupling"
                row = {c: "" for c in self.PLAN_COLUMNS}
                row.update({
                    "No": step_no,
                    "Unit name": protected,
                    "Unit eq": eq,
                    "Unit amount(g)": round(calc_g, 4) if calc_g else "",
                    "Unit volume(mL)": round(calc_ml, 4) if calc_ml else "",
                    "Coupling reagent 1": self.default_reagent.get(),
                    "Coupling reagent 1 eq": self.default_reagent_eq.get(),
                    "Coupling reagent 1 count": self.default_reagent_count.get(),
                    "Coupling reagent 2 / catalyst": self.default_catalyst.get(),
                    "Coupling reagent 2 / catalyst eq": self.default_catalyst_eq.get(),
                    "Coupling reagent 2 / catalyst count": self.default_catalyst_count.get(),
                    "Coupling base": self.default_base.get(),
                    "Coupling base eq": self.default_base_eq.get() if self.default_base.get() else "",
                    "Coupling base count": self.default_base_count.get() if self.default_base.get() else 0,
                    "Coupling cocktail solvent": self.default_coupling_solution_solvent.get(),
                    "Coupling cocktail volume(mL)": self._default_dissolve_volume(protected, phase_label),
                    "Deprotection base": "" if is_first_branch_coupling else self.default_depro.get(),
                    "Deprotection ratio": "" if is_first_branch_coupling else self.default_depro_ratio.get(),
                    "Deprotection count": 0 if is_first_branch_coupling else self.default_depro_count.get(),
                    "Solvent 1": self.default_solvent1.get(),
                    "Solvent 1 count": 2,
                    "Solvent 2": "",
                    "Solvent 2 count": 0,
                    "Repeat": repeat,
                })
                note = f"Branch arm coupling at {point}; branch arm={arm_raw}; protecting group={pg}"
                if is_first_branch_coupling:
                    note += "; first branch residue couples to deprotected side-chain handle without extra Fmoc deprotection"
                self._row_meta_by_no[str(step_no)] = {"MW": round(mw, 3) if mw else "", "calculated mmol": round(mmol, 4), "calculated g": round(calc_g, 4), "calculated mL": round(calc_ml, 4), "amount_unit": amount_unit, "Phase": phase_label, "Note": note}
                self.tree.insert("", "end", values=[row.get(c, "") for c in self.PLAN_COLUMNS])
                step_no += 1
        except Exception as e:
            self._log("Branch mode append warning: " + str(e) + "\n")

    def tree_rows(self) -> list[dict]:
        rows = []
        for child in self.tree.get_children():
            vals = list(self.tree.item(child, "values"))
            rows.append({col: vals[i] if i < len(vals) else "" for i, col in enumerate(self.PLAN_COLUMNS)})
        return rows

    def on_tree_edit(self, row_id, col_name, new_value):
        self.recalculate_row(row_id)
        self.refresh_outputs_from_tree()

    def _to_float(self, v, default=0.0):
        return self._amount_numeric(v, default)

    def _to_int(self, v, default=0):
        try:
            return int(float(str(v).replace(",", "")))
        except Exception:
            return default

    LIQUID_DENSITY = {
        "DIC": 0.815, "AC2O": 1.08, "ACETIC ANHYDRIDE": 1.08, "ACOH": 1.05, "ACETIC ACID": 1.05,
        "DIEA": 0.742, "DIPEA": 0.742, "NMM": 0.92, "TEA": 0.726, "PYRIDINE": 0.982,
        "2,4,6-COLLIDINE": 0.917, "2,6-LUTIDINE": 0.925, "PIPERIDINE": 0.862, "DBU": 1.02,
        "DMF": 0.944, "NMP": 1.03, "DCM": 1.33, "MEOH": 0.792, "ETOH": 0.789,
        "I-PROH": 0.786, "ACN": 0.786, "THF": 0.889, "DMSO": 1.10, "TFA": 1.49,
        "TIS": 0.773, "WATER": 1.00, "ETHER": 0.713, "DIETHYL ETHER": 0.713, "MTBE": 0.740,
    }

    def _amount_numeric(self, value, default=0.0):
        """Parse numeric value from a cell that may contain 'g' or 'mL'."""
        try:
            if value is None or str(value).strip() == "":
                return default
            m = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", str(value).replace(",", ""))
            return float(m.group(0)) if m else default
        except Exception:
            return default

    def _is_amount_ml(self, value) -> bool:
        return "ml" in str(value or "").lower()

    def _is_liquid_like(self, name: str) -> bool:
        s = str(name or "").upper()
        if not s:
            return False
        liquid_markers = ["AC2O", "ACOH", "ACETIC", "DIC", "DIEA", "DIPEA", "NMM", "TEA", "PYRIDINE", "COLLIDINE", "LUTIDINE", "PIPERIDINE", "DBU", "DMF", "NMP", "DCM", "MEOH", "ETOH", "I-PROH", "ACN", "THF", "DMSO", "TFA", "TIS", "WATER", "ETHER", "MTBE"]
        return any(m in s for m in liquid_markers)

    def _density_for(self, name: str) -> float:
        s = str(name or "").upper()
        for key, dens in self.LIQUID_DENSITY.items():
            if key in s:
                return dens
        return 1.0

    def _is_ac_unit(self, name: str) -> bool:
        u = str(name or "").strip().upper()
        key = self._unit_key(name) if hasattr(self, "_unit_key") else re.sub(r"[^A-Za-z0-9]", "", u)
        return (
            u in {"AC", "AC-", "ACETYL", "ACETYL CAP", "AC / ACETYL CAP"}
            or key in {"AC", "ACETYL", "ACETYLCAP", "ACETICANHYDRIDEAC2OFORNTERMINALACETYLATION", "ACETICANHYDRIDE", "AC2O"}
            or "ACETIC ANHYDRIDE" in u
        )

    def _amount_basis_for_unit(self, display_name: str, phase: str, coupling_reagent: str, mw: float):
        """Return calculation basis for the unit row.

        The editable row should show the user-facing unit such as 'Ac', but
        N-terminal acetylation is calculated from the actual liquid reagent
        Acetic anhydride (Ac2O) by default. Ac2O/AcOH must not appear in the
        coupling reagent columns.
        """
        if self._is_ac_unit(display_name):
            return "Ac2O", 102.09, "Ac2O"
        return display_name, mw, display_name

    def _format_unit_amount(self, mmol: float, mw: float, display_name: str, coupling_reagent: str = ""):
        """Return display amount, g, mL, and unit for editable plan.

        Solid Fmoc-AA/modifier reagents are reported as g. Liquid/solution-like
        reagents such as Ac2O/AcOH are reported as mL using density.
        """
        reagent_hint = coupling_reagent or display_name
        grams = (float(mmol) * float(mw) / 1000.0) if mw else 0.0
        if self._is_liquid_like(reagent_hint):
            dens = self._density_for(reagent_hint)
            ml = grams / dens if dens else 0.0
            return f"{ml:.4f} mL", 0.0, ml, "mL"
        return round(grams, 4), grams, 0.0, "g"

    # v2.0.0 recheck: separate amino-acid-like linkers from terminal chemical labels.
    # Linkers are synthesis units and should behave like AA coupling rows.
    # Labels/caps/dyes are terminal or side-chain chemical modifier rows.
    AA_LIKE_LINKER_TOKENS = {
        "AHX", "AEEA", "CHA", "AIB", "NLE", "ORN", "CIT", "HYP", "DAB", "NAL",
        "BALA", "B-ALA", "GABA", "PEG1", "PEG2", "PEG3", "PEG4", "PEG6", "PEG8",
        "PEG12", "PEG24", "G4S", "G4SX2", "SAR", "BA", "BETA-ALA",
    }
    CHEMICAL_LABEL_TOKENS = {
        "AC", "AC-", "ACETYL", "ACETYL CAP", "AC / ACETYL CAP",
        "FITC", "BIOTIN", "BIOTIN-NHS", "BIOTIN ACID", "BIOTINCAP",
        "FAM", "5-FAM", "6-FAM", "FAM-NHS", "TAMRA", "ROX",
        "CY3", "CY5", "CY5_5", "CY7", "DABCYL", "BHQ", "BHQ1", "BHQ2",
        "DOTA", "NOTA", "DFO", "NBD", "DANSYL", "BODIPY", "EDANS",
        "PAL", "PALMITIC ACID", "PALMITICACID", "PALMITOYL", "MYR", "MYRISTIC ACID", "MYRISTICACID", "MYRISTOYL",
        "STEAR", "STEARIC ACID", "STEARICACID", "OLE", "OLEIC ACID", "OLEICACID",
        "GAL", "GALLIC ACID", "GALLICACID", "GALLOYL", "NIC", "NICOTINIC ACID", "NICOTINICACID",
        "CAF", "CAFFEIC ACID", "CAFFEICACID", "CAFFEOYL",
        "MALEIMIDE", "NHS",
    }

    CHEMICAL_DISPLAY_NAMES = {
        "PAL": "Palmitic acid", "PALMITICACID": "Palmitic acid", "PALMITOYL": "Palmitic acid",
        "MYR": "Myristic acid", "MYRISTICACID": "Myristic acid", "MYRISTOYL": "Myristic acid",
        "GAL": "Gallic acid", "GALLICACID": "Gallic acid", "GALLOYL": "Gallic acid",
        "CAF": "Caffeic acid", "CAFFEICACID": "Caffeic acid", "CAFFEOYL": "Caffeic acid",
        "NIC": "Nicotinic acid", "NICOTINICACID": "Nicotinic acid", "NICOTINOYL": "Nicotinic acid",
        "STEAR": "Stearic acid", "STEARICACID": "Stearic acid", "STE": "Stearic acid",
        "OLE": "Oleic acid", "OLEICACID": "Oleic acid",
    }

    @staticmethod
    def _unit_key(name: str) -> str:
        return re.sub(r"[^A-Za-z0-9]", "", str(name or "")).upper()

    def _normalize_unit_display_name(self, name: str) -> str:
        s = str(name or "").strip()
        u = self._unit_key(s)
        if u in {"AC", "ACETYL", "ACETYL CAP".replace(" ", ""), "ACETICACID"}:
            return "Ac"
        if u in self.CHEMICAL_DISPLAY_NAMES:
            return self.CHEMICAL_DISPLAY_NAMES[u]
        return s

    def _is_linker_like_unit(self, name: str) -> bool:
        u = str(name or "").strip().upper()
        return u in self.AA_LIKE_LINKER_TOKENS or u.startswith("PEG") or u.startswith("G4S")

    def _is_chemical_label_like_unit(self, name: str) -> bool:
        u = str(name or "").strip().upper()
        key = self._unit_key(name)
        if u in self.CHEMICAL_LABEL_TOKENS or key in self.CHEMICAL_LABEL_TOKENS:
            return True
        # Hyphenated activated label/cap forms are chemical-like.
        if any(x in u for x in ["FITC", "FAM", "TAMRA", "BIOTIN", "CY3", "CY5", "CY7", "DOTA", "NOTA", "PAL", "MYR", "NHS"]):
            return not self._is_linker_like_unit(u)
        return False

    def _resin_needs_initial_deprotection(self) -> bool:
        """Return whether the selected resin requires an initial Fmoc deprotection.

        Practical rule used in this planner:
        - Trityl / 2-CTC loading does not have an initial Fmoc handle on resin.
        - Wang and amide/Rink-type resins are treated as Fmoc resins and require
          initial deprotection before the first coupling.
        """
        r = str(self.resin.get() or "").lower()
        if "trityl" in r or "2-ctc" in r or "ctc" in r:
            return False
        return True

    def _is_first_synthesis_row(self, row_dict: dict) -> bool:
        try:
            return int(float(str(row_dict.get("No", "0")))) == 1
        except Exception:
            return False

    def _needs_deprotection_for_row(self, row_dict: dict, meta: dict | None = None) -> bool:
        """Return whether a pre-reaction Fmoc deprotection is scheduled.

        Important distinction:
        - Final Ac/chemical/label/modifier rows do not need a *post-coupling*
          deprotection, but they usually need a pre-reaction Fmoc deprotection to
          expose the N-terminus before the final non-Fmoc reaction.
        - 2-CTC/trityl first loading and the first branch arm coupling start from an
          already available attachment point and skip this initial Fmoc deprotection.
        """
        meta = meta or {}
        phase = str(meta.get("Phase", row_dict.get("Phase", ""))).lower()
        if "branch first" in phase or "branch deprotection" in phase:
            return False
        # Any explicit final N-terminal chemical/label/tag/cap row is handled
        # as a practical coupling/capping unit.  It needs the preceding Fmoc group
        # removed immediately before the row, followed by DMF wash x6, just like
        # a terminal chemical modifier setup.  It still must not receive a *post-row*
        # deprotection.
        if self._is_non_fmoc_modifier_row(row_dict, meta):
            return True
        if self._is_first_synthesis_row(row_dict) and not self._resin_needs_initial_deprotection():
            return False
        return True

    def _is_non_fmoc_modifier_row(self, row_dict: dict, meta: dict | None = None) -> bool:
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
        phase = str(meta.get("Phase", row_dict.get("Phase", ""))).lower()
        name = str(row_dict.get("Unit name", "")).strip()
        if self._is_linker_like_unit(name):
            return False
        if self._is_ac_unit(name) or self._is_chemical_label_like_unit(name):
            return True
        # Trust explicit engine phases for true terminal modifier rows, but do not
        # classify rows as modifiers solely because the UI column label contains
        # the word linker.
        if any(m in phase for m in ["modifier", "label", "chemical", "n-term", "terminal", "cap"]):
            return not self._is_linker_like_unit(name)
        return False

    def recalculate_row(self, row_id):
        cols = self.PLAN_COLUMNS
        vals = list(self.tree.item(row_id, "values"))
        d = {cols[i]: vals[i] if i < len(vals) else "" for i in range(len(cols))}
        no_key = str(d.get("No", ""))
        meta = self._row_meta_by_no.get(no_key, {})

        eq = self._to_float(d.get("Unit eq"), self._to_float(d.get("Coupling reagent 1 eq"), 1.0))
        repeat = max(1, self._to_int(d.get("Repeat"), 1))
        # MW is intentionally displayed in Material Usage, not the editable plan.
        # Therefore live recalculation must read MW from the row metadata.
        mw = self._to_float(meta.get("MW"), 0.0)
        calc_mmol = self._to_float(self.scale.get(), 0.0) * eq * repeat
        amount_basis_name, amount_basis_mw, amount_basis_hint = self._amount_basis_for_unit(
            d.get("Unit name", ""), meta.get("Phase", ""), d.get("Coupling reagent 1", ""), mw
        )
        if amount_basis_mw:
            mw = amount_basis_mw
        amount_display, calc_g, calc_ml, amount_unit = self._format_unit_amount(
            calc_mmol, mw, d.get("Unit name", ""), amount_basis_hint
        )
        if not mw:
            # For manual rows without MW, preserve manually edited amount fields.
            calc_g = self._amount_numeric(d.get("Unit amount(g)", ""), 0.0)
            calc_ml = self._amount_numeric(d.get("Unit volume(mL)", ""), 0.0)
            amount_unit = "mL" if calc_ml else "g"

        d["Unit amount(g)"] = round(calc_g, 4) if calc_g else ""
        d["Unit volume(mL)"] = round(calc_ml, 4) if calc_ml else ""
        # Coupling reagent/catalyst eq fields are intentionally optional.
        # Do not auto-fill them from the AA/modifier eq: some protocols use
        # only base or a manually selected reagent system, and blank reagent eq
        # should remain blank rather than being forced.

        # Rows that truly do not require pre-reaction Fmoc removal are kept at
        # deprotection count 0. Final Ac/chemical/label/tag/cap rows now carry
        # the pre-reaction Fmoc removal themselves, followed by DMF wash x6; no
        # post-coupling deprotection is generated after the terminal reaction.
        if not self._needs_deprotection_for_row(d, meta):
            d["Deprotection count"] = 0
            d["Deprotection base"] = ""
            d["Deprotection ratio"] = ""
            if not meta.get("Note"):
                if "branch" in str(meta.get("Phase", "")).lower():
                    meta["Note"] = "first branch-arm coupling starts from the deprotected side-chain handle; no extra pre-coupling Fmoc deprotection"
                else:
                    meta["Note"] = "trityl/2-CTC first loading row; no initial Fmoc deprotection"
        elif self._is_non_fmoc_modifier_row(d, meta):
            if not meta.get("Note"):
                meta["Note"] = "non-Fmoc Ac/chemical/tag/label/modifier row; no deprotection is assigned to this row"

        meta.update({
            "MW": round(mw, 3) if mw else meta.get("MW", ""),
            "calculated mmol": round(calc_mmol, 4),
            "calculated g": round(calc_g, 4),
            "calculated mL": round(calc_ml, 4),
            "amount_unit": amount_unit,
            "Phase": meta.get("Phase", d.get("Phase", "")),
            "Note": meta.get("Note", d.get("Note", "")),
        })
        self._row_meta_by_no[no_key] = meta
        self.tree.item(row_id, values=[d.get(c, "") for c in cols])

    def refresh_outputs_from_tree(self):
        # Recalculate every row defensively before building usage tables.
        # This keeps amount(g/mL), deprotection counts, solvent counts, and resin-specific
        # Fmoc logic synchronized after any editable-cell change.
        for child in list(self.tree.get_children()):
            self.recalculate_row(child)
        rows = self.tree_rows()
        if not rows:
            self.rebuild_table()
            rows = self.tree_rows()
        plan_df = pd.DataFrame(rows)
        materials = self.materials_from_rows(plan_df)
        if (materials is None or materials.empty) and not plan_df.empty:
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
        self._write_tree(self.aa_summary_tree, aa_summary, ["material", "planned_mmol", "MW", "calculated_g", "actual_used_g"])
        self._write_tree(self.reagent_summary_tree, reagent_summary, ["material", "class", "MW", "density_g_per_mL", "planned_mmol", "planned_g", "planned_mL", "actual_used"])
        self._write_tree(self.solvent_summary_tree, solvent_summary, ["solvent", "planned_mL", "use_count", "note"])
        self._write_df(self.loading_text, loading_df)
        self._write_df(self.cleavage_text, cleavage_df)
        self._write_df(self.transfer_text, transfer_df)
        self._write_df(self.production_text, production_df)
        self._write_df(self.ml_text, ml)
        self._write_df(self.form_text, ops)
        self._write_df(self.check_text, checklist)
        self._populate_progress_tree(checklist)
        self._write_df(self.next_text, self.next_step_df())


    def amino_acid_usage_summary(self, materials: pd.DataFrame) -> pd.DataFrame:
        """Aggregate solid amino-acid / AA-like unit usage separately from solvents and reagents."""
        cols = ["material", "planned_mmol", "MW", "calculated_g", "actual_used_g"]
        if materials is None or materials.empty:
            return pd.DataFrame(columns=cols)
        df = materials.copy()
        cls = df.get("class", "").astype(str).str.lower()
        # Include amino acids / modifiers / labels / linkers that are tracked as solid unit mass.
        mask = cls.str.contains("aa/chemical|amino|modifier|label|tag|linker", regex=True, na=False)
        mask &= pd.to_numeric(df.get("planned_g", 0), errors="coerce").fillna(0) > 0
        if not mask.any():
            return pd.DataFrame(columns=cols)
        out = (df.loc[mask].groupby("material", dropna=False).agg({
            "planned_mmol": "sum",
            "MW": "first",
            "planned_g": "sum",
        }).reset_index())
        out = out.rename(columns={"planned_g": "calculated_g"})
        out["actual_used_g"] = ""
        for c in ["planned_mmol", "calculated_g"]:
            out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0).round(4)
        return out[cols]

    def reagent_usage_summary(self, materials: pd.DataFrame) -> pd.DataFrame:
        """Aggregate coupling reagents, bases, catalysts/additives, capping and deprotection reagents."""
        cols = ["material", "class", "MW", "density_g_per_mL", "planned_mmol", "planned_g", "planned_mL", "actual_used"]
        if materials is None or materials.empty:
            return pd.DataFrame(columns=cols)
        df = materials.copy()
        cls = df.get("class", "").astype(str).str.lower()
        excl = cls.str.contains("solvent|wash", regex=True, na=False)
        incl = cls.str.contains("reagent|base|catalyst|additive|deprotection|modifier", regex=True, na=False) & ~excl
        incl |= df.get("material", "").astype(str).str.contains("Ac2O|DIC|HOBt|HBTU|HATU|DIEA|DIPEA|Piperidine|TFA|TIS", case=False, regex=True, na=False)
        if not incl.any():
            return pd.DataFrame(columns=cols)
        tmp = df.loc[incl].copy()
        grouped = tmp.groupby(["material", "class"], dropna=False).agg({
            "MW": "first",
            "planned_mmol": "sum",
            "planned_g": "sum",
            "planned_mL": "sum",
        }).reset_index()
        grouped["density_g_per_mL"] = grouped["material"].apply(lambda x: self._density_for(x) if self._density_for(x) else "")
        grouped["actual_used"] = ""
        for c in ["planned_mmol", "planned_g", "planned_mL"]:
            grouped[c] = pd.to_numeric(grouped[c], errors="coerce").fillna(0).round(4)
        return grouped[cols]

    def solvent_usage_summary(self, materials: pd.DataFrame) -> pd.DataFrame:
        """Aggregate solvent consumption independently from reagent/material rows."""
        cols = ["solvent", "planned_mL", "use_count", "note"]
        if materials is None or materials.empty:
            return pd.DataFrame(columns=cols)
        df = materials.copy()
        cls = df.get("class", "").astype(str).str.lower()
        mask = cls.str.contains("solvent|wash", regex=True, na=False)
        if not mask.any():
            return pd.DataFrame(columns=cols)
        tmp = df.loc[mask].copy()
        tmp["planned_mL"] = pd.to_numeric(tmp.get("planned_mL", 0), errors="coerce").fillna(0)
        # use_count may contain floats/strings; sum only numeric values.
        tmp["_use_count_num"] = pd.to_numeric(tmp.get("use_count", 0), errors="coerce").fillna(0)
        out = tmp.groupby("material", dropna=False).agg({"planned_mL": "sum", "_use_count_num": "sum", "note": "first"}).reset_index()
        out = out.rename(columns={"material": "solvent", "_use_count_num": "use_count"})
        out["planned_mL"] = out["planned_mL"].round(4)
        out["use_count"] = out["use_count"].round(4)
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
        ml_per_mmol = self._to_float(self.ml_per_mmol.get(), 0.0)
        per_use_ml = scale * ml_per_mmol
        rows = []

        def mw_for(name: str):
            n = str(name or "").strip()
            if not n:
                return ""
            if n in self.MW_FALLBACK:
                return self.MW_FALLBACK[n]
            u = n.upper()
            for k, v in self.MW_FALLBACK.items():
                if k.upper() == u or k.upper() in u:
                    return v
            return ""

        def add(step="", material="", cls="", mmol=0, g=0, ml=0, count="", repeat="", phase="", note="", src="", mw=""):
            material = str(material or "").strip()
            if not material:
                return
            rows.append({
                "step": step,
                "material": material,
                "class": cls,
                "MW": mw if mw != "" else mw_for(material),
                "planned_mmol": round(self._to_float(mmol, 0.0), 4),
                "planned_g": round(self._to_float(g, 0.0), 4),
                "planned_mL": round(self._to_float(ml, 0.0), 4),
                "use_count": count,
                "repeat": repeat,
                "phase": phase,
                "note": note,
                "source": src,
            })

        def add_solution_components(step, solvent_name, total_ml, cls, phase, note, src, count=1):
            for solv_name, solv_ml, split_note in self._split_solution_name(solvent_name, total_ml):
                add(step=step, material=solv_name, cls=cls, ml=solv_ml, count=count,
                    phase=phase, note=(note + "; " + split_note).strip("; "), src=src)

        resin_g = scale / loading if loading else 0.0
        add(material="Resin", cls=self.resin.get(), mmol=scale, g=resin_g,
            phase="resin", note="calculated from scale/loading", src="scale/loading")
        swell_solvent = self._swell_solvent_for_resin()
        add(step="swell", material=swell_solvent, cls="resin swell solvent", ml=per_use_ml, count=1, repeat=1,
            phase="resin swell", note="Swell solvent follows resin/loading family: DCM for 2-CTC/trityl; DMF for amide/Wang/Rink-type resin.", src="resin swell")

        final_non_fmoc_step = self._last_non_fmoc_final_step_no(plan_df)
        last_fmoc_step = self._last_fmoc_step_no(plan_df)
        final_depro_added = False

        def add_final_depro_before(step_for_depro, before_step_note=""):
            nonlocal final_depro_added
            if final_depro_added or not step_for_depro:
                return
            try:
                last_row = plan_df[plan_df["No"].astype(str) == str(step_for_depro)].iloc[0]
            except Exception:
                return
            final_depro_count = self._to_int(last_row.get("Deprotection count"), self.default_depro_count.get())
            final_depro_base = last_row.get("Deprotection base", self.default_depro.get())
            final_depro_ratio = last_row.get("Deprotection ratio", self.default_depro_ratio.get())
            if final_depro_count > 0 and str(final_depro_base or "").strip():
                label = f"{step_for_depro}; final Fmoc removal"
                phase = "pre-modifier Fmoc removal" if before_step_note else "final deprotection"
                note = "Final Fmoc removal assigned to the last Fmoc-AA row; non-Fmoc Ac/chemical/tag/label/modifier rows do not receive deprotection."
                if not before_step_note:
                    note = "Final deprotection after the last Fmoc-AA coupling; followed only by final wash DMF x3 / DCM x3 / optional MeOH."
                add(step=label, material=final_depro_base, cls="final deprotection base", ml=per_use_ml * final_depro_count,
                    count=final_depro_count, phase=phase, note=note, src=f"step {step_for_depro}; final deprotection; ratio={final_depro_ratio}", mw=mw_for(final_depro_base))
                if before_step_note:
                    add(step=f"{step_for_depro}; final Fmoc removal wash", material="DMF", cls="final deprotection wash solvent",
                        ml=per_use_ml * 6, count=6, phase="pre-modifier final deprotection wash",
                        note="Before N-terminal Ac/modifier reaction: DMF wash x6 after final Fmoc removal; DCM is not used before Ac.",
                        src=f"step {step_for_depro}; pre-modifier final deprotection wash")
                final_depro_added = True

        for _, r in plan_df.iterrows():
            step = str(r.get("No", ""))
            meta = self._row_meta_by_no.get(str(step), {})
            name = str(r.get("Unit name", "") or "")
            eq = self._to_float(r.get("Unit eq"), 0)
            repeat = max(1, self._to_int(r.get("Repeat"), 1))
            mmol = scale * eq * repeat
            amount_g_cell = r.get("Unit amount(g)")
            amount_ml_cell = r.get("Unit volume(mL)")
            phase = meta.get("Phase", "")
            note = meta.get("Note", "")
            row_dict = r.to_dict() if hasattr(r, "to_dict") else dict(r)
            is_non_fmoc_final = str(step) == str(final_non_fmoc_step)
            is_last_fmoc = str(step) == str(last_fmoc_step)

            # Final chemical/label/linker/tag rows now carry their own pre-reaction
            # Fmoc removal, so do not inject a duplicate final deprotection onto the
            # preceding Fmoc-AA row.

            # Standard pre-coupling deprotection for Fmoc-AA rows and terminal modifiers.
            needs_pre_depro = self._needs_deprotection_for_row(row_dict, meta)
            depro_count = self._to_int(r.get("Deprotection count"), 0)
            if needs_pre_depro and depro_count > 0:
                depro = r.get("Deprotection base", self.default_depro.get())
                ratio = r.get("Deprotection ratio", self.default_depro_ratio.get())
                add(step=f"{step}; pre-coupling deprotection", material=depro, cls="deprotection base",
                    ml=per_use_ml * depro_count, count=depro_count, phase="pre-coupling deprotection",
                    note="STD cycle: deprotection x2 before Fmoc-AA coupling", src=f"step {step}; ratio={ratio}", mw=mw_for(depro))
                add(step=f"{step}; deprotection wash", material="DMF", cls="deprotection wash solvent",
                    ml=per_use_ml * 6, count=6, phase="pre-coupling deprotection wash",
                    note="STD cycle: DMF wash x6 after deprotection and before coupling", src=f"step {step}; pre-coupling deprotection wash")

            # Unit/material row.
            if self._is_ac_unit(name):
                ac_mw = 102.09
                ac_g = mmol * ac_mw / 1000.0
                ac_ml = ac_g / self._density_for("Ac2O")
                add(step=step, material="Acetic anhydride (Ac2O) for Ac", cls="N-terminal modifier reagent",
                    mmol=mmol, ml=ac_ml, repeat=repeat, phase=phase,
                    note="N-terminal Ac is calculated from Acetic anhydride (Ac2O, MW 102.09, density 1.08 g/mL); no post-Ac deprotection.", src=f"step {step}", mw=ac_mw)
            else:
                mw_unit = meta.get("MW", "")
                if self._amount_numeric(amount_ml_cell, 0.0) > 0:
                    add(step=step, material=name, cls="AA/Chemical/label/tag/linker", mmol=mmol,
                        ml=self._amount_numeric(amount_ml_cell, 0.0), repeat=repeat, phase=phase, note=note, src=f"step {step}", mw=mw_unit)
                else:
                    g = self._amount_numeric(amount_g_cell, self._to_float(meta.get("calculated g"), 0))
                    add(step=step, material=name, cls="AA/Chemical/label/tag/linker", mmol=mmol,
                        g=g, repeat=repeat, phase=phase, note=note, src=f"step {step}", mw=mw_unit)

            # One and only one coupling cocktail solvent per row.
            csolv = str(r.get("Coupling cocktail solvent", "") or "")
            cvol = self._to_float(r.get("Coupling cocktail volume(mL)"), 0)
            if csolv and cvol > 0 and str(r.get("Unit name", "") or "").strip():
                components = [x for x in [r.get("Unit name", ""), r.get("Coupling reagent 1", ""), r.get("Coupling reagent 2 / catalyst", ""), r.get("Coupling base", "")] if str(x or "").strip()]
                comp_txt = " + ".join(map(str, components))
                add_solution_components(step=f"{step}; coupling cocktail", solvent_name=csolv, total_ml=cvol,
                    cls="coupling cocktail solvent", phase=phase,
                    note=f"Single cocktail solvent for: {comp_txt}", src=f"step {step}; coupling cocktail", count=1)

            # Individual component amounts are still tracked separately.
            r1_name = r.get("Coupling reagent 1")
            r1eq = self._to_float(r.get("Coupling reagent 1 eq"), 0)
            r1count = self._to_float(r.get("Coupling reagent 1 count"), repeat)
            r1mmol = scale * r1eq * r1count
            r1_mw = mw_for(r1_name)
            r1_g = (r1mmol * self._to_float(r1_mw, 0) / 1000.0) if r1_mw else 0.0
            if self._is_liquid_like(r1_name):
                add(step=step, material=r1_name, cls="coupling reagent", mmol=r1mmol,
                    ml=r1_g / self._density_for(r1_name) if r1_g else 0, count=r1count, repeat=repeat, src=f"step {step}", mw=r1_mw)
            else:
                add(step=step, material=r1_name, cls="coupling reagent", mmol=r1mmol,
                    g=r1_g, count=r1count, repeat=repeat, src=f"step {step}", mw=r1_mw)

            c2_name = r.get("Coupling reagent 2 / catalyst")
            c2eq = self._to_float(r.get("Coupling reagent 2 / catalyst eq"), 0)
            c2count = self._to_float(r.get("Coupling reagent 2 / catalyst count"), repeat)
            c2mmol = scale * c2eq * c2count
            c2_mw = mw_for(c2_name)
            c2_g = (c2mmol * self._to_float(c2_mw, 0) / 1000.0) if c2_mw else 0.0
            if self._is_liquid_like(c2_name):
                add(step=step, material=c2_name, cls="catalyst/additive", mmol=c2mmol,
                    ml=c2_g / self._density_for(c2_name) if c2_g else 0, count=c2count, repeat=repeat, src=f"step {step}", mw=c2_mw)
            else:
                add(step=step, material=c2_name, cls="catalyst/additive", mmol=c2mmol,
                    g=c2_g, count=c2count, repeat=repeat, src=f"step {step}", mw=c2_mw)

            base_name = r.get("Coupling base")
            beq = self._to_float(r.get("Coupling base eq"), 0)
            bcount = self._to_float(r.get("Coupling base count"), repeat)
            bmmol = scale * beq * bcount
            base_mw = mw_for(base_name)
            base_g = (bmmol * self._to_float(base_mw, 0) / 1000.0) if base_mw else 0.0
            if self._is_liquid_like(base_name):
                add(step=step, material=base_name, cls="base", mmol=bmmol,
                    ml=base_g / self._density_for(base_name) if base_g else 0, count=bcount, repeat=repeat, src=f"step {step}", mw=base_mw)
            else:
                add(step=step, material=base_name, cls="base", mmol=bmmol,
                    g=base_g, count=bcount, repeat=repeat, src=f"step {step}", mw=base_mw)

            # Post-coupling transition wash.
            # Final rows must NOT receive the ordinary DMF x2 transition wash.
            # Practical rule requested for Pepforge V2.0.0: after the last
            # deprotection or after the last terminal chemical/label/tag/cap
            # coupling, go directly to the final wash sequence: DMF x3 -> DCM x3.
            skip_transition_wash = bool(is_non_fmoc_final or (is_last_fmoc and not final_non_fmoc_step))
            if not skip_transition_wash:
                s1_count = self._to_int(r.get("Solvent 1 count"), 0)
                s2_count = self._to_int(r.get("Solvent 2 count"), 0)
                if s1_count > 0:
                    add(step=f"{step}; post-coupling wash", material=r.get("Solvent 1"), cls="post-coupling wash solvent",
                        ml=per_use_ml * s1_count, count=s1_count, phase="post-coupling wash",
                        note="Default transition wash after coupling is DMF x2 unless edited", src=f"step {step}")
                if s2_count > 0:
                    add(step=f"{step}; post-coupling wash", material=r.get("Solvent 2"), cls="post-coupling wash solvent",
                        ml=per_use_ml * s2_count, count=s2_count, phase="post-coupling wash",
                        note="Special/user-edited post-coupling wash", src=f"step {step}")

            # If no terminal non-Fmoc row exists, the last Fmoc-AA row receives final deprotection and final wash.
            if is_last_fmoc and not final_non_fmoc_step:
                add_final_depro_before(last_fmoc_step)
                for solvent_name, wash_count in self._final_wash_specs():
                    if wash_count > 0:
                        add(step=f"{step}; final wash", material=solvent_name, cls="final wash solvent",
                            ml=per_use_ml * wash_count, count=wash_count, phase="final wash",
                            note="Final wash after final Fmoc deprotection: DMF x3 / DCM x3 / optional MeOH", src=f"step {step}; final wash")

            # Terminal chemical/label/tag/cap rows do not receive post-row deprotection,
            # but the practical Last wash still follows the terminal reaction:
            # first DMF x3, then DCM x3 (plus optional MeOH if enabled).
            if is_non_fmoc_final:
                for solvent_name, wash_count in self._final_wash_specs():
                    if wash_count > 0:
                        add(step=f"{step}; final wash", material=solvent_name, cls="final wash solvent",
                            ml=per_use_ml * wash_count, count=wash_count, phase="final wash",
                            note="Last wash after terminal chemical/label/tag/cap reaction: DMF x3 first, then DCM x3", src=f"step {step}; final wash")

        df = pd.DataFrame(rows)
        if not df.empty:
            for col in ["planned_mmol", "planned_g", "planned_mL"]:
                if col in df.columns:
                    df[col] = df[col].apply(lambda x: round(float(x), 4) if str(x) not in ["", "nan"] else x)
        return df

    def _minimal_materials_from_plan(self, plan_df: pd.DataFrame) -> pd.DataFrame:
        """Fallback material renderer used when the full process table returns empty.

        It prevents a blank Materials tab and makes SPPS Planner usable while the
        user edits custom rows. The full calculator is still used whenever it
        returns rows.
        """
        rows=[]
        scale=self._to_float(self.scale.get(),0.0)
        def add(step, material, cls, mmol=0, g=0, ml=0, note="fallback"):
            if str(material or "").strip():
                rows.append({"step":step,"material":material,"class":cls,"MW":"","planned_mmol":round(self._to_float(mmol,0),4),"planned_g":round(self._to_float(g,0),4),"planned_mL":round(self._to_float(ml,0),4),"use_count":"","repeat":"","phase":"fallback","note":note,"source":"editable plan fallback"})
        add("resin","Resin",self.resin.get(),mmol=scale,g=(scale/self._to_float(self.loading.get(),1) if self._to_float(self.loading.get(),0) else 0),note="scale/loading")
        for _, r in plan_df.iterrows():
            step=r.get("No","")
            unit=r.get("Unit name","")
            eq=self._to_float(r.get("Unit eq"),0)
            rep=max(1,self._to_int(r.get("Repeat"),1))
            mmol=scale*eq*rep
            add(step, unit, "AA/chemical/linker", mmol=mmol, g=self._to_float(r.get("Unit amount(g)"),0), ml=self._to_float(r.get("Unit volume(mL)"),0), note="unit from editable plan")
            for col, cls in [("Coupling reagent 1","coupling reagent"),("Coupling reagent 2 / catalyst","catalyst/additive"),("Coupling base","base"),("Deprotection base","deprotection base"),("Coupling cocktail solvent","coupling solvent"),("Solvent 1","wash solvent"),("Solvent 2","wash solvent")]:
                add(step, r.get(col,""), cls, note=col)
        return pd.DataFrame(rows, columns=self.MATERIAL_COLUMNS)


    def ml_log_from_rows(self, plan_df: pd.DataFrame) -> pd.DataFrame:
        out = plan_df.copy()
        out.insert(0, "project_name", self.project_name.get())
        out.insert(1, "sequence", self.seq.get())
        out.insert(1, "resin", self.resin.get())
        out.insert(2, "scale_mmol", self.scale.get())
        out.insert(3, "loading_mmol_g", self.loading.get())
        out.insert(4, "ml_per_mmol", self.ml_per_mmol.get())
        out.insert(5, "branch_mode", bool(self.branch_mode.get()))
        out.insert(6, "branch_point", self.branch_point.get())
        out.insert(7, "branch_arm", self.branch_arm.get())
        out.insert(8, "branch_protecting_group", self.branch_pg.get())
        out["actual_yield"] = ""
        out["purity"] = ""
        out["lcms_result"] = ""
        out["hplc_method"] = ""
        out["operator_note"] = ""
        return out

    def operation_form_from_rows(self, plan_df: pd.DataFrame) -> pd.DataFrame:
        ops = []
        line = 1
        swell_solvent = self._swell_solvent_for_resin()
        loading_family = "DCM-family loading" if self._resin_family_text() == "CTC/Trityl" else "DMF-family loading / preloaded Fmoc resin handling"
        ops.append({"line": line, "step": "swell", "operation": "resin swell", "unit": self.resin.get(), "solution": swell_solvent, "repeat/count": 1, "date": "", "operator": "", "note": f"Swell before loading; {loading_family}"}); line += 1
        final_non_fmoc_step = self._last_non_fmoc_final_step_no(plan_df)
        # Final non-Fmoc chemical/label/tag/cap rows carry their own
        # pre-reaction Fmoc removal and DMF wash x6.
        last_fmoc_step = self._last_fmoc_step_no(plan_df)
        for _, r in plan_df.iterrows():
            step = str(r.get("No", ""))
            unit = r.get("Unit name", "")
            rep = max(1, self._to_int(r.get("Repeat"), 1))
            depro = r.get("Deprotection base", self.default_depro.get())
            ratio = r.get("Deprotection ratio", self.default_depro_ratio.get())
            dcount = self._to_int(r.get("Deprotection count"), self.default_depro_count.get())
            row_dict = r.to_dict() if hasattr(r, "to_dict") else dict(r)
            meta = self._row_meta_by_no.get(str(step), {})
            needs_pre_depro = self._needs_deprotection_for_row(row_dict, meta)
            is_last_fmoc = str(step) == str(last_fmoc_step)
            is_final_non_fmoc = str(step) == str(final_non_fmoc_step)
            phase_text = str(meta.get("Phase", ""))
            is_loading = "loading" in phase_text.lower()

            if dcount > 0 and needs_pre_depro:
                ops.append({"line": line, "step": step, "operation": "deprotection", "unit": unit, "solution": f"{depro} ({ratio})", "repeat/count": dcount, "date": "", "operator": "", "note": "Pre-coupling Fmoc deprotection"}); line += 1
                ops.append({"line": line, "step": step, "operation": "DMF wash after deprotection", "unit": unit, "solution": "DMF", "repeat/count": 6, "date": "", "operator": "", "note": "STD cycle: DMF wash x6 after deprotection before coupling"}); line += 1

            for i in range(rep):
                if is_loading:
                    op_name = "resin loading / first unit attachment"
                    note_extra = "Loading is distinct from regular coupling; solvent follows resin family"
                elif is_last_fmoc:
                    op_name = "last coupling step"
                    note_extra = "After this Fmoc-AA coupling: DMF wash x2 -> next terminal row or final deprotection"
                elif is_final_non_fmoc:
                    op_name = "final chemical / label / modifier coupling"
                    note_extra = "Terminal chemical/label/tag/cap coupling after Fmoc removal + DMF x6; followed by last wash DMF x3 then DCM x3"
                else:
                    op_name = "coupling reaction"
                    note_extra = "STD cycle: coupling -> DMF wash x2 -> next cycle"
                ops.append({"line": line, "step": step, "operation": op_name, "unit": unit, "solution": f"Prepare coupling cocktail: {unit} + {r.get('Coupling reagent 1','')} + {r.get('Coupling reagent 2 / catalyst','')} + {r.get('Coupling base','')} in {r.get('Coupling cocktail solvent', r.get('Solvent 1',''))} ({r.get('Coupling cocktail volume(mL)','')} mL); add to resin", "repeat/count": i+1, "date": "", "operator": "", "note": (str(meta.get("Note", r.get("Note", ""))) + " | " + note_extra).strip(" |")}); line += 1

            s1 = r.get("Solvent 1", ""); c1 = self._to_int(r.get("Solvent 1 count"), 0)
            s2 = r.get("Solvent 2", ""); c2 = self._to_int(r.get("Solvent 2 count"), 0)
            skip_transition_wash = bool(is_final_non_fmoc or (is_last_fmoc and not final_non_fmoc_step))
            if (c1 > 0 or c2 > 0) and not skip_transition_wash:
                ops.append({"line": line, "step": step, "operation": "post-coupling wash", "unit": unit, "solution": f"{s1} x {c1} / {s2} x {c2}", "repeat/count": "", "date": "", "operator": "", "note": "Default transition wash is DMF x2; DCM is not used between ordinary coupling cycles unless edited by the user"}); line += 1

            if is_last_fmoc and (not final_non_fmoc_step) and dcount > 0 and needs_pre_depro:
                ops.append({"line": line, "step": step, "operation": "final deprotection", "unit": unit, "solution": f"{depro} ({ratio})", "repeat/count": dcount, "date": "", "operator": "", "note": "Final Fmoc deprotection after the last Fmoc-AA coupling"}); line += 1

            if is_last_fmoc and not final_non_fmoc_step:
                for solvent_name, wash_count in self._final_wash_specs():
                    ops.append({"line": line, "step": step, "operation": "final wash", "unit": unit, "solution": solvent_name, "repeat/count": wash_count, "date": "", "operator": "", "note": "Final wash after final deprotection: DMF x3 then DCM x3"}); line += 1
            elif is_final_non_fmoc:
                for solvent_name, wash_count in self._final_wash_specs():
                    ops.append({"line": line, "step": step, "operation": "final wash", "unit": unit, "solution": solvent_name, "repeat/count": wash_count, "date": "", "operator": "", "note": "Last wash after terminal chemical/label/tag/cap reaction: DMF x3 first, then DCM x3"}); line += 1
        return pd.DataFrame(ops)

    def checklist_from_rows(self, plan_df: pd.DataFrame) -> pd.DataFrame:
        """Printable checklist with one row per practical SPPS operation."""
        rows = []
        line = 1
        swell_solvent = self._swell_solvent_for_resin()
        loading_family = "DCM-family loading" if self._resin_family_text() == "CTC/Trityl" else "DMF-family loading / preloaded Fmoc resin handling"
        rows.append({"Line": line, "Step": "swell", "Operation": "Resin swell", "AA/Chemical/label/tag/linker": self.resin.get(), "Reagent/Solution": swell_solvent, "Eq/Count": 1, "Amount(g or mL)": "", "Date": "", "Checked": "No", "Operator": "", "Note": f"Swell before loading; {loading_family}"}); line += 1
        final_non_fmoc_step = self._last_non_fmoc_final_step_no(plan_df)
        # Final non-Fmoc chemical/label/tag/cap rows carry their own
        # pre-reaction Fmoc removal and DMF wash x6.
        last_fmoc_step = self._last_fmoc_step_no(plan_df)
        for _, r in plan_df.iterrows():
            step = str(r.get("No", ""))
            unit = r.get("Unit name", "")
            rep = max(1, self._to_int(r.get("Repeat"), 1))
            depro = r.get("Deprotection base", self.default_depro.get())
            ratio = r.get("Deprotection ratio", self.default_depro_ratio.get())
            dcount = self._to_int(r.get("Deprotection count"), self.default_depro_count.get())
            row_dict = r.to_dict() if hasattr(r, "to_dict") else dict(r)
            meta = self._row_meta_by_no.get(str(step), {})
            needs_pre_depro = self._needs_deprotection_for_row(row_dict, meta)
            is_last_fmoc = str(step) == str(last_fmoc_step)
            is_final_non_fmoc = str(step) == str(final_non_fmoc_step)
            phase_text = str(meta.get("Phase", ""))
            is_loading = "loading" in phase_text.lower()

            if dcount > 0 and needs_pre_depro:
                for i in range(dcount):
                    rows.append({"Line": line, "Step": step, "Operation": "Deprotection", "AA/Chemical/label/tag/linker": unit, "Reagent/Solution": f"{depro} ({ratio})", "Eq/Count": i+1, "Amount(g or mL)": "", "Date": "", "Checked": "No", "Operator": "", "Note": "Pre-coupling Fmoc deprotection"}); line += 1
                for i in range(6):
                    rows.append({"Line": line, "Step": step, "Operation": "DMF wash after deprotection", "AA/Chemical/label/tag/linker": unit, "Reagent/Solution": "DMF", "Eq/Count": i+1, "Amount(g or mL)": "", "Date": "", "Checked": "No", "Operator": "", "Note": "STD cycle: DMF wash x6 before coupling"}); line += 1

            for i in range(rep):
                op = "Resin loading / first unit attachment" if is_loading else ("Last coupling step" if is_last_fmoc else ("Final chemical / label / modifier coupling" if is_final_non_fmoc else "Coupling reaction"))
                rows.append({"Line": line, "Step": step, "Operation": op, "AA/Chemical/label/tag/linker": unit, "Reagent/Solution": f"Coupling cocktail: {unit} + {r.get('Coupling reagent 1','')} + {r.get('Coupling reagent 2 / catalyst','')} + {r.get('Coupling base','')} in {r.get('Coupling cocktail solvent', r.get('Solvent 1',''))} ({r.get('Coupling cocktail volume(mL)','')} mL)", "Eq/Count": f"repeat {i+1}/{rep}; unit eq={r.get('Unit eq','')}", "Amount(g or mL)": (r.get("Unit amount(g)", "") or r.get("Unit volume(mL)", "")), "Date": "", "Checked": "No", "Operator": "", "Note": str(meta.get("Note", ""))}); line += 1

            s1 = r.get("Solvent 1", ""); c1 = self._to_int(r.get("Solvent 1 count"), 0)
            s2 = r.get("Solvent 2", ""); c2 = self._to_int(r.get("Solvent 2 count"), 0)
            skip_transition_wash = bool(is_final_non_fmoc or (is_last_fmoc and not final_non_fmoc_step))
            if not skip_transition_wash:
                for i in range(c1):
                    rows.append({"Line": line, "Step": step, "Operation": "Post-coupling wash", "AA/Chemical/label/tag/linker": unit, "Reagent/Solution": s1, "Eq/Count": i+1, "Amount(g or mL)": "", "Date": "", "Checked": "No", "Operator": "", "Note": "Default transition wash is DMF x2"}); line += 1
                for i in range(c2):
                    rows.append({"Line": line, "Step": step, "Operation": "Post-coupling wash", "AA/Chemical/label/tag/linker": unit, "Reagent/Solution": s2, "Eq/Count": i+1, "Amount(g or mL)": "", "Date": "", "Checked": "No", "Operator": "", "Note": "User-edited/special wash"}); line += 1

            if is_last_fmoc and (not final_non_fmoc_step) and dcount > 0 and needs_pre_depro:
                for i in range(dcount):
                    rows.append({"Line": line, "Step": step, "Operation": "Final deprotection", "AA/Chemical/label/tag/linker": unit, "Reagent/Solution": f"{depro} ({ratio})", "Eq/Count": i+1, "Amount(g or mL)": "", "Date": "", "Checked": "No", "Operator": "", "Note": "After last Fmoc-AA coupling"}); line += 1

            if is_last_fmoc and not final_non_fmoc_step:
                for solvent_name, wash_count in self._final_wash_specs():
                    for i in range(wash_count):
                        rows.append({"Line": line, "Step": step, "Operation": "Final wash", "AA/Chemical/label/tag/linker": unit, "Reagent/Solution": solvent_name, "Eq/Count": i+1, "Amount(g or mL)": "", "Date": "", "Checked": "No", "Operator": "", "Note": "Final wash order: first DMF x3, then DCM x3"}); line += 1
            elif is_final_non_fmoc:
                for solvent_name, wash_count in self._final_wash_specs():
                    for i in range(wash_count):
                        rows.append({"Line": line, "Step": step, "Operation": "Final wash", "AA/Chemical/label/tag/linker": unit, "Reagent/Solution": solvent_name, "Eq/Count": i+1, "Amount(g or mL)": "", "Date": "", "Checked": "No", "Operator": "", "Note": "Last wash order after terminal chemical/label/tag/cap: first DMF x3, then DCM x3"}); line += 1
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
                return ""
            # pandas NaN check without importing numpy directly
            try:
                if pd.isna(value):
                    return ""
            except Exception:
                pass
            if isinstance(value, float):
                return (f"{value:.4f}").rstrip("0").rstrip(".")
            text = str(value)
            for bad in ("\u266a", "\u266b", "\u266c", "\u2669", "\u266d", "\u266f"):
                text = text.replace(bad, "")
            text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", text)
            return text.strip()
        except Exception:
            return str(value) if value is not None else ""

    def _write_tree(self, tree: ttk.Treeview, df: pd.DataFrame, columns):
        """Write a DataFrame into a Treeview safely.

        This keeps the live Material Usage and Material Usage tab in sync without
        relying on any Tk root-level helper. Missing columns are rendered as blank
        cells, and previous rows are cleared before writing.
        """
        try:
            for item in tree.get_children():
                tree.delete(item)
            # Synchronize tree columns defensively.
            existing = list(tree["columns"])
            if list(existing) != list(columns):
                tree.configure(columns=list(columns))
                for col in columns:
                    tree.heading(col, text=col)
                    tree.column(col, width=130, minwidth=60, anchor="w", stretch=True)
            if df is None or df.empty:
                # Do not leave critical panes visually blank; show an actionable placeholder.
                if tree in (getattr(self, "live_usage_tree", None), getattr(self, "material_tree", None)):
                    blank = {c: "" for c in columns}
                    if "material" in blank:
                        blank["material"] = "No material rows calculated yet"
                    if "note" in blank:
                        blank["note"] = "Click Build/Rebuild; verify sequence, scale, resin, and coupling settings."
                    tree.insert("", "end", values=[blank.get(c, "") for c in columns])
                return
            for _, row in df.iterrows():
                vals = [self._sanitize_display_value(row.get(c, "")) for c in columns]
                tree.insert("", "end", values=vals)
        except Exception as e:
            try:
                for item in tree.get_children():
                    tree.delete(item)
                blank = {c: "" for c in columns}
                if "material" in blank:
                    blank["material"] = "Material table render warning"
                if "note" in blank:
                    blank["note"] = str(e)
                tree.insert("", "end", values=[blank.get(c, "") for c in columns])
            except Exception:
                pass
            self._log(f"Tree render warning: {e}\n")

    def _write_df(self, widget: tk.Text, df: pd.DataFrame):
        widget.delete("1.0", "end")
        if df is None or df.empty:
            return
        widget.insert("1.0", df.to_csv(index=False, sep="\t"))

    def append_blank_row(self):
        no = len(self.tree.get_children()) + 1
        d = {c: "" for c in self.PLAN_COLUMNS}
        d["No"] = no
        d["Unit eq"] = self.coupling_eq.get()
        d["Repeat"] = 1
        d["Coupling reagent 1"] = self.default_reagent.get()
        d["Coupling reagent 1 eq"] = self.default_reagent_eq.get()
        d["Coupling reagent 1 count"] = self.default_reagent_count.get()
        d["Coupling reagent 2 / catalyst"] = self.default_catalyst.get()
        d["Coupling reagent 2 / catalyst eq"] = self.default_catalyst_eq.get()
        d["Coupling reagent 2 / catalyst count"] = self.default_catalyst_count.get()
        d["Coupling base"] = self.default_base.get()
        d["Coupling base eq"] = self.default_base_eq.get() if self.default_base.get() else ""
        d["Coupling base count"] = self.default_base_count.get() if self.default_base.get() else 0
        d["Coupling cocktail solvent"] = self.default_coupling_solution_solvent.get()
        d["Coupling cocktail volume(mL)"] = self._default_dissolve_volume("manual", "manual")
        d["Deprotection base"] = self.default_depro.get()
        d["Deprotection ratio"] = self.default_depro_ratio.get()
        d["Deprotection count"] = self.default_depro_count.get()
        d["Solvent 1"] = self.default_solvent1.get()
        d["Solvent 1 count"] = self.default_solvent1_count.get()
        d["Solvent 2"] = self.default_solvent2.get()
        d["Solvent 2 count"] = self.default_solvent2_count.get()
        self._row_meta_by_no[str(no)] = {"MW": "", "calculated mmol": "", "calculated g": "", "Phase": "manual", "Note": "manual row"}
        self.tree.insert("", "end", values=[d.get(c, "") for c in self.PLAN_COLUMNS])
        self.refresh_outputs_from_tree()

    def delete_selected(self):
        for item in self.tree.selection():
            self.tree.delete(item)
        for i, item in enumerate(self.tree.get_children(), start=1):
            vals = list(self.tree.item(item, "values")); vals[0] = i; self.tree.item(item, values=vals)
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
        loading_volume = self._to_float(self.ml_per_mmol.get(), 0.0) * scale
        rows = [
            {"field":"project_name", "value":self.project_name.get(), "unit":"", "note":"user-defined project/run name"},
            {"field":"sequence", "value":self.seq.get(), "unit":"", "note":"input peptide sequence"},
            {"field":"resin_type", "value":self.resin.get(), "unit":"", "note":"selected resin family"},
            {"field":"target_scale", "value":round(scale,4), "unit":"mmol", "note":"target synthesis scale"},
            {"field":"resin_loading", "value":round(loading,4), "unit":"mmol/g", "note":"resin substitution/loading"},
            {"field":"required_resin", "value":round(resin_g,4), "unit":"g", "note":"target_scale / resin_loading"},
            {"field":"swell_solvent", "value":self._swell_solvent_for_resin(), "unit":"", "note":"DCM for CTC/trityl; DMF for amide/Rink/Wang"},
            {"field":"loading_cocktail_solvent", "value":loading_solvent, "unit":"", "note":"default loading solution solvent"},
            {"field":"estimated_loading_solution_volume", "value":round(loading_volume,4), "unit":"mL", "note":"scale x mL per mmol"},
        ]
        return pd.DataFrame(rows)

    def cleavage_calculator_df(self) -> pd.DataFrame:
        """Cleavage planning scaffold.

        This is intentionally editable after export. It uses the current Pepforge
        resin/scale defaults and the user's empirical rules can be adjusted in Excel.
        """
        scale = self._to_float(self.scale.get(), 0.0)
        seq = str(self.seq.get() or "")
        core = re.sub(r"[^A-Za-z]", "", seq.replace("Ac", "").replace("NH2", ""))
        length = len(core)
        cys_count = core.upper().count("C")
        base_tfa_eq = 30 if length <= 7 else (80 if length <= 15 else 100)
        tfa_eq = base_tfa_eq + 100*cys_count
        tfa_mmol_equiv = scale * tfa_eq
        # Use MW/density to produce a planning volume for pure TFA equivalent.
        tfa_mL = (tfa_mmol_equiv * 114.02 / 1000.0) / self._density_for("TFA") if scale else 0
        rows = [
            {"component":"TFA", "ratio_percent":"editable", "equiv":tfa_eq, "estimated_mL":round(tfa_mL,4), "note":"base rule: short 30 eq, 15mer 80 eq, 22mer 100 eq, +100 eq per Cys; verify lab protocol"},
            {"component":"TIS", "ratio_percent":"editable", "equiv":"", "estimated_mL":"", "note":"scavenger; fill according to cleavage cocktail"},
            {"component":"Water", "ratio_percent":"editable", "equiv":"", "estimated_mL":"", "note":"scavenger; fill according to cleavage cocktail"},
            {"component":"EDT", "ratio_percent":"editable", "equiv":"", "estimated_mL":"", "note":"optional Cys scavenger; use only when protocol requires"},
        ]
        return pd.DataFrame(rows)

    def manufacturing_transfer_df(self, materials: pd.DataFrame, plan: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame([{
            "project_name": self.project_name.get(),
            "sequence": self.seq.get(),
            "resin": self.resin.get(),
            "scale_mmol": self.scale.get(),
            "resin_loading_mmol_g": self.loading.get(),
            "current_status": "",
            "completed_step": "",
            "next_step": "",
            "critical_note": "",
            "operator": "",
            "date": "",
            "company_contact": "",
            "handover_note": "Use this sheet to communicate synthesis progress, material status, and next operation to an external company or collaborator.",
        }])

    def production_tracking_df(self, plan: pd.DataFrame) -> pd.DataFrame:
        rows = []
        for _, r in plan.iterrows():
            rows.append({
                "project_name": self.project_name.get(),
                "sequence": self.seq.get(),
                "step": r.get("No", ""),
                "unit": r.get("Unit name", ""),
                "phase": self._row_meta_by_no.get(str(r.get("No", "")), {}).get("Phase", ""),
                "status": "Not started",
                "date": "",
                "operator": "",
                "note": "",
            })
        return pd.DataFrame(rows)

    def bench_checklist_layout_df(self, plan: pd.DataFrame, materials: pd.DataFrame) -> pd.DataFrame:
        """Bench-sheet style checklist separated from material usage.

        The top section is a step/date/check grid. The lower sections are intended
        for AA usage and reagent/base/capping usage. It is exported to Excel as a
        standalone practical checklist sheet.
        """
        rows = []
        rows.append({"section":"STEP_TRACKING", "item":"Project", "value":self.project_name.get(), "unit":"", "date":"", "check":"", "note":""})
        rows.append({"section":"STEP_TRACKING", "item":"Sequence", "value":self.seq.get(), "unit":"", "date":"", "check":"", "note":""})
        for _, r in plan.iterrows():
            rows.append({"section":"STEP_TRACKING", "item":r.get("Unit name", ""), "value":"", "unit":"", "date":"", "check":"No", "note":self._row_meta_by_no.get(str(r.get("No", "")), {}).get("Phase", "")})
        aa = self.amino_acid_usage_summary(materials)
        for _, r in aa.iterrows():
            rows.append({"section":"AA_USAGE", "item":r.get("material", ""), "value":r.get("calculated_g", ""), "unit":"g", "date":"", "check":"", "note":f"mmol={r.get('planned_mmol','')}; MW={r.get('MW','')}"})
        reag = self.reagent_usage_summary(materials)
        for _, r in reag.iterrows():
            rows.append({"section":"REAGENT_BASE_CAPPING", "item":r.get("material", ""), "value":r.get("planned_mL", "") if r.get("planned_mL", 0) else r.get("planned_g", ""), "unit":"mL/g", "date":"", "check":"", "note":f"MW={r.get('MW','')}; density={r.get('density_g_per_mL','')}"})
        return pd.DataFrame(rows)


    def _safe_name(self, value: str) -> str:
        raw = str(value or "").strip() or "Pepforge_Project"
        raw = re.sub(r'[<>:"/\\|?*]+', "_", raw)
        raw = re.sub(r"\s+", " ", raw).strip()
        return raw[:120] if len(raw) > 120 else raw

    def _project_export_dir(self) -> Path:
        base = Path(self.outdir.get())
        chosen = self.project_name.get().strip() or self.seq.get().strip() or "Pepforge_Project"
        folder = self._safe_name(chosen) + "_" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        return base / folder

    def _column_width_file(self) -> Path:
        p = ROOT / "outputs"
        p.mkdir(parents=True, exist_ok=True)
        return p / "spps_column_widths.json"

    def _save_column_widths(self):
        try:
            data = {c: int(self.tree.column(c, "width")) for c in self.tree["columns"]}
            self._column_width_file().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _load_column_widths(self):
        try:
            p = self._column_width_file()
            if p.exists():
                self.plan_width_map.update(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            pass

    def progress_df(self) -> pd.DataFrame:
        rows = []
        for iid in self.progress_tree.get_children():
            vals = list(self.progress_tree.item(iid, "values"))
            cols = list(self.progress_tree["columns"])
            rows.append({c: vals[i] if i < len(vals) else "" for i, c in enumerate(cols)})
        return pd.DataFrame(rows)

    def _progress_key(self, row: dict) -> str:
        return f"{row.get('line','')}|{row.get('operation','')}|{row.get('unit','')}"

    def _populate_progress_tree(self, checklist: pd.DataFrame):
        old = {}
        for iid in self.progress_tree.get_children():
            vals = list(self.progress_tree.item(iid, "values"))
            if len(vals) >= 5:
                key = f"{vals[0]}|{vals[3]}|{vals[4]}"
                old[key] = vals
        self.progress_tree.delete(*self.progress_tree.get_children())
        if checklist is None or checklist.empty:
            return
        rows = []
        for i, r in checklist.iterrows():
            operation = r.get("Operation", "")
            unit = r.get("AA/Chemical/label/tag/linker", "")
            line = r.get("Line", i+1)
            key = f"{line}|{operation}|{unit}"
            next_step = ""
            if i + 1 < len(checklist.index):
                nr = checklist.iloc[i+1]
                next_step = f"{nr.get('Operation','')} / {nr.get('AA/Chemical/label/tag/linker','')}"
            if key in old:
                vals = old[key]
            else:
                vals = [line, "No", "", operation, unit, next_step, r.get("Note", "")]
            self.progress_tree.insert("", "end", values=vals)
        self._update_progress_widgets()

    def _update_progress_widgets(self):
        try:
            total = len(self.progress_tree.get_children())
            done = sum(1 for x in self.progress_tree.get_children() if list(self.progress_tree.item(x, "values"))[1] == "Yes")
            pct = round((done / total) * 100, 1) if total else 0.0
            if hasattr(self, "checklist_progress_var"):
                self.checklist_progress_var.set(pct)
            if hasattr(self, "checklist_progress_label"):
                self.checklist_progress_label.configure(text=f"Progress: {done}/{total} ({pct}%)")
        except Exception:
            pass

    def toggle_progress_row(self, event=None):
        item = self.progress_tree.focus() or (self.progress_tree.selection()[0] if self.progress_tree.selection() else "")
        if not item:
            return
        vals = list(self.progress_tree.item(item, "values"))
        if len(vals) < 7:
            return
        if vals[1] == "Yes":
            vals[1] = "No"; vals[2] = ""
        else:
            vals[1] = "Yes"; vals[2] = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.progress_tree.item(item, values=vals)
        self._update_progress_widgets()
        self._write_df(self.next_text, self.next_step_df())

    def _set_progress_item_done(self, item, done: bool):
        vals = list(self.progress_tree.item(item, "values"))
        if len(vals) < 7:
            return
        if done:
            vals[1] = "Yes"
            if not vals[2]:
                vals[2] = datetime.now().strftime("%Y-%m-%d %H:%M")
        else:
            vals[1] = "No"
            vals[2] = ""
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
        target = self.progress_tree.focus() or (self.progress_tree.selection()[0] if self.progress_tree.selection() else "")
        if not target or target not in children:
            target = children[-1]
        end = children.index(target)
        for item in children[:end+1]:
            self._set_progress_item_done(item, True)
        self._update_progress_widgets()
        self._write_df(self.next_text, self.next_step_df())

    def next_step_df(self) -> pd.DataFrame:
        for iid in self.progress_tree.get_children():
            vals = list(self.progress_tree.item(iid, "values"))
            if len(vals) >= 7 and vals[1] != "Yes":
                total = len(self.progress_tree.get_children())
                done = sum(1 for x in self.progress_tree.get_children() if list(self.progress_tree.item(x, "values"))[1] == "Yes")
                return pd.DataFrame([{
                    "progress": f"{done}/{total}",
                    "percent": round((done/total)*100, 1) if total else 0,
                    "next_line": vals[0],
                    "next_operation": vals[3],
                    "next_unit": vals[4],
                    "next_step_after_that": vals[5],
                    "note": vals[6],
                }])
        total = len(self.progress_tree.get_children())
        return pd.DataFrame([{"progress": f"{total}/{total}", "percent": 100 if total else 0, "next_line": "", "next_operation": "Complete", "next_unit": "", "next_step_after_that": "", "note": "All checklist rows are checked."}])

    def save_project_state(self, path: Path):
        data = {
            "project_name": self.project_name.get(),
            "sequence": self.seq.get(),
            "resin": self.resin.get(),
            "scale_mmol": self.scale.get(),
            "loading_mmol_g": self.loading.get(),
            "outdir": self.outdir.get(),
            "plan_rows": self.tree_rows(),
            "row_meta": self._row_meta_by_no,
            "progress_rows": self.progress_df().to_dict("records"),
            "saved_at": datetime.now().isoformat(timespec="seconds"),
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_project(self):
        p = filedialog.askopenfilename(filetypes=[("Pepforge project state", "project_state.json *.json"), ("All files", "*.*")])
        if not p:
            return
        try:
            data = json.loads(Path(p).read_text(encoding="utf-8"))
            self.project_name.set(data.get("project_name", ""))
            self.seq.set(data.get("sequence", self.seq.get()))
            self.resin.set(data.get("resin", self.resin.get()))
            self.scale.set(float(data.get("scale_mmol", self.scale.get())))
            self.loading.set(float(data.get("loading_mmol_g", self.loading.get())))
            self.outdir.set(data.get("outdir", self.outdir.get()))
            self.tree.delete(*self.tree.get_children())
            self._row_meta_by_no = data.get("row_meta", {})
            for row in data.get("plan_rows", []):
                self.tree.insert("", "end", values=[row.get(c, "") for c in self.PLAN_COLUMNS])
            self.refresh_outputs_from_tree()
            # restore progress states after refresh builds rows
            progress_rows = data.get("progress_rows", [])
            if progress_rows:
                by_key = {f"{r.get('line','')}|{r.get('operation','')}|{r.get('unit','')}": r for r in progress_rows}
                for iid in self.progress_tree.get_children():
                    vals = list(self.progress_tree.item(iid, "values"))
                    key = f"{vals[0]}|{vals[3]}|{vals[4]}"
                    r = by_key.get(key)
                    if r:
                        vals[1] = r.get("done", vals[1]); vals[2] = r.get("checked_at", vals[2])
                        self.progress_tree.item(iid, values=vals)
            self._write_df(self.next_text, self.next_step_df())
            self._log(f"Loaded project state: {p}\n")
        except Exception as e:
            messagebox.showerror("Load error", str(e))

    def load_output_folder(self):
        folder = filedialog.askdirectory(title="Select a Pepforge SPPS output folder")
        if not folder:
            return
        try:
            base = Path(folder)
            plan_path = base / "editable_spps_plan.csv"
            xlsx_path = base / "spps_plan.xlsx"
            if plan_path.exists():
                plan = pd.read_csv(plan_path)
            elif xlsx_path.exists():
                plan = pd.read_excel(xlsx_path, sheet_name="00_EDITABLE_PLAN")
            else:
                raise FileNotFoundError("No editable_spps_plan.csv or spps_plan.xlsx found in selected folder.")
            self.tree.delete(*self.tree.get_children())
            self._row_meta_by_no = {}
            for _, row in plan.iterrows():
                d = {c: row.get(c, "") for c in self.PLAN_COLUMNS}
                no = str(d.get("No", len(self.tree.get_children())+1))
                self._row_meta_by_no[no] = {"Phase": row.get("Phase", "loaded output"), "Note": row.get("Note", "loaded from output folder")}
                self.tree.insert("", "end", values=[d.get(c, "") for c in self.PLAN_COLUMNS])
            state_path = base / "project_state.json"
            if state_path.exists():
                try:
                    data = json.loads(state_path.read_text(encoding="utf-8"))
                    self.project_name.set(data.get("project_name", self.project_name.get()))
                    self.seq.set(data.get("sequence", self.seq.get()))
                    self.resin.set(data.get("resin", self.resin.get()))
                    self.scale.set(float(data.get("scale_mmol", self.scale.get())))
                    self.loading.set(float(data.get("loading_mmol_g", self.loading.get())))
                except Exception:
                    pass
            self.last_outdir = base
            self.outdir.set(str(base.parent))
            self.refresh_outputs_from_tree()
            self._log(f"Loaded output folder: {base}\n")
        except Exception as e:
            messagebox.showerror("Load output error", str(e))


    def export_outputs(self):
        try:
            outdir = self._project_export_dir(); outdir.mkdir(parents=True, exist_ok=True)
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
            self.save_project_state(outdir / "project_state.json")
            plan.to_csv(outdir / "editable_spps_plan.csv", index=False, encoding="utf-8-sig")
            materials.to_csv(outdir / "material_usage_from_editable_plan.csv", index=False, encoding="utf-8-sig")
            ops.to_csv(outdir / "operation_form_from_editable_plan.csv", index=False, encoding="utf-8-sig")
            checklist.to_csv(outdir / "printable_synthesis_checklist.csv", index=False, encoding="utf-8-sig")
            ml.to_csv(outdir / "spps_ml_ready_log_from_editable_plan.csv", index=False, encoding="utf-8-sig")
            progress_df.to_csv(outdir / "checklist_progress.csv", index=False, encoding="utf-8-sig")
            next_df.to_csv(outdir / "next_step.csv", index=False, encoding="utf-8-sig")
            self.amino_acid_usage_summary(materials).to_csv(outdir / "total_amino_acid_usage.csv", index=False, encoding="utf-8-sig")
            self.reagent_usage_summary(materials).to_csv(outdir / "total_reagent_base_usage.csv", index=False, encoding="utf-8-sig")
            self.solvent_usage_summary(materials).to_csv(outdir / "total_solvent_usage.csv", index=False, encoding="utf-8-sig")
            if export_csvs is not None:
                try:
                    export_csvs(self._input(), outdir)
                except Exception as e:
                    self._log(f"Classic export warning: {e}\n")
            xlsx = outdir / "spps_plan.xlsx"
            with pd.ExcelWriter(xlsx, engine="openpyxl") as writer:
                plan.to_excel(writer, index=False, sheet_name="00_EDITABLE_PLAN")
                materials.to_excel(writer, index=False, sheet_name="01_MATERIAL_USAGE")
                checklist.to_excel(writer, index=False, sheet_name="02_PRINT_CHECKLIST")
                ops.to_excel(writer, index=False, sheet_name="03_OPERATION_FORM")
                ml.to_excel(writer, index=False, sheet_name="04_ML_READY_LOG")
                loading_df.to_excel(writer, index=False, sheet_name="06_LOADING_CALC")
                cleavage_df.to_excel(writer, index=False, sheet_name="07_CLEAVAGE_CALC")
                transfer_df.to_excel(writer, index=False, sheet_name="08_TRANSFER_SHEET")
                production_df.to_excel(writer, index=False, sheet_name="09_PRODUCTION_TRACKING")
                bench_df.to_excel(writer, index=False, sheet_name="10_BENCH_CHECKLIST")
                progress_df.to_excel(writer, index=False, sheet_name="11_CHECKLIST_PROGRESS")
                next_df.to_excel(writer, index=False, sheet_name="12_NEXT_STEP")
                try:
                    pd.DataFrame([plan_summary(self._input())]).to_excel(writer, index=False, sheet_name="05_SUMMARY")
                except Exception:
                    pass
            with pd.ExcelWriter(outdir / "bench_checklist.xlsx", engine="openpyxl") as cw:
                progress_df.to_excel(cw, index=False, sheet_name="CHECKLIST_PROGRESS")
                bench_df.to_excel(cw, index=False, sheet_name="BENCH_SHEET")
                self.amino_acid_usage_summary(materials).to_excel(cw, index=False, sheet_name="AA_USAGE")
                self.reagent_usage_summary(materials).to_excel(cw, index=False, sheet_name="REAGENT_BASE")
                self.solvent_usage_summary(materials).to_excel(cw, index=False, sheet_name="SOLVENT_TOTAL")
            (outdir / "OUTPUT_MANIFEST.txt").write_text("Pepforge SPPS output folder\n" + "Created: " + datetime.now().isoformat(timespec="seconds") + "\n" + "Open this folder from SPPS Planner with Load Output or Open Output.\n", encoding="utf-8")
            self.last_outdir = outdir
            self._log(f"Exported: {outdir}\n")
            messagebox.showinfo("Export complete", f"CSV/XLSX exported to:\n{outdir}")
        except Exception as e:
            messagebox.showerror("Export error", str(e))
            self._log("ERROR export: " + str(e) + "\n")

    def browse_outdir(self):
        p = filedialog.askdirectory()
        if p:
            self.outdir.set(p)

    def open_output(self):
        p = self.last_outdir or Path(self.outdir.get())
        if p.exists():
            open_path(p)
        else:
            messagebox.showinfo("Not found", str(p))

    def _log(self, msg):
        self.log_text.insert("end", msg)
        self.log_text.see("end")


def main():
    app = SPPSGui()
    app.mainloop()


if __name__ == "__main__":
    main()
