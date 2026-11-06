from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from suite_gui import data_system, data_workbook, data_workflow, ml_dataset, state_persistence, synthesis_execution


def _item() -> dict:
    item = {
        "work_item_id": "work-1", "project": "P1", "peptide": "Pep1",
        "sequence": "G-H-K", "scale": "0.2", "resin": "Rink Amide AM",
        "loading": "0.8", "lot": "LOT-1", "chemistry": "DIC/HOBt", "copies": "1",
        "selected_plan_rows": [{"No": "1", "Unit name": "Fmoc-Gly-OH", "Unit eq": "2", "Repeat": "1"}],
        "selected_material_rows": [{"step": "1", "material": "Fmoc-Gly-OH", "planned_mmol": "0.4"}],
        "selected_total_rows": [{"material": "Fmoc-Gly-OH", "total mmol": "0.4"}],
        "selected_checklist_rows": [{"line": "1", "operation": "Coupling 1", "unit": "Fmoc-Gly-OH"}],
        "selected_cleavage_rows": [{"component": "TFA", "volume_mL": "1.0"}],
    }
    synthesis_execution.append_event(
        item, event_type="step_status", step_no=1, unit="Fmoc-Gly-OH",
        field="step_status", before="Planned", after="Completed", reason="Completed",
    )
    ml_dataset.review_item(
        item, actual_yield_percent=72.5, actual_purity_percent=91.2,
        failure_flag=False, included=True, review_reason="Final HPLC reviewed",
    )
    return item


def test_legacy_item_migrates_to_run_and_new_run_is_isolated():
    item = _item()
    first = data_system.ensure_hierarchy(item)
    assert first["name"] == "Run 001"
    assert first["synthesis_execution"]["events"]
    assert first["snapshots"]["selected_plan_rows"][0]["Repeat"] == "1"

    second = data_system.new_run(item, "Repeat synthesis", reason="Scale-up repeat")
    assert second["run_id"] != first["run_id"]
    assert item["active_run_id"] == second["run_id"]
    assert item["synthesis_execution"]["events"] == []
    assert item["ml_review"]["current"] == {}
    item["selected_plan_rows"][0]["Repeat"] = "2"
    synthesis_execution.append_event(
        item, event_type="doubling", step_no=1, unit="Fmoc-Gly-OH",
        field="Repeat", before="1", after="2", reason="Repeat run correction",
    )
    data_system.sync_active_run(item)

    restored = data_system.activate_run(item, first["run_id"], reason="Review original run")
    assert restored["name"] == "Run 001"
    assert item["selected_plan_rows"][0]["Repeat"] == "1"
    assert item["synthesis_execution"]["events"][0]["event_type"] == "step_status"
    assert item["ml_review"]["current"]["actual_yield_percent"] == 72.5


def test_hplc_crud_file_integrity_search_sort_and_history(tmp_path):
    item = _item(); data_system.ensure_hierarchy(item)
    raw = tmp_path / "sample.raw"; raw.write_bytes(b"HPLC-DATA")
    record = data_system.upsert_hplc(item, {
        "sample_name": "Pep1 crude", "instrument": "Waters", "column": "C18",
        "purity_percent": "91.2", "retention_time_min": "8.4",
        "acquired_at": "2026-08-02T10:00:00+09:00", "analyst": "Operator A",
        "data_file_path": str(raw), "method_file_path": "missing-method.m",
    }, reason="Initial HPLC result")
    assert record["data_file"]["exists"] is True
    assert record["data_file"]["sha256"]
    assert record["method_file"]["exists"] is False

    updated = data_system.upsert_hplc(item, {
        **record, "purity_percent": "92.0", "notes": "Reintegrated",
    }, reason="Peak integration reviewed")
    assert updated["purity_percent"] == pytest.approx(92.0)
    rows = data_system.search_hplc([item], "waters", sort_by="purity_percent")
    assert len(rows) == 1 and rows[0]["sample_name"] == "Pep1 crude"
    deleted = data_system.delete_hplc(item, record["hplc_record_id"], reason="Superseded chromatogram")
    assert deleted["deleted"] is True
    assert data_system.search_hplc([item], "Pep1") == []
    assert [row["action"] for row in data_system.change_history(item)][-3:] == ["create", "update", "delete"]


