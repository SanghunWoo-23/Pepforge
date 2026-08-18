"""Shared Tk Project Manager helpers for SPPS Planner V4.0.0.

This module is the first real extraction from the historical 43k-line Tk file.
It owns state snapshots, list refresh, tree export, PlanInput construction, and
selected-output refresh.  New GUI patches should call these helpers instead of
legacy ``_v2093_*`` globals.
"""
from __future__ import annotations

from pathlib import Path
import json
import sys
from typing import Any, Iterable


def ensure_app_path() -> Path:
    root = Path(__file__).resolve().parents[2]
    app = root / "apps" / "spps_planner_app"
    for p in (str(root), str(app)):
        if p not in sys.path:
            sys.path.insert(0, p)
    return app


def walk_widgets(gui) -> list[Any]:
    out: list[Any] = []
    try:
        stack = list(gui.winfo_children())
    except Exception:
        return out
    while stack:
        w = stack.pop(0)
        out.append(w)
        try:
            stack.extend(w.winfo_children())
        except Exception:
            pass
    return out


def get_var(gui, attr: str, default: Any = "") -> Any:
    try:
        v = getattr(gui, attr)
        return v.get() if hasattr(v, "get") else v
    except Exception:
        return default


def set_var(gui, attr: str, value: Any) -> None:
    try:
        v = getattr(gui, attr)
        if hasattr(v, "set"):
            v.set("" if value is None else str(value))
        else:
            setattr(gui, attr, value)
    except Exception:
        pass

def get_text_widget_value(gui, attr: str, default: str = "") -> str:
    try:
        w = getattr(gui, attr)
        return w.get("1.0", "end-1c")
    except Exception:
        return default or ""


def set_text_widget_value(gui, attr: str, value: Any) -> None:
    try:
        w = getattr(gui, attr)
        w.delete("1.0", "end")
        if value is not None:
            w.insert("1.0", str(value))
    except Exception:
        pass


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        text = str(value).strip()
        if not text:
            return default
        return float(text)
    except Exception:
        return default


def as_int(value: Any, default: int = 0) -> int:
    try:
        text = str(value).strip()
        if not text:
            return default
        return int(float(text))
    except Exception:
        return default

def as_bool(value: Any, default: bool = False) -> bool:
    try:
        if isinstance(value, bool):
            return value
        if hasattr(value, "get"):
            value = value.get()
        text = str(value).strip().lower()
        if text in {"1", "true", "yes", "y", "on"}:
            return True
        if text in {"0", "false", "no", "n", "off", ""}:
            return False
    except Exception:
        pass
    return bool(default)


def normalize_resin(text: str) -> str:
    low = str(text or "").lower().replace("-", " ")
    if any(x in low for x in ("ctc", "trityl", "chlorotrityl", "2 chloro")):
        return "CTC/Trityl"
    return "Amide"


def parse_chemistry(chemistry: str, default_reagent: str = "DIC", default_catalyst: str = "HOBt", default_base: str = "") -> tuple[str, str, str]:
    text = str(chemistry or "").strip()
    if not text:
        return default_reagent or "DIC", default_catalyst or "HOBt", default_base or ""
    compact = text.upper().replace(" ", "")
    if compact in {"DIC", "DIC/HOBT", "DIC+HOBT"}:
        return "DIC", "HOBt", ""
    if compact in {"DCC", "DCC/HOBT", "DCC+HOBT"}:
        return "DCC", "HOBt", ""
    if compact in {"HBTU", "HBTU/DIEA", "HBTU+DIPEA", "HBTU/DIPEA"}:
        return "HBTU", "", "DIEA"
    if compact in {"HATU", "HATU/DIEA", "HATU/DIPEA"}:
        return "HATU", "", "DIEA"
    if compact in {"COMU", "COMU/DIEA", "COMU/DIPEA"}:
        return "COMU", "", "DIEA"
    if compact in {"PYBOP", "PYBOP/DIEA", "PYBOP/DIPEA"}:
        return "PyBOP", "", "DIEA"
    parts = [p.strip() for p in text.replace("+", "/").split("/") if p.strip()]
    reagent = parts[0] if parts else (default_reagent or "DIC")
    catalyst = ""
    base = default_base or ""
    for p in parts[1:]:
        up = p.upper()
        if up in {"DIEA", "DIPEA", "TEA", "NMM", "COLLIDINE", "BASE"}:
            base = "DIEA" if up == "DIPEA" else p
        elif up in {"HOBT", "HOAT", "OXYMA"}:
            catalyst = p
        else:
            base = p
    return reagent, catalyst or default_catalyst or "", base


