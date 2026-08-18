"""Append-only synthesis execution records for SPPS Planner V4.0.0.

The module is intentionally UI-independent.  An execution history lives inside
one peptide item and can therefore travel with project JSON, autosave JSON and
future ML exports without a second sidecar database.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Mapping
from uuid import uuid4


SCHEMA_VERSION = 1
EXECUTION_KEY = "synthesis_execution"
REVERSIBLE_EVENT_TYPES = {
    "plan_correction",
    "doubling",
    "step_status",
    "actual_material",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id() -> str:
    return uuid4().hex


def ensure_work_item_id(
    item: dict[str, Any],
    *,
    id_factory: Callable[[], str] = _new_id,
) -> str:
    value = str(item.get("work_item_id", "")).strip()
    if not value:
        value = id_factory()
        item["work_item_id"] = value
    return value


def normalize_execution(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, Mapping) else {}
    events = [
        dict(event)
        for event in source.get("events", [])
        if isinstance(event, Mapping)
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "events": events,
    }


def ensure_execution(item: dict[str, Any]) -> dict[str, Any]:
    ensure_work_item_id(item)
    execution = normalize_execution(item.get(EXECUTION_KEY))
    item[EXECUTION_KEY] = execution
    return execution


def append_event(
    item: dict[str, Any],
    *,
    event_type: str,
    step_no: Any,
    unit: str,
    field: str,
    before: Any,
    after: Any,
    reason: str,
    operator_note: str = "",
    target_event_id: str = "",
    metadata: Mapping[str, Any] | None = None,
    clock: Callable[[], str] = _utc_now,
    id_factory: Callable[[], str] = _new_id,
) -> dict[str, Any]:
    """Append one immutable event dictionary and return a detached copy."""
    event_type = str(event_type).strip()
    field = str(field).strip()
    reason = str(reason).strip()
    if not event_type:
        raise ValueError("event_type is required.")
    if not field:
        raise ValueError("field is required.")
    if event_type in {"plan_correction", "doubling", "revert"} and not reason:
        raise ValueError("A reason is required for plan changes.")
    event = {
        "event_id": id_factory(),
        "timestamp": clock(),
        "work_item_id": ensure_work_item_id(item),
        "event_type": event_type,
        "step_no": str(step_no),
        "unit": str(unit or ""),
        "field": field,
        "before": deepcopy(before),
        "after": deepcopy(after),
        "reason": reason,
        "operator_note": str(operator_note or ""),
        "target_event_id": str(target_event_id or ""),
        "metadata": dict(metadata or {}),
    }
    ensure_execution(item)["events"].append(event)
    return deepcopy(event)


def events(item: Mapping[str, Any]) -> list[dict[str, Any]]:
    execution = normalize_execution(item.get(EXECUTION_KEY))
    return [deepcopy(event) for event in execution["events"]]


def compensated_event_ids(history: Iterable[Mapping[str, Any]]) -> set[str]:
    return {
        str(event.get("target_event_id", ""))
        for event in history
        if event.get("event_type") == "revert"
        and str(event.get("target_event_id", "")).strip()
    }


def latest_reversible_event(item: Mapping[str, Any]) -> dict[str, Any] | None:
    history = events(item)
    compensated = compensated_event_ids(history)
    for event in reversed(history):
        if (
            event.get("event_type") in REVERSIBLE_EVENT_TYPES
            and event.get("event_id") not in compensated
        ):
            return event
    return None


def append_revert(
    item: dict[str, Any],
    target: Mapping[str, Any],
    *,
    reason: str,
    operator_note: str = "",
    clock: Callable[[], str] = _utc_now,
    id_factory: Callable[[], str] = _new_id,
) -> dict[str, Any]:
    target_id = str(target.get("event_id", "")).strip()
    if not target_id:
        raise ValueError("The target event has no event_id.")
    if target_id in compensated_event_ids(events(item)):
        raise ValueError("The target event was already reverted.")
    return append_event(
        item,
        event_type="revert",
        step_no=target.get("step_no", ""),
        unit=str(target.get("unit", "")),
        field=str(target.get("field", "")),
        before=target.get("after"),
        after=target.get("before"),
        reason=reason,
        operator_note=operator_note,
        target_event_id=target_id,
        metadata={
            "reverted_event_type": target.get("event_type", ""),
            **dict(target.get("metadata", {}) or {}),
        },
        clock=clock,
        id_factory=id_factory,
    )


def current_values(item: Mapping[str, Any]) -> dict[tuple[str, str], Any]:
    """Replay the ledger into the current per-step execution values."""
    values: dict[tuple[str, str], Any] = {}
    for event in events(item):
        values[(str(event.get("step_no", "")), str(event.get("field", "")))] = (
            deepcopy(event.get("after"))
        )
    return values


def ml_records(item: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return flat, lossless event rows suitable for Stage 3 feature building."""
    records = []
    for event in events(item):
        row = {key: deepcopy(value) for key, value in event.items() if key != "metadata"}
        for key, value in dict(event.get("metadata", {}) or {}).items():
            row[f"meta_{key}"] = deepcopy(value)
        records.append(row)
    return records


__all__ = [
    "EXECUTION_KEY",
    "REVERSIBLE_EVENT_TYPES",
    "SCHEMA_VERSION",
    "append_event",
    "append_revert",
    "compensated_event_ids",
    "current_values",
    "ensure_execution",
    "ensure_work_item_id",
    "events",
    "latest_reversible_event",
    "ml_records",
    "normalize_execution",
]
