"""Project Manager peptide-item editor and output snapshot state."""
from __future__ import annotations

from spps_v4_gui import catalogs


EDITOR_FIELDS = (
    ("pm_project", "project", ""),
    ("pm_peptide", "peptide", ""),
    ("pm_sequence", "sequence", ""),
    ("pm_scale", "scale", "0.2"),
    ("pm_resin", "resin", "Rink Amide AM"),
    ("pm_loading", "loading", "0.8"),
    ("pm_lot", "lot", ""),
    ("pm_chemistry", "chemistry", "DIC/HOBt"),
    ("pm_copies", "copies", "1"),
    ("loading_aa_eq", "loading_aa_eq", "2"),
    ("loading_diea_eq", "loading_diea_eq", "4"),
    ("loading_time_h", "loading_time_h", ""),
    ("coupling_time_h", "coupling_time_h", "0.5"),
    ("cleavage_preset", "cleavage_preset", ""),
    ("cleavage_eq_override", "cleavage_eq_override", "0"),
    ("cleavage_components_text", "cleavage_components_text", ""),
    ("cleavage_time_h", "cleavage_time_h", ""),
)

OUTPUT_TREES = (
    ("selected_plan_rows", "pm_selected_plan_tree"),
    ("selected_material_rows", "pm_selected_material_tree"),
    ("selected_total_rows", "pm_selected_total_tree"),
    ("selected_checklist_rows", "progress_tree"),
    ("selected_cleavage_rows", "pm_cleavage_tree"),
)

TAB_TO_OUTPUT = {
    "Selected Plan": "selected_plan_rows",
    "Plan": "selected_plan_rows",
    "Selected Materials": "selected_material_rows",
    "Materials": "selected_material_rows",
    "Selected Total Materials": "selected_total_rows",
    "Total Materials": "selected_total_rows",
    "Selected Checklist": "selected_checklist_rows",
    "Checklist": "selected_checklist_rows",
    "Cleavage Cocktail": "selected_cleavage_rows",
}


def _canonicalize_saved_rows(rows):
    """Migrate legacy display aliases while preserving sequence notation."""
    result = []
    unit_fields = {
        "Unit name", "material", "AA/Chemical/label/tag/linker", "unit",
    }
    for source in list(rows or []):
        row = dict(source)
        for field in unit_fields:
            if field in row:
                row[field] = catalogs.canonical_unit_name(row.get(field, ""))
        result.append(row)
    return result


def snapshot(gui, adapter, active_index):
    index = active_index(gui)
    if index is None:
        return
    item = gui.pm_items[index]
    item.update(adapter._editor_payload(gui))
    for item_key, tree_name in OUTPUT_TREES:
        rendered = getattr(gui, "_pm_rendered_output_index", {})
        if rendered and rendered.get(item_key) != index:
            continue
        item[item_key] = adapter._tree_rows(getattr(gui, tree_name, None))
    try:
        adapter._refresh_list_label(gui, index)
    except Exception:
        pass


def save_active(
    gui,
    adapter,
    active_index,
    commit_editor,
    *,
    include_outputs=True,
):
    index = active_index(gui)
    if index is None or getattr(gui, "_v229_switching", False):
        return
    gui.pm_items[index].update(adapter._editor_payload(gui))
    if include_outputs:
        commit_editor(gui)
        snapshot(gui, adapter, active_index)


def clear_editor_and_outputs(gui, adapter, set_value):
    gui._v229_switching = True
    try:
        for name in (
            "pm_project", "pm_peptide", "pm_sequence", "pm_scale",
            "pm_resin", "pm_loading", "pm_lot", "pm_chemistry", "pm_copies",
        ):
            set_value(gui, name, "")
        set_value(gui, "cleavage_preset", "")
        set_value(gui, "cleavage_eq_override", "0")
        set_value(gui, "cleavage_components_text", "")
        set_value(gui, "cleavage_time_h", "")
        set_value(gui, "loading_time_h", "")
        set_value(gui, "coupling_time_h", "0.5")
        for _, tree_name in OUTPUT_TREES:
            adapter._clear_tree(getattr(gui, tree_name, None))
        # Checklist must be visually empty at startup as well as logically empty.
        # Reset progress state so a restored/saved checklist cannot leave stale UI.
        try:
            gui.checklist_progress_var.set(0.0)
        except Exception:
            pass
        try:
            gui.checklist_progress_label.configure(text="Progress: 0/0 (0.0%)")
        except Exception:
            pass
        try:
            gui.pm_list.selection_clear(0, "end")
        except Exception:
            pass
        gui._v229_active_index = None
        gui._v229_dirty_columns = {}
    finally:
        gui._v229_switching = False


