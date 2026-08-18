"""Controller-facing V4 experimental-data workflow."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from spps_v4_gui import experimental_data, ml_advisor_v4, condition_optimizer_v4


def db_path(gui: Any = None) -> Path:
    override = getattr(gui, "experimental_db_path", None) if gui is not None else None
    return Path(override) if override else experimental_data.default_db_path()


def initialize(gui: Any = None) -> Path:
    """Initialize an empty user-local experimental database.

    The public/GitHub build intentionally bundles no experimental observations.
    Users add authorized records through Record Lab Data or Import Lab Data.
    """
    return experimental_data.initialize(db_path(gui))


def import_file(gui: Any, path: str | Path) -> list[dict[str, Any]]:
    result = experimental_data.import_path(path, db_path(gui))
    try:
        gui._log(f"Experimental data import: {path} -> {result}\n")
    except Exception as exc:
        _ignored_log_error = exc
    return result


def loading_records(gui: Any, statuses=None):
    return experimental_data.list_records("loading", db_path(gui), statuses=statuses)


def cleavage_records(gui: Any, statuses=None):
    return experimental_data.list_records("cleavage", db_path(gui), statuses=statuses)


def set_status(gui: Any, kind: str, ids, status: str) -> int:
    return experimental_data.set_status(kind, ids, status, db_path(gui))

def update_record(gui: Any, kind: str, record_id: str, changes: dict[str, Any]):
    return experimental_data.update_record(kind, record_id, changes, db_path(gui))



def add_loading_record(gui: Any, values: dict[str, Any], *, status: str = "verified"):
    return experimental_data.add_record("loading", values, db_path(gui), status=status)


def add_cleavage_record(gui: Any, values: dict[str, Any], *, status: str = "verified"):
    return experimental_data.add_record("cleavage", values, db_path(gui), status=status)


def record_coupling_review(gui: Any, *, actual_yield_percent: Any = None, actual_purity_percent: Any = None, failure_flag: Any = None, doubling_required: Any = None, operator_note: str = ""):
    """Record a simple operator coupling outcome on the active Work Item."""
    from spps_v4_gui import ml_dataset
    from spps_v4_gui.modules import gui_common
    gui_common.save_active(gui)
    items = list(getattr(gui, "pm_items", []) or [])
    idx = gui_common.active_index(gui)
    if idx is None or not (0 <= int(idx) < len(items)):
        raise ValueError("Select a peptide item before recording a coupling result.")
    item = items[int(idx)]
    version = ml_dataset.review_item(
        item, actual_yield_percent=actual_yield_percent, actual_purity_percent=actual_purity_percent,
        failure_flag=failure_flag, doubling_required=doubling_required, included=True,
        review_reason="Operator lab result entry", operator_note=operator_note,
    )
    gui_common.save_active(gui)
    return version

def advise_loading(gui: Any, **query: Any):
    return ml_advisor_v4.loading_advice(db_path=db_path(gui), **query)


def advise_cleavage(gui: Any, **query: Any):
    return ml_advisor_v4.cleavage_advice(db_path=db_path(gui), **query)


def recommend_loading(gui: Any, **query: Any):
    return ml_advisor_v4.loading_recommendation(db_path=db_path(gui), **query)


def recommend_cleavage(gui: Any, **query: Any):
    return ml_advisor_v4.cleavage_recommendation(db_path=db_path(gui), **query)


def advise_coupling(gui: Any):
    try:
        from spps_v4_gui.modules import gui_common
        gui_common.save_active(gui)
    except Exception as exc:
        try:
            gui._log(f"Coupling advisor save-active warning: {exc}\n")
        except Exception as log_exc:
            _coupling_save_log_error = log_exc
    items = list(getattr(gui, "pm_items", []) or [])
    active = None
    try:
        from spps_v4_gui.modules import gui_common
        idx = gui_common.active_index(gui)
        if idx is not None and 0 <= int(idx) < len(items):
            active = items[int(idx)]
    except Exception as exc:
        active = None
        try:
            gui._log(f"Coupling advisor active-item warning: {exc}\n")
        except Exception as log_exc:
            _coupling_active_log_error = log_exc
    if active is None:
        active = {
            "sequence": getattr(getattr(gui, "pm_sequence", None), "get", lambda: "")(),
            "resin": getattr(getattr(gui, "pm_resin", None), "get", lambda: "")(),
        }
    return condition_optimizer_v4.coupling_advice(items, active)


def open_window(gui: Any) -> Any:
    from spps_v4_gui.modules.experimental_data_panel import ExperimentalDataWindow
    existing = getattr(gui, "_experimental_data_window", None)
    if existing is not None:
        try:
            if existing.winfo_exists():
                existing.deiconify(); existing.lift(); return existing
        except Exception as exc:
            _ignored_window_probe_error = exc
    window = ExperimentalDataWindow(gui)
    gui._experimental_data_window = window
    return window


def open_advisor(gui: Any, kind: str) -> Any:
    window = open_window(gui)
    try:
        window.focus_advisor(kind)
    except Exception as exc:
        try:
            gui._log(f"Experimental advisor focus warning: {exc}\n")
        except Exception as log_exc:
            _ignored_focus_log_error = log_exc
    return window


def open_condition_optimizer(gui: Any) -> Any:
    window = open_window(gui)
    try:
        window.focus_optimizer()
    except Exception as exc:
        try:
            gui._log(f"Condition optimizer focus warning: {exc}\n")
        except Exception as log_exc:
            _condition_optimizer_log_error = log_exc
    return window

__all__ = ["initialize", "import_file", "loading_records", "cleavage_records", "set_status", "update_record", "add_loading_record", "add_cleavage_record", "record_coupling_review", "advise_loading", "advise_cleavage", "recommend_loading", "recommend_cleavage", "advise_coupling", "open_window", "open_advisor", "open_condition_optimizer", "db_path"]
