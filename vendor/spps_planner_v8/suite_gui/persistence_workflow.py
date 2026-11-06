"""Direct project/session persistence for SPPS Planner V6.0.0."""
from __future__ import annotations
from suite_gui.runtime_state import get_active_index, set_active_index, get_calculation_namespace

from copy import deepcopy
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any, Mapping
from uuid import uuid4

from suite_gui import batch_workflow, data_system, data_workflow, ml_dataset, state_persistence, synthesis_execution
from suite_gui.modules import plan_workflow, project_manager_workflow
from suite_gui.modules.release_ui import _normalize_resin
from suite_gui.session_state import DEFAULT_STATE_FIELDS


VERSION = "V8.0.0"
EXTRA_DEFAULT_FIELDS = (
    "solvent_volume_mode",
    "amide_ml_per_mmol",
    "ctc_ml_per_mmol",
    "solvent_molarity_m",
    "reagent_eq_follows_coupling_eq",
    "use_default_aa_eq",
    "use_default_aa_repeat",
    "unit_defaults_unified",
    "use_position_aa_eq",
    "position_aa_eq_rules",
    "use_position_doubling",
    "position_doubling_rules",
    "apply_loading_calc",
    "loading_time_h",
    "cleavage_time_h",
    "cleavage_preset",
    "cleavage_eq_override",
    "cleavage_components_text",
)


def session_path(gui: Any) -> Path:
    try:
        path = Path(gui._state_file_path())
    except Exception:
        from spps_planner.build_profile import FALLBACK_DOT_DIR
        path = Path.home() / FALLBACK_DOT_DIR / "spps_planner_session_v1.json"
    gui.state_file = path
    return path


def _value(variable: Any) -> Any:
    try:
        return variable.get()
    except Exception:
        return None


def _migrate_volume_defaults(defaults: Mapping[str, Any] | None) -> dict[str, Any]:
    """Upgrade the removed global volume field to the canonical controls.

    Modern resin-specific settings always win.  A project that predates them
    receives its former global factor in both resin fields so it opens with the
    same calculated volume and can then be refined independently.
    """
    migrated = dict(defaults or {})
    legacy = migrated.pop("ml_per_mmol", None)
    if legacy not in (None, ""):
        migrated.setdefault("amide_ml_per_mmol", legacy)
        migrated.setdefault("ctc_ml_per_mmol", legacy)
    return migrated


def _active_index(gui: Any) -> int:
    try:
        index = int(get_active_index(gui, 0))
    except Exception:
        index = 0
    items = list(getattr(gui, "pm_items", []) or [])
    return max(0, min(index, len(items) - 1)) if items else 0


def _tree_rows(tree: Any) -> list[dict[str, Any]]:
    if tree is None:
        return []
    try:
        columns = list(tree["columns"])
        return [
            dict(zip(columns, tree.item(item_id, "values")))
            for item_id in tree.get_children()
        ]
    except Exception:
        return []


def collect_state(gui: Any, *, sync_runs: bool = True) -> dict[str, Any]:
    """Collect the complete portable state without inherited patch callbacks."""
    try:
        plan_workflow._save_active(gui, include_outputs=True)
    except Exception as exc:
        raise RuntimeError("Could not capture the active Planner state before project save.") from exc
    if sync_runs:
        for item in getattr(gui, "pm_items", []) or []:
            try:
                data_system.sync_active_run(item)
            except Exception as exc:
                raise RuntimeError("Could not synchronize active Run linkage before project save.") from exc
    if not str(getattr(gui, "_project_id", "")).strip():
        gui._project_id = uuid4().hex

    defaults = {}
    for name in dict.fromkeys(DEFAULT_STATE_FIELDS + EXTRA_DEFAULT_FIELDS):
        variable = getattr(gui, name, None)
        value = _value(variable)
        if value is not None:
            defaults[name] = value

    batch_rows = _tree_rows(getattr(gui, "batch_tree", None))
    state = state_persistence.project_state(
        app_version=VERSION,
        saved_at=datetime.now().isoformat(timespec="seconds"),
        active_index=_active_index(gui),
        selected_pm_index=_active_index(gui),
        pm_items=getattr(gui, "pm_items", []),
        defaults=defaults,
        batch_rows=batch_rows,
    )
    state["custom_materials"] = dict(
        getattr(gui, "custom_materials", {}) or {},
    )
    state["data_schema_version"] = data_system.SCHEMA_VERSION
    state["project_id"] = gui._project_id
    state["project_revision"] = int(getattr(gui, "_project_revision", 0) or 0)
    state["project_change_history"] = list(getattr(gui, "_project_change_history", []) or [])
    return state