def restore_item(
    gui,
    index,
    adapter,
    set_value,
    bind_plan_editor,
    namespace,
    *,
    plan_columns,
    plan_widths,
    material_columns,
    material_widths,
    total_columns,
    total_widths,
    check_columns,
    check_widths,
):
    if not (0 <= int(index) < len(gui.pm_items)):
        return
    item = gui.pm_items[int(index)]
    for output_key, _tree_name in OUTPUT_TREES:
        if output_key in item:
            item[output_key] = _canonicalize_saved_rows(item[output_key])
    gui._v229_switching = True
    try:
        for name, key, default in EDITOR_FIELDS:
            if not hasattr(gui, name):
                continue
            current = item.get(
                key,
                item.get("lot_no", default) if key == "lot" else default,
            )
            set_value(gui, name, current)
        try:
            gui.apply_loading_calc.set(
                bool(item.get("apply_loading_calc", False))
            )
        except Exception:
            pass
        gui._v229_active_index = int(index)
        gui.pm_list.selection_clear(0, "end")
        gui.pm_list.selection_set(index)
        gui.pm_list.activate(index)
    finally:
        gui._v229_switching = False
    writers = {
        "selected_plan_rows": lambda: adapter._write_rows(
            gui.pm_selected_plan_tree, item.get("selected_plan_rows", []),
            plan_columns, plan_widths,
        ),
        "selected_material_rows": lambda: adapter._write_rows(
            gui.pm_selected_material_tree, item.get("selected_material_rows", []),
            material_columns, material_widths,
        ),
        "selected_total_rows": lambda: adapter._write_rows(
            getattr(gui, "pm_selected_total_tree", getattr(gui, "pm_total_tree", None)),
            item.get("selected_total_rows", []), total_columns, total_widths,
        ),
        "selected_checklist_rows": lambda: adapter._write_rows(
            gui.progress_tree, item.get("selected_checklist_rows", []),
            check_columns, check_widths,
        ),
        "selected_cleavage_rows": lambda: adapter._write_rows(
            gui.pm_cleavage_tree, item.get("selected_cleavage_rows", []),
        ),
    }
    notebook = getattr(gui, "pm_results_notebook", None)
    rendered = getattr(gui, "_pm_rendered_output_index", {})
    gui._pm_rendered_output_index = rendered

    def selected_output_key():
        try:
            tab = notebook.select()
            return TAB_TO_OUTPUT.get(str(notebook.tab(tab, "text")))
        except Exception:
            return None

    def render_current_tab(_event=None):
        current_index = getattr(gui, "_v229_active_index", None)
        if current_index is None or not (0 <= int(current_index) < len(gui.pm_items)):
            return
        key = selected_output_key()
        if key is None or rendered.get(key) == int(current_index):
            return
        current_item = gui.pm_items[int(current_index)]
        original_item = item
        if current_item is original_item:
            writers[key]()
        else:
            # Re-enter through the normal restore path on the next selection;
            # this guard prevents a queued tab event painting an older item.
            return
        rendered[key] = int(current_index)
        if key == "selected_plan_rows":
            bind_plan_editor(gui, namespace)

    if notebook is None:
        for key, writer in writers.items():
            writer()
            rendered[key] = int(index)
    else:
        render_current_tab()
        gui._pm_lazy_output_renderer = render_current_tab
        if not getattr(gui, "_pm_lazy_output_bound", False):
            def dispatch_current_renderer(_event=None):
                renderer = getattr(gui, "_pm_lazy_output_renderer", None)
                if callable(renderer):
                    renderer()

            notebook.bind(
                "<<NotebookTabChanged>>", dispatch_current_renderer, add="+",
            )
            gui._pm_lazy_output_bound = True
    gui._v229_dirty_columns = {}
    if notebook is None:
        bind_plan_editor(gui, namespace)


def live_sync(gui, adapter, active_index):
    if getattr(gui, "_v229_switching", False):
        return
    index = active_index(gui)
    if index is None:
        return
    gui.pm_items[index].update(adapter._editor_payload(gui))
    try:
        adapter._refresh_list_label(gui, index)
        gui.schedule_autosave()
    except Exception:
        pass


__all__ = [
    "EDITOR_FIELDS",
    "OUTPUT_TREES",
    "clear_editor_and_outputs",
    "live_sync",
    "restore_item",
    "save_active",
    "snapshot",
]