def active_index(gui) -> int | None:
    for attr in ("_v2097_active_index", "_v2096_active_index", "_v2095_active_index", "_v2093_active_index"):
        try:
            idx = getattr(gui, attr)
            if idx is not None:
                idx = int(idx)
                if 0 <= idx < len(getattr(gui, "pm_items", []) or []):
                    return idx
        except Exception:
            pass
    try:
        sels = [int(i) for i in gui.pm_list.curselection()]
        if sels:
            idx = sels[0]
            if 0 <= idx < len(getattr(gui, "pm_items", []) or []):
                return idx
    except Exception:
        pass
    return 0 if getattr(gui, "pm_items", None) else None


def selected_indices(gui) -> list[int]:
    n = len(getattr(gui, "pm_items", []) or [])
    try:
        vals = sorted({int(i) for i in gui.pm_list.curselection() if 0 <= int(i) < n})
        if vals:
            return vals
    except Exception:
        pass
    idx = active_index(gui)
    return [idx] if idx is not None else []


def display_name(gui, item: dict[str, Any]) -> str:
    try:
        return gui.pm_display_name(item)
    except Exception:
        project = item.get("project", "")
        peptide = item.get("peptide", item.get("name", ""))
        lot = item.get("lot", item.get("lot_no", ""))
        seq = item.get("sequence", "")
        return f"{project} | {peptide} | {seq} | {lot}".strip(" |")


def refresh_list(gui, selected: Iterable[int] | None = None, load_index: int | None = None) -> None:
    lb = getattr(gui, "pm_list", None)
    items = getattr(gui, "pm_items", []) or []
    if lb is None:
        return
    n = len(items)
    selected_set = sorted({int(i) for i in (selected or []) if 0 <= int(i) < n})
    try:
        lb.delete(0, "end")
        for item in items:
            lb.insert("end", display_name(gui, item))
        lb.selection_clear(0, "end")
        if selected_set:
            for i in selected_set:
                lb.selection_set(i)
            lb.activate(selected_set[0]); lb.see(selected_set[0])
            gui._v2097_active_index = selected_set[0]
        elif n:
            i = 0 if load_index is None else max(0, min(int(load_index), n - 1))
            lb.selection_set(i); lb.activate(i); lb.see(i)
            gui._v2097_active_index = i
    except Exception:
        pass
    try:
        gui.pm_update_summary()
    except Exception:
        pass


def blank_item(gui, n: int = 1) -> dict[str, Any]:
    from datetime import datetime
    try:
        lot = gui._generate_lot_no()
    except Exception:
        lot = f"SPPS-{datetime.now().strftime('%y%m%d')}-{int(n):02d}"
    return {
        "project": f"Project-{int(n):03d}", "peptide": f"Peptide-{int(n):03d}",
        "sequence": "", "copies": "1", "scale": "400", "scale_preset": "Lab STD 400 mmol", "resin": "Rink Amide AM",
        "loading": "0.8", "lot": lot, "lot_no": lot, "chemistry": "DIC/HOBt",
        "status": "Ready", "loading_aa_eq": "2", "loading_diea_eq": "4", "loading_time_h": "",
        "coupling_eq": "5", "coupling_time_h": "0.5", "modifier_eq": "3", "coupling_repeats": "1", "modifier_repeats": "1",
        "default_reagent": "DIC", "default_catalyst": "HOBt", "default_base": "", "default_coupling_solution_solvent": "DMF",
        "auto_short_peptide_eq": True, "short_peptide_coupling_eq": "2", "step_overrides_text": "",
        "cleavage_eq_override": "0", "cleavage_preset": "AUTO", "cleavage_components_text": "", "cleavage_time_h": "",
    }