def _output_directory(gui: Any) -> Path:
    text = ""
    for name in ("project_outdir", "outdir"):
        value = _value(getattr(gui, name, None))
        if str(value or "").strip():
            text = str(value).strip()
            break
    return Path(text or "outputs/project_manager_exports")


def _same_path(left: Any, right: Any) -> bool:
    try:
        return Path(left).resolve() == Path(right).resolve()
    except Exception:
        return False


def _save_project_path(gui: Any, path: Path, show: bool, *, expected_destination_sha: str | None = None, expected_absent: bool = False) -> Path:
    loaded_path = getattr(gui, "_loaded_project_path", None)
    expected = str(getattr(gui, "_loaded_project_fingerprint", "") or "")
    if path.exists() and loaded_path and _same_path(path, loaded_path) and expected:
        actual = state_persistence.file_sha256(path)
        if actual != expected:
            raise RuntimeError(
                "Project file changed outside SPPS Planner. Reload it or use Save Project As to avoid overwriting another edit."
            )
    # Capture first. A failed editor/Run capture or failed file publication must
    # not mutate the in-memory revision/history and then report an unsaved state.
    previous_revision = int(getattr(gui, "_project_revision", 0) or 0)
    previous_history = list(getattr(gui, "_project_change_history", []) or [])
    state = collect_state(gui)
    revision = previous_revision + 1
    history = list(previous_history)
    history.append({
        "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
        "action": "save", "revision": revision, "path": str(path),
    })
    state["project_revision"] = revision
    state["project_change_history"] = history
    # Recheck under the same OS lock as the backup/write to close the race
    # between a separate editor's update and our initial fingerprint check.
    guard = expected if (loaded_path and _same_path(path, loaded_path) and expected) else expected_destination_sha
    kwargs = {}
    if guard is not None:
        kwargs["expected_sha256"] = guard
    if expected_absent:
        kwargs["expected_absent"] = True
    state_persistence.atomic_write_json_with_backup(path, state, **kwargs)
    # Publish in-memory metadata only after the atomic file write succeeds.
    gui._project_revision = revision
    gui._project_change_history = history
    gui._loaded_project_path = path
    gui._loaded_project_fingerprint = state_persistence.file_sha256(path)
    gui.last_outdir = path.parent
    data_workflow.add_recent(gui, path)
    if show:
        try:
            messagebox.showinfo("Save Project", f"Saved revision {revision}:\n{path}")
        except Exception:
            pass
    return path


def save_project(gui: Any, show: bool = True) -> Path | None:
    try:
        loaded = getattr(gui, "_loaded_project_path", None)
        path = Path(loaded) if loaded else _output_directory(gui) / "project_manager_state.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return _save_project_path(gui, path, show)
    except Exception as exc:
        try:
            messagebox.showerror("Save Project", str(exc))
        except Exception:
            pass
        return None


def save_project_as(gui: Any, path: str | Path | None = None, show: bool = True) -> Path | None:
    if path is None:
        selected = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("SPPS Planner Project", "*.json")],
            initialfile="project_manager_state.json",
        )
        if not selected:
            return None
        path = selected
    previous_path = getattr(gui, "_loaded_project_path", None)
    previous_fingerprint = str(getattr(gui, "_loaded_project_fingerprint", "") or "")
    try:
        destination = Path(path)
        destination_existed = destination.exists()
        destination_sha = state_persistence.file_sha256(destination) if destination_existed else None
        # A supplied destination bypasses the native save dialog. Never silently
        # overwrite an existing project, including the currently loaded one.
        if destination.exists():
            if not messagebox.askyesno(
                "Overwrite existing project?",
                f"This file already exists:\n{destination}\n\nReplace it?",
                default="no",
            ):
                return None
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Preserve the fingerprint for the currently open project. An
        # overwrite confirmation does not waive external-edit protection.
        if not (previous_path and _same_path(destination, previous_path)):
            gui._loaded_project_path = None
            gui._loaded_project_fingerprint = ""
        saved = _save_project_path(gui, destination, show, expected_destination_sha=destination_sha, expected_absent=not destination_existed)
        return saved
    except Exception as exc:
        gui._loaded_project_path = previous_path
        gui._loaded_project_fingerprint = previous_fingerprint
        try:
            messagebox.showerror("Save Project As", str(exc))
        except Exception:
            pass
        return None


def save_autosave_state(gui: Any) -> Path | None:
    path = session_path(gui)
    try:
        state_persistence.atomic_write_json_with_backup(
            path, collect_state(gui, sync_runs=False),
        )
        gui._autosave_after_id = None
        return path
    except Exception as exc:
        gui._autosave_after_id = None
        try:
            gui._log(f"Autosave warning: {exc}\n")
        except Exception:
            pass
        return None


