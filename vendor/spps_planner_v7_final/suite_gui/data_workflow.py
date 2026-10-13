"""Controller-facing Stage 4 data, Run, HPLC and workbook workflows."""
from __future__ import annotations
from suite_gui.runtime_state import get_active_index, get_calculation_namespace

from datetime import datetime, timezone
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any, Mapping

from suite_gui import data_system, data_workbook, state_persistence
from suite_gui.modules import plan_workflow, project_manager_workflow


def active_item(gui: Any) -> dict[str, Any]:
    items = getattr(gui, "pm_items", []) or []
    try:
        index = int(get_active_index(gui, -1))
    except Exception as exc:
        raise ValueError("No active Work Item.") from exc
    if not 0 <= index < len(items):
        raise ValueError("No active Work Item.")
    return items[index]


def _persist(gui: Any) -> None:
    plan_workflow._save_active(gui, include_outputs=True)
    data_system.sync_active_run(active_item(gui))
    try:
        gui.schedule_autosave()
    except Exception:
        pass


def list_runs(gui: Any) -> list[dict[str, Any]]:
    plan_workflow._save_active(gui, include_outputs=True)
    item = active_item(gui)
    data_system.sync_active_run(item)
    return data_system.list_runs(item)


def create_run(gui: Any, name: str = "", reason: str = "New synthesis run") -> dict[str, Any]:
    plan_workflow._save_active(gui, include_outputs=True)
    run = data_system.new_run(active_item(gui), name, reason=reason)
    project_manager_workflow._restore(
        gui, plan_workflow, get_calculation_namespace(gui, {}), int(get_active_index(gui, -1)),
    )
    _persist(gui)
    return run


def activate_run(gui: Any, run_id: str, reason: str = "Operator selected run") -> dict[str, Any]:
    plan_workflow._save_active(gui, include_outputs=True)
    run = data_system.activate_run(active_item(gui), run_id, reason=reason)
    project_manager_workflow._restore(
        gui, plan_workflow, get_calculation_namespace(gui, {}), int(get_active_index(gui, -1)),
    )
    _persist(gui)
    return run


def upsert_hplc(gui: Any, values: Mapping[str, Any], reason: str) -> dict[str, Any]:
    record = data_system.upsert_hplc(active_item(gui), values, reason=reason)
    _persist(gui)
    return record


def delete_hplc(gui: Any, record_id: str, reason: str) -> dict[str, Any]:
    record = data_system.delete_hplc(active_item(gui), record_id, reason=reason)
    _persist(gui)
    return record


def search_hplc(gui: Any, query: str = "", sort_by: str = "acquired_at",
                descending: bool = True) -> list[dict[str, Any]]:
    return data_system.search_hplc(
        getattr(gui, "pm_items", []) or [], query, sort_by=sort_by, descending=descending,
    )


def change_history(gui: Any) -> list[dict[str, Any]]:
    return data_system.change_history(active_item(gui))


def export_workbook(gui: Any, path: str | Path | None = None) -> Path | None:
    if path is None:
        selected = filedialog.asksaveasfilename(
            defaultextension=".xlsx", filetypes=[("SPPS Planner Workbook", "*.xlsx")],
            initialfile="SPPS_Planner_Data.xlsx",
        )
        if not selected:
            return None
        path = selected
    plan_workflow._save_active(gui, include_outputs=True)
    for item in getattr(gui, "pm_items", []) or []:
        data_system.sync_active_run(item)
    result = data_workbook.export_workbook(
        path, gui.pm_items, project_id=str(getattr(gui, "_project_id", "")),
    )
    return result


