"""Direct live synthesis execution workflow for the V3 controller."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from spps_v4_gui import synthesis_execution
from spps_v4_gui.modules import plan_workflow


PLAN_EDITABLE_FIELDS = tuple(
    column
    for column in plan_workflow.PLAN_COLUMNS
    if column not in {
        "No", "Unit mmol", "Unit amount", "R1 mmol", "R1 amount",
        "R2 mmol", "R2 amount", "Base mmol", "Base amount",
    }
)
STEP_STATUSES = ("Planned", "In Progress", "Completed", "Hold", "Failed")
MATERIAL_STATUSES = ("Planned", "Prepared", "Charged", "Used", "Adjusted", "Rejected")


def active_item(gui: Any) -> dict[str, Any]:
    items = getattr(gui, "pm_items", []) or []
    try:
        index = int(getattr(gui, "_v229_active_index", -1))
    except Exception as exc:
        raise ValueError("No active Work Item.") from exc
    if not (0 <= index < len(items)):
        raise ValueError("No active Work Item.")
    item = items[index]
    synthesis_execution.ensure_execution(item)
    return item


def _plan_row(gui: Any, step_no: Any) -> tuple[Any, dict[str, Any]]:
    tree = getattr(gui, "pm_selected_plan_tree", None)
    if tree is None:
        raise ValueError("Selected Plan is not available.")
    requested = str(step_no).strip()
    columns = list(tree["columns"])
    for iid in tree.get_children():
        row = dict(zip(columns, tree.item(iid, "values")))
        if str(row.get("No", "")).strip() == requested:
            return iid, row
    raise ValueError(f"Plan step {requested!r} was not found.")


def _persist(gui: Any) -> None:
    plan_workflow._save_active(gui, include_outputs=True)
    try:
        gui.schedule_autosave()
    except Exception:
        try:
            gui.save_autosave_state()
        except Exception:
            pass


def _refresh_open_window(gui: Any) -> None:
    current = getattr(gui, "_v3_work_item_window", None)
    if current is not None:
        try:
            current.refresh()
        except Exception:
            pass


def record_plan_correction(
    gui: Any,
    *,
    step_no: Any,
    field: str,
    value: Any,
    reason: str,
    operator_note: str = "",
) -> dict[str, Any]:
    field = str(field).strip()
    if field not in PLAN_EDITABLE_FIELDS:
        raise ValueError(f"{field!r} is not an editable Plan field.")
    if not str(reason).strip():
        raise ValueError("Enter a reason for the correction.")
    iid, row = _plan_row(gui, step_no)
    before = row.get(field, "")
    requested = str(value)
    if str(before) == requested:
        raise ValueError("The new value is the same as the current value.")
    tree = gui.pm_selected_plan_tree
    tree.set(iid, field, requested)
    applied = gui.apply_change()
    if applied is not True:
        tree.set(iid, field, before)
        try:
            gui.apply_change()
        except Exception:
            pass
        raise ValueError("Apply Change rejected the correction.")
    _, recalculated = _plan_row(gui, step_no)
    after = recalculated.get(field, requested)
    event_type = "doubling" if field == "Repeat" else "plan_correction"
    event = synthesis_execution.append_event(
        active_item(gui),
        event_type=event_type,
        step_no=step_no,
        unit=str(recalculated.get("Unit name", row.get("Unit name", ""))),
        field=field,
        before=before,
        after=after,
        reason=reason,
        operator_note=operator_note,
        metadata={"requested_value": requested},
    )
    _persist(gui)
    _refresh_open_window(gui)
    return event


def apply_doubling(
    gui: Any,
    *,
    step_no: Any,
    reason: str,
    operator_note: str = "",
) -> dict[str, Any]:
    return record_plan_correction(
        gui,
        step_no=step_no,
        field="Repeat",
        value="2",
        reason=reason,
        operator_note=operator_note,
    )


def record_step_status(
    gui: Any,
    *,
    step_no: Any,
    status: str,
    reason: str = "",
    operator_note: str = "",
) -> dict[str, Any]:
    if status not in STEP_STATUSES:
        raise ValueError(f"Unsupported step status: {status}")
    _, row = _plan_row(gui, step_no)
    item = active_item(gui)
    key = (str(step_no), "step_status")
    before = synthesis_execution.current_values(item).get(key, "Planned")
    event = synthesis_execution.append_event(
        item,
        event_type="step_status",
        step_no=step_no,
        unit=str(row.get("Unit name", "")),
        field="step_status",
        before=before,
        after=status,
        reason=reason or f"Step status → {status}",
        operator_note=operator_note,
    )
    _persist(gui)
    _refresh_open_window(gui)
    return event


def record_actual_material(
    gui: Any,
    *,
    step_no: Any,
    material: str,
    amount: Any,
    amount_unit: str,
    status: str,
    reason: str = "",
    operator_note: str = "",
) -> dict[str, Any]:
    material = str(material).strip()
    amount_text = str(amount).strip()
    amount_unit = str(amount_unit).strip()
    if not material:
        raise ValueError("Material is required.")
    if not amount_text:
        raise ValueError("Actual amount is required.")
    try:
        numeric_amount = float(amount_text)
    except ValueError as exc:
        raise ValueError("Actual amount must be numeric.") from exc
    if numeric_amount < 0:
        raise ValueError("Actual amount cannot be negative.")
    if status not in MATERIAL_STATUSES:
        raise ValueError(f"Unsupported material status: {status}")
    _, row = _plan_row(gui, step_no)
    item = active_item(gui)
    field = f"actual_material::{material}"
    before = synthesis_execution.current_values(item).get((str(step_no), field))
    after = {
        "material": material,
        "amount": numeric_amount,
        "unit": amount_unit,
        "status": status,
    }
    event = synthesis_execution.append_event(
        item,
        event_type="actual_material",
        step_no=step_no,
        unit=str(row.get("Unit name", "")),
        field=field,
        before=before,
        after=after,
        reason=reason or f"Actual material → {status}",
        operator_note=operator_note,
    )
    _persist(gui)
    _refresh_open_window(gui)
    return event


def revert_last(
    gui: Any,
    *,
    reason: str,
    operator_note: str = "",
) -> dict[str, Any]:
    if not str(reason).strip():
        raise ValueError("Enter a reason for the revert.")
    item = active_item(gui)
    target = synthesis_execution.latest_reversible_event(item)
    if target is None:
        raise ValueError("There is no execution event to revert.")
    if target.get("event_type") in {"plan_correction", "doubling"}:
        iid, _row = _plan_row(gui, target.get("step_no", ""))
        tree = gui.pm_selected_plan_tree
        current = tree.set(iid, str(target.get("field", "")))
        tree.set(iid, str(target.get("field", "")), target.get("before", ""))
        if gui.apply_change() is not True:
            tree.set(iid, str(target.get("field", "")), current)
            try:
                gui.apply_change()
            except Exception:
                pass
            raise ValueError("Apply Change rejected the revert.")
    event = synthesis_execution.append_revert(
        item,
        target,
        reason=reason,
        operator_note=operator_note,
    )
    _persist(gui)
    _refresh_open_window(gui)
    return event


def history(gui: Any) -> list[dict[str, Any]]:
    return synthesis_execution.events(active_item(gui))


def ml_ready_history(gui: Any) -> list[dict[str, Any]]:
    return synthesis_execution.ml_records(active_item(gui))


__all__ = [
    "MATERIAL_STATUSES",
    "PLAN_EDITABLE_FIELDS",
    "STEP_STATUSES",
    "active_item",
    "apply_doubling",
    "history",
    "ml_ready_history",
    "record_actual_material",
    "record_plan_correction",
    "record_step_status",
    "revert_last",
]