def save_active(gui) -> None:
    idx = active_index(gui)
    items = getattr(gui, "pm_items", []) or []
    if idx is None or not (0 <= int(idx) < len(items)):
        return
    item = items[int(idx)]
    old = dict(item)
    lot = get_var(gui, "pm_lot", item.get("lot", item.get("lot_no", "")))
    item.update({
        "project": get_var(gui, "pm_project", item.get("project", "")),
        "peptide": get_var(gui, "pm_peptide", item.get("peptide", item.get("name", ""))),
        "sequence": get_var(gui, "pm_sequence", item.get("sequence", "")),
        "scale": get_var(gui, "pm_scale", item.get("scale", "400")),
        "scale_preset": get_var(gui, "scale_preset", item.get("scale_preset", "Custom / manual")),
        "resin": get_var(gui, "pm_resin", item.get("resin", "Rink Amide AM")),
        "loading": get_var(gui, "pm_loading", item.get("loading", "0.8")),
        "lot": lot, "lot_no": lot,
        "chemistry": get_var(gui, "pm_chemistry", item.get("chemistry", "DIC/HOBt")),
        "copies": get_var(gui, "pm_copies", item.get("copies", "1")),
        "status": item.get("status", "Ready"),
        "loading_aa_eq": get_var(gui, "loading_aa_eq", item.get("loading_aa_eq", "2")),
        "loading_diea_eq": get_var(gui, "loading_diea_eq", item.get("loading_diea_eq", "4")),
        "loading_time_h": get_var(gui, "loading_time_h", item.get("loading_time_h", "")),
        "cleavage_eq_override": get_var(gui, "cleavage_eq_override", item.get("cleavage_eq_override", "0")),
        "cleavage_preset": get_var(gui, "cleavage_preset", item.get("cleavage_preset", "AUTO")),
        "coupling_eq": get_var(gui, "coupling_eq", item.get("coupling_eq", "5")),
        "coupling_time_h": get_var(gui, "coupling_time_h", item.get("coupling_time_h", "0.5")),
        "modifier_eq": get_var(gui, "modifier_eq", item.get("modifier_eq", "3")),
        "coupling_repeats": get_var(gui, "coupling_repeats", item.get("coupling_repeats", "1")),
        "modifier_repeats": get_var(gui, "modifier_repeats", item.get("modifier_repeats", "1")),
        "default_reagent": get_var(gui, "default_reagent", item.get("default_reagent", "DIC")),
        "default_catalyst": get_var(gui, "default_catalyst", item.get("default_catalyst", "HOBt")),
        "default_base": get_var(gui, "default_base", item.get("default_base", "")),
        "default_coupling_solution_solvent": get_var(gui, "default_coupling_solution_solvent", item.get("default_coupling_solution_solvent", "DMF")),
        "auto_short_peptide_eq": as_bool(get_var(gui, "auto_short_peptide_eq", item.get("auto_short_peptide_eq", True)), True),
        "short_peptide_coupling_eq": get_var(gui, "short_peptide_coupling_eq", item.get("short_peptide_coupling_eq", "2")),
        "step_overrides_text": get_text_widget_value(gui, "step_overrides_text_widget", item.get("step_overrides_text", "")),
        "cleavage_components_text": get_var(gui, "cleavage_components_text", item.get("cleavage_components_text", "")),
        "cleavage_time_h": get_var(gui, "cleavage_time_h", item.get("cleavage_time_h", "")),
    })
    # Never let a blank editor erase a valid item during duplicate/delete/reorder.
    for key in ("project", "peptide", "sequence", "scale", "resin", "loading", "lot", "lot_no", "chemistry", "copies"):
        if not str(item.get(key, "") or "").strip() and str(old.get(key, "") or "").strip():
            item[key] = old.get(key, "")
    if not str(item.get("lot_no", "") or "").strip() and str(item.get("lot", "") or "").strip():
        item["lot_no"] = item.get("lot", "")
    if not str(item.get("lot", "") or "").strip() and str(item.get("lot_no", "") or "").strip():
        item["lot"] = item.get("lot_no", "")
    try:
        item["apply_loading_calc"] = bool(getattr(gui, "apply_loading_calc").get())
    except Exception:
        pass