def test_hplc_validation_rejects_bad_percent_and_missing_reason():
    item = _item(); data_system.ensure_hierarchy(item)
    with pytest.raises(ValueError, match="between 0 and 100"):
        data_system.upsert_hplc(item, {"sample_name": "Bad", "purity_percent": 120}, reason="Test")
    with pytest.raises(ValueError, match="reason"):
        data_system.upsert_hplc(item, {"sample_name": "Bad"}, reason="")


def test_multisheet_workbook_round_trip_preserves_run_ml_events_and_hplc(tmp_path):
    item = _item(); data_system.ensure_hierarchy(item)
    data_system.upsert_hplc(item, {
        "sample_name": "Pep1 final", "purity_percent": 95.1,
        "retention_time_min": 7.8, "instrument": "Agilent 1260",
    }, reason="Final HPLC")
    path = data_workbook.export_workbook(tmp_path / "project.xlsx", [item], project_id="project-1")
    assert path.is_file()
    sheets = pd.ExcelFile(path).sheet_names
    for required in (
        "Project", "Work_Items", "Runs", "Plan", "Execution_Events",
        "ML_Current", "ML_Revisions", "HPLC", "Materials", "Checklist",
        "Cleavage", "Totals", "Change_History", "Column_Map",
    ):
        assert required in sheets

    restored = data_workbook.import_workbook(path)
    loaded = restored["items"][0]
    run = data_system.active_run(loaded)
    assert restored["project"]["project_id"] == "project-1"
    assert loaded["selected_plan_rows"][0]["Unit name"] == "Fmoc-Gly-OH"
    assert loaded["selected_total_rows"][0]["material"] == "Fmoc-Gly-OH"
    assert run["synthesis_execution"]["events"][0]["event_type"] == "step_status"
    assert run["ml_review"]["current"]["actual_purity_percent"] == pytest.approx(91.2)
    assert run["hplc_records"][0]["sample_name"] == "Pep1 final"
    assert run["hplc_records"][0]["purity_percent"] == pytest.approx(95.1)


def test_hplc_column_mapping_accepts_common_instrument_exports(tmp_path):
    path = tmp_path / "hplc.xlsx"
    pd.DataFrame([{
        "Sample ID": "AHP-8", "Purity": 96.4, "RT": 9.2,
        "Instrument Name": "Shimadzu", "Data File": "AHP8.lcd",
    }]).to_excel(path, index=False, sheet_name="Results")
    rows = data_workbook.import_hplc_rows(path)
    assert rows[0]["sample_name"] == "AHP-8"
    assert rows[0]["purity_percent"] == pytest.approx(96.4)
    assert rows[0]["retention_time_min"] == pytest.approx(9.2)
    assert rows[0]["instrument"] == "Shimadzu"

    mapped = data_workbook.import_hplc_rows(
        path, column_mapping={"Purity": "area_percent"},
    )
    assert mapped[0]["area_percent"] == pytest.approx(96.4)

    mapped_path = tmp_path / "mapped_hplc.xlsx"
    with pd.ExcelWriter(mapped_path, engine="openpyxl") as writer:
        pd.DataFrame([{"Sample Code": "Mapped", "Signal %": 97.1}]).to_excel(writer, sheet_name="HPLC", index=False)
        pd.DataFrame([
            {"sheet": "HPLC", "source_column": "Sample Code", "canonical_column": "sample_name"},
            {"sheet": "HPLC", "source_column": "Signal %", "canonical_column": "purity_percent"},
        ]).to_excel(writer, sheet_name="Column_Map", index=False)
    embedded = data_workbook.import_hplc_rows(mapped_path)
    assert embedded[0]["sample_name"] == "Mapped"
    assert embedded[0]["purity_percent"] == pytest.approx(97.1)


def test_atomic_backup_recovery_and_recent_project_registry(tmp_path):
    path = tmp_path / "project.json"
    state_persistence.atomic_write_json_with_backup(path, {"revision": 1})
    state_persistence.atomic_write_json_with_backup(path, {"revision": 2})
    assert json.loads(path.with_suffix(".json.bak").read_text(encoding="utf-8"))["revision"] == 1
    path.write_text("{broken", encoding="utf-8")
    data, source, recovered = state_persistence.read_json_with_recovery(path)
    assert recovered is True and source.name == "project.json.bak"
    assert data["revision"] == 1

    class Gui:
        recent_projects_path = tmp_path / "recent.json"
    gui = Gui()
    data_workflow.add_recent(gui, path, recovered=True)
    recent = data_workflow.recent_projects(gui)
    assert recent[0]["path"] == str(path.resolve())
    assert recent[0]["recovered"] is True
    assert recent[0]["exists"] is True
