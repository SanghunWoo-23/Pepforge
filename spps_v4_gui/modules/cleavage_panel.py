"""Cleavage cocktail panel helpers for SPPS Planner V4.0.0."""
from __future__ import annotations
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
    ):
        if not hasattr(gui, attr):
            try: setattr(gui, attr, tk.StringVar(value=default))
            except Exception: pass


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
        frame.rowconfigure(1, weight=1); frame.columnconfigure(0, weight=1)
    except Exception:
        pass
    if not getattr(gui, "_v2097_cleavage_controls_added", False):
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
        gui._v2097_cleavage_controls_added = True
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
        tree.grid(row=1, column=0, sticky="nsew")
        y.grid(row=1, column=1, sticky="ns")
        x.grid(row=2, column=0, sticky="ew")
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