def load_item_to_editor(gui, idx: int) -> None:
    items = getattr(gui, "pm_items", []) or []
    try:
        idx = int(idx)
    except Exception:
        return
    if not (0 <= idx < len(items)):
        return
    item = items[idx]
    gui._v2097_active_index = idx
    for attr, key, default in [
        ("pm_project", "project", ""), ("pm_peptide", "peptide", item.get("name", "")),
        ("pm_sequence", "sequence", ""), ("pm_scale", "scale", "400"),
        ("scale_preset", "scale_preset", "Custom / manual"),
        ("pm_resin", "resin", "Rink Amide AM"), ("pm_loading", "loading", "0.8"),
        ("pm_lot", "lot", item.get("lot_no", "")), ("pm_chemistry", "chemistry", "DIC/HOBt"),
        ("pm_copies", "copies", "1"), ("loading_aa_eq", "loading_aa_eq", "2"),
        ("loading_diea_eq", "loading_diea_eq", "4"),
        ("loading_time_h", "loading_time_h", ""),
        ("coupling_eq", "coupling_eq", "5"), ("coupling_time_h", "coupling_time_h", "0.5"), ("modifier_eq", "modifier_eq", "3"),
        ("coupling_repeats", "coupling_repeats", "1"), ("modifier_repeats", "modifier_repeats", "1"),
        ("default_reagent", "default_reagent", "DIC"), ("default_catalyst", "default_catalyst", "HOBt"),
        ("default_base", "default_base", ""), ("default_coupling_solution_solvent", "default_coupling_solution_solvent", "DMF"),
        ("auto_short_peptide_eq", "auto_short_peptide_eq", True), ("short_peptide_coupling_eq", "short_peptide_coupling_eq", "2"),
        ("cleavage_eq_override", "cleavage_eq_override", "0"),
        ("cleavage_preset", "cleavage_preset", "AUTO"),
        ("cleavage_components_text", "cleavage_components_text", ""),
        ("cleavage_time_h", "cleavage_time_h", ""),
    ]:
        value = item.get(key, default)
        if attr == "pm_lot" and not value:
            value = item.get("lot_no", "")
        set_var(gui, attr, value)
    set_text_widget_value(gui, "step_overrides_text_widget", item.get("step_overrides_text", ""))


