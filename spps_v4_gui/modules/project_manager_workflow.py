"""Accepted peptide-item and Project Manager workflow.

Adds the operator-requested peptide item behaviours without removing legacy
settings:
- single click saves current item and restores the clicked item;
- Ctrl/Shift multi-select remains available for delete;
- Delete can remove several items, including the last remaining item;
- drag selected rows to reorder peptide items while keeping saved data attached;
- Unit defaults keeps one AA/modifier eq system and preserves default/manual checks;
- Selected Total Materials are grouped in the requested operating order.
"""
from __future__ import annotations

from typing import Any
import re
import tkinter as tk
from tkinter import ttk
from spps_v4_gui import peptide_item_collection

APP_VERSION = "V4.0.0"
VERSION_LABEL = "SPPS Planner V4.0.0"


def _walk(widget):
    try:
        children = widget.winfo_children()
    except Exception:
        return
    for child in children:
        yield child
        yield from _walk(child)


def _safe_get(var, default=""):
    try:
        return var.get()
    except Exception:
        return default


def _safe_set(var, value):
    try:
        var.set(value)
    except Exception:
        pass


def _active_index(gui):
    try:
        idx = int(getattr(gui, "_v229_active_index", -1))
        if 0 <= idx < len(getattr(gui, "pm_items", []) or []):
            return idx
    except Exception:
        pass
    return None


def _display_name(gui, item: dict[str, Any]) -> str:
    try:
        return gui.pm_display_name(item)
    except Exception:
        return f"{item.get('project','')} | {item.get('peptide','')} | {item.get('lot','')}"


def _clear_listbox(gui):
    try:
        gui.pm_list.delete(0, "end")
    except Exception:
        pass


def _rebuild_listbox(gui, selected: list[int] | None = None, active: int | None = None):
    _clear_listbox(gui)
    items = list(getattr(gui, "pm_items", []) or [])
    for item in items:
        try:
            gui.pm_list.insert("end", _display_name(gui, item))
        except Exception:
            gui.pm_list.insert("end", str(item))
    try:
        gui.pm_list.selection_clear(0, "end")
        if selected:
            for idx in selected:
                if 0 <= int(idx) < len(items):
                    gui.pm_list.selection_set(int(idx))
        elif active is not None and 0 <= int(active) < len(items):
            gui.pm_list.selection_set(int(active))
            gui.pm_list.activate(int(active))
    except Exception:
        pass


def _refresh_label(gui, index: int):
    try:
        gui.pm_list.delete(index)
        gui.pm_list.insert(index, _display_name(gui, gui.pm_items[index]))
        gui.pm_list.selection_set(index)
        gui.pm_list.activate(index)
    except Exception:
        _rebuild_listbox(gui, [index], index)


def _empty_editor_outputs(gui):
    """Empty the peptide editor and all result panes when no item remains."""
    try:
        gui._v229_switching = True
    except Exception:
        pass
    try:
        for name in (
            "pm_project", "pm_peptide", "pm_sequence", "pm_scale", "pm_resin",
            "pm_loading", "pm_lot", "pm_chemistry", "pm_copies",
            "loading_time_h", "cleavage_time_h", "cleavage_preset", "cleavage_eq_override", "cleavage_components_text",
        ):
            var = getattr(gui, name, None)
            if var is not None:
                _safe_set(var, "")
        for name in ("apply_loading_calc",):
            var = getattr(gui, name, None)
            if var is not None:
                _safe_set(var, False)
        for tree_name in (
            "pm_selected_plan_tree", "pm_selected_material_tree", "pm_selected_total_tree",
            "pm_total_tree", "progress_tree", "pm_cleavage_tree", "pm_summary_tree",
        ):
            tree = getattr(gui, tree_name, None)
            if tree is None:
                continue
            try:
                for iid in list(tree.get_children()):
                    tree.delete(iid)
            except Exception:
                pass
        for text_name in ("pm_selected_check_text", "check_text", "short_step_text"):
            text = getattr(gui, text_name, None)
            if text is not None:
                try:
                    text.delete("1.0", "end")
                except Exception:
                    pass
        try:
            gui.checklist_progress_var.set(0)
            gui.checklist_progress_label.configure(text="Progress: 0/0 (0.0%)")
        except Exception:
            pass
        gui._v229_active_index = None
        gui._v229_dirty_columns = {}
    finally:
        try:
            gui._v229_switching = False
        except Exception:
            pass


