from __future__ import annotations
import os
import sys
import re
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

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
            self.column(col, width=140, minwidth=80, anchor="w", stretch=True)
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
        "Unit amount(g/mL)",
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
        "DOTA": 404.42, "NOTA": 393.35, "Pal": 256.43, "Myr": 228.38, "Nic": 123.11, "Caf": 194.19,
    }

    def __init__(self):
        super().__init__()
        self.title("Pepforge SPPS Planner")
        self.geometry("1660x940")
        self.minsize(1320, 760)
        self.last_outdir: Path | None = None
        self._row_meta_by_no = {}
        self._build()
        self.rebuild_table()

    def _build(self):
        main = ttk.Frame(self, padding=10)
        main.pack(fill="both", expand=True)
        ttk.Label(main, text="SPPS Planner — editable Excel-like synthesis table", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(
            main,
            text="Sequence를 넣으면 C-term→N-term 합성 순서로 editable table이 생성됩니다. 상단 Default unit eq/repeat는 AA, modifier, label, chemical에 공통 기본값으로 적용되고, 각 step별 Unit eq/Repeat/Reagent/Base/Count는 아래 editable table에서 직접 수정합니다. MW/계산 mmol/g/mL/phase/note와 집계 사용량은 Material Usage 표에서 확인합니다.",
            wraplength=1500,
        ).pack(anchor="w", pady=(4, 10))

        form = ttk.Labelframe(main, text="Top input / global defaults", padding=8)
        form.pack(fill="x")
        self.seq = tk.StringVar(value="Ac-EEMQRR-NH2")
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

        def add(label, widget, r, c, span=1):
            ttk.Label(form, text=label).grid(row=r, column=c*2, sticky="w", padx=(0, 4), pady=3)
            widget.grid(row=r, column=c*2+1, sticky="ew", padx=(0, 10), pady=3, columnspan=span)

        for i in range(6):
            form.columnconfigure(i*2+1, weight=1)
        add("Sequence", ttk.Entry(form, textvariable=self.seq), 0, 0, span=3)

        # Top action bar: keep all primary workflow buttons visible and aligned.
        # Do not grid individual buttons into compressed columns; a packed sub-frame
        # prevents labels such as "Export CSV/XLSX" from being truncated.
        action_bar = ttk.Frame(form)
        action_bar.grid(row=0, column=8, columnspan=4, sticky="e", padx=(12, 4), pady=2)
        ttk.Button(action_bar, text="Build Table", width=16, command=self.rebuild_table).pack(side="left", padx=3)
        ttk.Button(action_bar, text="Recalculate Usage", width=18, command=self.refresh_outputs_from_tree).pack(side="left", padx=3)
        ttk.Button(action_bar, text="Export CSV/XLSX", width=18, command=self.export_outputs).pack(side="left", padx=3)
        ttk.Button(action_bar, text="Open Output Folder", width=20, command=self.open_output).pack(side="left", padx=3)

        add("Resin type / family", ttk.Combobox(form, textvariable=self.resin, values=self.RESIN_VALUES, state="normal", width=34), 1, 0)
        add("Resin scale (mmol)", ttk.Entry(form, textvariable=self.scale), 1, 1)
        add("Loading (mmol/g)", ttk.Entry(form, textvariable=self.loading), 1, 2)
        add("Default unit eq (AA / modifier / label)", ttk.Entry(form, textvariable=self.coupling_eq), 1, 3)
        add("mL per mmol", ttk.Entry(form, textvariable=self.ml_per_mmol), 1, 4)
        add("Default coupling cocktail solvent", ttk.Combobox(form, textvariable=self.default_coupling_solution_solvent, values=self.SOLVENT_VALUES, state="normal", width=30), 1, 5)

        add("Default unit repeat", ttk.Spinbox(form, from_=1, to=20, textvariable=self.coupling_repeats), 2, 0)
        add("Coupling reagent 1", ttk.Combobox(form, textvariable=self.default_reagent, values=self.REAGENT_VALUES, state="normal", width=28), 2, 1)
        add("Coupling reagent 1 eq", ttk.Entry(form, textvariable=self.default_reagent_eq), 2, 2)
        add("Coupling reagent 1 count", ttk.Spinbox(form, from_=0, to=30, textvariable=self.default_reagent_count), 2, 3)
        add("Coupling reagent 2 / catalyst", ttk.Combobox(form, textvariable=self.default_catalyst, values=self.CATALYST_VALUES, state="normal", width=30), 2, 5)

        add("Coupling reagent 2 / catalyst eq", ttk.Entry(form, textvariable=self.default_catalyst_eq), 3, 0)
        add("Coupling reagent 2 / catalyst count", ttk.Spinbox(form, from_=0, to=30, textvariable=self.default_catalyst_count), 3, 1)
        add("Coupling base", ttk.Combobox(form, textvariable=self.default_base, values=self.BASE_VALUES, state="normal", width=28), 3, 3)
        add("Coupling base eq", ttk.Entry(form, textvariable=self.default_base_eq), 3, 4)
        add("Coupling base count", ttk.Spinbox(form, from_=0, to=30, textvariable=self.default_base_count), 3, 5)

        add("Loading cocktail solvent (2-CTC default)", ttk.Combobox(form, textvariable=self.default_loading_dissolve_solvent, values=self.SOLVENT_VALUES, state="normal", width=30), 4, 0)
        add("Deprotection base", ttk.Combobox(form, textvariable=self.default_depro, values=self.DEPRO_VALUES, state="normal", width=28), 4, 2)
        add("Deprotection ratio", ttk.Combobox(form, textvariable=self.default_depro_ratio, values=self.RATIO_VALUES, state="normal", width=32), 4, 3)
        add("Deprotection count", ttk.Spinbox(form, from_=0, to=20, textvariable=self.default_depro_count), 4, 4)
        add("Final MeOH wash count", ttk.Spinbox(form, from_=0, to=30, textvariable=self.final_meoh_count), 4, 5)

        add("Solvent 1", ttk.Combobox(form, textvariable=self.default_solvent1, values=self.SOLVENT_VALUES, state="normal", width=28), 5, 0)
        add("Solvent 1 count", ttk.Spinbox(form, from_=0, to=30, textvariable=self.default_solvent1_count), 5, 1)
        add("Solvent 2", ttk.Combobox(form, textvariable=self.default_solvent2, values=self.SOLVENT_VALUES, state="normal", width=28), 5, 2)
        add("Solvent 2 count", ttk.Spinbox(form, from_=0, to=30, textvariable=self.default_solvent2_count), 5, 3)

        add("Output folder", ttk.Entry(form, textvariable=self.outdir), 6, 0, span=5)
        ttk.Button(form, text="Browse", command=self.browse_outdir).grid(row=6, column=11, sticky="ew", padx=4)

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
        ttk.Button(btns, text="Reset column widths", command=self.reset_column_widths).pack(side="left", padx=4)
        ttk.Label(btns, text="Primary actions are in the top action bar. Double-click a cell to edit; edits auto-update usage.").pack(side="left", padx=12)

        self.tabs = ttk.Notebook(main)
        self.tabs.pack(fill="both", expand=True)

        plan_frame = ttk.Frame(self.tabs)
        self.tabs.add(plan_frame, text="Editable SPPS Plan + Live Usage")
        plan_frame.rowconfigure(0, weight=1)
        plan_frame.columnconfigure(0, weight=1)
        horiz = ttk.PanedWindow(plan_frame, orient="horizontal")
        horiz.grid(row=0, column=0, sticky="nsew")

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
            self.live_usage_tree.column(c, width=110, anchor="w", stretch=True)
        uy = ttk.Scrollbar(usage_frame, orient="vertical", command=self.live_usage_tree.yview)
        ux = ttk.Scrollbar(usage_frame, orient="horizontal", command=self.live_usage_tree.xview)
        self.live_usage_tree.configure(yscrollcommand=uy.set, xscrollcommand=ux.set)
        self.live_usage_tree.grid(row=0, column=0, sticky="nsew")
        uy.grid(row=0, column=1, sticky="ns"); ux.grid(row=1, column=0, sticky="ew")
        horiz.add(usage_frame, weight=3)

        self.plan_width_map = {
            "No": 60,
            "Unit name": 270,
            "Unit eq": 95,
            "Unit amount(g/mL)": 150,
            "Coupling reagent 1": 145,
            "Coupling reagent 1 eq": 135,
            "Coupling reagent 1 count": 145,
            "Coupling reagent 2 / catalyst": 170,
            "Coupling reagent 2 / catalyst eq": 180,
            "Coupling reagent 2 / catalyst count": 195,
            "Coupling base": 140,
            "Coupling base eq": 135,
            "Coupling base count": 150,
            "Coupling cocktail solvent": 190,
            "Coupling cocktail volume(mL)": 200,
            "Coupling base volume(mL)": 170,
            "Deprotection base": 160,
            "Deprotection ratio": 200,
            "Deprotection count": 160,
            "Solvent 1": 100,
            "Solvent 1 count": 130,
            "Solvent 2": 100,
            "Solvent 2 count": 130,
            "Repeat": 80,
        }
        existing_plan_columns = set(self.tree["columns"])
        for k, v in self.plan_width_map.items():
            if k in existing_plan_columns:
                self.tree.column(k, width=v, minwidth=80, stretch=True)

        self.material_tree = self._tree_tab("Material Usage table", self.MATERIAL_COLUMNS)
        self.form_text = self._text_tab("Operation Form")
        self.check_text = self._text_tab("Printable Checklist")
        self.ml_text = self._text_tab("ML-ready Log")
        self.log_text = self._text_tab("Log")

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
            # keep the horizontal scrollbar active and preserve user data
            self.tree.update_idletasks()
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
        is_non_fmoc_final = self._is_ac_unit(unit_name) or any(x in unit_u for x in ["FITC", "BIOTIN", "CY", "FAM", "TAMRA", "DOTA", "NOTA", "PAL", "MYR", "GAL", "NIC", "CAF"])
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
                    note = (note + " | non-Fmoc modifier/label/chemical step; no post-coupling deprotection").strip(" |")
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
                    "Unit amount(g/mL)": amount_display,
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
                "Unit amount(g/mL)": "",
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
                    "Unit amount(g/mL)": amount_display,
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
        return str(name or "").strip().upper() in {"AC", "AC-", "ACETYL", "ACETYL CAP", "AC / ACETYL CAP"}

    def _amount_basis_for_unit(self, display_name: str, phase: str, coupling_reagent: str, mw: float):
        """Return calculation basis for the unit row.

        The editable row should show the user-facing unit such as 'Ac', but
        N-terminal acetylation is calculated from the actual liquid reagent
        Acetic anhydride (Ac2O) by default. Ac2O/AcOH must not appear in the
        coupling reagent columns.
        """
        if self._is_ac_unit(display_name):
            return "Ac2O", 102.09, "Ac2O"
        return display_name, mw, coupling_reagent or display_name

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

    def _normalize_unit_display_name(self, name: str) -> str:
        s = str(name or "").strip()
        u = s.upper().strip()
        if u in {"AC", "AC / ACETYL CAP", "ACETYL CAP", "AC-", "ACETYL"}:
            return "Ac"
        return s

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
        # Final Ac / chemical / tag / label / modifier rows are non-Fmoc
        # operations. They must not schedule their own deprotection.
        # If a terminal modifier follows a Fmoc-AA, the required Fmoc removal is
        # assigned to the preceding last Fmoc-AA row as the final deprotection,
        # not to the modifier row itself.
        if self._is_non_fmoc_modifier_row(row_dict, meta):
            return False
        if self._is_first_synthesis_row(row_dict) and not self._resin_needs_initial_deprotection():
            return False
        return True

    def _is_non_fmoc_modifier_row(self, row_dict: dict, meta: dict | None = None) -> bool:
        """Return True for final N-terminal chemical/label/modifier steps.

        These steps do not introduce an Fmoc-protected amino acid, so the planner
        must not schedule a deprotection after the modifier coupling. Examples:
        Ac, FITC, Biotin, Cy dyes, FAM/TAMRA, Pal/Myr/Gal/Nic/Caf, tags and linkers
        when represented as chemical/modifier rows.
        """
        meta = meta or {}
        phase = str(meta.get("Phase", row_dict.get("Phase", ""))).lower()
        name = str(row_dict.get("Unit name", "")).upper()
        markers = [
            "modifier", "label", "chemical", "n-term", "n_terminal", "terminal",
            "AC", "ACETYL", "FITC", "BIOTIN", "CY3", "CY5", "CY7", "FAM",
            "TAMRA", "DABCYL", "DOTA", "NOTA", "PAL", "MYR", "GAL", "NIC",
            "CAF", "PEG", "AHX", "LINKER", "TAG", "NHS"
        ]
        if any(m in phase for m in ["modifier", "label", "chemical", "n-term", "terminal"]):
            return True
        return any(m in name for m in markers)

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
            # For manual rows without MW, preserve the edited amount value.
            amount_display = d.get("Unit amount(g/mL)", "")
            calc_g = self._amount_numeric(amount_display, 0.0) if not self._is_amount_ml(amount_display) else 0.0
            calc_ml = self._amount_numeric(amount_display, 0.0) if self._is_amount_ml(amount_display) else 0.0
            amount_unit = "mL" if self._is_amount_ml(amount_display) else "g"

        d["Unit amount(g/mL)"] = amount_display
        # Coupling reagent/catalyst eq fields are intentionally optional.
        # Do not auto-fill them from the AA/modifier eq: some protocols use
        # only base or a manually selected reagent system, and blank reagent eq
        # should remain blank rather than being forced.

        # Rows that truly do not require pre-reaction Fmoc removal are kept at
        # deprotection count 0. Final Ac/chemical/label/modifier rows may still
        # carry a pre-reaction deprotection, but no post-coupling deprotection is
        # generated after the modifier reaction.
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
        plan_df = pd.DataFrame(rows)
        materials = self.materials_from_rows(plan_df)
        ml = self.ml_log_from_rows(plan_df)
        ops = self.operation_form_from_rows(plan_df)
        checklist = self.checklist_from_rows(plan_df)
        self._write_tree(self.live_usage_tree, materials, self.MATERIAL_COLUMNS)
        self._write_tree(self.material_tree, materials, self.MATERIAL_COLUMNS)
        self._write_df(self.ml_text, ml)
        self._write_df(self.form_text, ops)
        self._write_df(self.check_text, checklist)

    def _estimate_reagent_g(self, name, mmol):
        mw = self.MW_FALLBACK.get(str(name).strip(), 0.0)
        return mmol * mw / 1000 if mw else 0.0

    def materials_from_rows(self, plan_df: pd.DataFrame) -> pd.DataFrame:
        """Build a process-ordered material usage table from the editable plan.

        Important SPPS rules enforced here:
        - A coupling row uses one coupling cocktail solvent for unit + reagent 1 + reagent 2/catalyst + base.
        - Non-Fmoc final rows such as Ac/chemical/tag/label/modifier do not receive deprotection of their own.
        - If a terminal non-Fmoc modifier follows a Fmoc-AA chain, the required Fmoc removal is displayed as
          "pre-modifier Fmoc removal" before the modifier row, not as a modifier deprotection.
        - Final deprotection is followed only by final wash DMF x3 / DCM x3 / optional MeOH, not by DMF x6.
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
                final_depro_added = True

        for _, r in plan_df.iterrows():
            step = str(r.get("No", ""))
            meta = self._row_meta_by_no.get(str(step), {})
            name = str(r.get("Unit name", "") or "")
            eq = self._to_float(r.get("Unit eq"), 0)
            repeat = max(1, self._to_int(r.get("Repeat"), 1))
            mmol = scale * eq * repeat
            amount_cell = r.get("Unit amount(g/mL)")
            phase = meta.get("Phase", "")
            note = meta.get("Note", "")
            row_dict = r.to_dict() if hasattr(r, "to_dict") else dict(r)
            is_non_fmoc_final = str(step) == str(final_non_fmoc_step)
            is_last_fmoc = str(step) == str(last_fmoc_step)

            # Before a final Ac/chemical/tag/label/modifier row, show the Fmoc removal as a pre-modifier operation,
            # never as a deprotection attached to the modifier row.
            if is_non_fmoc_final and last_fmoc_step:
                add_final_depro_before(last_fmoc_step, before_step_note=f"before step {step}")

            # Standard pre-coupling deprotection for Fmoc-AA rows only.
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
                if self._is_amount_ml(amount_cell):
                    add(step=step, material=name, cls="AA/Chemical/label/tag/linker", mmol=mmol,
                        ml=self._amount_numeric(amount_cell, 0.0), repeat=repeat, phase=phase, note=note, src=f"step {step}", mw=mw_unit)
                else:
                    g = self._amount_numeric(amount_cell, self._to_float(meta.get("calculated g"), 0))
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
            s1_count = self._to_int(r.get("Solvent 1 count"), 0)
            s2_count = self._to_int(r.get("Solvent 2 count"), 0)
            add(step=f"{step}; post-coupling wash", material=r.get("Solvent 1"), cls="post-coupling wash solvent",
                ml=per_use_ml * s1_count, count=s1_count, phase="post-coupling wash",
                note="Default transition wash after coupling is DMF x2 unless edited", src=f"step {step}")
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

            # For terminal non-Fmoc rows: no deprotection after the row; only final wash.
            if is_non_fmoc_final:
                for solvent_name, wash_count in self._final_wash_specs():
                    if wash_count > 0:
                        add(step=f"{step}; final wash", material=solvent_name, cls="final wash solvent",
                            ml=per_use_ml * wash_count, count=wash_count, phase="final wash",
                            note="Final wash after non-Fmoc Ac/chemical/tag/label/modifier; no post-modifier deprotection", src=f"step {step}; final wash")

        df = pd.DataFrame(rows)
        if not df.empty:
            for col in ["planned_mmol", "planned_g", "planned_mL"]:
                if col in df.columns:
                    df[col] = df[col].apply(lambda x: round(float(x), 4) if str(x) not in ["", "nan"] else x)
        return df

    def ml_log_from_rows(self, plan_df: pd.DataFrame) -> pd.DataFrame:
        out = plan_df.copy()
        out.insert(0, "sequence", self.seq.get())
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
        # Always preserve the preceding last Fmoc-AA final deprotection.
        # Final non-Fmoc modifier rows do not receive deprotection of their own.
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
                    note_extra = "After this Fmoc-AA coupling: DMF wash x2 -> final deprotection -> final wash"
                elif is_final_non_fmoc:
                    op_name = "final chemical / label / modifier coupling"
                    note_extra = "No post-modifier Fmoc deprotection; final wash follows"
                else:
                    op_name = "coupling reaction"
                    note_extra = "STD cycle: coupling -> DMF wash x2 -> next cycle"
                ops.append({"line": line, "step": step, "operation": op_name, "unit": unit, "solution": f"Prepare coupling cocktail: {unit} + {r.get('Coupling reagent 1','')} + {r.get('Coupling reagent 2 / catalyst','')} + {r.get('Coupling base','')} in {r.get('Coupling cocktail solvent', r.get('Solvent 1',''))} ({r.get('Coupling cocktail volume(mL)','')} mL); add to resin", "repeat/count": i+1, "date": "", "operator": "", "note": (str(meta.get("Note", r.get("Note", ""))) + " | " + note_extra).strip(" |")}); line += 1

            s1 = r.get("Solvent 1", ""); c1 = self._to_int(r.get("Solvent 1 count"), 0)
            s2 = r.get("Solvent 2", ""); c2 = self._to_int(r.get("Solvent 2 count"), 0)
            if c1 > 0 or c2 > 0:
                ops.append({"line": line, "step": step, "operation": "post-coupling wash", "unit": unit, "solution": f"{s1} x {c1} / {s2} x {c2}", "repeat/count": "", "date": "", "operator": "", "note": "Default transition wash is DMF x2; DCM is not used between ordinary coupling cycles unless edited by the user"}); line += 1

            if is_last_fmoc and dcount > 0 and needs_pre_depro:
                ops.append({"line": line, "step": step, "operation": "final deprotection", "unit": unit, "solution": f"{depro} ({ratio})", "repeat/count": dcount, "date": "", "operator": "", "note": "Final Fmoc deprotection after the last Fmoc-AA coupling"}); line += 1

            if is_last_fmoc or is_final_non_fmoc:
                for solvent_name, wash_count in self._final_wash_specs():
                    ops.append({"line": line, "step": step, "operation": "final wash", "unit": unit, "solution": solvent_name, "repeat/count": wash_count, "date": "", "operator": "", "note": "Final wash after final deprotection or final non-Fmoc chemical/label/modifier coupling"}); line += 1
        return pd.DataFrame(ops)

    def checklist_from_rows(self, plan_df: pd.DataFrame) -> pd.DataFrame:
        """Printable checklist with one row per practical SPPS operation."""
        rows = []
        line = 1
        swell_solvent = self._swell_solvent_for_resin()
        loading_family = "DCM-family loading" if self._resin_family_text() == "CTC/Trityl" else "DMF-family loading / preloaded Fmoc resin handling"
        rows.append({"Line": line, "Step": "swell", "Operation": "Resin swell", "AA/Chemical/label/tag/linker": self.resin.get(), "Reagent/Solution": swell_solvent, "Eq/Count": 1, "Amount(g or mL)": "", "Date": "", "Checked": "□", "Operator": "", "Note": f"Swell before loading; {loading_family}"}); line += 1
        final_non_fmoc_step = self._last_non_fmoc_final_step_no(plan_df)
        # Always preserve the preceding last Fmoc-AA final deprotection.
        # Final non-Fmoc modifier rows do not receive deprotection of their own.
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
                    rows.append({"Line": line, "Step": step, "Operation": "Deprotection", "AA/Chemical/label/tag/linker": unit, "Reagent/Solution": f"{depro} ({ratio})", "Eq/Count": i+1, "Amount(g or mL)": "", "Date": "", "Checked": "□", "Operator": "", "Note": "Pre-coupling Fmoc deprotection"}); line += 1
                for i in range(6):
                    rows.append({"Line": line, "Step": step, "Operation": "DMF wash after deprotection", "AA/Chemical/label/tag/linker": unit, "Reagent/Solution": "DMF", "Eq/Count": i+1, "Amount(g or mL)": "", "Date": "", "Checked": "□", "Operator": "", "Note": "STD cycle: DMF wash x6 before coupling"}); line += 1

            for i in range(rep):
                op = "Resin loading / first unit attachment" if is_loading else ("Last coupling step" if is_last_fmoc else ("Final chemical / label / modifier coupling" if is_final_non_fmoc else "Coupling reaction"))
                rows.append({"Line": line, "Step": step, "Operation": op, "AA/Chemical/label/tag/linker": unit, "Reagent/Solution": f"Coupling cocktail: {unit} + {r.get('Coupling reagent 1','')} + {r.get('Coupling reagent 2 / catalyst','')} + {r.get('Coupling base','')} in {r.get('Coupling cocktail solvent', r.get('Solvent 1',''))} ({r.get('Coupling cocktail volume(mL)','')} mL)", "Eq/Count": f"repeat {i+1}/{rep}; unit eq={r.get('Unit eq','')}", "Amount(g or mL)": r.get("Unit amount(g/mL)", ""), "Date": "", "Checked": "□", "Operator": "", "Note": str(meta.get("Note", ""))}); line += 1

            s1 = r.get("Solvent 1", ""); c1 = self._to_int(r.get("Solvent 1 count"), 0)
            s2 = r.get("Solvent 2", ""); c2 = self._to_int(r.get("Solvent 2 count"), 0)
            for i in range(c1):
                rows.append({"Line": line, "Step": step, "Operation": "Post-coupling wash", "AA/Chemical/label/tag/linker": unit, "Reagent/Solution": s1, "Eq/Count": i+1, "Amount(g or mL)": "", "Date": "", "Checked": "□", "Operator": "", "Note": "Default transition wash is DMF x2"}); line += 1
            for i in range(c2):
                rows.append({"Line": line, "Step": step, "Operation": "Post-coupling wash", "AA/Chemical/label/tag/linker": unit, "Reagent/Solution": s2, "Eq/Count": i+1, "Amount(g or mL)": "", "Date": "", "Checked": "□", "Operator": "", "Note": "User-edited/special wash"}); line += 1

            if is_last_fmoc and dcount > 0 and needs_pre_depro:
                for i in range(dcount):
                    rows.append({"Line": line, "Step": step, "Operation": "Final deprotection", "AA/Chemical/label/tag/linker": unit, "Reagent/Solution": f"{depro} ({ratio})", "Eq/Count": i+1, "Amount(g or mL)": "", "Date": "", "Checked": "□", "Operator": "", "Note": "After last Fmoc-AA coupling"}); line += 1

            if is_last_fmoc or is_final_non_fmoc:
                for solvent_name, wash_count in self._final_wash_specs():
                    for i in range(wash_count):
                        rows.append({"Line": line, "Step": step, "Operation": "Final wash", "AA/Chemical/label/tag/linker": unit, "Reagent/Solution": solvent_name, "Eq/Count": i+1, "Amount(g or mL)": "", "Date": "", "Checked": "□", "Operator": "", "Note": "DMF x3 / DCM x3; optional MeOH x3 depending on lab practice"}); line += 1
        return pd.DataFrame(rows)


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
                return
            for _, row in df.iterrows():
                vals = [row.get(c, "") for c in columns]
                tree.insert("", "end", values=vals)
        except Exception as e:
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

    def export_outputs(self):
        try:
            outdir = Path(self.outdir.get()); outdir.mkdir(parents=True, exist_ok=True)
            plan = pd.DataFrame(self.tree_rows())
            materials = self.materials_from_rows(plan)
            ml = self.ml_log_from_rows(plan)
            ops = self.operation_form_from_rows(plan)
            checklist = self.checklist_from_rows(plan)
            plan.to_csv(outdir / "editable_spps_plan.csv", index=False, encoding="utf-8-sig")
            materials.to_csv(outdir / "material_usage_from_editable_plan.csv", index=False, encoding="utf-8-sig")
            ops.to_csv(outdir / "operation_form_from_editable_plan.csv", index=False, encoding="utf-8-sig")
            checklist.to_csv(outdir / "printable_synthesis_checklist.csv", index=False, encoding="utf-8-sig")
            ml.to_csv(outdir / "spps_ml_ready_log_from_editable_plan.csv", index=False, encoding="utf-8-sig")
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
                try:
                    pd.DataFrame([plan_summary(self._input())]).to_excel(writer, index=False, sheet_name="05_SUMMARY")
                except Exception:
                    pass
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
