from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PDE = ROOT / "apps" / "peptide_design_engine" / "Python"
sys.path.insert(0, str(PDE))

import ml_trainer
import peptide_engine as pe


def test_modified_candidate_never_gets_canonical_surrogate():
    report = pe.docking_readiness_report(["FITC", "Cha", "AEEA", "dK", "NH2"])
    assert report["docking_surrogate_sequence"] == ""
    assert all(row["canonical_export_fragment"] == "" for row in report["docking_manifest"])


def test_statistical_prior_requires_explicit_reviewed_csv():
    pe.update_config({"USE_ML_PRIOR": True, "ML_PRIOR_TABLE_PATH": ""})
    try:
        pe.ml_prior_score(list("KLVFF"))
    except ValueError as exc:
        assert "explicit user-reviewed CSV" in str(exc)
    else:
        raise AssertionError("Missing prior CSV was accepted")


def test_user_data_model_records_lower_is_better_direction(tmp_path):
    db = tmp_path / "train.csv"
    with db.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["candidate_id", "clean_sequence", "prodigy_kd"])
        writer.writeheader()
        for i, seq in enumerate(["AAAA", "RRRR", "DDDD", "FFFF", "GGGG", "KKKK", "LLLL", "SSSS", "TTTT", "VVVV"]):
            writer.writerow({"candidate_id": i, "clean_sequence": seq, "prodigy_kd": 10 - i})
    model_path = ml_trainer.train_from_csv(db, tmp_path, "prodigy_kd")
    model = json.loads(Path(model_path).read_text(encoding="utf-8"))
    assert model["higher_is_better"] is False