def plan_input(gui):
    ensure_app_path()
    from spps_planner.engine import PlanInput
    save_active(gui)
    idx = active_index(gui)
    items = getattr(gui, "pm_items", []) or []
    item = items[idx] if idx is not None and 0 <= idx < len(items) else {}
    seq = get_var(gui, "pm_sequence", item.get("sequence", "")) or get_var(gui, "seq", "")
    resin_text = get_var(gui, "pm_resin", item.get("resin", "Rink Amide AM"))
    chem = get_var(gui, "pm_chemistry", item.get("chemistry", "DIC/HOBt"))
    reagent, catalyst, base = parse_chemistry(chem, get_var(gui, "default_reagent", "DIC"), get_var(gui, "default_catalyst", "HOBt"), get_var(gui, "default_base", ""))
    return PlanInput(
        sequence=str(seq), resin=normalize_resin(resin_text),
        scale_mmol=as_float(get_var(gui, "pm_scale", item.get("scale", "400")), 400.0),
        resin_loading_mmol_g=as_float(get_var(gui, "pm_loading", item.get("loading", "0.8")), 0.8),
        coupling_eq=as_float(get_var(gui, "coupling_eq", item.get("coupling_eq", "5")), 5.0),
        ac_eq=as_float(get_var(gui, "modifier_eq", item.get("modifier_eq", "3")), 3.0),
        default_coupling_repeats=max(1, as_int(get_var(gui, "coupling_repeats", item.get("coupling_repeats", "1")), 1)),
        default_modifier_repeats=max(1, as_int(get_var(gui, "modifier_repeats", item.get("modifier_repeats", "1")), 1)),
        default_coupling_reagent=reagent, default_catalyst=catalyst, default_base=base,
        default_reaction_solvent=get_var(gui, "default_coupling_solution_solvent", "DMF") or "DMF",
        loading_aa_eq=as_float(get_var(gui, "loading_aa_eq", item.get("loading_aa_eq", "2")), 2.0),
        loading_diea_eq=as_float(get_var(gui, "loading_diea_eq", item.get("loading_diea_eq", "4")), 4.0),
        loading_time_h=as_float(get_var(gui, "loading_time_h", item.get("loading_time_h", "")), 0.0),
        cleavage_time_h=as_float(get_var(gui, "cleavage_time_h", item.get("cleavage_time_h", "")), 0.0),
        auto_short_peptide_eq=as_bool(get_var(gui, "auto_short_peptide_eq", item.get("auto_short_peptide_eq", True)), True),
        short_peptide_coupling_eq=as_float(get_var(gui, "short_peptide_coupling_eq", item.get("short_peptide_coupling_eq", "2")), 2.0),
        step_overrides_text=get_text_widget_value(gui, "step_overrides_text_widget", item.get("step_overrides_text", "")),
        cleavage_eq_override=as_float(get_var(gui, "cleavage_eq_override", item.get("cleavage_eq_override", "0")), 0.0),
        cleavage_preset=get_var(gui, "cleavage_preset", item.get("cleavage_preset", "AUTO")) or "AUTO",
        cleavage_components_text=get_var(gui, "cleavage_components_text", item.get("cleavage_components_text", "")),
    )


def metadata(gui, inp=None) -> dict[str, Any]:
    ensure_app_path()
    from spps_planner.version import VERSION
    if inp is None:
        inp = plan_input(gui)
    idx = active_index(gui)
    items = getattr(gui, "pm_items", []) or []
    item = items[idx] if idx is not None and 0 <= idx < len(items) else {}
    return {
        "app_version": VERSION,
        "project": item.get("project", get_var(gui, "pm_project", "")),
        "peptide": item.get("peptide", get_var(gui, "pm_peptide", "")),
        "lot_no": item.get("lot", item.get("lot_no", get_var(gui, "pm_lot", ""))),
        "sequence": inp.sequence, "resin": inp.resin,
        "resin_text": item.get("resin", get_var(gui, "pm_resin", "")),
        "scale_mmol": inp.scale_mmol,
        "resin_loading_mmol_g": inp.resin_loading_mmol_g,
        "loading_aa_eq": inp.loading_aa_eq,
        "loading_diea_eq": inp.loading_diea_eq,
        "loading_time_h": inp.loading_time_h,
        "cleavage_time_h": inp.cleavage_time_h,
        "cleavage_eq_override": inp.cleavage_eq_override,
        "cleavage_preset": inp.cleavage_preset,
        "cleavage_components_text": inp.cleavage_components_text,
    }


def add_metadata_columns(df, meta: dict[str, Any]):
    import pandas as pd
    out = df.copy() if df is not None else pd.DataFrame()
    for k, v in reversed(list(meta.items())):
        if k not in out.columns:
            out.insert(0, k, v)
    return out


def tree_to_df(tree):
    import pandas as pd
    try:
        cols = list(tree["columns"])
        rows = []
        for iid in tree.get_children():
            vals = list(tree.item(iid, "values"))
            vals += [""] * max(0, len(cols) - len(vals))
            rows.append(dict(zip(cols, vals)))
        return pd.DataFrame(rows, columns=cols)
    except Exception:
        return pd.DataFrame()


def write_tree(tree, df) -> None:
    if tree is None or df is None:
        return
    cols = [str(c) for c in list(df.columns)]
    try:
        tree.configure(columns=cols, show="headings")
        for c in cols:
            tree.heading(c, text=c)
            width = 80
            if c in {"note", "warning", "source", "operation_detail"}: width = 360
            elif c in {"sequence", "protected_reagent", "reagent", "component"}: width = 170
            elif c in {"project", "peptide", "lot_no"}: width = 130
            tree.column(c, width=width, anchor="w", stretch=False)
        kids = list(tree.get_children())
        if kids:
            tree.delete(*kids)
        for _, row in df.fillna("").iterrows():
            tree.insert("", "end", values=[row.get(c, "") for c in cols])
    except Exception:
        pass



