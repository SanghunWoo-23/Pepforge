"""Cleavage cocktail panel helpers for SPPS Planner V3.0.0."""
from __future__ import annotations
from suite_gui import runtime_state
from . import gui_common as state


def ensure_cleavage_vars(gui) -> None:
    try:
        import tkinter as tk
    except Exception:
        tk = None
    if tk is None:
        return
    for attr, default in (
        ("cleavage_eq_override", "0"),
        ("cleavage_preset", "AUTO"),
        ("cleavage_components_text", ""),
        ("cleavage_time_h", ""),
        ("post_cleavage_rescue", "None"),
        ("nh4i_eq", "2"),
        ("nh4i_concentration_m", "0.2"),
        ("nh4i_time_h", "1"),
    ):
        if not hasattr(gui, attr):
            try: setattr(gui, attr, tk.StringVar(value=default))
            except Exception: pass



NH4I_MW_G_MOL = 144.94

def post_cleavage_rescue_summary(gui) -> dict:
    """Return a separate post-cleavage rescue calculation; never a cocktail row."""
    ensure_cleavage_vars(gui)
    rescue=str(getattr(gui,"post_cleavage_rescue").get() or "None").strip()
    if rescue != "NH4I Reduction":
        return {"enabled":False,"rescue":"None","valid":True,"note":"Default: no post-cleavage rescue."}
    def num(attr,default):
        try: return float(getattr(gui,attr).get())
        except Exception: return float(default)
    eq=num("nh4i_eq",2.0); conc=num("nh4i_concentration_m",0.2); time_h=num("nh4i_time_h",1.0)
    try:
        scale=float(state.plan_input(gui).scale_mmol)
    except Exception:
        try: scale=float(getattr(gui,"pm_scale").get())
        except Exception: scale=0.0
    valid=bool(eq>0 and conc>0 and conc<=0.2 and time_h>0 and scale>0)
    mmol=scale*eq if scale>0 and eq>0 else None
    mass_mg=(mmol*NH4I_MW_G_MOL) if mmol is not None else None
    final_ml=(mmol/conc) if mmol is not None and conc>0 else None
    warning=""
    if conc>0.2:
        warning="NH4I concentration >0.2 M is blocked by the operator protocol because precipitation can occur."
    elif conc<=0:
        warning="NH4I concentration must be >0 and ≤0.2 M."
    elif scale<=0:
        warning="Enter a valid peptide scale to calculate NH4I amount."
    return {
        "enabled":True,"rescue":"NH4I Reduction","valid":valid,"nh4i_eq":eq,"concentration_m":conc,"time_h":time_h,
        "peptide_scale_mmol":scale,"nh4i_mmol":mmol,"nh4i_mass_mg":mass_mg,"final_solution_ml":final_ml,
        "solvent":"TFA / DW","warning":warning,
        "note":"Conditional post-cleavage rescue only; use after oxidation/specific impurity is observed. It is not part of the cleavage cocktail.",
    }

def install_post_cleavage_rescue_controls(gui, frame, *, row: int = 1):
    """Add one compact rescue row to the existing Cleavage Cocktail panel."""
    ensure_cleavage_vars(gui)
    try:
        import tkinter.ttk as ttk
        import tkinter as tk
    except Exception:
        return None
    box=ttk.LabelFrame(frame,text="Post-cleavage Rescue",padding=(6,4))
    box.grid(row=row,column=0,columnspan=2,sticky="ew",padx=4,pady=(0,4))
    ttk.Label(box,text="Rescue").pack(side="left",padx=(0,3))
    rescue=ttk.Combobox(box,textvariable=gui.post_cleavage_rescue,values=["None","NH4I Reduction"],state="readonly",width=18)
    rescue.pack(side="left",padx=(0,10))
    ttk.Label(box,text="NH4I eq").pack(side="left",padx=(0,3)); eq=ttk.Entry(box,textvariable=gui.nh4i_eq,width=6); eq.pack(side="left",padx=(0,8))
    ttk.Label(box,text="Conc. (M)").pack(side="left",padx=(0,3)); conc=ttk.Entry(box,textvariable=gui.nh4i_concentration_m,width=6); conc.pack(side="left",padx=(0,8))
    ttk.Label(box,text="Time (h)").pack(side="left",padx=(0,3)); tm=ttk.Entry(box,textvariable=gui.nh4i_time_h,width=6); tm.pack(side="left",padx=(0,8))
    ttk.Label(box,text="Solvent: TFA / DW").pack(side="left",padx=(0,10))
    summary=tk.StringVar(value="None — use only if oxidation/specific impurity is observed.")
    ttk.Label(box,textvariable=summary).pack(side="left",fill="x",expand=True)
    gui.post_cleavage_rescue_summary_var=summary
    gui._post_cleavage_rescue_widgets=(eq,conc,tm)
    def refresh(*_):
        info=post_cleavage_rescue_summary(gui)
        enabled=bool(info.get("enabled")); state_name="normal" if enabled else "disabled"
        for w in gui._post_cleavage_rescue_widgets:
            try: w.configure(state=state_name)
            except Exception: pass
        if not enabled:
            summary.set("None — use only if oxidation/specific impurity is observed."); return
        if not info.get("valid"):
            summary.set(info.get("warning") or "Invalid rescue settings."); return
        summary.set(f"NH4I {info['nh4i_mmol']:.3g} mmol / {info['nh4i_mass_mg']:.3g} mg; final solution ≈ {info['final_solution_ml']:.3g} mL at {info['concentration_m']:.3g} M")
    for var in (gui.post_cleavage_rescue,gui.nh4i_eq,gui.nh4i_concentration_m,gui.nh4i_time_h):
        try: var.trace_add("write",refresh)
        except Exception: pass
    refresh()
    return box