def import_workbook(gui: Any, path: str | Path | None = None,
                    column_mapping: Mapping[str, Mapping[str, str]] | None = None) -> Path | None:
    if path is None:
        selected = filedialog.askopenfilename(filetypes=[("SPPS Planner Workbook", "*.xlsx")])
        if not selected:
            return None
        path = selected
    imported = data_workbook.import_workbook(path, column_mapping=column_mapping)
    gui.pm_items = imported["items"]
    gui._project_id = str(imported.get("project", {}).get("project_id", "")) or getattr(gui, "_project_id", "")
    index = 0
    project_manager_workflow._rebuild_listbox(gui, [index], index)
    project_manager_workflow._restore(gui, plan_workflow, get_calculation_namespace(gui, {}), index)
    _persist(gui)
    return Path(path)


def import_hplc(gui: Any, path: str | Path | None = None,
                column_mapping: Mapping[str, str] | None = None,
                reason: str = "Imported HPLC table") -> int:
    if path is None:
        selected = filedialog.askopenfilename(
            filetypes=[("HPLC CSV/XLSX", "*.csv *.xlsx"), ("All files", "*.*")],
        )
        if not selected:
            return 0
        path = selected
    rows = data_workbook.import_hplc_rows(path, column_mapping=column_mapping)
    count = 0
    for row in rows:
        data_system.upsert_hplc(active_item(gui), row, reason=reason)
        count += 1
    _persist(gui)
    return count



def upsert_analytical(gui: Any, values: Mapping[str, Any], reason: str) -> dict[str, Any]:
    record=data_system.upsert_analytical(active_item(gui),values,reason=reason); _persist(gui); return record

def delete_analytical(gui: Any, record_id: str, reason: str) -> dict[str, Any]:
    record=data_system.delete_analytical(active_item(gui),record_id,reason=reason); _persist(gui); return record

def list_analytical(gui: Any) -> list[dict[str, Any]]:
    return data_system.list_analytical(active_item(gui))

def import_analytical(gui: Any, path: str | Path | None=None, reason: str='Imported analytical table') -> int:
    if path is None:
        selected=filedialog.askopenfilename(filetypes=[('Analytical CSV/XLSX','*.csv *.xlsx'),('All files','*.*')])
        if not selected: return 0
        path=selected
    frame = __import__('pandas').read_csv(path) if str(path).lower().endswith('.csv') else __import__('pandas').read_excel(path,engine='openpyxl')
    count=0
    for row in frame.to_dict('records'):
        data_system.upsert_analytical(active_item(gui),row,reason=reason); count+=1
    _persist(gui); return count

def recent_path(gui: Any) -> Path:
    override = getattr(gui, "recent_projects_path", None)
    if override:
        return Path(override)
    try:
        return Path(gui._state_file_path()).parent / "recent_projects.json"
    except Exception:
        from spps_planner.build_profile import FALLBACK_DOT_DIR
        return Path.home() / FALLBACK_DOT_DIR / "recent_projects.json"


def add_recent(gui: Any, path: str | Path, *, recovered: bool = False) -> None:
    registry_path = recent_path(gui)
    try:
        state = state_persistence.read_json_object(registry_path) if registry_path.exists() else {}
    except Exception:
        state = {}
    target = str(Path(path).resolve())
    rows = [row for row in state.get("recent", []) if isinstance(row, Mapping) and row.get("path") != target]
    rows.insert(0, {"path": target, "opened_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "recovered": bool(recovered)})
    state_persistence.atomic_write_json(registry_path, {"recent": rows[:12]})


def recent_projects(gui: Any) -> list[dict[str, Any]]:
    path = recent_path(gui)
    if not path.exists():
        return []
    try:
        rows = state_persistence.read_json_object(path).get("recent", [])
    except Exception:
        return []
    return [dict(row) | {"exists": Path(str(row.get("path", ""))).is_file()} for row in rows if isinstance(row, Mapping)]


__all__ = [
    "activate_run", "active_item", "add_recent", "change_history", "create_run",
    "delete_hplc", "delete_analytical", "export_workbook", "import_hplc", "import_analytical", "import_workbook",
    "list_runs", "list_analytical", "recent_path", "recent_projects", "search_hplc", "upsert_hplc", "upsert_analytical",
]