# Columns shown in the GUI Selected Plan tree.  Metadata is kept in Summary/export,
# but the operator-facing plan must stay readable.  Loading/LOT conditions are kept
# at the end so they are not lost while the step plan remains first.
SELECTED_PLAN_DISPLAY_COLUMNS = [
    # Operator-facing synthesis plan.  Repeated metadata is intentionally not
    # shown here; LOT/scale/loading live in Summary and export core sheets.
    "step", "unit", "phase", "chemistry", "protected_reagent",
    "reagent_eq", "coupling_repeat", "total_reagent_eq",
    "planned_reagent_mmol", "planned_reagent_g", "planned_reagent_mg",
    "coupling_reagent", "catalyst", "base", "reaction_solvent",
    "depro_x", "dmf_wash_x", "post_dmf_wash_x", "dcm_wash_x",
    "dmf_mL", "piperidine_mL", "dcm_mL", "note",
]

SELECTED_MATERIAL_DISPLAY_COLUMNS = [
    # Step-by-step operator material table.  Liquids show mL only; solids show g/mg.
    "step", "material", "class", "MW", "density_g_mL",
    "planned_mmol", "planned_g", "planned_mg", "planned_mL", "unit",
    "use_count", "repeat", "phase", "note", "source",
]

SELECTED_TOTAL_MATERIAL_DISPLAY_COLUMNS = [
    "material", "class", "reagent", "planned_mmol", "planned_g", "planned_mg",
    "planned_mL", "unit", "MW", "density_g_mL", "physical_state", "source", "warning",
]


def display_columns(df, preferred: list[str], include_unknown: bool = False):
    """Return a deliberately small operator-facing dataframe.

    V2.1.9 preserves the V2.0.94-style essential view: normal GUI tabs show
    only curated columns.  Full metadata and diagnostic columns remain in core
    export sheets, JSON state, and detailed CSVs.
    """
    import pandas as pd
    if df is None:
        return pd.DataFrame()
    out = df.copy()
    keep_known = [c for c in preferred if c in out.columns]
    if include_unknown:
        noisy = {"app_version", "project", "peptide", "sequence", "resin", "cleavage_eq_override", "cleavage_preset", "cleavage_components_text", "lot_no", "scale_mmol", "resin_text", "resin_loading_mmol_g", "loading_aa_eq", "loading_diea_eq"}
        remaining = [c for c in out.columns if c not in keep_known and c not in noisy]
        return out[keep_known + remaining]
    return out[keep_known]


def clear_selected_outputs(gui) -> None:
    """Clear calculated result views while keeping editor/project state intact.

    An empty sequence is a normal idle editor state, not a failed synthesis.
    Auto-refresh routes use this helper instead of invoking the core with an
    empty sequence.
    """
    import pandas as pd
    seen: set[int] = set()
    for attr in (
        "pm_selected_plan_tree", "pm_selected_material_tree",
        "pm_selected_total_tree", "pm_total_tree", "pm_validation_tree",
        "pm_summary_tree", "pm_cleavage_tree", "progress_tree",
    ):
        tree = getattr(gui, attr, None)
        if tree is None or id(tree) in seen:
            continue
        seen.add(id(tree))
        try:
            write_tree(tree, pd.DataFrame())
        except Exception:
            try:
                children = list(tree.get_children())
                if children:
                    tree.delete(*children)
            except Exception:
                continue
    text = getattr(gui, "pm_selected_check_text", None)
    if text is not None:
        try:
            text.delete("1.0", "end")
        except Exception:
            pass
    for attr, value in (("checklist_progress_var", 0.0), ("checklist_progress_text", "Progress: 0/0 (0.0%)")):
        var = getattr(gui, attr, None)
        if hasattr(var, "set"):
            try:
                var.set(value)
            except Exception:
                pass


