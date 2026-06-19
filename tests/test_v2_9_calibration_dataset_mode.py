from pathlib import Path
import csv
import json

from peptiforg_core.calibration_dataset_mode import (
    normalize_affinity_to_nM,
    potency_class_from_nM,
    read_calibration_dataset,
    build_calibration_model,
    predict_candidate_class,
    export_calibration_report,
)


def test_affinity_normalization_and_class():
    assert normalize_affinity_to_nM("0.1", "uM") == 100.0
    assert potency_class_from_nM(5) == "very_strong_nM"
    assert potency_class_from_nM(80) == "strong_nM"


def test_calibration_model_and_prediction(tmp_path):
    p = tmp_path / "cal.csv"
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["target","sequence","affinity_value","affinity_unit","pepforge_score"])
        w.writeheader()
        w.writerow({"target":"T","sequence":"AAA","affinity_value":"5","affinity_unit":"nM","pepforge_score":"-9"})
        w.writerow({"target":"T","sequence":"BBB","affinity_value":"80","affinity_unit":"nM","pepforge_score":"-7"})
        w.writerow({"target":"T","sequence":"CCC","affinity_value":"2","affinity_unit":"uM","pepforge_score":"-4"})
    rows = read_calibration_dataset(p)
    model = build_calibration_model(rows)
    pred = predict_candidate_class(model, "-8")
    assert model["usable_records"] == 3
    assert pred["predicted_class"] in {"very_strong_nM", "strong_nM", "moderate_uM_edge"}


def test_export_calibration_report(tmp_path):
    p = tmp_path / "cal.csv"
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["target","sequence","affinity_value","affinity_unit","pepforge_score"])
        w.writeheader()
        w.writerow({"target":"T","sequence":"AAA","affinity_value":"5","affinity_unit":"nM","pepforge_score":"-9"})
        w.writerow({"target":"T","sequence":"BBB","affinity_value":"80","affinity_unit":"nM","pepforge_score":"-7"})
    paths = export_calibration_report(p, tmp_path, candidate_score="-8")
    assert Path(paths["calibration_report_md"]).exists()
    assert Path(paths["calibration_claim_guard_table"]).exists()