def _sync_modifier_to_aa(gui):
    """Modifier/chemical eq/repeat follow the single AA default system."""
    if not bool(_safe_get(getattr(gui, "unit_defaults_unified", None), True)):
        return
    try:
        if hasattr(gui, "coupling_eq") and hasattr(gui, "modifier_eq"):
            _safe_set(gui.modifier_eq, _safe_get(gui.coupling_eq, ""))
    except Exception:
        pass
    try:
        if hasattr(gui, "coupling_repeats") and hasattr(gui, "modifier_repeats"):
            _safe_set(gui.modifier_repeats, _safe_get(gui.coupling_repeats, ""))
    except Exception:
        pass


def _save_active(gui, v229, include_outputs=True):
    if getattr(gui, "_v2212_switching", False):
        return
    _sync_modifier_to_aa(gui)
    try:
        v229._save_active(gui, include_outputs=include_outputs)
    except Exception:
        # Fallback: save editor-only values to active item.
        idx = _active_index(gui)
        if idx is None:
            return
        try:
            gui.pm_items[idx].update({
                "project": _safe_get(gui.pm_project, ""),
                "peptide": _safe_get(gui.pm_peptide, ""),
                "sequence": _safe_get(gui.pm_sequence, ""),
                "scale": _safe_get(gui.pm_scale, ""),
                "resin": _safe_get(gui.pm_resin, ""),
                "loading": _safe_get(gui.pm_loading, ""),
                "lot": "",
                "lot_no": "",
                "chemistry": _safe_get(gui.pm_chemistry, ""),
                "copies": _safe_get(gui.pm_copies, ""),
            })
        except Exception:
            pass


def _restore(gui, v229, ns: dict[str, Any], index: int):
    if not (0 <= int(index) < len(getattr(gui, "pm_items", []) or [])):
        _empty_editor_outputs(gui)
        return
    gui._v2212_switching = True
    try:
        v229._restore_item(gui, int(index), ns)
        gui._v229_active_index = int(index)
    finally:
        gui._v2212_switching = False


def single_select(gui, v229, ns: dict[str, Any], _event=None):
    if getattr(gui, "_v2212_switching", False) or getattr(gui, "_v2212_dragging", False):
        return None
    try:
        selected = [int(i) for i in gui.pm_list.curselection()]
    except Exception:
        selected = []
    if len(selected) != 1:
        # Multi-selection is for batch delete/reorder; do not replace editor.
        return None
    new_index = selected[0]
    old_index = _active_index(gui)
    if old_index is not None:
        # Generated/applied outputs already live on the item.  Re-reading every
        # Treeview row on every click was the dominant Project Manager delay.
        # Snapshot the large output tables only when a Plan cell is actually
        # being edited; ordinary switching saves the small editor payload only.
        tree = getattr(gui, "pm_selected_plan_tree", None)
        editor = getattr(tree, "_v229_editor", None) if tree is not None else None
        include_outputs = bool(
            getattr(gui, "_v229_dirty_columns", {})
            or editor is not None
        )
        _save_active(gui, v229, include_outputs=include_outputs)
    if old_index != new_index:
        _restore(gui, v229, ns, new_index)
    else:
        _refresh_label(gui, new_index)
    return None


def double_click(gui, v229, ns: dict[str, Any], _event=None):
    # Explicit reload path: same behaviour as single-select, but forced even when
    # the selected item equals the active index.
    if getattr(gui, "_v2212_dragging", False):
        return "break"
    try:
        selected = [int(i) for i in gui.pm_list.curselection()]
    except Exception:
        selected = []
    if not selected:
        return "break"
    _save_active(gui, v229, include_outputs=True)
    _restore(gui, v229, ns, selected[0])
    return "break"


def delete_items(gui, v229, ns: dict[str, Any]):
    try:
        selected = sorted({int(i) for i in gui.pm_list.curselection()})
    except Exception:
        selected = []
    if not selected:
        idx = _active_index(gui)
        if idx is not None:
            selected = [idx]
    if not selected:
        return
    _save_active(gui, v229, include_outputs=True)
    result = peptide_item_collection.delete_items(
        getattr(gui, "pm_items", []),
        selected,
    )
    if not result.deleted_indices:
        return
    gui.pm_items = result.items
    if not result.items:
        gui._v229_active_index = None
        _rebuild_listbox(gui, [], None)
        _empty_editor_outputs(gui)
    else:
        new_index = result.active_index
        _rebuild_listbox(gui, [new_index], new_index)
        _restore(gui, v229, ns, new_index)
    try:
        gui.schedule_autosave()
    except Exception:
        pass


