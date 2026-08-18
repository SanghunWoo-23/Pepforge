"""V2.2.8 fast legacy Project Manager controller.

The historical file contains many stacked UI patches.  This module deliberately
bypasses that build-wrapper chain and starts from the original, complete legacy
V2.0.94-style builder once.  Current engine/calculation functions remain in use,
but the operator workflow is explicit:

* Generate: create/recreate Selected Plan from the editor and Setup.
* Apply Change: keep the edited Selected Plan and propagate it to adjacent tabs.
* Peptide item click: save the old item and restore the clicked item, no generation.
* Cleavage cocktail presets are actual cocktail presets, never resin names.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
import json
import re
import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
from spps_v4_gui import state_persistence

VERSION = "V4.0.0"
TITLE = "SPPS Planner V4.0.0"

PLAN_COLUMNS = [
    "No", "Unit name", "MW", "Density(g/mL)", "Unit mmol", "Unit amount",
    "Reagent 1", "R1 MW", "R1 Density", "R1 mmol", "R1 amount",
    "Reagent 2 / catalyst", "R2 MW", "R2 Density", "R2 mmol", "R2 amount",
    "Base", "Base MW", "Base Density", "Base mmol", "Base amount",
    "Coupling solvent", "Solvent mL", "Repeat", "Note",
]

PLAN_WIDTHS = {
    "No": 50, "Unit name": 280, "MW": 90, "Density(g/mL)": 115,
    "Unit mmol": 100, "Unit amount": 120, "Reagent 1": 120, "R1 MW": 85,
    "R1 Density": 100, "R1 mmol": 100, "R1 amount": 115,
    "Reagent 2 / catalyst": 170, "R2 MW": 85, "R2 Density": 100,
    "R2 mmol": 100, "R2 amount": 115, "Base": 110, "Base MW": 85,
    "Base Density": 100, "Base mmol": 100, "Base amount": 115,
    "Coupling solvent": 165, "Solvent mL": 100, "Repeat": 70, "Note": 340,
}

CHECK_COLUMNS = ["line", "done", "checked_at", "operation", "unit", "next_step", "note"]
CHECK_WIDTHS = {
    "line": 65, "done": 70, "checked_at": 145, "operation": 260,
    "unit": 180, "next_step": 250, "note": 520,
}

MATERIAL_COLUMNS = [
    "step", "material", "class", "MW", "density_g_per_mL",
    "planned_mmol", "planned_g", "planned_mL", "use_count", "repeat",
    "phase", "note", "source",
]
MATERIAL_WIDTHS = {
    "step": 70, "material": 240, "class": 175, "MW": 90,
    "density_g_per_mL": 125, "planned_mmol": 115, "planned_g": 110,
    "planned_mL": 110, "use_count": 90, "repeat": 80, "phase": 170,
    "note": 440, "source": 220,
}
TOTAL_COLUMNS = ["material", "class", "MW", "Density(g/mL)", "total mmol", "total amount", "note"]
TOTAL_WIDTHS = {"material": 240, "class": 180, "MW": 90, "Density(g/mL)": 125,
                "total mmol": 115, "total amount": 145, "note": 440}


def _walk(root):
    """One bounded traversal used only once during UI installation."""
    out = []
    stack = [root]
    while stack:
        widget = stack.pop()
        out.append(widget)
        try:
            stack.extend(reversed(widget.winfo_children()))
        except Exception:
            pass
    return out


def _find_results_notebook(gui):
    for widget in _walk(gui):
        if not isinstance(widget, ttk.Notebook):
            continue
        try:
            labels = [str(widget.tab(tab, "text")) for tab in widget.tabs()]
        except Exception:
            continue
        if "Selected Plan" in labels and "Selected Materials" in labels:
            return widget
    return None


def _tab_frame(notebook, label):
    if notebook is None:
        return None
    for tab in notebook.tabs():
        try:
            if str(notebook.tab(tab, "text")) == label:
                return notebook.nametowidget(tab)
        except Exception:
            pass
    return None


def _tree_rows(tree):
    if tree is None:
        return []
    columns = list(tree["columns"])
    rows = []
    for iid in tree.get_children():
        values = list(tree.item(iid, "values"))
        values += [""] * max(0, len(columns) - len(values))
        rows.append({column: values[i] if i < len(values) else "" for i, column in enumerate(columns)})
    return rows


def _write_rows(tree, rows, columns=None, widths=None):
    if tree is None:
        return
    rows = list(rows or [])
    if columns is None:
        columns = []
        for row in rows:
            for key in row.keys():
                key = str(key)
                if key not in columns:
                    columns.append(key)
        if not columns:
            columns = list(tree["columns"])
    width_signature = tuple(
        (column, (widths or {}).get(column, 130)) for column in columns
    )
    schema_signature = (tuple(columns), width_signature)
    if getattr(tree, "_spps_schema_signature", None) != schema_signature:
        tree.configure(columns=columns, show="headings")
        for column in columns:
            tree.heading(column, text=column)
            width = (widths or {}).get(column, 130)
            if column in {"material", "protected_reagent", "operation", "next_step", "note", "source"}:
                width = max(width, 220 if column != "note" else 420)
            tree.column(
                column, width=width, minwidth=45, anchor="w", stretch=False,
            )
        tree._spps_schema_signature = schema_signature
    children = list(tree.get_children())
    if children:
        tree.delete(*children)
    for row in rows:
        tree.insert("", "end", values=[str(row.get(column, "") or "") for column in columns])


def _clear_tree(tree):
    if tree is None:
        return
    children = list(tree.get_children())
    if children:
        tree.delete(*children)




def _cancel_pending_legacy_jobs(gui):
    """Cancel delayed jobs queued by superseded stacked legacy controllers.

    The old file schedules multiple after/after_idle refreshes during build and
    variable edits.  They can repaint or clear the new operator tree after a
    correct Generate.  V2.2.8 owns refresh timing, so these jobs are obsolete.
    """
    try:
        ids = list(gui.tk.call("after", "info"))
    except Exception:
        ids = []
    for job_id in ids:
        try:
            gui.after_cancel(job_id)
        except Exception:
            pass

def _active_index(gui):
    value = getattr(gui, "_v228_active_index", None)
    try:
        value = int(value)
        if 0 <= value < len(gui.pm_items):
            return value
    except Exception:
        pass
    try:
        selected = list(gui.pm_list.curselection())
        if selected:
            value = int(selected[0])
            if 0 <= value < len(gui.pm_items):
                return value
    except Exception:
        pass
    return None


def _editor_payload(gui):
    def value(name, default=""):
        try:
            return str(getattr(gui, name).get()).strip()
        except Exception:
            return str(default)

    def flag(name, default=False):
        try:
            return bool(getattr(gui, name).get())
        except Exception:
            return bool(default)

    return {
        "project": value("pm_project"),
        "peptide": value("pm_peptide"),
        "sequence": value("pm_sequence"),
        "scale": value("pm_scale", "0.2"),
        "resin": value("pm_resin", "Rink Amide AM"),
        "loading": value("pm_loading", "0.8"),
        "lot": "",
        "lot_no": "",
        "chemistry": value("pm_chemistry", "DIC/HOBt"),
        "copies": value("pm_copies", "1"),
        # Direct-loading settings are peptide-specific.  Keeping these fields in
        # the item payload prevents a 2-CTC item from leaking into a preloaded
        # CTC synthesizer item when the operator clicks between peptides.
        "apply_loading_calc": flag("apply_loading_calc", False),
        "loading_aa_eq": value("loading_aa_eq", "2"),
        "loading_diea_eq": value("loading_diea_eq", "4"),
        "loading_time_h": value("loading_time_h", ""),
        "cleavage_preset": value("cleavage_preset", "AUTO"),
        "cleavage_eq_override": value("cleavage_eq_override", "0"),
        "cleavage_components_text": value("cleavage_components_text", ""),
        "cleavage_time_h": value("cleavage_time_h", ""),
        "branch_point": value("branch_point", ""),
        "branch_arm_sequence": value("branch_arm_sequence", ""),
        "branch_pg": value("branch_pg", ""),
        "branch_depro_condition": value("branch_depro_condition", ""),
        "step_overrides_text": value("step_overrides_text", ""),
    }


def _snapshot_outputs(gui, item):
    item["selected_plan_rows"] = _tree_rows(getattr(gui, "pm_selected_plan_tree", None))
    item["selected_material_rows"] = _tree_rows(getattr(gui, "pm_selected_material_tree", None))
    item["selected_total_rows"] = _tree_rows(getattr(gui, "pm_selected_total_tree", None))
    item["selected_checklist_rows"] = _tree_rows(getattr(gui, "progress_tree", None))
    item["selected_cleavage_rows"] = _tree_rows(getattr(gui, "pm_cleavage_tree", None))


def save_active(gui, include_outputs=True):
    index = _active_index(gui)
    if index is None or getattr(gui, "_v228_switching", False):
        return
    item = gui.pm_items[index]
    item.update(_editor_payload(gui))
    item.setdefault("status", "Ready")
    if include_outputs:
        _commit_open_editor(gui)
        _snapshot_outputs(gui, item)
    _refresh_list_label(gui, index)


def _refresh_list_label(gui, index):
    try:
        text = gui.pm_display_name(gui.pm_items[index])
    except Exception:
        item = gui.pm_items[index]
        text = f"{item.get('project','')} | {item.get('peptide','')}"
    try:
        gui._v228_switching = True
        selected = list(gui.pm_list.curselection())
        gui.pm_list.delete(index)
        gui.pm_list.insert(index, text)
        if index in selected or index == _active_index(gui):
            gui.pm_list.selection_set(index)
            gui.pm_list.activate(index)
    except Exception:
        pass
    finally:
        gui._v228_switching = False


def _set_var(gui, name, value):
    try:
        getattr(gui, name).set(value)
    except Exception:
        pass


def _set_bool(gui, name, value):
    try:
        getattr(gui, name).set(bool(value))
    except Exception:
        pass


def restore_item(gui, index, ns):
    if not (0 <= int(index) < len(gui.pm_items)):
        return
    item = gui.pm_items[int(index)]
    gui._v228_switching = True
    try:
        _set_var(gui, "pm_project", item.get("project", ""))
        _set_var(gui, "pm_peptide", item.get("peptide", ""))
        _set_var(gui, "pm_sequence", item.get("sequence", ""))
        _set_var(gui, "pm_scale", item.get("scale", "0.2"))
        _set_var(gui, "pm_resin", item.get("resin", "Rink Amide AM"))
        _set_var(gui, "pm_loading", item.get("loading", "0.8"))
        _set_var(gui, "pm_lot", "")
        _set_var(gui, "pm_chemistry", item.get("chemistry", "DIC/HOBt"))
        _set_var(gui, "pm_copies", item.get("copies", "1"))
        _set_bool(gui, "apply_loading_calc", item.get("apply_loading_calc", False))
        _set_var(gui, "loading_aa_eq", item.get("loading_aa_eq", "2"))
        _set_var(gui, "loading_diea_eq", item.get("loading_diea_eq", "4"))
        _set_var(gui, "loading_time_h", item.get("loading_time_h", ""))
        _set_var(gui, "cleavage_preset", item.get("cleavage_preset", "AUTO"))
        _set_var(gui, "cleavage_eq_override", item.get("cleavage_eq_override", "0"))
        _set_var(gui, "cleavage_components_text", item.get("cleavage_components_text", ""))
        _set_var(gui, "cleavage_time_h", item.get("cleavage_time_h", ""))
        _set_var(gui, "branch_point", item.get("branch_point", ""))
        _set_var(gui, "branch_arm_sequence", item.get("branch_arm_sequence", ""))
        _set_var(gui, "branch_pg", item.get("branch_pg", ""))
        _set_var(gui, "branch_depro_condition", item.get("branch_depro_condition", ""))
        _set_var(gui, "step_overrides_text", item.get("step_overrides_text", ""))
        gui._v228_active_index = int(index)
    finally:
        gui._v228_switching = False

    plan_rows = list(item.get("selected_plan_rows") or [])
    if plan_rows:
        _write_rows(gui.pm_selected_plan_tree, plan_rows, PLAN_COLUMNS, PLAN_WIDTHS)
        _bind_plan_editor(gui, ns)
    else:
        _clear_tree(gui.pm_selected_plan_tree)
    _write_rows(gui.pm_selected_material_tree, list(item.get("selected_material_rows") or []))
    _write_rows(getattr(gui, "pm_selected_total_tree", getattr(gui, "pm_total_tree", None)), list(item.get("selected_total_rows") or []))
    _write_rows(getattr(gui, "progress_tree", None), list(item.get("selected_checklist_rows") or []), CHECK_COLUMNS, CHECK_WIDTHS)
    _write_rows(getattr(gui, "pm_cleavage_tree", None), list(item.get("selected_cleavage_rows") or []))
    try:
        gui._update_progress_widgets()
    except Exception:
        pass
    try:
        gui.pm_update_summary()
    except Exception:
        pass


def on_item_select(gui, ns, _event=None):
    if getattr(gui, "_v228_switching", False):
        return "break"
    try:
        selected = list(gui.pm_list.curselection())
        if not selected:
            return "break"
        new_index = int(selected[0])
    except Exception:
        return "break"
    old_index = _active_index(gui)
    if old_index is not None and old_index != new_index:
        save_active(gui, include_outputs=True)
    restore_item(gui, new_index, ns)
    try:
        gui.schedule_autosave()
    except Exception:
        pass
    return "break"


def live_sync(gui):
    """Save edits in place without clearing or regenerating the current plan."""
    if getattr(gui, "_v228_switching", False):
        return
    # Only 2-CTC is a direct-loading profile.  Preloaded/synthesizer resins must
    # not inherit a stale loading checkbox from the previously selected item.
    try:
        resin = str(gui.pm_resin.get() or "").strip()
        if resin != "2-CTC" and hasattr(gui, "apply_loading_calc") and bool(gui.apply_loading_calc.get()):
            gui._v228_switching = True
            gui.apply_loading_calc.set(False)
            gui._v228_switching = False
    except Exception:
        gui._v228_switching = False
    index = _active_index(gui)
    if index is None:
        return
    gui.pm_items[index].update(_editor_payload(gui))
    gui.pm_items[index].setdefault("status", "Ready")
    _refresh_list_label(gui, index)
    try:
        gui.schedule_autosave()
    except Exception:
        pass


def _commit_open_editor(gui):
    tree = getattr(gui, "pm_selected_plan_tree", None)
    if tree is None:
        return
    for attr in ("_v228_editor", "_v254_editor", "_v257_editor"):
        try:
            editor = getattr(tree, attr, None)
            if editor is not None and editor.winfo_exists():
                editor.event_generate("<Return>")
                gui.update_idletasks()
                return
        except Exception:
            pass


def _bind_plan_editor(gui, ns):
    tree = getattr(gui, "pm_selected_plan_tree", None)
    if tree is None:
        return
    # The proven legacy editor supports comboboxes and MW/density recalculation.
    binder = ns.get("_v254_bind_selected_plan_editor")
    if callable(binder):
        try:
            binder(gui)
            return
        except Exception:
            pass

    def begin(event):
        if tree.identify("region", event.x, event.y) != "cell":
            return
        iid = tree.identify_row(event.y)
        col_id = tree.identify_column(event.x)
        if not iid or not col_id:
            return
        index = int(col_id[1:]) - 1
        columns = list(tree["columns"])
        if index < 0 or index >= len(columns) or columns[index] == "No":
            return
        bbox = tree.bbox(iid, col_id)
        if not bbox:
            return
        values = list(tree.item(iid, "values"))
        values += [""] * max(0, len(columns) - len(values))
        x, y, width, height = bbox
        editor = ttk.Entry(tree)
        editor.insert(0, str(values[index]))
        editor.select_range(0, "end")
        editor.place(x=x, y=y, width=width, height=height)
        editor.focus_set()
        tree._v228_editor = editor

        def commit(_e=None):
            if not editor.winfo_exists():
                return
            values[index] = editor.get()
            tree.item(iid, values=values)
            editor.destroy()
            tree._v228_editor = None

        editor.bind("<Return>", commit)
        editor.bind("<FocusOut>", commit)
        editor.bind("<Escape>", lambda _e: editor.destroy())

    tree.bind("<Double-1>", begin, add=False)


def _core_tables(gui, ns):
    function = ns.get("_v221_core_tables") or ns.get("_v217_core_tables")
    if not callable(function):
        return {}
    result = function(gui)
    if isinstance(result, tuple) and len(result) >= 3:
        return result[2]
    return result if isinstance(result, dict) else {}


def generate(gui, ns):
    """Generate: rebuild the plan from editor/setup values."""
    if getattr(gui, "_v228_generating", False):
        return None
    gui._v228_generating = True
    try:
        _cancel_pending_legacy_jobs(gui)
        save_active(gui, include_outputs=False)
        plan_input = ns.get("_v226_plan_input") or ns.get("_v222_plan_input") or ns.get("_v218_plan_input")
        if not callable(plan_input):
            raise RuntimeError("PlanInput controller is unavailable.")
        inp = plan_input(gui)

        from spps_v4_gui.modules import plan_workflow
        rows = plan_workflow._generated_plan_rows(gui, ns, inp)

        # Core table generation still calls several legacy refresh helpers.
        # Run it before painting Selected Plan so none of those helpers can
        # clear or replace the operator-edited legacy plan tree afterwards.
        tables = _core_tables(gui, ns)
        _write_rows(gui.pm_selected_plan_tree, rows, PLAN_COLUMNS, PLAN_WIDTHS)
        _bind_plan_editor(gui, ns)
        writer = ns.get("_v2093_write_tree")
        materials = tables.get("selected_materials_core", pd.DataFrame())
        totals = tables.get("selected_total_materials_visible", pd.DataFrame())
        if callable(writer):
            writer(gui, gui.pm_selected_material_tree, materials)
            writer(gui, gui.pm_selected_total_tree, totals)
        else:
            _write_rows(gui.pm_selected_material_tree, materials.fillna("").to_dict("records") if hasattr(materials, "to_dict") else [])
            _write_rows(gui.pm_selected_total_tree, totals.fillna("").to_dict("records") if hasattr(totals, "to_dict") else [])
        # The direct Plan service owns linked checklist/material generation.
        plan_workflow._write_linked(
            gui, ns, inp,
            include_cleavage=False,
            paint_all_linked=True,
        )

        index = _active_index(gui)
        if index is not None:
            gui.pm_items[index]["status"] = "Calculated"
            _snapshot_outputs(gui, gui.pm_items[index])
            _refresh_list_label(gui, index)
        _cancel_pending_legacy_jobs(gui)
        # Paint once more after cancelling superseded delayed refresh jobs.
        _write_rows(gui.pm_selected_plan_tree, rows, PLAN_COLUMNS, PLAN_WIDTHS)
        _bind_plan_editor(gui, ns)
        try:
            gui.pm_update_summary()
            gui.schedule_autosave()
        except Exception:
            pass
        return tables
    except Exception as exc:
        try:
            messagebox.showerror("Generate", str(exc))
        except Exception:
            pass
        return None
    finally:
        gui._v228_generating = False


def _amount_number(value, unit):
    text = str(value or "")
    match = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", text.replace(",", ""))
    if not match or unit.lower() not in text.lower():
        return ""
    try:
        number = float(match.group(0))
        return f"{number:.6f}".rstrip("0").rstrip(".")
    except Exception:
        return ""


def _protocol_material_detail_rows(frame):
    """Convert the visible-plan protocol material frame to the legacy table schema.

    Selected Materials keeps the V2.1.7 columns and actual protocol order.  This
    avoids the old Apply Change bug where seven compact values were inserted into
    a thirteen-column legacy tree and appeared under the wrong headings.
    """
    if frame is None or getattr(frame, "empty", True):
        return []
    rows = []
    for order, record in enumerate(frame.fillna("").to_dict("records"), 1):
        note = str(record.get("note", "") or "")
        match = re.search(r"(?:protocol\s+)?step\s+([^:;]+)", note, flags=re.I)
        step = match.group(1).strip() if match else str(order)
        amount = str(record.get("total amount", "") or "")
        rows.append({
            "step": step,
            "material": record.get("material", ""),
            "class": record.get("class", ""),
            "MW": record.get("MW", ""),
            "density_g_per_mL": record.get("Density(g/mL)", ""),
            "planned_mmol": record.get("total mmol", ""),
            "planned_g": _amount_number(amount, "g"),
            "planned_mL": _amount_number(amount, "mL"),
            "use_count": "",
            "repeat": "",
            "phase": record.get("class", ""),
            "note": note,
            "source": "Visible Selected Plan / SPPS protocol",
        })
    return rows


def _refresh_linked_from_visible_plan(gui, ns):
    """Single V2.2.8 Apply Change pipeline; no legacy UI wrapper is called."""
    _commit_open_editor(gui)
    tree = getattr(gui, "pm_selected_plan_tree", None)
    if tree is None:
        raise RuntimeError("Selected Plan is unavailable.")

    recalc = ns.get("_v251_recalc_visible_row")
    if callable(recalc):
        for iid in list(tree.get_children()):
            recalc(gui, tree, iid)
    volume = ns.get("_v257_apply_volume_to_plan")
    if callable(volume):
        volume(gui)

    material_builder = ns.get("_v260_visible_plan_protocol_materials")
    if not callable(material_builder):
        raise RuntimeError("Visible-plan material controller is unavailable.")
    materials = material_builder(gui)
    _write_rows(gui.pm_selected_material_tree, _protocol_material_detail_rows(materials), MATERIAL_COLUMNS, MATERIAL_WIDTHS)

    total_builder = ns.get("_v252_total_from_materials") or ns.get("_v251_total_from_materials")
    totals = total_builder(materials) if callable(total_builder) else pd.DataFrame()
    total_rows = totals.fillna("").to_dict("records") if hasattr(totals, "to_dict") else []
    _write_rows(getattr(gui, "pm_selected_total_tree", getattr(gui, "pm_total_tree", None)), total_rows, TOTAL_COLUMNS, TOTAL_WIDTHS)

    checklist = ns.get("_v260_refresh_checklist_protocol")
    if callable(checklist):
        checklist(gui)
    else:
        try:
            from spps_v4_gui.modules import plan_workflow
            plan_workflow._write_linked(gui, ns, inp, include_cleavage=True)
        except Exception:
            pass

    try:
        if hasattr(gui, "_v260_schedule_batch_refresh"):
            gui._v260_schedule_batch_refresh()
        elif hasattr(gui, "refresh_batch_workspace_preview"):
            gui.after_idle(gui.refresh_batch_workspace_preview)
    except Exception:
        pass
    _bind_plan_editor(gui, ns)
    return materials


def apply_change(gui, ns):
    """Apply Change: keep visible edits and refresh only linked outputs."""
    if getattr(gui, "_v228_applying", False):
        return None
    gui._v228_applying = True
    try:
        _refresh_linked_from_visible_plan(gui, ns)
        index = _active_index(gui)
        if index is not None:
            _snapshot_outputs(gui, gui.pm_items[index])
            gui.pm_items[index]["status"] = "Changed"
            _refresh_list_label(gui, index)
        try:
            gui.schedule_autosave()
        except Exception:
            pass
        return True
    except Exception as exc:
        try:
            messagebox.showerror("Apply Change", str(exc))
        except Exception:
            pass
        return None
    finally:
        gui._v228_applying = False


def delete_selected_rows(gui, ns):
    tree = getattr(gui, "pm_selected_plan_tree", None)
    if tree is None:
        return
    for iid in list(tree.selection()):
        tree.delete(iid)
    columns = list(tree["columns"])
    if "No" in columns:
        pos = columns.index("No")
        for number, iid in enumerate(tree.get_children(), 1):
            values = list(tree.item(iid, "values"))
            values += [""] * max(0, len(columns) - len(values))
            values[pos] = number
            tree.item(iid, values=values)
    apply_change(gui, ns)


def edit_unit(gui, ns):
    for name in ("_v276c_edit_unit", "_v269_open_unit_picker", "_v239_edit_selected_unit"):
        function = ns.get(name)
        if callable(function):
            try:
                return function(gui)
            except Exception:
                pass
    try:
        messagebox.showinfo("Edit Unit name", "Select a row, then double-click a cell to edit it.")
    except Exception:
        pass


def _cocktail_presets():
    try:
        from spps_planner.engine import cleavage_cocktail_presets
        frame = cleavage_cocktail_presets()
        values = [str(x) for x in frame.get("preset", []).tolist() if str(x).strip()]
        if values:
            return values
    except Exception:
        pass
    return ["AUTO", "DEFAULT_TFA_WATER", "DEFAULT_TFA_TIS_WATER", "CUSTOM"]


def refresh_cleavage(gui, ns, show_errors=True):
    try:
        save_active(gui, include_outputs=False)
        plan_input = ns.get("_v226_plan_input") or ns.get("_v222_plan_input") or ns.get("_v218_plan_input")
        if not callable(plan_input):
            return None
        inp = plan_input(gui)
        from spps_planner.engine import generate_cleavage_cocktail
        frame = generate_cleavage_cocktail(inp)
        rows = frame.fillna("").to_dict("records")
        _write_rows(gui.pm_cleavage_tree, rows)
        index = _active_index(gui)
        if index is not None:
            gui.pm_items[index].update(_editor_payload(gui))
            gui.pm_items[index]["selected_cleavage_rows"] = _tree_rows(gui.pm_cleavage_tree)
        return frame
    except Exception as exc:
        if show_errors:
            try:
                messagebox.showerror("Cleavage cocktail", str(exc))
            except Exception:
                pass
        return None


def _install_checklist(gui, frame):
    for child in list(frame.winfo_children()):
        try:
            child.destroy()
        except Exception:
            pass
    frame.rowconfigure(1, weight=1)
    frame.columnconfigure(0, weight=1)
    controls = ttk.Frame(frame, padding=(4, 3))
    controls.grid(row=0, column=0, columnspan=2, sticky="ew")
    gui.checklist_progress_var = tk.DoubleVar(value=0.0)
    gui.checklist_progress_label = ttk.Label(controls, text="Progress: 0/0 (0.0%)")
    gui.checklist_progress_label.pack(side="left", padx=(0, 10))
    gui.checklist_progress_bar = ttk.Progressbar(controls, variable=gui.checklist_progress_var, maximum=100, length=230)
    gui.checklist_progress_bar.pack(side="left", padx=(0, 10))
    ttk.Label(controls, text="Toggle rows with double-click or Space").pack(side="left", padx=(0, 10))
    ttk.Button(controls, text="All Done", command=gui.select_all_progress_rows).pack(side="left", padx=3)
    ttk.Button(controls, text="Selected Done", command=gui.selected_progress_rows_yes).pack(side="left", padx=3)
    ttk.Button(controls, text="Done Until Selected", command=gui.mark_until_selected_progress_row).pack(side="left", padx=3)
    ttk.Button(controls, text="Clear", command=gui.clear_all_progress_rows).pack(side="left", padx=3)

    tree = ttk.Treeview(frame, columns=CHECK_COLUMNS, show="headings", selectmode="extended")
    for column in CHECK_COLUMNS:
        tree.heading(column, text=column)
        tree.column(column, width=CHECK_WIDTHS[column], minwidth=45, anchor="w", stretch=False)
    ybar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    xbar = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
    tree.grid(row=1, column=0, sticky="nsew")
    ybar.grid(row=1, column=1, sticky="ns")
    xbar.grid(row=2, column=0, sticky="ew")
    tree.bind("<Double-1>", gui.toggle_progress_row)
    tree.bind("<space>", gui.toggle_progress_row)
    gui.progress_tree = tree
    gui.pm_selected_check_text = None


def _install_cleavage(gui, notebook):
    frame = _tab_frame(notebook, "Cleavage Cocktail")
    if frame is None:
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Cleavage Cocktail")
    for child in list(frame.winfo_children()):
        try:
            child.destroy()
        except Exception:
            pass
    frame.rowconfigure(1, weight=1)
    frame.columnconfigure(0, weight=1)
    if not hasattr(gui, "loading_time_h"):
        gui.loading_time_h = tk.StringVar(value="")
    if not hasattr(gui, "cleavage_time_h"):
        gui.cleavage_time_h = tk.StringVar(value="")
    if not hasattr(gui, "cleavage_reserve_mL"):
        gui.cleavage_reserve_mL = tk.StringVar(value="0")
    if not hasattr(gui, "cleavage_eq_override"):
        gui.cleavage_eq_override = tk.StringVar(value="0")
    if not hasattr(gui, "cleavage_preset"):
        gui.cleavage_preset = tk.StringVar(value="AUTO")
    if not hasattr(gui, "cleavage_components_text"):
        gui.cleavage_components_text = tk.StringVar(value="")

    controls = ttk.Frame(frame, padding=(4, 4))
    controls.grid(row=0, column=0, columnspan=2, sticky="ew")
    ttk.Label(controls, text="Eq override (0=auto)").pack(side="left", padx=(0, 3))
    ttk.Entry(controls, textvariable=gui.cleavage_eq_override, width=8).pack(side="left", padx=(0, 8))
    ttk.Label(controls, text="Cocktail preset").pack(side="left", padx=(0, 3))
    presets = _cocktail_presets()
    if str(gui.cleavage_preset.get() or "") not in presets:
        gui.cleavage_preset.set("AUTO")
    combo = ttk.Combobox(controls, textvariable=gui.cleavage_preset, values=presets, state="readonly", width=29)
    combo.pack(side="left", padx=(0, 8))
    ttk.Label(controls, text="Custom components").pack(side="left", padx=(0, 3))
    ttk.Entry(controls, textvariable=gui.cleavage_components_text, width=42).pack(side="left", padx=(0, 8), fill="x", expand=True)
    ttk.Label(controls, text="Time (h)").pack(side="left", padx=(2, 3))
    ttk.Entry(controls, textvariable=gui.cleavage_time_h, width=7).pack(side="left", padx=(0, 8))
    ttk.Label(controls, text="Min total (mL)").pack(side="left", padx=(2, 3))
    ttk.Entry(controls, textvariable=gui.cleavage_reserve_mL, width=9).pack(side="left", padx=(0, 8))
    ttk.Button(controls, text="Apply cleavage", command=lambda: refresh_cleavage(gui, gui._v228_ns)).pack(side="left")

    tree = ttk.Treeview(frame, columns=["component", "role", "recommended_eq", "percent", "percent_basis", "volume_mL", "density_g_mL", "approx_g", "physical_state", "selected_preset", "auto_recommended_preset", "include", "note"], show="headings")
    for column in tree["columns"]:
        tree.heading(column, text=column)
        tree.column(column, width=125 if column != "note" else 420, minwidth=45, anchor="w", stretch=False)
    ybar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    xbar = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
    tree.grid(row=1, column=0, sticky="nsew")
    ybar.grid(row=1, column=1, sticky="ns")
    xbar.grid(row=2, column=0, sticky="ew")
    gui.pm_cleavage_tree = tree



def _normalize_setup_panel(gui):
    """Keep all useful setup controls but remove duplicated editor fields.

    Resin and resin loading are edited in the Selected peptide editor.  Older
    stacked patches repeated the same loading rate and loading solvent inside a
    separate setup tab, which was both confusing and a source of conflicting
    values.  The setup tab now contains only direct-loading chemistry controls;
    the shared loading solvent remains in Solvents / Wash.
    """
    panel = getattr(gui, "pm_setup_panel", None)
    if panel is None:
        return
    notebook = None
    for child in panel.winfo_children():
        if isinstance(child, ttk.Notebook):
            notebook = child
            break
    if notebook is None:
        return
    direct_frame = None
    for tab in notebook.tabs():
        try:
            label = str(notebook.tab(tab, "text"))
        except Exception:
            continue
        if label in {"Loading rate", "Resin loading", "Direct loading"}:
            direct_frame = notebook.nametowidget(tab)
            notebook.tab(tab, text="Direct loading")
            break
    if direct_frame is None:
        return

    pm_loading_var = str(getattr(gui, "pm_loading", ""))
    loading_solvent_var = str(getattr(gui, "default_loading_dissolve_solvent", ""))
    remove_rows = set()
    for child in list(direct_frame.winfo_children()):
        try:
            text = str(child.cget("text")).strip()
        except Exception:
            text = ""
        try:
            textvariable = str(child.cget("textvariable"))
        except Exception:
            textvariable = ""
        # The editor already owns resin loading, and Solvents / Wash already owns
        # the loading solvent. Remove those duplicate controls from this tab.
        if text in {"Loading rate", "Resin loading", "Resin loading (mmol/g)", "mmol/g", "Loading solvent"}:
            try:
                info = child.grid_info()
                remove_rows.add(int(info.get("row", -1)))
            except Exception:
                pass
            child.destroy()
        elif textvariable and textvariable in {pm_loading_var, loading_solvent_var}:
            try:
                info = child.grid_info()
                remove_rows.add(int(info.get("row", -1)))
            except Exception:
                pass
            child.destroy()

    # Remove orphan unit labels left in the rows of deleted fields only.
    for child in list(direct_frame.winfo_children()):
        try:
            info = child.grid_info()
            row = int(info.get("row", -1))
            text = str(child.cget("text")).strip()
        except Exception:
            continue
        if row in remove_rows and text in {"mmol/g", ""} and not isinstance(child, (ttk.Entry, ttk.Combobox, ttk.Spinbox, ttk.Checkbutton)):
            child.destroy()

    # Make the surviving labels explicit and remove the old duplicated wording.
    for child in direct_frame.winfo_children():
        if not isinstance(child, ttk.Label):
            continue
        try:
            text = str(child.cget("text"))
        except Exception:
            continue
        if text.startswith("Selected resin is controlled"):
            child.configure(text="Resin and loading rate are edited once in the peptide editor above. Direct loading applies only to 2-CTC.")
        elif text.startswith("Default: resin"):
            child.configure(text="Direct-loading default: resin : amino acid : DIEA = 1 : 2 : 4. Change only when the SOP differs.")


def _make_item_buttons_visible(gui):
    """Keep Add / Duplicate / Delete visible in the legacy left pane."""
    try:
        parent = gui.pm_list.master
        button_bar = next((w for w in parent.winfo_children() if isinstance(w, ttk.Frame)), None)
        if button_bar is not None:
            widths = {"Add": 7, "Duplicate": 9, "Delete": 7}
            for widget in button_bar.winfo_children():
                if isinstance(widget, ttk.Button):
                    text = str(widget.cget("text"))
                    if text in widths:
                        widget.configure(width=widths[text])
        gui.update_idletasks()
        try:
            gui.pm_paned.sash_place(0, 235, 1)
        except Exception:
            try:
                gui.pm_paned.sashpos(0, 235)
            except Exception:
                pass
    except Exception:
        pass


def save_project(gui, ns, show=True):
    """Save a portable Project Manager state without exporting calculations."""
    try:
        save_active(gui, include_outputs=True)
        try:
            out_text = gui.project_outdir.get() if hasattr(gui, "project_outdir") else ""
            if not str(out_text or "").strip() and hasattr(gui, "outdir"):
                out_text = gui.outdir.get()
            out = Path(str(out_text or "").strip() or "outputs/project_manager_exports")
        except Exception:
            out = Path("outputs/project_manager_exports")
        out.mkdir(parents=True, exist_ok=True)
        state = gui._collect_state() if hasattr(gui, "_collect_state") else {}
        active = _active_index(gui)
        state = state_persistence.project_state(
            app_version=VERSION,
            saved_at=datetime.now().isoformat(timespec="seconds"),
            active_index=active,
            selected_pm_index=active or 0,
            pm_items=getattr(gui, "pm_items", []),
            defaults=state.get("defaults", {}),
            batch_rows=state.get("batch_rows"),
            base=state,
        )
        path = out / "project_manager_state.json"
        state_persistence.atomic_write_json(path, state)
        gui.last_outdir = out
        if show:
            try:
                messagebox.showinfo("Save Project", f"Saved:\n{path}")
            except Exception:
                pass
        return path
    except Exception as exc:
        try:
            messagebox.showerror("Save Project", str(exc))
        except Exception:
            pass
        return None


def _install_save_project_button(gui, ns):
    """Restore the useful legacy Save Project action exactly once."""
    save_session_button = None
    for widget in _walk(gui):
        if isinstance(widget, ttk.Button):
            try:
                if str(widget.cget("text")) == "Save Session Now":
                    save_session_button = widget
                    break
            except Exception:
                pass
    if save_session_button is None:
        return
    editor = save_session_button.master.master
    global_row = None
    for child in editor.winfo_children():
        if not isinstance(child, ttk.Frame):
            continue
        labels = [str(w.cget("text")) for w in child.winfo_children() if isinstance(w, ttk.Label)]
        buttons = [str(w.cget("text")) for w in child.winfo_children() if isinstance(w, ttk.Button)]
        if "Global actions:" in labels or "Export" in buttons:
            global_row = child
            break
    if global_row is None:
        return
    for widget in global_row.winfo_children():
        if isinstance(widget, ttk.Button) and str(widget.cget("text")) == "Save Project":
            widget.configure(command=gui.save_project)
            return
    ttk.Button(global_row, text="Save Project", command=gui.save_project).pack(side="left", padx=3)


def _startup_refresh_noop(gui, *args, **kwargs):
    """Ignore obsolete constructor refreshes; Generate owns plan creation."""
    return None

def _install_editor_traces(gui):
    """Remove legacy clear/regenerate traces and keep one non-destructive saver."""
    names = [
        "pm_project", "pm_peptide", "pm_sequence", "pm_scale", "pm_resin",
        "pm_loading", "pm_lot", "pm_chemistry", "pm_copies",
        "apply_loading_calc", "loading_aa_eq", "loading_diea_eq", "loading_time_h",
        "cleavage_preset", "cleavage_eq_override", "cleavage_components_text", "cleavage_time_h", "cleavage_reserve_mL",
        "branch_point", "branch_arm_sequence", "branch_pg", "branch_depro_condition",
        "step_overrides_text",
    ]
    gui._v228_trace_tokens = []
    for name in names:
        variable = getattr(gui, name, None)
        if variable is None or not hasattr(variable, "trace_info"):
            continue
        try:
            for modes, callback_name in list(variable.trace_info()):
                for mode in modes:
                    try:
                        variable.trace_remove(mode, callback_name)
                    except Exception:
                        pass
        except Exception:
            pass
        try:
            token = variable.trace_add("write", lambda *_a, _gui=gui: _gui.after_idle(lambda: live_sync(_gui)))
            gui._v228_trace_tokens.append((variable, token))
        except Exception:
            pass


def _install_action_buttons(gui, ns):
    # Find the exact legacy action row by the Save Session Now button.
    save_button = None
    for widget in _walk(gui):
        if isinstance(widget, ttk.Button):
            try:
                if str(widget.cget("text")) == "Save Session Now" and isinstance(widget.master, ttk.Frame):
                    # Prefer the row inside the Selected peptide editor.
                    siblings = [str(x.cget("text")) for x in widget.master.winfo_children() if isinstance(x, ttk.Button)]
                    if any(text.startswith("Generate") for text in siblings):
                        save_button = widget
                        break
            except Exception:
                pass
    if save_button is None:
        return
    parent = save_button.master
    for child in list(parent.winfo_children()):
        if isinstance(child, ttk.Button):
            try:
                text = str(child.cget("text"))
            except Exception:
                text = ""
            if text.startswith("Generate") or text in {"Apply Change", "Apply Plan"}:
                child.destroy()
    # Repack in the requested order. Save is preserved, only moved.
    try:
        save_button.pack_forget()
    except Exception:
        pass
    ttk.Button(parent, text="Generate", command=lambda: generate(gui, ns)).pack(side="left", padx=3)
    ttk.Button(parent, text="Apply Change", command=lambda: apply_change(gui, ns)).pack(side="left", padx=3)
    # Experimental / ML (V4): V4 advisors are next to the actual planner actions. They read the active
    # item and can write recommendations back only after explicit Apply.
    ttk.Button(parent, text="Recommend Conditions", command=gui.open_condition_optimizer).pack(side="left", padx=(9, 3))
    ttk.Button(parent, text="Loading Advice", command=gui.open_loading_advisor).pack(side="left", padx=3)
    ttk.Button(parent, text="Cleavage Advice", command=gui.open_cleavage_advisor).pack(side="left", padx=3)
    ttk.Button(parent, text="Record Lab Data", command=gui.open_experimental_data).pack(side="left", padx=3)
    save_button.pack(side="left", padx=3)


def _install_plan_toolbar(gui, ns):
    tree = gui.pm_selected_plan_tree
    parent = tree.master
    found_delete = None
    found_edit = None
    # Remove Apply Plan; it duplicates and conflicts with top-level Apply Change.
    for widget in _walk(parent):
        if isinstance(widget, ttk.Button):
            try:
                text = str(widget.cget("text"))
            except Exception:
                continue
            if text in {"Apply Plan", "Apply Change"}:
                widget.destroy()
            elif text == "Delete selected row":
                found_delete = widget
                widget.configure(command=lambda: delete_selected_rows(gui, ns))
            elif text == "Edit Unit name":
                found_edit = widget
                widget.configure(command=lambda: edit_unit(gui, ns))

    if found_delete is None or found_edit is None:
        # The earliest legacy builder has no plan-local toolbar. Add only the two
        # useful editing actions; no duplicate Apply button is created.
        try:
            parent.rowconfigure(0, weight=0)
            parent.rowconfigure(1, weight=1)
            parent.columnconfigure(0, weight=1)
            tree.grid(row=1, column=0, sticky="nsew")
            for child in parent.winfo_children():
                if isinstance(child, ttk.Scrollbar):
                    orient = str(child.cget("orient")).lower()
                    if orient == "vertical":
                        child.grid(row=1, column=1, sticky="ns")
                    elif orient == "horizontal":
                        child.grid(row=2, column=0, sticky="ew")
            bar = ttk.Frame(parent)
            bar.grid(row=0, column=0, sticky="ew", pady=(0, 2))
            ttk.Button(bar, text="Delete selected row", command=lambda: delete_selected_rows(gui, ns)).pack(side="left", padx=(0, 4))
            ttk.Button(bar, text="Edit Unit name", command=lambda: edit_unit(gui, ns)).pack(side="left", padx=(0, 4))
            gui._v228_plan_toolbar = bar
        except Exception:
            pass
    _bind_plan_editor(gui, ns)

def _install_result_tabs(gui, ns):
    notebook = _find_results_notebook(gui)
    if notebook is None:
        return
    gui.pm_results_notebook = notebook
    # Use the current, user-facing names; remove only the obsolete duplicate summary.
    for tab in list(notebook.tabs()):
        label = str(notebook.tab(tab, "text"))
        if label == "Batch Total Materials":
            notebook.tab(tab, text="Selected Total Materials")
        elif label == "Batch Summary":
            notebook.forget(tab)
    # Alias the legacy total tree to the current name.
    gui.pm_selected_total_tree = getattr(gui, "pm_total_tree", None)

    checklist_frame = _tab_frame(notebook, "Selected Checklist")
    if checklist_frame is not None:
        _install_checklist(gui, checklist_frame)
    _install_cleavage(gui, notebook)

    # Selected Plan must only contain operator-facing columns.  Raw direction and
    # C/N-position columns from the core dataframe are intentionally not present.
    current = _tree_rows(gui.pm_selected_plan_tree)
    _write_rows(gui.pm_selected_plan_tree, current, PLAN_COLUMNS, PLAN_WIDTHS)
    _install_plan_toolbar(gui, ns)


def _replace_item_actions(gui, ns):
    try:
        gui.pm_list.bind("<<ListboxSelect>>", lambda e: on_item_select(gui, ns, e), add=False)
        gui.pm_list.bind("<Double-Button-1>", lambda e: on_item_select(gui, ns, e), add=False)
        gui.pm_list.bind("<Return>", lambda e: on_item_select(gui, ns, e), add=False)
    except Exception:
        pass


def add_item(gui, item=None):
    save_active(gui)
    number = len(gui.pm_items) + 1
    if item is None:
        item = {
            "project": f"Project-{number:03d}", "peptide": f"Peptide-{number:03d}",
            "sequence": "", "copies": "1", "scale": "0.2", "resin": "Rink Amide AM",
            "loading": "0.8", "lot": f"SPPS-{datetime.now().strftime('%y%m%d')}-{number:02d}",
            "chemistry": "DIC/HOBt", "status": "Ready", "cleavage_preset": "AUTO",
        }
    gui.pm_items.append(dict(item))
    gui._v228_switching = True
    try:
        gui.pm_list.insert("end", gui.pm_display_name(gui.pm_items[-1]))
        gui.pm_list.selection_clear(0, "end")
        gui.pm_list.selection_set(len(gui.pm_items) - 1)
        gui.pm_list.activate(len(gui.pm_items) - 1)
    finally:
        gui._v228_switching = False
    # During the legacy builder this method is called before the result trees
    # exist.  Defer full restore until build installation finishes.
    if all(hasattr(gui, name) for name in ("pm_selected_plan_tree", "pm_selected_material_tree", "pm_total_tree")):
        restore_item(gui, len(gui.pm_items) - 1, gui._v228_ns)
    else:
        gui._v228_active_index = len(gui.pm_items) - 1


def duplicate_item(gui):
    index = _active_index(gui)
    if index is None:
        return
    save_active(gui)
    item = dict(gui.pm_items[index])
    item["peptide"] = str(item.get("peptide", "Peptide")) + "_copy"
    item["lot"] = f"SPPS-{datetime.now().strftime('%y%m%d')}-{len(gui.pm_items)+1:02d}"
    add_item(gui, item)


def delete_item(gui):
    index = _active_index(gui)
    if index is None:
        return
    del gui.pm_items[index]
    gui.pm_list.delete(index)
    if not gui.pm_items:
        add_item(gui)
        return
    new_index = min(index, len(gui.pm_items) - 1)
    gui._v228_switching = True
    try:
        gui.pm_list.selection_set(new_index)
        gui.pm_list.activate(new_index)
    finally:
        gui._v228_switching = False
    restore_item(gui, new_index, gui._v228_ns)


def _bind_item_buttons(gui):
    # Only buttons in the left Peptide items frame.
    try:
        parent = gui.pm_list.master
        for widget in _walk(parent):
            if not isinstance(widget, ttk.Button):
                continue
            text = str(widget.cget("text"))
            if text == "Add":
                widget.configure(command=lambda: add_item(gui))
            elif text == "Duplicate":
                widget.configure(command=lambda: duplicate_item(gui))
            elif text == "Delete":
                widget.configure(command=lambda: delete_item(gui))
    except Exception:
        pass


def _hide_non_workbench_tabs(gui):
    """Keep the Pepforge SPPS workspace focused on Project Manager."""
    notebook = getattr(gui, "tabs", None)
    if not isinstance(notebook, ttk.Notebook):
        return
    keep = {"Project Manager"}
    for tab in list(notebook.tabs()):
        try:
            label = str(notebook.tab(tab, "text"))
            if label not in keep:
                notebook.forget(tab)
        except Exception:
            pass
    try:
        for tab in notebook.tabs():
            if str(notebook.tab(tab, "text")) == "Project Manager":
                notebook.select(tab)
                break
    except Exception:
        pass


def _normalize_title(gui):
    gui.title(TITLE)
    for widget in _walk(gui):
        if isinstance(widget, ttk.Label):
            try:
                text = str(widget.cget("text"))
            except Exception:
                continue
            if text.startswith("SPPS Planner GitHub"):
                widget.configure(text=TITLE)
                break


def export_outputs(gui, ns):
    """Export the visible edited plan exactly as shown; never regenerate on export."""
    try:
        if not _tree_rows(getattr(gui, "pm_selected_plan_tree", None)):
            generate(gui, ns)
        save_active(gui, include_outputs=True)
        plan_input = ns.get("_v226_plan_input") or ns.get("_v222_plan_input")
        inp = plan_input(gui) if callable(plan_input) else None
        try:
            out_text = gui.project_outdir.get() if hasattr(gui, "project_outdir") else ""
            if not str(out_text or "").strip() and hasattr(gui, "outdir"):
                out_text = gui.outdir.get()
            out = Path(str(out_text or "").strip() or "outputs/project_manager_exports")
        except Exception:
            out = Path("outputs/project_manager_exports")
        out.mkdir(parents=True, exist_ok=True)

        if inp is not None:
            try:
                from spps_planner.export import export_csvs, export_excel
                export_csvs(inp, out / "core_engine_outputs")
                export_excel(inp, out / "spps_plan_core_engine.xlsx")
            except Exception:
                pass

        visible_plan = pd.DataFrame(_tree_rows(getattr(gui, "pm_selected_plan_tree", None)))
        visible_materials = pd.DataFrame(_tree_rows(getattr(gui, "pm_selected_material_tree", None)))
        total_tree = getattr(gui, "pm_selected_total_tree", None) or getattr(gui, "pm_total_tree", None)
        visible_total = pd.DataFrame(_tree_rows(total_tree))
        visible_checklist = pd.DataFrame(_tree_rows(getattr(gui, "progress_tree", None)))
        visible_cleavage = pd.DataFrame(_tree_rows(getattr(gui, "pm_cleavage_tree", None)))
        try:
            from spps_planner.engine import cleavage_cocktail_presets, validate_plan, plan_summary
            presets = cleavage_cocktail_presets()
            validation = validate_plan(inp) if inp is not None else pd.DataFrame()
            summary = pd.DataFrame([plan_summary(inp)]) if inp is not None else pd.DataFrame()
        except Exception:
            presets = validation = summary = pd.DataFrame()

        index = _active_index(gui)
        item = dict(gui.pm_items[index]) if index is not None and 0 <= index < len(gui.pm_items) else {}
        editor_summary = pd.DataFrame([{
            "app_version": VERSION,
            "project": item.get("project", ""),
            "peptide": item.get("peptide", ""),
            "sequence": item.get("sequence", ""),
            "scale": item.get("scale", ""),
            "resin": item.get("resin", ""),
            "loading": item.get("loading", ""),
            "chemistry": item.get("chemistry", ""),
            "copies": item.get("copies", ""),
            "apply_loading_calc": item.get("apply_loading_calc", False),
            "loading_aa_eq": item.get("loading_aa_eq", ""),
            "loading_diea_eq": item.get("loading_diea_eq", ""),
            "loading_time_h": item.get("loading_time_h", ""),
            "cleavage_time_h": item.get("cleavage_time_h", ""),
            "cleavage_preset": item.get("cleavage_preset", ""),
        }])

        xlsx = out / "project_manager_selected_outputs_v2.2.8.xlsx"
        with pd.ExcelWriter(xlsx, engine="openpyxl") as writer:
            editor_summary.to_excel(writer, index=False, sheet_name="00_EDITOR_SUMMARY")
            visible_plan.to_excel(writer, index=False, sheet_name="01_SELECTED_PLAN_VISIBLE")
            visible_materials.to_excel(writer, index=False, sheet_name="02_SELECTED_MATERIALS_STEP")
            visible_total.to_excel(writer, index=False, sheet_name="03_SELECTED_TOTAL_MATERIALS")
            visible_checklist.to_excel(writer, index=False, sheet_name="04_SELECTED_CHECKLIST")
            visible_cleavage.to_excel(writer, index=False, sheet_name="05_CLEAVAGE_COCKTAIL")
            presets.to_excel(writer, index=False, sheet_name="06_CLEAVAGE_PRESETS")
            validation.to_excel(writer, index=False, sheet_name="07_VALIDATION")
            summary.to_excel(writer, index=False, sheet_name="08_SUMMARY")

        for filename, frame in (
            ("01_SELECTED_PLAN_VISIBLE.csv", visible_plan),
            ("02_SELECTED_MATERIALS_STEP.csv", visible_materials),
            ("03_SELECTED_TOTAL_MATERIALS.csv", visible_total),
            ("04_SELECTED_CHECKLIST.csv", visible_checklist),
            ("05_CLEAVAGE_COCKTAIL.csv", visible_cleavage),
        ):
            frame.to_csv(out / filename, index=False, encoding="utf-8-sig")

        state = {
            "app_version": VERSION,
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "active_index": index,
            "pm_items": list(getattr(gui, "pm_items", []) or []),
            "visible_selected_plan_source": "current edited TreeView; no regeneration during export",
        }
        (out / "project_manager_state_v2.2.8.json").write_text(
            json.dumps(state, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        gui.last_outdir = out
        try:
            messagebox.showinfo("Export complete", f"CSV/XLSX exported to:\n{out}")
        except Exception:
            pass
        return xlsx
    except Exception as exc:
        try:
            messagebox.showerror("Export error", str(exc))
        except Exception:
            pass
        return None


def save_session(gui):
    """Atomic, lightweight session save used by both autosave and the button."""
    try:
        save_active(gui, include_outputs=True)
        state = gui._collect_state() if hasattr(gui, "_collect_state") else {}
        state["app_version"] = VERSION
        state["pm_items"] = list(getattr(gui, "pm_items", []) or [])
        state["selected_pm_index"] = _active_index(gui) or 0
        path = Path(getattr(gui, "state_file", Path.cwd() / "project_manager_autosave.json"))
        state_persistence.atomic_write_json(path, state)
        gui._autosave_after_id = None
        return path
    except Exception:
        gui._autosave_after_id = None
        return None


def schedule_autosave(gui):
    try:
        pending = getattr(gui, "_autosave_after_id", None)
        if pending:
            gui.after_cancel(pending)
    except Exception:
        pass
    try:
        gui._autosave_after_id = gui.after(700, lambda: save_session(gui))
    except Exception:
        gui._autosave_after_id = None
