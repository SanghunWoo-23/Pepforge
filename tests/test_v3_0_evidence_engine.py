from pathlib import Path
import csv
import json

from peptiforg_core.evidence_engine import (
    score_component,
    build_evidence_components,
    summarize_evidence,
    export_evidence_engine_report,
)


def test_evidence_grade_missing_only():
    comps = build_evidence_components()
    summary = summarize_evidence(comps)
    assert summary["evidence_grade"] in {"C", "D"}
    assert "Pepforge proves true nM binding" in summary["blocked_claims"]


def test_evidence_with_target_and_contacts(tmp_path):
    target = tmp_path / "target_quality_warnings.csv"
    with target.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["level","issue","recommendation"])
        w.writeheader()
        w.writerow({"level":"ok","issue":"basic_structure_checks_passed","recommendation":"proceed"})
    contacts = tmp_path / "contacts.csv"
    with contacts.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["a","b"])
        w.writeheader()
        for i in range(10):
            w.writerow({"a":i,"b":i})
    comps = build_evidence_components(target_quality_csv=target, docking_contacts_csv=contacts)
    summary = summarize_evidence(comps)
    assert summary["total_points"] > 0
    assert "target_quality_evidence" not in summary["missing_evidence"]


def test_export_evidence_engine_report(tmp_path):
    paths = export_evidence_engine_report(tmp_path)
    assert Path(paths["evidence_report_md"]).exists()
    assert Path(paths["evidence_summary_json"]).exists()
    assert Path(paths["evidence_claim_guard_table"]).exists()
