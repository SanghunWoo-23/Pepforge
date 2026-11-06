from __future__ import annotations

import json
from pathlib import Path
import warnings

import joblib
import pandas as pd
import pytest

from suite_gui import ml_dataset, ml_workflow, peptide_item_collection, synthesis_execution


def _item(number: int) -> dict:
    item = {
        "work_item_id": f"work-{number}",
        "project": "P-ML",
        "peptide": f"Pep-{number}",
        "sequence": "G-H-K" if number % 2 else "G-H-K-L-M",
        "scale": str(0.1 * number),
        "resin": "Rink Amide AM" if number % 2 else "2-CTC",
        "loading": "0.8",
        "chemistry": "DIC/HOBt",
        "copies": "1",
        "selected_plan_rows": [
            {"No": "1", "Unit name": "Fmoc-Gly-OH", "Unit eq": "2", "Repeat": "1"},
            {"No": "2", "Unit name": "Fmoc-His(Trt)-OH", "Unit eq": "2", "Repeat": "1"},
        ],
    }
    synthesis_execution.append_event(
        item,
        event_type="step_status",
        step_no=1,
        unit="Fmoc-Gly-OH",
        field="step_status",
        before="Planned",
        after="Completed" if number != 6 else "Failed",
        reason="Observed execution status",
    )
    if number % 2 == 0:
        synthesis_execution.append_event(
            item,
            event_type="doubling",
            step_no=2,
            unit="Fmoc-His(Trt)-OH",
            field="Repeat",
            before="1",
            after="2",
            reason="Positive coupling test",
        )
        item["selected_plan_rows"][1]["Repeat"] = "2"
    synthesis_execution.append_event(
        item,
        event_type="actual_material",
        step_no=1,
        unit="Fmoc-Gly-OH",
        field="actual_material::Fmoc-Gly-OH",
        before=None,
        after={"material": "Fmoc-Gly-OH", "amount": 10 + number, "unit": "mg", "status": "Charged"},
        reason="Balance reading",
    )
    return item


class _Gui:
    def __init__(self, tmp_path: Path, items: list[dict]):
        self.pm_items = items
        self._v229_active_index = 0
        self.actual_runs_path = tmp_path / "actual_runs.csv"
        self.ml_dataset_dir = tmp_path / "datasets"
        self.ml_models_dir = tmp_path / "models"


def test_review_is_versioned_and_exclusion_requires_reason():
    item = _item(1)
    first = ml_dataset.review_item(
        item,
        actual_yield_percent="71.2",
        actual_purity_percent="88.5",
        failure_flag="No",
        doubling_required="Auto",
        included=True,
        review_reason="HPLC result entered",
        clock=lambda: "2026-08-02T10:00:00+00:00",
        id_factory=lambda: "review-1",
    )
    second = ml_dataset.review_item(
        item,
        actual_yield_percent="72.0",
        actual_purity_percent="89.0",
        failure_flag="No",
        doubling_required="No",
        included=False,
        exclusion_reason="Wrong HPLC integration method",
        review_reason="Exclude invalid integration",
        clock=lambda: "2026-08-02T11:00:00+00:00",
        id_factory=lambda: "review-2",
    )

    assert first["revision"] == 1
    assert second["revision"] == 2
    assert second["before"]["actual_yield_percent"] == 71.2
    review = ml_dataset.normalize_review(item["ml_review"])
    assert review["current"]["included"] is False
    assert [row["version_id"] for row in review["versions"]] == ["review-1", "review-2"]
    with pytest.raises(ValueError, match="exclusion reason"):
        ml_dataset.review_item(
            item, included=False, review_reason="Exclude", exclusion_reason="",
        )


def test_execution_history_becomes_reviewed_feature_row():
    item = _item(2)
    ml_dataset.review_item(
        item,
        actual_yield_percent=66,
        actual_purity_percent=82,
        failure_flag=False,
        doubling_required=None,
        included=True,
        review_reason="Final result",
    )
    row = ml_dataset.observation(item)

    assert row["sequence_length"] == 5
    assert row["plan_step_count"] == 2
    assert row["doubling_event_count"] == 1
    assert row["plan_doubling_step_count"] == 1
    assert row["completed_step_count"] == 1
    assert row["actual_material_record_count"] == 1
    assert row["actual_total_mg"] == pytest.approx(12)
    assert row["doubling_required"] is True
    assert row["actual_yield_percent"] == 66
    assert row["included"] is True


def test_dataset_snapshot_is_content_addressed_and_versioned(tmp_path):
    item = _item(1)
    ml_dataset.review_item(
        item, actual_yield_percent=70, included=True, review_reason="Result 1",
    )
    gui = _Gui(tmp_path, [item])
    first = ml_workflow.build_execution_dataset(gui)
    same = ml_workflow.build_execution_dataset(gui)
    ml_dataset.review_item(
        item, actual_yield_percent=71, included=True, review_reason="Corrected result",
    )
    second = ml_workflow.build_execution_dataset(gui)

    assert first["version"] == 1 and first["created"] is True
    assert same["version"] == 1 and same["created"] is False
    assert second["version"] == 2 and second["created"] is True
    assert first["fingerprint"] != second["fingerprint"]
    manifest = json.loads((tmp_path / "datasets" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["current_version"] == 2
    assert len(manifest["versions"]) == 2
    assert Path(second["path"]).is_file()


def test_real_reviewed_dataset_trains_without_outcome_leakage_and_predicts(tmp_path):
    items = [_item(number) for number in range(1, 7)]
    yields = [82, 78, 74, 70, 65, 58]
    for index, (item, outcome) in enumerate(zip(items, yields), 1):
        ml_dataset.review_item(
            item,
            actual_yield_percent=outcome,
            actual_purity_percent=outcome + 8,
            failure_flag=index == 6,
            doubling_required=index % 2 == 0,
            included=index != 6,
            exclusion_reason="Scale interrupted" if index == 6 else "",
            review_reason="Final reviewed result",
        )
    gui = _Gui(tmp_path, items)
    metrics = ml_workflow.train(gui, "actual_yield_percent", "regression")

    assert metrics["data_source"] == "execution_dataset"
    assert metrics["dataset_version"] == 1
    assert metrics["rows"] == 5
    model_path = Path(metrics["model_path"])
    assert model_path.is_file()
    assert model_path.with_suffix(".metadata.json").is_file()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        bundle = joblib.load(model_path)
    assert not (set(bundle["feature_columns"]) & set(ml_dataset.TARGETS))

    prediction = ml_workflow.predict_active(gui, "actual_yield_percent")
    assert prediction["target"] == "actual_yield_percent"
    assert isinstance(prediction["prediction"], float)


def test_classification_requires_two_real_classes(tmp_path):
    items = [_item(number) for number in range(1, 6)]
    for item in items:
        ml_dataset.review_item(
            item, failure_flag=False, included=True, review_reason="Final result",
        )
    gui = _Gui(tmp_path, items)
    with pytest.raises(ValueError, match="two observed classes"):
        ml_workflow.train(gui, "failure_flag", "classification")


def test_duplicate_keeps_plan_but_not_execution_or_ml_review():
    item = _item(1)
    ml_dataset.review_item(
        item, actual_yield_percent=70, included=True, review_reason="Final result",
    )
    _items, _index, duplicate = peptide_item_collection.duplicate_item([item], 0)
    assert duplicate["selected_plan_rows"] == item["selected_plan_rows"]
    assert "synthesis_execution" not in duplicate
    assert "ml_review" not in duplicate
    assert duplicate["work_item_id"] != item["work_item_id"]