def core_tables(gui):
    ensure_app_path()
    import pandas as pd
    from spps_planner.engine import (
        generate_excel_like_synthesis_table, generate_step_materials, generate_materials,
        generate_detailed_operations, generate_cleavage_cocktail, cleavage_cocktail_presets,
        validate_plan, plan_summary,
    )
    inp = plan_input(gui)
    meta = metadata(gui, inp)
    return inp, meta, {
        "selected_plan_core": add_metadata_columns(generate_excel_like_synthesis_table(inp), meta),
        # Selected Materials is always step-by-step.  Aggregated totals are kept
        # separately so the operator does not see the total table twice.
        "selected_materials_core": add_metadata_columns(generate_step_materials(inp), meta),
        "selected_total_materials_core": add_metadata_columns(generate_materials(inp), meta),
        "operations_core": add_metadata_columns(generate_detailed_operations(inp), meta),
        "cleavage_cocktail": add_metadata_columns(generate_cleavage_cocktail(inp), meta),
        "cleavage_presets": cleavage_cocktail_presets(),
        "validation": add_metadata_columns(validate_plan(inp), meta),
        "summary": add_metadata_columns(pd.DataFrame([plan_summary(inp)]), meta),
    }


def refresh_selected_outputs(gui):
    sequence = str(get_var(gui, "pm_sequence", "") or "").strip()
    if not sequence:
        clear_selected_outputs(gui)
        return {}
    try:
        inp, meta, tables = core_tables(gui)
        if hasattr(gui, "pm_selected_plan_tree"):
            write_tree(gui.pm_selected_plan_tree, display_columns(tables["selected_plan_core"], SELECTED_PLAN_DISPLAY_COLUMNS))
        if hasattr(gui, "pm_selected_material_tree"):
            write_tree(gui.pm_selected_material_tree, display_columns(tables["selected_materials_core"], SELECTED_MATERIAL_DISPLAY_COLUMNS))
        total_tree = getattr(gui, "pm_selected_total_tree", None) or getattr(gui, "pm_total_tree", None)
        if total_tree is not None and "selected_total_materials_core" in tables:
            write_tree(total_tree, display_columns(tables["selected_total_materials_core"], SELECTED_TOTAL_MATERIAL_DISPLAY_COLUMNS))
        if hasattr(gui, "pm_validation_tree"):
            write_tree(gui.pm_validation_tree, display_columns(tables["validation"], ["severity", "category", "message", "field", "value", "suggestion"]))
        if hasattr(gui, "pm_summary_tree"):
            write_tree(gui.pm_summary_tree, display_columns(tables["summary"], ["sequence", "scale_mmol", "resin", "resin_loading_mmol_g", "peptide_length", "aa_count", "default_coupling_system", "cleavage_eq", "cleavage_preset", "lot_no"]))
        try:
            txt = getattr(gui, "pm_selected_check_text", None)
            if txt is not None:
                txt.delete("1.0", "end")
                for _, r in tables["operations_core"].iterrows():
                    txt.insert("end", f"[{r.get('line','')}] Step {r.get('step','')} {r.get('unit','')} - {r.get('operation_group','')}: {r.get('operation_detail','')} | {r.get('solution_note','')}\n")
        except Exception:
            pass
        return tables
    except Exception as exc:
        try:
            from tkinter import messagebox
            messagebox.showerror("Generate / Update", str(exc))
        except Exception:
            pass
        return None


def project_outdir(gui) -> Path:
    try:
        text = get_var(gui, "project_outdir", "") or get_var(gui, "outdir", "")
        return Path(text) if str(text).strip() else __import__("spps_planner.user_paths", fromlist=["user_outputs_dir"]).user_outputs_dir() / "project_manager_exports"
    except Exception:
        return __import__("spps_planner.user_paths", fromlist=["user_outputs_dir"]).user_outputs_dir() / "project_manager_exports"


def save_state_json(gui, out: Path, filename: str) -> None:
    try:
        state = {"active_index": active_index(gui), "pm_items": getattr(gui, "pm_items", [])}
        out.joinpath(filename).write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
