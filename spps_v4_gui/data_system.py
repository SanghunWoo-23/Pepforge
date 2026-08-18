"""Project → Work Item → Run hierarchy and HPLC record domain model."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from uuid import uuid4

from spps_v4_gui import ml_dataset, risk_assessment, synthesis_execution


SCHEMA_VERSION = 1
RUN_SNAPSHOT_KEYS = (
    "selected_plan_rows", "selected_material_rows", "selected_total_rows",
    "selected_checklist_rows", "selected_cleavage_rows",
)
HPLC_NUMERIC_FIELDS = {
    "flow_rate_mL_min", "wavelength_nm", "injection_volume_uL",
    "runtime_min", "retention_time_min", "area_percent", "purity_percent",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _id() -> str:
    return uuid4().hex


def _file_metadata(path_value: Any) -> dict[str, Any]:
    text = str(path_value or "").strip()
    if not text:
        return {"path": "", "exists": False, "size_bytes": None, "modified_at": "", "sha256": ""}
    path = Path(text).expanduser()
    if not path.is_file():
        return {"path": str(path), "exists": False, "size_bytes": None, "modified_at": "", "sha256": ""}
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    stat = path.stat()
    return {
        "path": str(path.resolve()), "exists": True, "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(timespec="seconds"),
        "sha256": digest.hexdigest(),
    }


def _change(run: dict[str, Any], action: str, entity: str, before: Any, after: Any, reason: str,
            *, clock: Callable[[], str] = _now, id_factory: Callable[[], str] = _id) -> dict[str, Any]:
    event = {
        "change_id": id_factory(), "timestamp": clock(), "run_id": run["run_id"],
        "action": action, "entity": entity, "before": deepcopy(before),
        "after": deepcopy(after), "reason": str(reason or ""),
    }
    run.setdefault("change_history", []).append(event)
    run["updated_at"] = event["timestamp"]
    return deepcopy(event)


def _run_snapshot(item: Mapping[str, Any]) -> dict[str, Any]:
    return {key: deepcopy(item.get(key, []) or []) for key in RUN_SNAPSHOT_KEYS}


def _new_run_record(item: Mapping[str, Any], number: int, name: str | None = None,
                    *, clock: Callable[[], str] = _now, id_factory: Callable[[], str] = _id,
                    carry_current: bool = True) -> dict[str, Any]:
    timestamp = clock()
    return {
        "run_id": id_factory(), "name": str(name or f"Run {number:03d}"),
        "status": "Active", "created_at": timestamp, "updated_at": timestamp,
        "lot": item.get("lot", item.get("lot_no", "")),
        "snapshots": _run_snapshot(item),
        "synthesis_execution": deepcopy(item.get("synthesis_execution", {"schema_version": 1, "events": []})) if carry_current else {"schema_version": 1, "events": []},
        "ml_review": deepcopy(item.get("ml_review", {"schema_version": 1, "revision": 0, "current": {}, "versions": []})) if carry_current else {"schema_version": 1, "revision": 0, "current": {}, "versions": []},
        "risk_review": deepcopy(item.get("risk_review", {"schema_version": 1, "revision": 0, "current": {}, "versions": [], "acknowledgements": []})) if carry_current else {"schema_version": 1, "revision": 0, "current": {}, "versions": [], "acknowledgements": []},
        "hplc_records": [], "change_history": [],
    }


def ensure_hierarchy(item: dict[str, Any]) -> dict[str, Any]:
    synthesis_execution.ensure_work_item_id(item)
    synthesis_execution.ensure_execution(item)
    ml_dataset.ensure_review(item)
    risk_assessment.ensure_review(item)
    runs = [dict(run) for run in item.get("runs", []) if isinstance(run, Mapping)]
    if not runs:
        runs = [_new_run_record(item, 1)]
    for index, run in enumerate(runs, 1):
        run.setdefault("run_id", _id())
        run.setdefault("name", f"Run {index:03d}")
        run.setdefault("status", "Active" if index == len(runs) else "Closed")
        run.setdefault("created_at", _now())
        run.setdefault("updated_at", run["created_at"])
        run.setdefault("lot", item.get("lot", ""))
        run.setdefault("snapshots", _run_snapshot(item))
        run.setdefault("synthesis_execution", {"schema_version": 1, "events": []})
        run.setdefault("ml_review", {"schema_version": 1, "revision": 0, "current": {}, "versions": []})
        risk_assessment.ensure_review(run)
        run["hplc_records"] = [dict(record) for record in run.get("hplc_records", []) if isinstance(record, Mapping)]
        run["change_history"] = [dict(event) for event in run.get("change_history", []) if isinstance(event, Mapping)]
    active_id = str(item.get("active_run_id", ""))
    if not any(run["run_id"] == active_id for run in runs):
        active_id = runs[-1]["run_id"]
    item["runs"] = runs
    item["active_run_id"] = active_id
    return active_run(item)


def active_run(item: dict[str, Any]) -> dict[str, Any]:
    runs = item.get("runs", [])
    active_id = str(item.get("active_run_id", ""))
    for run in runs:
        if str(run.get("run_id", "")) == active_id:
            return run
    if not runs:
        return ensure_hierarchy(item)
    item["active_run_id"] = runs[-1]["run_id"]
    return runs[-1]


def sync_active_run(item: dict[str, Any]) -> dict[str, Any]:
    run = ensure_hierarchy(item)
    run["snapshots"] = _run_snapshot(item)
    run["synthesis_execution"] = deepcopy(item.get("synthesis_execution", {}))
    run["ml_review"] = deepcopy(item.get("ml_review", {}))
    run["risk_review"] = deepcopy(item.get("risk_review", {}))
    run["lot"] = item.get("lot", item.get("lot_no", ""))
    return run


def new_run(item: dict[str, Any], name: str = "", *, reason: str = "New synthesis run",
            clock: Callable[[], str] = _now, id_factory: Callable[[], str] = _id) -> dict[str, Any]:
    old = sync_active_run(item)
    old["status"] = "Closed"
    run = _new_run_record(item, len(item["runs"]) + 1, name or None, clock=clock, id_factory=id_factory, carry_current=False)
    item["runs"].append(run)
    item["active_run_id"] = run["run_id"]
    item["synthesis_execution"] = deepcopy(run["synthesis_execution"])
    item["ml_review"] = deepcopy(run["ml_review"])
    item["risk_review"] = deepcopy(run["risk_review"])
    _change(run, "create", "run", None, {"name": run["name"]}, reason, clock=clock, id_factory=id_factory)
    return run


def activate_run(item: dict[str, Any], run_id: str, *, reason: str = "Activate run",
                 sync_current: bool = True) -> dict[str, Any]:
    current = sync_active_run(item) if sync_current else ensure_hierarchy(item)
    target = next((run for run in item["runs"] if str(run.get("run_id")) == str(run_id)), None)
    if target is None:
        raise ValueError("Run was not found.")
    current["status"] = "Closed" if current is not target else current.get("status", "Active")
    target["status"] = "Active"
    item["active_run_id"] = target["run_id"]
    for key, rows in dict(target.get("snapshots", {})).items():
        if key in RUN_SNAPSHOT_KEYS:
            item[key] = deepcopy(rows or [])
    item["synthesis_execution"] = deepcopy(target.get("synthesis_execution", {}))
    item["ml_review"] = deepcopy(target.get("ml_review", {}))
    item["risk_review"] = deepcopy(target.get("risk_review", {}))
    _change(target, "activate", "run", None, {"run_id": target["run_id"]}, reason)
    return target


def list_runs(item: dict[str, Any]) -> list[dict[str, Any]]:
    ensure_hierarchy(item)
    return [
        {key: deepcopy(run.get(key)) for key in ("run_id", "name", "status", "created_at", "updated_at", "lot")}
        | {"hplc_count": sum(not record.get("deleted") for record in run.get("hplc_records", [])),
           "event_count": len((run.get("synthesis_execution") or {}).get("events", []))}
        for run in item["runs"]
    ]


def _clean_hplc(values: Mapping[str, Any]) -> dict[str, Any]:
    record = {str(key): value for key, value in values.items()}
    for field in HPLC_NUMERIC_FIELDS:
        value = record.get(field)
        if value is None or str(value).strip() == "":
            record[field] = None
        else:
            try:
                record[field] = float(str(value).replace(",", "").strip())
            except ValueError as exc:
                raise ValueError(f"{field} must be numeric.") from exc
    for field in ("purity_percent", "area_percent"):
        if record.get(field) is not None and not 0 <= record[field] <= 100:
            raise ValueError(f"{field} must be between 0 and 100.")
    if not str(record.get("sample_name", "")).strip():
        raise ValueError("HPLC sample name is required.")
    return record


def upsert_hplc(item: dict[str, Any], values: Mapping[str, Any], *, reason: str,
                clock: Callable[[], str] = _now, id_factory: Callable[[], str] = _id) -> dict[str, Any]:
    if not str(reason).strip():
        raise ValueError("A reason is required for HPLC changes.")
    run = sync_active_run(item)
    clean = _clean_hplc(values)
    record_id = str(clean.get("hplc_record_id", "")).strip()
    existing = next((row for row in run["hplc_records"] if row.get("hplc_record_id") == record_id), None)
    before = deepcopy(existing) if existing else None
    timestamp = clock()
    clean.update({
        "hplc_record_id": record_id or id_factory(), "run_id": run["run_id"],
        "updated_at": timestamp, "created_at": (existing or {}).get("created_at", timestamp),
        "deleted": False,
        "data_file": _file_metadata(clean.get("data_file_path", "")),
        "method_file": _file_metadata(clean.get("method_file_path", "")),
    })
    if existing:
        existing.clear(); existing.update(clean)
        result = existing
        action = "update"
    else:
        run["hplc_records"].append(clean)
        result = clean
        action = "create"
    _change(run, action, "hplc", before, result, reason, clock=clock, id_factory=id_factory)
    return deepcopy(result)


def delete_hplc(item: dict[str, Any], record_id: str, *, reason: str) -> dict[str, Any]:
    if not str(reason).strip():
        raise ValueError("A reason is required to remove an HPLC record.")
    run = sync_active_run(item)
    record = next((row for row in run["hplc_records"] if row.get("hplc_record_id") == record_id), None)
    if record is None:
        raise ValueError("HPLC record was not found.")
    before = deepcopy(record)
    record["deleted"] = True
    record["updated_at"] = _now()
    _change(run, "delete", "hplc", before, record, reason)
    return deepcopy(record)


def search_hplc(items: Iterable[Any], query: str = "", *, sort_by: str = "acquired_at",
                descending: bool = True, include_deleted: bool = False) -> list[dict[str, Any]]:
    needle = str(query or "").strip().lower()
    rows = []
    for item in items:
        if not isinstance(item, dict):
            continue
        ensure_hierarchy(item)
        for run in item["runs"]:
            for record in run.get("hplc_records", []):
                if record.get("deleted") and not include_deleted:
                    continue
                row = {
                    "project": item.get("project", ""), "peptide": item.get("peptide", ""),
                    "work_item_id": item.get("work_item_id", ""), "run_name": run.get("name", ""),
                    **deepcopy(record),
                }
                if needle and needle not in " ".join(str(value).lower() for value in row.values()):
                    continue
                rows.append(row)
    rows.sort(key=lambda row: (row.get(sort_by) is not None, str(row.get(sort_by, ""))), reverse=descending)
    return rows


def change_history(item: dict[str, Any]) -> list[dict[str, Any]]:
    ensure_hierarchy(item)
    rows = []
    for run in item["runs"]:
        rows.extend(deepcopy(run.get("change_history", [])))
    return sorted(rows, key=lambda row: str(row.get("timestamp", "")))


__all__ = [
    "HPLC_NUMERIC_FIELDS", "RUN_SNAPSHOT_KEYS", "SCHEMA_VERSION",
    "activate_run", "active_run", "change_history", "delete_hplc",
    "ensure_hierarchy", "list_runs", "new_run", "search_hplc",
    "sync_active_run", "upsert_hplc",
]