def _find_results_notebook(gui):
    for w in state.walk_widgets(gui):
        try:
            if w.winfo_class() != "TNotebook":
                continue
            names = [w.tab(tid, "text") for tid in w.tabs()]
            if "Selected Plan" in names and ("Selected Materials" in names or "Batch Summary" in names):
                return w
        except Exception:
            pass
    return None


def ensure_cleavage_panel(gui, ns: dict | None = None):
    ensure_cleavage_vars(gui)
    try:
        import tkinter.ttk as ttk
    except Exception:
        return getattr(gui, "pm_cleavage_tree", None)
    nb = _find_results_notebook(gui)
    if nb is None:
        return getattr(gui, "pm_cleavage_tree", None)
    frame = None
    for tid in nb.tabs():
        try:
            if nb.tab(tid, "text") == "Cleavage Cocktail":
                frame = nb.nametowidget(tid)
                break
        except Exception:
            pass
    if frame is None:
        frame = ttk.Frame(nb)
        nb.add(frame, text="Cleavage Cocktail")
    try:
        frame.rowconfigure(2, weight=1); frame.columnconfigure(0, weight=1)
    except Exception:
        pass
    if not runtime_state.get_flag(gui,"cleavage_controls_added"):
        ctl = ttk.Frame(frame)
        ctl.grid(row=0, column=0, columnspan=2, sticky="ew", padx=4, pady=4)
        try:
            state.ensure_app_path()
            from spps_planner.engine import cleavage_cocktail_presets
            presets = ["AUTO"] + cleavage_cocktail_presets()["preset"].tolist() + ["CUSTOM"]
        except Exception:
            presets = ["AUTO", "DEFAULT_TFA_TIS_WATER", "CYS_EDT", "REAGENT_B", "REAGENT_K", "CUSTOM"]
        ttk.Label(ctl, text="Eq override (0=auto)").pack(side="left", padx=(0, 2))
        ttk.Entry(ctl, textvariable=gui.cleavage_eq_override, width=8).pack(side="left", padx=(0, 8))
        ttk.Label(ctl, text="Preset").pack(side="left", padx=(0, 2))
        ttk.Combobox(ctl, textvariable=gui.cleavage_preset, values=presets, width=24, state="readonly").pack(side="left", padx=(0, 8))
        ttk.Label(ctl, text="Custom components").pack(side="left", padx=(0, 2))
        ttk.Entry(ctl, textvariable=gui.cleavage_components_text, width=38).pack(side="left", padx=(0, 8), fill="x", expand=True)
        ttk.Label(ctl, text="Time (h)").pack(side="left", padx=(0, 2))
        ttk.Entry(ctl, textvariable=gui.cleavage_time_h, width=7).pack(side="left", padx=(0, 8))
        ttk.Button(ctl, text="Apply cleavage", command=lambda _gui=gui: refresh_cleavage_panel(_gui)).pack(side="left")
        for var in (gui.cleavage_eq_override, gui.cleavage_preset, gui.cleavage_components_text, gui.cleavage_time_h):
            try: var.trace_add("write", lambda *_args, _gui=gui: _gui.after_idle(lambda: refresh_cleavage_panel(_gui)))
            except Exception: pass
        runtime_state.set_flag(gui,"cleavage_controls_added",True)
    if not runtime_state.get_flag(gui,"post_cleavage_rescue_added"):
        install_post_cleavage_rescue_controls(gui, frame, row=1)
        runtime_state.set_flag(gui,"post_cleavage_rescue_added",True)
    tree = getattr(gui, "pm_cleavage_tree", None)
    try:
        exists = bool(tree and str(tree.winfo_exists()))
    except Exception:
        exists = False
    if not exists:
        cols = ["component", "role", "recommended_eq", "percent", "percent_basis", "volume_mL", "density_g_mL", "approx_g", "include", "note"]
        tree = ttk.Treeview(frame, columns=cols, show="headings", height=12, selectmode="extended")
        for c in cols:
            tree.heading(c, text=c); tree.column(c, width=130 if c != "note" else 450, anchor="w", stretch=False)
        y = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        x = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        tree.grid(row=2, column=0, sticky="nsew")
        y.grid(row=2, column=1, sticky="ns")
        x.grid(row=3, column=0, sticky="ew")
        gui.pm_cleavage_tree = tree
    return gui.pm_cleavage_tree


def refresh_cleavage_panel(gui, ns: dict | None = None):
    try:
        state.ensure_app_path()
        from spps_planner.engine import generate_cleavage_cocktail
        tree = ensure_cleavage_panel(gui)
        if tree is None:
            return None
        df = generate_cleavage_cocktail(state.plan_input(gui))
        state.write_tree(tree, df)
        return df
    except Exception:
        return None