def schedule_autosave(gui: Any) -> None:
    if getattr(gui, "_restoring_state", False):
        return
    try:
        pending = getattr(gui, "_autosave_after_id", None)
        if pending:
            gui.after_cancel(pending)
    except Exception:
        pass
    try:
        gui._autosave_after_id = gui.after(
            700, gui.save_autosave_state,
        )
    except Exception:
        gui._autosave_after_id = None


def _legacy_item(gui: Any, data: Mapping[str, Any]) -> dict[str, Any]:
    def current(name: str, default: str) -> str:
        value = _value(getattr(gui, name, None))
        return str(value if value is not None else default)

    return {
        "project": data.get(
            "project_name", data.get("project", current("pm_project", "")),
        ),
        "peptide": data.get(
            "peptide_name", data.get("peptide", current("pm_peptide", "")),
        ),
        "sequence": data.get(
            "sequence", data.get("seq", current("pm_sequence", "")),
        ),
        "scale": str(data.get(
            "scale_mmol", data.get("scale", current("pm_scale", "0.2")),
        )),
        "resin": _normalize_resin(data.get(
            "resin", current("pm_resin", "Rink Amide AM"),
        )),
        "loading": str(data.get(
            "loading_mmol_g", data.get("loading", current("pm_loading", "0.8")),
        )),
        "lot": data.get("lot_no", data.get("lot", current("pm_lot", ""))),
        "chemistry": data.get(
            "chemistry", current("pm_chemistry", "DIC/HOBt"),
        ),
        "copies": str(data.get("copies", current("pm_copies", "1"))),
        "status": "Loaded",
    }


def _validate_loaded_state(data: Mapping[str, Any]) -> None:
    """Reject structurally damaged files before updating any GUI variables."""
    if not isinstance(data, Mapping) or not data:
        raise ValueError("Empty or invalid project/session data; existing work was not changed.")
    if "pm_items" in data:
        items = data["pm_items"]
        if not isinstance(items, list) or any(not isinstance(item, Mapping) for item in items):
            raise ValueError("Invalid pm_items structure; refusing a destructive project import.")
    elif not any(key in data for key in ("sequence", "seq", "project", "project_name", "peptide_name")):
        raise ValueError("Unrecognized SPPS project format; existing work was not changed.")
    for field in ("defaults", "custom_materials"):
        if field in data and not isinstance(data[field], Mapping):
            raise ValueError(f"Invalid {field} structure in saved project.")
    if "project_change_history" in data and not isinstance(data["project_change_history"], list):
        raise ValueError("Invalid project history structure.")
    for field in ("selected_pm_index", "active_index", "project_revision"):
        if field in data:
            try:
                int(data[field] or 0)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid {field} in saved project.") from exc


def _prepare_state(gui: Any, data: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], bool, int]:
    """Validate and construct model data before changing any live GUI state."""
    _validate_loaded_state(data)
    defaults = _migrate_volume_defaults(data.get("defaults", {}))
    custom = deepcopy(dict(data.get("custom_materials", {})))
    items = state_persistence.normalize_items(data.get("pm_items", []))
    # An explicitly present (even empty) pm_items collection is a modern
    # project. Never fabricate a legacy item when the user saved zero items.
    legacy_flat = "pm_items" not in data
    if legacy_flat:
        items = [_legacy_item(gui, data)]
    for item in items:
        item["resin"] = _normalize_resin(item.get("resin", ""))
        synthesis_execution.ensure_execution(item)
        ml_dataset.ensure_review(item)
        data_system.ensure_hierarchy(item)
        data_system.sync_active_run(item)
    index = int(data.get("selected_pm_index", data.get("active_index", 0)) or 0)
    index = max(0, min(index, len(items) - 1))
    # Test conversion before touching widgets.
    int(data.get("project_revision", 0) or 0)
    if "batch_rows" in data and (not isinstance(data["batch_rows"], list) or
                                  any(not isinstance(row, Mapping) for row in data["batch_rows"])):
        raise ValueError("Invalid batch_rows structure in saved project.")
    if any(not isinstance(row, Mapping) for row in data.get("project_change_history", [])):
        raise ValueError("Invalid project history row in saved project.")
    return defaults, custom, items, legacy_flat, index


