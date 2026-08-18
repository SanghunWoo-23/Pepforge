"""Multi-sheet Excel interchange for the V3 Project/Work Item/Run system."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd

from spps_v4_gui import data_system, ml_dataset, risk_assessment, synthesis_execution


WORK_ITEM_FIELDS = (
    "work_item_id", "project", "peptide", "sequence", "scale", "resin",
    "loading", "lot", "chemistry", "copies", "status", "active_run_id",
)
SHEET_ALIASES = {
    "Project": ("project",), "Work_Items": ("workitems", "work_items", "items"),
    "Runs": ("runs",), "Plan": ("plan", "selectedplan"),
    "Execution_Events": ("executionevents", "events"),
    "ML_Current": ("mlcurrent", "outcomes"), "ML_Revisions": ("mlrevisions",),
    "HPLC": ("hplc", "chromatography"), "Materials": ("materials",), "Totals": ("totals", "totalmaterials"),
    "Checklist": ("checklist",), "Cleavage": ("cleavage",),
    "Change_History": ("changehistory", "history"),
    "Risk_Assessments": ("riskassessments", "riskreviews"),
    "Risk_Findings": ("riskfindings",),
    "Risk_Acknowledgements": ("riskacknowledgements", "riskacks"),
}
HPLC_ALIASES = {
    "sample": "sample_name", "sampleid": "sample_name", "samplename": "sample_name",
    "purity": "purity_percent", "puritypercent": "purity_percent", "area": "area_percent",
    "areapercent": "area_percent", "rt": "retention_time_min", "retentiontime": "retention_time_min",
    "retentiontimemin": "retention_time_min", "wavelength": "wavelength_nm",
    "flowrate": "flow_rate_mL_min", "instrumentname": "instrument",
    "columnname": "column", "datafile": "data_file_path", "methodfile": "method_file_path",
    "date": "acquired_at", "acquired": "acquired_at", "operator": "analyst", "note": "notes",
}


def _norm(value: Any) -> str:
    return "".join(ch.lower() for ch in str(value or "") if ch.isalnum() or ch == "_").replace("_", "")


def _clean(value: Any) -> Any:
    if value is None or (not isinstance(value, (dict, list)) and pd.isna(value)):
        return ""
    return value


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return [{str(key): _clean(value) for key, value in row.items()} for row in frame.to_dict("records")]


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _frame(rows: Iterable[Mapping[str, Any]], columns: Iterable[str] = ()) -> pd.DataFrame:
    result = pd.DataFrame(list(rows))
    if result.empty and columns:
        result = pd.DataFrame(columns=list(columns))
    return result


def workbook_tables(items: list[dict[str, Any]], *, project_id: str = "") -> dict[str, pd.DataFrame]:
    work_items, runs, plan, events, ml_current, ml_revisions = [], [], [], [], [], []
    hplc, materials, totals, checklist, cleavage, changes = [], [], [], [], [], []
    risk_versions, risk_findings, risk_acknowledgements = [], [], []
    for item in items:
        data_system.sync_active_run(item)
        work_items.append({field: item.get(field, "") for field in WORK_ITEM_FIELDS})
        for run in item.get("runs", []):
            base = {"work_item_id": item.get("work_item_id", ""), "run_id": run.get("run_id", "")}
            runs.append({**base, **{key: run.get(key, "") for key in ("name", "status", "created_at", "updated_at", "lot")}})
            snapshots = dict(run.get("snapshots", {}) or {})
            for row in snapshots.get("selected_plan_rows", []): plan.append({**base, **dict(row)})
            for row in snapshots.get("selected_material_rows", []): materials.append({**base, **dict(row)})
            for row in snapshots.get("selected_total_rows", []): totals.append({**base, **dict(row)})
            for row in snapshots.get("selected_checklist_rows", []): checklist.append({**base, **dict(row)})
            for row in snapshots.get("selected_cleavage_rows", []): cleavage.append({**base, **dict(row)})
            for row in (run.get("synthesis_execution") or {}).get("events", []):
                event = dict(row); event["metadata"] = _json(event.get("metadata", {})); events.append({**base, **event})
            review = ml_dataset.normalize_review(run.get("ml_review"))
            if review.get("current"):
                ml_current.append({**base, "revision": review["revision"], **dict(review["current"])})
            for version in review.get("versions", []):
                row = dict(version); row["before"] = _json(row.get("before", {})); row["after"] = _json(row.get("after", {})); ml_revisions.append({**base, **row})
            for record in run.get("hplc_records", []):
                row = dict(record)
                data_meta = dict(row.pop("data_file", {}) or {})
                method_meta = dict(row.pop("method_file", {}) or {})
                row.update({f"data_file_{key}": value for key, value in data_meta.items() if key != "path"})
                row.update({f"method_file_{key}": value for key, value in method_meta.items() if key != "path"})
                hplc.append({**base, **row})
            for event in run.get("change_history", []):
                row = dict(event); row["before"] = _json(row.get("before")); row["after"] = _json(row.get("after")); changes.append({**base, **row})
            risk = risk_assessment.ensure_review(run)
            for version in risk.get("versions", []):
                row = dict(version)
                findings = list(row.pop("findings", []) or [])
                signals = row.pop("ml_signals", [])
                row["ml_signals"] = _json(signals)
                row["parser_warnings"] = _json(row.get("parser_warnings", []))
                risk_versions.append({**base, **row})
                for finding in findings:
                    finding_row = dict(finding)
                    finding_row["sequence_positions"] = _json(finding_row.get("sequence_positions", []))
                    risk_findings.append({**base, "assessment_id": version.get("assessment_id", ""), **finding_row})
            for acknowledgement in risk.get("acknowledgements", []):
                risk_acknowledgements.append({**base, **dict(acknowledgement)})
    project_names = sorted({str(item.get("project", "")) for item in items if str(item.get("project", ""))})
    project = [{
        "app_version": "V4.0.0", "data_schema_version": data_system.SCHEMA_VERSION,
        "project_id": project_id, "project_names": " | ".join(project_names),
        "work_item_count": len(items), "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }]
    mapping_rows = []
    tables = {
        "Project": _frame(project), "Work_Items": _frame(work_items, WORK_ITEM_FIELDS),
        "Runs": _frame(runs, ("work_item_id", "run_id", "name", "status", "created_at", "updated_at", "lot")),
        "Plan": _frame(plan), "Execution_Events": _frame(events),
        "ML_Current": _frame(ml_current), "ML_Revisions": _frame(ml_revisions),
        "HPLC": _frame(hplc), "Materials": _frame(materials), "Totals": _frame(totals),
        "Checklist": _frame(checklist), "Cleavage": _frame(cleavage),
        "Change_History": _frame(changes),
        "Risk_Assessments": _frame(risk_versions),
        "Risk_Findings": _frame(risk_findings),
        "Risk_Acknowledgements": _frame(risk_acknowledgements),
    }
    for sheet, frame in tables.items():
        for column in frame.columns:
            mapping_rows.append({"sheet": sheet, "source_column": column, "canonical_column": column, "required": column in {"work_item_id", "run_id"}})
    tables["Column_Map"] = _frame(mapping_rows)
    return tables


def export_workbook(path: str | Path, items: list[dict[str, Any]], *, project_id: str = "") -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp.xlsx")
    with pd.ExcelWriter(temporary, engine="openpyxl") as writer:
        for sheet, frame in workbook_tables(items, project_id=project_id).items():
            frame.to_excel(writer, sheet_name=sheet[:31], index=False)
            worksheet = writer.book[sheet[:31]]
            worksheet.freeze_panes = "A2"
            worksheet.auto_filter.ref = worksheet.dimensions
            for cells in worksheet.columns:
                width = min(48, max(10, max(len(str(cell.value or "")) for cell in cells) + 2))
                worksheet.column_dimensions[cells[0].column_letter].width = width
    temporary.replace(destination)
    return destination


def _sheet(frames: Mapping[str, pd.DataFrame], canonical: str) -> pd.DataFrame:
    aliases = {_norm(canonical), *SHEET_ALIASES.get(canonical, ())}
    for name, frame in frames.items():
        if _norm(name) in aliases:
            return frame.copy()
    return pd.DataFrame()


def _apply_mapping(frame: pd.DataFrame, mapping: Mapping[str, str] | None, *, hplc: bool = False) -> pd.DataFrame:
    rename = dict(mapping or {})
    if hplc:
        for column in frame.columns:
            canonical = HPLC_ALIASES.get(_norm(column))
            if canonical:
                rename.setdefault(column, canonical)
    return frame.rename(columns=rename)


def _parse_json(value: Any, default: Any) -> Any:
    if isinstance(value, (dict, list)):
        return deepcopy(value)
    try:
        return json.loads(str(value))
    except Exception:
        return deepcopy(default)


def import_workbook(path: str | Path, *, column_mapping: Mapping[str, Mapping[str, str]] | None = None) -> dict[str, Any]:
    frames = pd.read_excel(path, sheet_name=None, engine="openpyxl")
    mapping: dict[str, dict[str, str]] = {}
    embedded = _sheet(frames, "Column_Map")
    if not embedded.empty:
        for row in _records(embedded):
            sheet = str(row.get("sheet", "")).strip()
            source = str(row.get("source_column", "")).strip()
            canonical = str(row.get("canonical_column", "")).strip()
            if sheet and source and canonical:
                mapping.setdefault(sheet, {})[source] = canonical
    for sheet, values in dict(column_mapping or {}).items():
        mapping.setdefault(sheet, {}).update(dict(values))
    work = _apply_mapping(_sheet(frames, "Work_Items"), mapping.get("Work_Items"))
    if work.empty:
        raise ValueError("Workbook must contain a Work_Items sheet with at least one row.")
    items = []
    for row in _records(work):
        item = {field: row.get(field, "") for field in WORK_ITEM_FIELDS if field != "active_run_id"}
        synthesis_execution.ensure_work_item_id(item)
        item["active_run_id"] = str(row.get("active_run_id", ""))
        item["runs"] = []
        items.append(item)
    by_item = {item["work_item_id"]: item for item in items}
    runs_frame = _apply_mapping(_sheet(frames, "Runs"), mapping.get("Runs"))
    for row in _records(runs_frame):
        item = by_item.get(str(row.get("work_item_id", "")))
        if item is None:
            continue
        run = {key: row.get(key, "") for key in ("run_id", "name", "status", "created_at", "updated_at", "lot")}
        run.update({"snapshots": {key: [] for key in data_system.RUN_SNAPSHOT_KEYS}, "synthesis_execution": {"schema_version": 1, "events": []}, "ml_review": {"schema_version": 1, "revision": 0, "current": {}, "versions": []}, "risk_review": {"schema_version": 1, "revision": 0, "current": {}, "versions": [], "acknowledgements": []}, "hplc_records": [], "change_history": []})
        item["runs"].append(run)
    run_index = {(item["work_item_id"], str(run.get("run_id"))): run for item in items for run in item["runs"]}
    sheet_snapshots = {"Plan": "selected_plan_rows", "Materials": "selected_material_rows", "Totals": "selected_total_rows", "Checklist": "selected_checklist_rows", "Cleavage": "selected_cleavage_rows"}
    for sheet, key in sheet_snapshots.items():
        frame = _apply_mapping(_sheet(frames, sheet), mapping.get(sheet))
        for row in _records(frame):
            run = run_index.get((str(row.pop("work_item_id", "")), str(row.pop("run_id", ""))))
            if run is not None:
                run["snapshots"][key].append(row)
    for row in _records(_apply_mapping(_sheet(frames, "Execution_Events"), mapping.get("Execution_Events"))):
        run = run_index.get((str(row.pop("work_item_id", "")), str(row.pop("run_id", ""))))
        if run is not None:
            row["metadata"] = _parse_json(row.get("metadata"), {}); run["synthesis_execution"]["events"].append(row)
    for row in _records(_apply_mapping(_sheet(frames, "ML_Current"), mapping.get("ML_Current"))):
        run = run_index.get((str(row.pop("work_item_id", "")), str(row.pop("run_id", ""))))
        if run is not None:
            run["ml_review"]["revision"] = int(row.pop("revision", 0) or 0); run["ml_review"]["current"] = row
    for row in _records(_apply_mapping(_sheet(frames, "ML_Revisions"), mapping.get("ML_Revisions"))):
        run = run_index.get((str(row.pop("work_item_id", "")), str(row.pop("run_id", ""))))
        if run is not None:
            row["before"] = _parse_json(row.get("before"), {}); row["after"] = _parse_json(row.get("after"), {}); run["ml_review"]["versions"].append(row)
    hplc_frame = _apply_mapping(_sheet(frames, "HPLC"), mapping.get("HPLC"), hplc=True)
    for row in _records(hplc_frame):
        run = run_index.get((str(row.pop("work_item_id", "")), str(row.get("run_id", ""))))
        if run is not None:
            row["data_file"] = {
                "path": row.get("data_file_path", ""), "exists": row.get("data_file_exists", False),
                "size_bytes": row.get("data_file_size_bytes", ""), "modified_at": row.get("data_file_modified_at", ""),
                "sha256": row.get("data_file_sha256", ""),
            }
            row["method_file"] = {
                "path": row.get("method_file_path", ""), "exists": row.get("method_file_exists", False),
                "size_bytes": row.get("method_file_size_bytes", ""), "modified_at": row.get("method_file_modified_at", ""),
                "sha256": row.get("method_file_sha256", ""),
            }
            run["hplc_records"].append(row)
    for row in _records(_apply_mapping(_sheet(frames, "Change_History"), mapping.get("Change_History"))):
        run = run_index.get((str(row.pop("work_item_id", "")), str(row.get("run_id", ""))))
        if run is not None:
            row["before"] = _parse_json(row.get("before"), None); row["after"] = _parse_json(row.get("after"), None); run["change_history"].append(row)
    finding_index: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in _records(_apply_mapping(_sheet(frames, "Risk_Findings"), mapping.get("Risk_Findings"))):
        work_id, run_id, assessment_id = str(row.pop("work_item_id", "")), str(row.pop("run_id", "")), str(row.pop("assessment_id", ""))
        row["sequence_positions"] = _parse_json(row.get("sequence_positions"), [])
        finding_index.setdefault((work_id, run_id, assessment_id), []).append(row)
    for row in _records(_apply_mapping(_sheet(frames, "Risk_Assessments"), mapping.get("Risk_Assessments"))):
        work_id, run_id = str(row.pop("work_item_id", "")), str(row.pop("run_id", ""))
        run = run_index.get((work_id, run_id))
        if run is not None:
            row["ml_signals"] = _parse_json(row.get("ml_signals"), [])
            row["parser_warnings"] = _parse_json(row.get("parser_warnings"), [])
            row["findings"] = finding_index.get((work_id, run_id, str(row.get("assessment_id", ""))), [])
            run["risk_review"]["versions"].append(row)
            if int(row.get("revision", 0) or 0) >= int(run["risk_review"].get("revision", 0) or 0):
                run["risk_review"]["revision"] = int(row.get("revision", 0) or 0)
                run["risk_review"]["current"] = deepcopy(row)
    for row in _records(_apply_mapping(_sheet(frames, "Risk_Acknowledgements"), mapping.get("Risk_Acknowledgements"))):
        run = run_index.get((str(row.pop("work_item_id", "")), str(row.pop("run_id", ""))))
        if run is not None:
            run["risk_review"]["acknowledgements"].append(row)
    for item in items:
        active = data_system.ensure_hierarchy(item)
        item["active_run_id"] = active["run_id"] if not item.get("active_run_id") else item["active_run_id"]
        data_system.activate_run(
            item, item["active_run_id"], reason="Imported workbook active run",
            sync_current=False,
        )
    project_frame = _sheet(frames, "Project")
    project = _records(project_frame)[0] if not project_frame.empty else {}
    return {"items": items, "project": project, "sheets": sorted(frames)}


def import_hplc_rows(path: str | Path, *, column_mapping: Mapping[str, str] | None = None) -> list[dict[str, Any]]:
    source = Path(path)
    if source.suffix.lower() == ".csv":
        frame = pd.read_csv(source)
    else:
        frames = pd.read_excel(source, sheet_name=None, engine="openpyxl")
        frame = _sheet(frames, "HPLC")
        if frame.empty and frames:
            frame = next(iter(frames.values())).copy()
        embedded = _sheet(frames, "Column_Map")
        workbook_mapping = {}
        if not embedded.empty:
            for row in _records(embedded):
                if str(row.get("sheet", "")).strip() == "HPLC":
                    source_column = str(row.get("source_column", "")).strip()
                    canonical = str(row.get("canonical_column", "")).strip()
                    if source_column and canonical:
                        workbook_mapping[source_column] = canonical
        workbook_mapping.update(dict(column_mapping or {}))
        column_mapping = workbook_mapping
    frame = _apply_mapping(frame, column_mapping, hplc=True)
    return _records(frame)


__all__ = [
    "HPLC_ALIASES", "SHEET_ALIASES", "WORK_ITEM_FIELDS", "export_workbook",
    "import_hplc_rows", "import_workbook", "workbook_tables",
]