def _start_drag(gui, event):
    try:
        gui._v2212_drag_start_y = int(event.y)
        gui._v2212_drag_last_target = int(gui.pm_list.nearest(event.y))
        gui._v2212_drag_selection = sorted({int(i) for i in gui.pm_list.curselection()})
    except Exception:
        gui._v2212_drag_selection = []
    gui._v2212_dragging = False
    return None


def _move_block(gui, selected: list[int], target: int):
    result = peptide_item_collection.move_block(
        getattr(gui, "pm_items", []),
        selected,
        target,
        _active_index(gui),
    )
    gui.pm_items = result.items
    gui._v229_active_index = result.active_index
    new_selected = list(result.selected_indices)
    _rebuild_listbox(gui, new_selected, result.active_index)
    return new_selected


def _drag_motion(gui, event):
    try:
        if abs(int(event.y) - int(getattr(gui, "_v2212_drag_start_y", event.y))) < 4:
            return None
        gui._v2212_dragging = True
        target = int(gui.pm_list.nearest(event.y))
        last = getattr(gui, "_v2212_drag_last_target", None)
        if target == last:
            return None
        selected = sorted({int(i) for i in gui.pm_list.curselection()}) or list(getattr(gui, "_v2212_drag_selection", []) or [])
        if not selected:
            return None
        gui._v2212_drag_last_target = target
        new_selected = _move_block(gui, selected, target)
        gui._v2212_drag_selection = new_selected
    except Exception:
        pass
    return "break"


def _end_drag(gui, event):
    if getattr(gui, "_v2212_dragging", False):
        try:
            gui.schedule_autosave()
        except Exception:
            pass
        # Do not immediately load during reorder; preserve editor unless exactly
        # one reordered item is explicitly selected after the drag finishes.
        try:
            gui.after(120, lambda: setattr(gui, "_v2212_dragging", False))
        except Exception:
            gui._v2212_dragging = False
        return "break"
    gui._v2212_dragging = False
    return None


def _install_item_bindings(gui, v229, ns: dict[str, Any]):
    try:
        gui.pm_list.configure(selectmode=tk.EXTENDED, exportselection=False)
    except Exception:
        pass
    try:
        gui.pm_list.bind("<<ListboxSelect>>", gui.pm_on_select, add=False)
        gui.pm_list.bind("<Double-Button-1>", gui.pm_on_double_click, add=False)
        gui.pm_list.bind("<Return>", gui.pm_on_double_click, add=False)
        gui.pm_list.bind("<Delete>", lambda _e: (gui.pm_delete_peptide(), "break"), add=False)
        gui.pm_list.bind("<BackSpace>", lambda _e: (gui.pm_delete_peptide(), "break"), add=False)
        gui.pm_list.bind("<ButtonPress-1>", lambda e, _g=gui: _start_drag(_g, e), add=False)
        gui.pm_list.bind("<B1-Motion>", lambda e, _g=gui: _drag_motion(_g, e), add=False)
        gui.pm_list.bind("<ButtonRelease-1>", lambda e, _g=gui: _end_drag(_g, e), add=False)
    except Exception:
        pass
    try:
        parent = gui.pm_list.master
        for widget in _walk(parent):
            if isinstance(widget, ttk.Button):
                text = str(widget.cget("text"))
                if text == "Delete":
                    widget.configure(command=gui.pm_delete_peptide)
    except Exception:
        pass


def _find_setup_notebook(gui):
    for widget in _walk(gui):
        if not isinstance(widget, ttk.Notebook):
            continue
        try:
            labels = [str(widget.tab(tab, "text")) for tab in widget.tabs()]
        except Exception:
            continue
        if "Unit defaults" in labels and "Reagents" in labels:
            return widget
    return None


def _tab_frame(notebook, label: str):
    for tab in notebook.tabs():
        try:
            if str(notebook.tab(tab, "text")) == label:
                return notebook.nametowidget(tab)
        except Exception:
            pass
    return None


def _grid_next_row(frame) -> int:
    rows = []
    for child in frame.winfo_children():
        try:
            rows.append(int(child.grid_info().get("row", 0)))
        except Exception:
            pass
    return (max(rows) + 1) if rows else 0


