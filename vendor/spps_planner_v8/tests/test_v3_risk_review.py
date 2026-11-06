from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest

from suite_gui import data_system, data_workbook, ml_dataset, ml_workflow, peptide_item_collection, risk_assessment, risk_engine, risk_workflow


def _item(sequence: str = "ADGSVVVVVV") -> dict:
    return {
        "work_item_id": "risk-work-1", "project": "Risk", "peptide": "Candidate",
        "sequence": sequence, "scale": "0.1", "resin": "Rink Amide AM",
        "loading": "0.8", "chemistry": "DIC/HOBt", "copies": "1",
        "selected_plan_rows": [{"No": "3", "Unit name": "Fmoc-Val-OH", "Repeat": "2"}],
        "selected_material_rows": [], "selected_total_rows": [],
        "selected_checklist_rows": [], "selected_cleavage_rows": [],
    }


class _Gui:
    def __init__(self, root: Path, items: list[dict]):
        self.pm_items = items
        self._v229_active_index = 0
        self.ml_models_dir = root / "models"
        self.ml_dataset_dir = root / "datasets"
        self.actual_runs_path = root / "actual_runs.csv"

    def schedule_autosave(self):
        return None


def test_rules_detect_distinct_chemistry_patterns_and_explain_actions():
    report = risk_engine.evaluate_rules(_item())
    by_rule = {row["rule_id"]: row for row in report["findings"]}
    assert {"SEQ-ASPARTIMIDE", "SEQ-AGGREGATION", "SEQ-DIFFICULT-COUPLING", "PLAN-REPEAT"} <= set(by_rule)
    assert by_rule["SEQ-ASPARTIMIDE"]["sequence_positions"] == [2, 3]
    assert report["rule_score"] > 0
    assert all(row["evidence"] and row["impact"] and row["recommendation"] for row in report["findings"])
    assert all(row["requires_review"] for row in report["findings"])


def test_cys_and_oxidation_review_and_no_plan_mutation():
    item = _item("ACMW")
    before = deepcopy(item)
    report = risk_engine.evaluate_rules(item)
    assert {"SEQ-CYS", "SEQ-OXIDATION"} <= {row["rule_id"] for row in report["findings"]}
    assert item == before


def test_assessment_version_is_content_addressed_and_acknowledgement_requires_reason():
    item = _item()
    report = risk_assessment.assess(item)
    first = risk_assessment.save_assessment(item, report, clock=lambda: "2026-08-02T00:00:00+00:00", id_factory=lambda: "assessment-1")
    same = risk_assessment.save_assessment(item, first, clock=lambda: "later", id_factory=lambda: "not-used")
    assert first["revision"] == 1 and same["assessment_id"] == "assessment-1"
    finding_id = first["findings"][0]["finding_id"]
    with pytest.raises(ValueError, match="reason"):
        risk_assessment.acknowledge(item, finding_id, "")
    event = risk_assessment.acknowledge(item, finding_id, "Reviewed against SOP", id_factory=lambda: "ack-1")
    assert event["finding_id"] == finding_id
    assert len(item["risk_review"]["acknowledgements"]) == 1


def test_workflow_does_not_fabricate_ml_score_without_model(tmp_path):
    item = _item()
    gui = _Gui(tmp_path, [item])
    report = risk_workflow.evaluate(gui)
    assert report["ml_status"] == "ML unavailable: reviewed data/model insufficient"
    assert all(row["available"] is False for row in report["ml_signals"])
    assert all("positive_probability" not in row for row in report["ml_signals"])


def test_real_reviewed_classifier_exposes_probability_and_dataset_fingerprint(tmp_path):
    items = []
    for number in range(1, 9):
        item = _item("G-H-K" if number % 2 else "G-V-I-L-F-W")
        item["work_item_id"] = f"risk-{number}"
        item["scale"] = str(number / 10)
        ml_dataset.review_item(
            item, failure_flag=number % 2 == 0, doubling_required=number % 3 == 0,
            included=True, review_reason="Reviewed final result",
        )
        items.append(item)
    gui = _Gui(tmp_path, items)
    metadata = ml_workflow.train(gui, "failure_flag", "classification")
    assert metadata["dataset_fingerprint"]
    report = risk_workflow.evaluate(gui)
    signal = next(row for row in report["ml_signals"] if row["target"] == "failure_flag")
    assert signal["available"] is True
    assert 0 <= signal["positive_probability"] <= 1
    assert signal["dataset_fingerprint"] == metadata["dataset_fingerprint"]


def test_risk_review_round_trips_through_run_and_workbook(tmp_path):
    item = _item()
    saved = risk_assessment.save_assessment(item, risk_assessment.assess(item), id_factory=lambda: "assessment-1")
    risk_assessment.acknowledge(item, saved["findings"][0]["finding_id"], "Operator reviewed", id_factory=lambda: "ack-1")
    data_system.ensure_hierarchy(item)
    path = data_workbook.export_workbook(tmp_path / "risk.xlsx", [item])
    sheets = pd.ExcelFile(path).sheet_names
    assert {"Risk_Assessments", "Risk_Findings", "Risk_Acknowledgements"} <= set(sheets)
    loaded = data_workbook.import_workbook(path)["items"][0]
    review = risk_assessment.ensure_review(loaded)
    assert review["current"]["assessment_id"] == "assessment-1"
    assert review["current"]["findings"]
    assert review["acknowledgements"][0]["acknowledgement_id"] == "ack-1"


def test_duplicate_preserves_plan_but_not_run_or_risk_history():
    item = _item()
    risk_assessment.save_assessment(item, risk_assessment.assess(item))
    data_system.ensure_hierarchy(item)
    _items, _index, duplicate = peptide_item_collection.duplicate_item([item], 0)
    assert duplicate["selected_plan_rows"] == item["selected_plan_rows"]
    assert "risk_review" not in duplicate
    assert "runs" not in duplicate and "active_run_id" not in duplicate