def _restore_state(gui: Any, data: Mapping[str, Any]) -> bool:
    defaults, custom, items, legacy_flat, index = _prepare_state(gui, data)
    # Snapshot mutable model and Tk variables so a widget failure can roll back.
    old_model = {
        name: deepcopy(getattr(gui, name)) for name in (
            "pm_items", "custom_materials", "_project_id", "_project_revision",
            "_project_change_history",
        ) if hasattr(gui, name)
    }
    old_values = {}
    for name in defaults:
        var = getattr(gui, name, None)
        if var is not None and hasattr(var, "get") and hasattr(var, "set"):
            old_values[name] = var.get()
    old_index = get_active_index(gui, 0)
    old_batch_rows = _tree_rows(getattr(gui, "batch_tree", None))
    required = (
        "pm_selected_plan_tree", "pm_selected_material_tree",
        "pm_selected_total_tree", "progress_tree", "pm_cleavage_tree",
    )
    gui._restoring_state = True
    try:
        for name, value in defaults.items():
            variable = getattr(gui, name, None)
            if variable is not None and hasattr(variable, "set"):
                variable.set(value)
        gui.custom_materials = custom
        gui.pm_items = items
        gui._project_id = str(data.get("project_id", "")) or uuid4().hex
        gui._project_revision = int(data.get("project_revision", 0) or 0)
        gui._project_change_history = [dict(row) for row in data.get("project_change_history", [])]
        project_manager_workflow._rebuild_listbox(gui, [index], index)
        if all(hasattr(gui, name) for name in required):
            project_manager_workflow._restore(
                gui, plan_workflow, get_calculation_namespace(gui, {}), index,
            )
        else:
            set_active_index(gui, index)
        if legacy_flat and hasattr(gui, "generate_update_plan"):
            gui.generate_update_plan()
        batch_workflow.restore_input_rows(gui, data.get("batch_rows", []))
        return True
    except Exception:
        for name, value in old_model.items():
            setattr(gui, name, value)
        for name, value in old_values.items():
            try:
                getattr(gui, name).set(value)
            except Exception:
                pass
        try:
            project_manager_workflow._rebuild_listbox(gui, [old_index], old_index)
            if all(hasattr(gui, name) for name in required):
                project_manager_workflow._restore(
                    gui, plan_workflow, get_calculation_namespace(gui, {}), old_index,
                )
            else:
                set_active_index(gui, old_index)
        except Exception:
            # A failing widget may prevent full visual rollback; model is restored.
            pass
        try:
            if getattr(gui, "batch_tree", None) is not None:
                batch_workflow.restore_input_rows(gui, old_batch_rows)
        except Exception:
            pass
        raise
    finally:
        gui._restoring_state = False



def _read_valid_project_with_recovery(gui: Any, source: Path) -> tuple[dict[str, Any], Path, bool]:
    """Reject schema-damaged primary JSON and try an independently valid backup.

    Preparation here is side-effect free for the live UI; full GUI commit still
    happens only after a candidate has passed the project-model validation.
    """
    try:
        data = state_persistence.read_json_object(source)
        _prepare_state(gui, data)
        return data, source, False
    except (ValueError, TypeError, KeyError, OSError, UnicodeError) as primary_error:
        backup = source.with_suffix(source.suffix + ".bak")
        if not backup.exists():
            raise primary_error
        recovered = state_persistence.read_json_object(backup)
        _prepare_state(gui, recovered)
        return recovered, backup, True


def load_project(gui: Any, path: str | Path | None = None) -> Path | None:
    if path is None:
        selected = filedialog.askopenfilename(
            filetypes=[
                (
                    "SPPS Planner session / project JSON",
                    "*.json project_manager_state.json",
                ),
                ("All files", "*.*"),
            ],
        )
        if not selected:
            return None
        path = selected
    source = Path(path)
    try:
        data, loaded_source, recovered = _read_valid_project_with_recovery(gui, source)
        _restore_state(gui, data)
        gui._loaded_project_path = source
        gui._loaded_project_fingerprint = (
            state_persistence.file_sha256(source) if source.exists() else ""
        )
        data_workflow.add_recent(gui, source, recovered=recovered)
        try:
            recovery = f" (recovered from {loaded_source.name})" if recovered else ""
            gui._log(f"Loaded project/session: {source}{recovery}\n")
        except Exception:
            pass
        return source
    except Exception as exc:
        try:
            messagebox.showerror("Load error", str(exc))
        except Exception:
            pass
        return None


def load_autosave_state(gui: Any) -> Path | None:
    path = session_path(gui)
    if not path.exists():
        return None
    try:
        data, loaded_source, recovered = _read_valid_project_with_recovery(gui, path)
        _restore_state(gui, data)
        if recovered:
            try:
                gui._log(f"Autosave recovered from: {loaded_source}\n")
            except Exception:
                pass
        return path
    except Exception as exc:
        try:
            gui._log(f"Autosave restore warning: {exc}\n")
        except Exception:
            pass
        return None


__all__ = [
    "collect_state",
    "load_autosave_state",
    "load_project",
    "save_autosave_state",
    "save_project",
    "save_project_as",
    "schedule_autosave",
    "session_path",
]
