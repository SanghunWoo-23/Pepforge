from __future__ import annotations

import json
import zipfile
from io import BytesIO
from types import SimpleNamespace

import pandas as pd
import pytest
from pathlib import Path

from suite_gui import data_system, experimental_workflow, run_package
from suite_gui.preflight import check_snapshot
from suite_gui.modules.evidence_detail_dialog import format_sections


def _item() -> dict:
    return {
        "work_item_id": "w1", "project": "P", "peptide": "Pep", "sequence": "GHK",
        "scale": "0.2", "resin": "Rink Amide AM", "loading": "0.8", "lot": "L1",
        "selected_plan_rows": [{
            "No": "1", "Unit name": "Fmoc-Gly-OH", "MW": "297.31", "Density(g/mL)": "",
            "Reagent 1": "DIC", "R1 MW": "126.2", "R1 Density": "0.815",
            "Reagent 2 / catalyst": "HOBt", "R2 MW": "135.13", "R2 Density": "",
            "Base": "", "Base MW": "", "Base Density": "", "Coupling solvent": "DMF", "Repeat": "1",
        }],
        "selected_material_rows": [{"step": "1", "material": "Fmoc-Gly-OH", "planned_mmol": "0.4"}],
        "selected_total_rows": [{"material": "Fmoc-Gly-OH", "total_mmol": "0.4"}],
        "selected_checklist_rows": [{"line": "1", "operation": "Coupling", "unit": "Fmoc-Gly-OH"}],
        "selected_cleavage_rows": [{"component": "TFA", "volume_mL": "1.0"}],
    }


def _snapshot(item: dict) -> dict:
    return {
        "sequence": item["sequence"], "resin": item["resin"], "scale_mmol": item["scale"],
        "loading_target_mmol_g": item["loading"], "selected_plan_rows": item["selected_plan_rows"],
        "selected_cleavage_rows": item["selected_cleavage_rows"],
    }


def test_preflight_accepts_resolved_generated_rows_and_blocks_purpose_suffix():
    item = _item()
    report = check_snapshot(_snapshot(item))
    assert report["ready"] is True
    assert report["requires_review"] is False

    bad = _snapshot(item)
    bad["selected_plan_rows"] = [dict(item["selected_plan_rows"][0], **{
        "Unit name": "Acetic anhydride (Ac2O) for N-terminal acetylation", "MW": "102.09",
    })]
    blocked = check_snapshot(bad)
    assert blocked["ready"] is False
    assert any(row["code"] == "CANONICAL_NAMES" and row["status"] == "BLOCK" for row in blocked["checks"])


def test_start_snapshots_are_immutable_and_repeat_copies_plan_not_results():
    item = _item()
    first = data_system.ensure_hierarchy(item)
    first_id = first["run_id"]
    data_system.start_active_run(item, _snapshot(item), clock=lambda: "2026-09-04T01:00:00+00:00", id_factory=lambda: "event-start")
    first = data_system.active_run(item)
    assert first["start_snapshots_v6"]["selected_material_rows"][0]["planned_mmol"] == "0.4"

    # Later live edits must not rewrite the immutable start package.
    item["selected_material_rows"][0]["planned_mmol"] = "0.9"
    first.setdefault("hplc_records", []).append({"hplc_record_id": "h1", "sample_name": "Final"})
    data_system.sync_active_run(item)
    assert first["start_snapshots_v6"]["selected_material_rows"][0]["planned_mmol"] == "0.4"

    data_system.finish_active_run(item, clock=lambda: "2026-09-04T02:00:00+00:00", id_factory=lambda: "event-finish")
    first = next(run for run in item["runs"] if run["run_id"] == first_id)
    assert first["status"] == "Completed"
    repeat = data_system.repeat_active_run(item, clock=lambda: "2026-09-04T03:00:00+00:00", id_factory=iter(["run-repeat", "event-create", "event-repeat"]).__next__)
    assert repeat["repeat_of_run_id"] == first_id
    assert repeat["hplc_records"] == []
    assert repeat["synthesis_execution"]["events"] == []
    assert repeat["start_snapshots_v6"] == {}
    assert repeat["snapshots"]["selected_material_rows"][0]["planned_mmol"] == "0.4"
    # Creating the new active Run must not rewrite the source's terminal outcome.
    source = next(run for run in item["runs"] if run["run_id"] == first_id)
    assert source["status"] == "Completed"


