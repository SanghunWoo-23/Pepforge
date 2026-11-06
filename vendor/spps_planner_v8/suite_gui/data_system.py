"""Project → Work Item → Run hierarchy and HPLC record domain model."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from uuid import uuid4

from suite_gui import ml_dataset, risk_assessment, synthesis_execution


SCHEMA_VERSION = 3
RUN_SNAPSHOT_KEYS = (
    "selected_plan_rows", "selected_material_rows", "selected_total_rows",
    "selected_checklist_rows", "selected_cleavage_rows",
)
ANALYTICAL_NUMERIC_FIELDS={"expected_neutral_mass","expected_mh","expected_mna","observed_mz","charge","observed_assigned_mass","delta_da","delta_ppm"}
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
        "started_at": "", "completed_at": "", "planner_snapshot_v6": {}, "start_snapshots_v6": {},
        "lot": item.get("lot", item.get("lot_no", "")),
        "snapshots": _run_snapshot(item),
        "synthesis_execution": deepcopy(item.get("synthesis_execution", {"schema_version": 1, "events": []})) if carry_current else {"schema_version": 1, "events": []},
        "ml_review": deepcopy(item.get("ml_review", {"schema_version": 1, "revision": 0, "current": {}, "versions": []})) if carry_current else {"schema_version": 1, "revision": 0, "current": {}, "versions": []},
        "risk_review": deepcopy(item.get("risk_review", {"schema_version": 1, "revision": 0, "current": {}, "versions": [], "acknowledgements": []})) if carry_current else {"schema_version": 1, "revision": 0, "current": {}, "versions": [], "acknowledgements": []},
        "hplc_records": [], "analytical_records": [], "change_history": [],
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
        run.setdefault("started_at", "")
        run.setdefault("completed_at", "")
        run.setdefault("planner_snapshot_v6", {})
        run.setdefault("start_snapshots_v6", {})
        run.setdefault("lot", item.get("lot", ""))
        run.setdefault("snapshots", _run_snapshot(item))
        run.setdefault("synthesis_execution", {"schema_version": 1, "events": []})
        run.setdefault("ml_review", {"schema_version": 1, "revision": 0, "current": {}, "versions": []})
        risk_assessment.ensure_review(run)
        run["hplc_records"] = [dict(record) for record in run.get("hplc_records", []) if isinstance(record, Mapping)]
        run["analytical_records"] = [dict(record) for record in run.get("analytical_records", []) if isinstance(record, Mapping)]
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


def start_active_run(item: dict[str, Any], planner_snapshot: Mapping[str, Any], *,
                     clock: Callable[[], str] = _now, id_factory: Callable[[], str] = _id) -> dict[str, Any]:
    """Start or resume the existing active Run without replacing its frozen start snapshot.

    The first successful start captures ``planner_snapshot_v6`` exactly once. Repeated
    Start clicks are idempotent while the Run is already in progress; terminal Runs
    cannot be restarted and require ``new_run`` instead.
    """
    run = sync_active_run(item)
    status = str(run.get("status") or "").strip()
    terminal = {"completed", "failed", "excluded", "closed"}
    if str(run.get("completed_at") or "").strip() or status.lower() in terminal:
        raise ValueError("The active Run is already finished/closed. Create a new synthesis Run before starting another experiment.")

    started_at = str(run.get("started_at") or "").strip()
    if started_at:
        # A repeated Start must never mutate the frozen condition or timestamp.
        if status.lower() != "in progress":
            before = status
            run["status"] = "In Progress"
            _change(run, "resume", "run_lifecycle", before, "In Progress", "Resume experiment", clock=clock, id_factory=id_factory)
        return run

    timestamp = clock()
    before = {"status": status, "started_at": run.get("started_at", ""), "planner_snapshot_v6": deepcopy(run.get("planner_snapshot_v6") or {})}
    run["started_at"] = timestamp
    run["status"] = "In Progress"
    run["planner_snapshot_v6"] = deepcopy(dict(planner_snapshot or {}))
    run["start_snapshots_v6"] = _run_snapshot(item)
    _change(
        run, "start", "run_lifecycle", before,
        {"status": "In Progress", "started_at": timestamp, "planner_snapshot_v6": deepcopy(run["planner_snapshot_v6"])},
        "Start experiment and freeze Planner condition", clock=clock, id_factory=id_factory,
    )
    return run


def finish_active_run(item: dict[str, Any], *, status: str = "Completed",
                      clock: Callable[[], str] = _now, id_factory: Callable[[], str] = _id) -> dict[str, Any]:
    """Finish the active Run once; repeated same-status Finish clicks are idempotent."""
    run = sync_active_run(item)
    if not str(run.get("started_at") or "").strip():
        raise ValueError("Start the active Run before finishing the experiment.")

    target = str(status or "Completed").strip() or "Completed"
    completed_at = str(run.get("completed_at") or "").strip()
    current = str(run.get("status") or "").strip()
    if completed_at:
        if current.lower() == target.lower():
            return run
        raise ValueError(f"The active Run is already finished as {current or 'Completed'}; its terminal status cannot be overwritten.")

    timestamp = clock()
    before = {"status": current, "completed_at": run.get("completed_at", "")}
    run["status"] = target
    run["completed_at"] = timestamp
    _change(
        run, "finish", "run_lifecycle", before,
        {"status": target, "completed_at": timestamp},
        f"Finish experiment as {target}", clock=clock, id_factory=id_factory,
    )
    return run


def new_run(item: dict[str, Any], name: str = "", *, reason: str = "New synthesis run",
            clock: Callable[[], str] = _now, id_factory: Callable[[], str] = _id) -> dict[str, Any]:
    old = sync_active_run(item)
    # Do not silently abandon an experiment that has actually started. The operator
    # must finish/close the active experimental lifecycle first so the frozen start
    # snapshot and terminal state stay traceable. Unstarted planning Runs may still
    # be replaced freely, preserving the legacy project workflow.
    if str(old.get("started_at") or "").strip() and not str(old.get("completed_at") or "").strip():
        raise ValueError("Finish the active experiment before creating a new synthesis Run.")
    if not str(old.get("completed_at") or "").strip() and str(old.get("status") or "").strip().lower() not in {"completed", "failed", "excluded"}:
        old["status"] = "Closed"
    run = _new_run_record(item, len(item["runs"]) + 1, name or None, clock=clock, id_factory=id_factory, carry_current=False)
    item["runs"].append(run)
    item["active_run_id"] = run["run_id"]
    item["synthesis_execution"] = deepcopy(run["synthesis_execution"])
    item["ml_review"] = deepcopy(run["ml_review"])
    item["risk_review"] = deepcopy(run["risk_review"])
    _change(run, "create", "run", None, {"name": run["name"]}, reason, clock=clock, id_factory=id_factory)
    return run



def repeat_active_run(item: dict[str, Any], name: str = "", *, reason: str = "Repeat prior synthesis run",
                      clock: Callable[[], str] = _now, id_factory: Callable[[], str] = _id) -> dict[str, Any]:
    """Create a new unstarted Run from the active Run's frozen/planned condition.

    Experimental events/results/HPLC records are never copied.  Only planning
    snapshots and planner input fields are carried forward, with an explicit
    ``repeat_of_run_id`` link for traceability.
    """
    source = sync_active_run(item)
    if str(source.get("started_at") or "").strip() and not str(source.get("completed_at") or "").strip():
        raise ValueError("Finish the active experiment before repeating it as a new Run.")
    source_id = str(source.get("run_id") or "")
    source_name = str(source.get("name") or "")
    source_status = str(source.get("status") or "")
    frozen = deepcopy(source.get("planner_snapshot_v6") or {})
    snapshots = deepcopy(source.get("start_snapshots_v6") or source.get("snapshots") or {})
    if frozen.get("selected_plan_rows") is not None:
        snapshots["selected_plan_rows"] = deepcopy(frozen.get("selected_plan_rows") or [])
    if frozen.get("selected_cleavage_rows") is not None:
        snapshots["selected_cleavage_rows"] = deepcopy(frozen.get("selected_cleavage_rows") or [])

    run = new_run(item, name=name or f"{source_name or 'Run'} repeat", reason=reason, clock=clock, id_factory=id_factory)
    run["repeat_of_run_id"] = source_id
    run["repeat_of_run_name"] = source_name
    run["repeat_source_status"] = source_status
    run["snapshots"] = deepcopy(snapshots)
    for key in RUN_SNAPSHOT_KEYS:
        item[key] = deepcopy(snapshots.get(key, []) or [])

    # Carry planner input values, not measured outcomes.
    mapping = {
        "product": "peptide", "sequence": "sequence", "scale_mmol": "scale",
        "resin": "resin", "loading_target_mmol_g": "loading",
        "loading_aa_eq": "loading_aa_eq", "loading_base_eq": "loading_diea_eq",
        "loading_time_h": "loading_time_h", "cleavage_eq": "cleavage_eq_override",
        "cleavage_time_h": "cleavage_time_h", "post_cleavage_rescue": "post_cleavage_rescue",
    }
    for source_key, item_key in mapping.items():
        if source_key in frozen and frozen.get(source_key) not in (None, ""):
            item[item_key] = deepcopy(frozen[source_key])
    _change(
        run, "repeat", "run", {"run_id": source_id, "name": source_name, "status": source_status},
        {"run_id": run["run_id"], "name": run["name"]}, reason, clock=clock, id_factory=id_factory,
    )
    return run

def activate_run(item: dict[str, Any], run_id: str, *, reason: str = "Activate run",
                 sync_current: bool = True) -> dict[str, Any]:
    current = sync_active_run(item) if sync_current else ensure_hierarchy(item)
    target = next((run for run in item["runs"] if str(run.get("run_id")) == str(run_id)), None)
    if target is None:
        raise ValueError("Run was not found.")
    if current is not target and not str(current.get("completed_at") or "").strip() and str(current.get("status") or "").strip().lower() not in {"completed", "failed", "excluded"}:
        current["status"] = "Closed"
    if not str(target.get("completed_at") or "").strip() and str(target.get("status") or "").strip().lower() not in {"completed", "failed", "excluded"}:
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
        {key: deepcopy(run.get(key)) for key in ("run_id", "name", "status", "created_at", "updated_at", "started_at", "completed_at", "lot", "repeat_of_run_id")}
        | {"hplc_count": sum(not record.get("deleted") for record in run.get("hplc_records", [])),
           "analytical_count": sum(not record.get("deleted") for record in run.get("analytical_records", [])),
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
    "ensure_hierarchy", "finish_active_run", "list_runs", "new_run", "repeat_active_run", "search_hplc",
    "start_active_run", "sync_active_run", "upsert_hplc",
]


# --- R9 structured analytical result domain ----------------------------------
def _clean_analytical(values: Mapping[str,Any])->dict[str,Any]:
    record={str(k):v for k,v in values.items()}
    kind=str(record.get('analytical_type') or '').strip().upper()
    if kind not in {'LC-MS','MALDI','OTHER'}: raise ValueError('analytical_type must be LC-MS, MALDI, or Other.')
    record['analytical_type']='Other' if kind=='OTHER' else kind
    for field in ANALYTICAL_NUMERIC_FIELDS:
        value=record.get(field)
        if value is None or str(value).strip()=='': record[field]=None
        else:
            try: record[field]=float(str(value).replace(',','').strip())
            except ValueError as exc: raise ValueError(f'{field} must be numeric.') from exc
    # Do not infer neutral mass from m/z. Delta is calculated only when both assigned/expected masses are explicit.
    if record.get('expected_neutral_mass') is not None and record.get('observed_assigned_mass') is not None:
        record['delta_da']=record['observed_assigned_mass']-record['expected_neutral_mass']
        record['delta_ppm']=(record['delta_da']/record['expected_neutral_mass']*1e6) if record['expected_neutral_mass'] else None
    return record

def upsert_analytical(item:dict[str,Any], values:Mapping[str,Any], *, reason:str, clock:Callable[[],str]=_now, id_factory:Callable[[],str]=_id)->dict[str,Any]:
    if not str(reason).strip(): raise ValueError('A reason is required for analytical-result changes.')
    run=sync_active_run(item); clean=_clean_analytical(values); rid=str(clean.get('analytical_result_id') or '').strip()
    existing=next((r for r in run['analytical_records'] if r.get('analytical_result_id')==rid),None); before=deepcopy(existing) if existing else None; timestamp=clock()
    clean.update({'analytical_result_id':rid or id_factory(),'run_id':run['run_id'],'updated_at':timestamp,'created_at':(existing or {}).get('created_at',timestamp),'deleted':False,
                  'data_file':_file_metadata(clean.get('data_file_path','')),'report_file':_file_metadata(clean.get('report_file_path',''))})
    if existing: existing.clear(); existing.update(clean); result=existing; action='update'
    else: run['analytical_records'].append(clean); result=clean; action='create'
    _change(run,action,'analytical',before,result,reason,clock=clock,id_factory=id_factory); return deepcopy(result)

def delete_analytical(item:dict[str,Any], record_id:str, *, reason:str)->dict[str,Any]:
    if not str(reason).strip(): raise ValueError('A reason is required to remove an analytical record.')
    run=sync_active_run(item); record=next((r for r in run['analytical_records'] if r.get('analytical_result_id')==record_id),None)
    if record is None: raise ValueError('Analytical record was not found.')
    before=deepcopy(record); record['deleted']=True; record['updated_at']=_now(); _change(run,'delete','analytical',before,record,reason); return deepcopy(record)

def list_analytical(item:dict[str,Any], *, include_deleted:bool=False)->list[dict[str,Any]]:
    run=ensure_hierarchy(item); return [deepcopy(r) for r in run.get('analytical_records',[]) if include_deleted or not r.get('deleted')]

def matched_repeat_observation(item:dict[str,Any], run_id:str|None=None)->dict[str,Any]:
    ensure_hierarchy(item); run=next((r for r in item['runs'] if str(r.get('run_id'))==str(run_id or item.get('active_run_id'))),None)
    if run is None: raise ValueError('Run was not found.')
    parent_id=str(run.get('repeat_of_run_id') or '')
    if not parent_id: return {'available':False,'reason':'Run is not a repeat.','causal_claim_allowed':False}
    parent=next((r for r in item['runs'] if str(r.get('run_id'))==parent_id),None)
    if parent is None: return {'available':False,'reason':'Parent Run is unavailable.','causal_claim_allowed':False}
    def condition(r):
        frozen=dict(r.get('planner_snapshot_v6') or {}); return {k:frozen.get(k) for k in ('resin','scale_mmol','loading_target_mmol_g','loading_aa_eq','loading_base_eq','loading_time_h','cleavage_eq','cleavage_time_h','post_cleavage_rescue') if k in frozen}
    a,b=condition(parent),condition(run); keys=sorted(set(a)|set(b)); changes={k:{'parent':a.get(k),'repeat':b.get(k)} for k in keys if a.get(k)!=b.get(k)}
    return {'available':True,'label':'paired observation','relationship':'matched repeat','parent_run_id':parent_id,'repeat_run_id':run.get('run_id'),'changed_variables':changes,
            'confounders':['Multiple variables changed'] if len(changes)>1 else [],'n_pairs':1,'small_n_warning':'Single matched pair is descriptive only; do not infer causality.',
            'causal_claim_allowed':False}