def _install_unit_defaults_ui(gui):
    if not hasattr(gui, "unit_defaults_unified"):
        gui.unit_defaults_unified = tk.BooleanVar(value=True)
    if not hasattr(gui, "use_default_aa_eq"):
        gui.use_default_aa_eq = tk.BooleanVar(value=True)
    if not hasattr(gui, "use_default_aa_repeat"):
        gui.use_default_aa_repeat = tk.BooleanVar(value=True)
    nb = _find_setup_notebook(gui)
    if nb is None:
        return
    frame = _tab_frame(nb, "Unit defaults")
    if frame is None:
        return
    # Hide/remove the separate modifier controls in this setup page only.
    modifier_rows = set()
    for child in list(frame.winfo_children()):
        try:
            text = str(child.cget("text"))
        except Exception:
            text = ""
        try:
            tv = str(child.cget("textvariable"))
        except Exception:
            tv = ""
        if "Modifier" in text or tv in {str(getattr(gui, "modifier_eq", "")), str(getattr(gui, "modifier_repeats", ""))}:
            try:
                modifier_rows.add(int(child.grid_info().get("row", -1)))
            except Exception:
                pass
            try:
                child.grid_remove()
            except Exception:
                pass
    for child in list(frame.winfo_children()):
        try:
            if int(child.grid_info().get("row", -2)) in modifier_rows:
                text = str(child.cget("text")) if hasattr(child, "cget") else ""
                if text in {"eq", ""} or child.__class__.__name__.endswith("Spinbox"):
                    child.grid_remove()
        except Exception:
            pass
    # Relabel repeat as doubling.
    for child in frame.winfo_children():
        if isinstance(child, ttk.Label):
            try:
                if str(child.cget("text")) == "Default AA repeat":
                    child.configure(text="Default AA doubling")
            except Exception:
                pass
    if getattr(gui, "_v2212_unit_ui_installed", False):
        return
    row = _grid_next_row(frame) + 1
    ttk.Checkbutton(frame, text="Use default AA eq for generated units", variable=gui.use_default_aa_eq).grid(row=row, column=0, columnspan=3, sticky="w", padx=2, pady=(8, 2))
    ttk.Checkbutton(frame, text="Use default doubling/repeat", variable=gui.use_default_aa_repeat).grid(row=row+1, column=0, columnspan=3, sticky="w", padx=2, pady=2)
    ttk.Checkbutton(frame, text="Use the same eq/doubling system for AA, Ac-AA-OH, modifier, label, and chemical", variable=gui.unit_defaults_unified, command=lambda _g=gui: _sync_modifier_to_aa(_g)).grid(row=row+2, column=0, columnspan=8, sticky="w", padx=2, pady=2)
    ttk.Label(frame, text="Manual per-unit values are still edited directly in Selected Plan, then applied with Apply Change.").grid(row=row+3, column=0, columnspan=8, sticky="w", padx=2, pady=(2, 0))
    gui._v2212_unit_ui_installed = True
    _sync_modifier_to_aa(gui)


def _install_checklist_widths(gui):
    widths = {"line": 55, "done": 60, "checked_at": 125, "operation": 250, "unit": 120, "next_step": 260, "note": 360}
    tree = getattr(gui, "progress_tree", None)
    if tree is None:
        return
    try:
        for col, width in widths.items():
            if col in tree["columns"]:
                tree.column(col, width=width, minwidth=35, stretch=False)
    except Exception:
        pass


def _install_title(gui):
    try:
        gui.title(VERSION_LABEL)
    except Exception:
        pass
    for widget in _walk(gui):
        try:
            if isinstance(widget, ttk.Label) and str(widget.cget("text")).startswith("SPPS Planner GitHub"):
                widget.configure(text=VERSION_LABEL)
        except Exception:
            pass


def apply_post_build(gui, v229, ns):
    gui._v2212_ns = ns
    _install_title(gui)
    _install_unit_defaults_ui(gui)
    _install_checklist_widths(gui)
    _install_item_bindings(gui, v229, ns)
    try:
        gui.pm_list.configure(selectmode=tk.EXTENDED, exportselection=False)
    except Exception:
        pass
    if not getattr(gui, "pm_items", None):
        _empty_editor_outputs(gui)
    elif _active_index(gui) is None:
        try:
            gui._v229_active_index = 0
            gui.pm_list.selection_clear(0, "end")
            gui.pm_list.selection_set(0)
            gui.pm_list.activate(0)
        except Exception:
            pass
