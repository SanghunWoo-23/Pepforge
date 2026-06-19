from pathlib import Path
import csv

from peptiforg_core.external_md_result_import_bridge import (
    export_external_md_result_import_bridge,
    import_external_md_results,
    summarize_external_md_results,
)


def test_external_md_import_bridge_exports(tmp_path):
    paths = export_external_md_result_import_bridge("FITC-Cha-AEEA-dK-NH2", tmp_path, "fitc_test")
    assert Path(paths["external_md_result_import_template"]).exists()
    assert Path(paths["external_md_validation_summary_json"]).exists()
    assert Path(paths["external_md_claim_guard_table"]).exists()


def test_external_md_result_import_and_summary(tmp_path):
    p = tmp_path / "md.csv"
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "engine", "engine_version", "force_field", "minimization_completed",
            "equilibration_completed", "production_time_ns", "rmsd_A",
            "contact_persistence_fraction", "clash_count_after_refinement", "notes"
        ])
        w.writeheader()
        w.writerow({
            "engine": "OpenMM",
            "engine_version": "8.x",
            "force_field": "example",
            "minimization_completed": "yes",
            "equilibration_completed": "yes",
            "production_time_ns": "10",
            "rmsd_A": "2.4",
            "contact_persistence_fraction": "0.65",
            "clash_count_after_refinement": "1",
            "notes": "smoke test",
        })
    rows = import_external_md_results(p)
    summary = summarize_external_md_results(rows)
    assert summary["import_status"] == "imported"
    assert summary["validation_grade"] in {"A", "B"}
    assert "experimental binding" in summary["safe_interpretation"] or "external" in summary["safe_interpretation"]
