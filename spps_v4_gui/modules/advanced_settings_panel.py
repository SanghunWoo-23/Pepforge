"""Advanced chemistry/default/override controls for the modern Tk GUI."""
from __future__ import annotations
from pathlib import Path
from . import gui_common as state

SCALE_PRESETS = {
    "Lab STD 400 mmol": "400",
    "Small bench 0.4 mmol": "0.4",
    "Micro test 0.2 mmol": "0.2",
    "Custom / manual": None,
}


def apply_scale_preset(gui) -> None:
    preset = state.get_var(gui, "scale_preset", "Custom / manual")
    value = SCALE_PRESETS.get(str(preset))
    if value is not None:
        state.set_var(gui, "pm_scale", value)
    try:
        gui._log(f"Scale preset applied: {preset} -> {state.get_var(gui, 'pm_scale', '')} mmol\n")
    except Exception:
        pass


def ensure_advanced_variables(gui) -> None:
    try:
        import tkinter as tk
    except Exception:
        return
    defaults = {
        "scale_preset": "Lab STD 400 mmol",
        "auto_short_peptide_eq": True,
        "short_peptide_coupling_eq": "2",
        "coupling_eq": "5",
        "modifier_eq": "3",
        "coupling_repeats": "1",
        "modifier_repeats": "1",
        "default_reagent": "DIC",
        "default_catalyst": "HOBt",
        "default_base": "",
        "default_coupling_solution_solvent": "DMF",
    }
    for attr, default in defaults.items():
        if not hasattr(gui, attr):
            var = tk.BooleanVar(value=bool(default)) if isinstance(default, bool) else tk.StringVar(value=str(default))
            setattr(gui, attr, var)


def build_advanced_tab(gui, notebook) -> None:
    ensure_advanced_variables(gui)
    import tkinter as tk
    import tkinter.ttk as ttk

    frame = ttk.Frame(notebook, padding=10)
    notebook.add(frame, text="Advanced Settings")
    frame.columnconfigure(0, weight=1)
    frame.columnconfigure(1, weight=1)

    scale_box = ttk.LabelFrame(frame, text="Scale preset / 기본 scale", padding=8)
    scale_box.grid(row=0, column=0, sticky="ew", padx=(0, 6), pady=(0, 8))
    scale_box.columnconfigure(1, weight=1)
    ttk.Label(scale_box, text="Preset").grid(row=0, column=0, sticky="w")
    cb = ttk.Combobox(scale_box, textvariable=gui.scale_preset, values=list(SCALE_PRESETS), state="readonly", width=28)
    cb.grid(row=0, column=1, sticky="ew", padx=6)
    ttk.Button(scale_box, text="Apply preset", command=lambda: (apply_scale_preset(gui), state.save_active(gui))).grid(row=0, column=2, padx=(6,0))
    ttk.Label(scale_box, text="CLI default와 GUI default를 Lab STD 400 mmol로 맞췄고, 0.4/0.2는 preset으로 선택합니다.", foreground="#555").grid(row=1, column=0, columnspan=3, sticky="w", pady=(5,0))

    stoich = ttk.LabelFrame(frame, text="Stoichiometry / repeats", padding=8)
    stoich.grid(row=1, column=0, sticky="nsew", padx=(0, 6), pady=(0, 8))
    stoich.columnconfigure(1, weight=1)
    fields = [
        ("Default AA coupling eq", gui.coupling_eq),
        ("Modifier/label/tag eq", gui.modifier_eq),
        ("Default AA repeat", gui.coupling_repeats),
        ("Modifier repeat", gui.modifier_repeats),
        ("Short peptide AA eq", gui.short_peptide_coupling_eq),
    ]
    for r, (label, var) in enumerate(fields):
        ttk.Label(stoich, text=label).grid(row=r, column=0, sticky="w", pady=2)
        ttk.Entry(stoich, textvariable=var, width=16).grid(row=r, column=1, sticky="w", pady=2, padx=(6,0))
    ttk.Checkbutton(stoich, text="Auto short peptide rule: 1–5 mer = 2 eq", variable=gui.auto_short_peptide_eq).grid(row=len(fields), column=0, columnspan=2, sticky="w", pady=(6,0))

    chem = ttk.LabelFrame(frame, text="Chemistry defaults", padding=8)
    chem.grid(row=1, column=1, sticky="nsew", padx=(6, 0), pady=(0, 8))
    chem.columnconfigure(1, weight=1)
    reagent_values = ["DIC", "HBTU", "HATU", "HCTU", "TBTU", "TSTU", "TNTU", "PyBOP", "PyBrOP", "PyClocK", "COMU", "DCC", "EDC-HCl", "DEPBT", "Ghosez reagent", ""]
    rows = [
        ("Coupling reagent", gui.default_reagent, reagent_values),
        ("Catalyst/additive", gui.default_catalyst, ["HOBt", "HOAt", "Oxyma", ""]),
        ("Base", gui.default_base, ["", "DIEA", "DIPEA", "TEA", "NMM"]),
        ("Reaction solvent", gui.default_coupling_solution_solvent, ["DMF", "DCM", "NMP", "DMF/DCM"]),
    ]
    for r, (label, var, values) in enumerate(rows):
        ttk.Label(chem, text=label).grid(row=r, column=0, sticky="w", pady=2)
        ttk.Combobox(chem, textvariable=var, values=values, width=28).grid(row=r, column=1, sticky="ew", pady=2, padx=(6,0))

    override = ttk.LabelFrame(frame, text="Manual step/reagent overrides", padding=8)
    override.grid(row=2, column=0, columnspan=2, sticky="nsew")
    frame.rowconfigure(2, weight=1)
    override.rowconfigure(1, weight=1); override.columnconfigure(0, weight=1)
    ttk.Label(override, text="예: unit=FITC; reagent_eq=2; base=DIEA  또는  step=3; coupling_repeat=2", foreground="#555").grid(row=0, column=0, sticky="w")
    text = tk.Text(override, height=7, wrap="none")
    text.grid(row=1, column=0, sticky="nsew", pady=(4,0))
    gui.step_overrides_text_widget = text
    y = ttk.Scrollbar(override, orient="vertical", command=text.yview)
    y.grid(row=1, column=1, sticky="ns")
    text.configure(yscrollcommand=y.set)
    ttk.Button(override, text="Generate / Update with overrides", command=lambda: gui._pm_controller.generate_update()).grid(row=2, column=0, sticky="e", pady=(6,0))