def test_completed_status_is_preserved_when_reactivated_for_late_results():
    item = _item()
    first = data_system.ensure_hierarchy(item)
    first_id = first["run_id"]
    data_system.start_active_run(item, _snapshot(item))
    data_system.finish_active_run(item)
    second = data_system.new_run(item, "Second")
    first = next(run for run in item["runs"] if run["run_id"] == first_id)
    assert first["status"] == "Completed"
    second_id = second["run_id"]
    selected = data_system.activate_run(item, first_id, reason="Late HPLC")
    assert selected["status"] == "Completed"
    second = next(run for run in item["runs"] if run["run_id"] == second_id)
    assert second["status"] == "Closed"



def test_repeat_workflow_rolls_back_if_regeneration_fails():
    item = _item()
    first = data_system.ensure_hierarchy(item)
    first_id = first["run_id"]
    data_system.start_active_run(item, _snapshot(item))
    data_system.finish_active_run(item)
    before = json.loads(json.dumps(item))
    gui = SimpleNamespace(pm_items=[item], _v2097_active_index=0, generate_update_plan=lambda: None)
    with pytest.raises(RuntimeError, match="regeneration did not complete"):
        experimental_workflow.repeat_experiment(gui, scale_mmol="0.3")
    assert item == before
    assert item["active_run_id"] == first_id


def test_repeat_workflow_rejects_invalid_scale_before_mutation():
    item = _item()
    first = data_system.ensure_hierarchy(item)
    data_system.start_active_run(item, _snapshot(item))
    data_system.finish_active_run(item)
    before = json.loads(json.dumps(item))
    gui = SimpleNamespace(pm_items=[item], _v2097_active_index=0)
    with pytest.raises(ValueError, match="scale must be numeric"):
        experimental_workflow.repeat_experiment(gui, scale_mmol="0")
    assert item == before

def test_run_package_contains_traceable_expected_files(tmp_path: Path):
    payload = {
        "schema_version": "6.0.0", "format": "detailed",
        "run": {"run_id": "r1", "run_name": "Run 001", "status": "Completed"},
        "planner_snapshot_frozen": {"selected_plan_rows": [{"No": 1, "Unit name": "Fmoc-Gly-OH"}]},
        "execution": {"steps": [{"step_no": 1, "status": "Completed"}]},
        "actual_condition": {"deviations": [], "planner_changes_since_start": []},
        "linked_records": {"outcomes": [{"record_id": "o1", "purity_percent": 97}], "issues": []},
    }
    target = run_package.build_package(
        payload, tmp_path / "run.zip",
        materials=[{"material": "Fmoc-Gly-OH", "amount": "10 mg"}],
        checklist=[{"operation": "Coupling", "checked": "Yes"}],
    )
    with zipfile.ZipFile(target) as archive:
        names = set(archive.namelist())
        assert names == {
            "PLAN.xlsx", "MATERIALS.xlsx", "CHECKLIST.xlsx", "ACTUAL_EXECUTION.xlsx",
            "RESULTS.xlsx", "ISSUES.xlsx", "RUN_SUMMARY.json", "MANIFEST.txt",
        }
        summary = json.loads(archive.read("RUN_SUMMARY.json"))
        assert summary["run"]["run_id"] == "r1"
        result_sheets = pd.ExcelFile(BytesIO(archive.read("RESULTS.xlsx"))).sheet_names
        assert result_sheets == ["Final outcomes", "Loading", "Cleavage", "Analytical", "Recommendation trace"]



def test_run_package_publish_is_atomic_on_zip_failure(tmp_path: Path, monkeypatch):
    target = tmp_path / "run.zip"
    target.write_bytes(b"previous-valid-package")

    class BrokenZip:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            raise RuntimeError("simulated archive failure")
        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(run_package.zipfile, "ZipFile", BrokenZip)
    with pytest.raises(RuntimeError, match="simulated archive failure"):
        run_package.build_package({"run": {"run_id": "r1"}}, target)
    assert target.read_bytes() == b"previous-valid-package"
    assert not list(tmp_path.glob(".run.zip.*.tmp"))

def test_evidence_detail_is_read_only_explanation_text():
    text = format_sections([("Loading", {
        "target_recommendation": {
            "recommendation_kind": "BOUNDED TARGET INTERPOLATION", "confidence": "HIGH",
            "evidence_count": 4, "verified_evidence_count": 4, "apply_allowed": True,
            "observed_aa_eq_min": 1.5, "observed_aa_eq_max": 3.0, "basis": "same resin + AA",
        },
        "evidence": [{"date": "2026-09-01", "resin_type": "2-CTC", "aa_eq": 2.0, "status": "verified"}],
    })])
    assert "Source: Bounded interpolation" in text
    assert "Confidence: HIGH" in text
    assert "Evidence records (1)" in text
