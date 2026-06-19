from pathlib import Path
from peptiforg_core.publication_validation_report_builder import build_claim_guard_table, compute_publication_readiness, export_publication_validation_report

def test_publication_report_exports(tmp_path):
    paths = export_publication_validation_report("FITC-Cha-AEEA-dK-NH2", tmp_path, "fitc_pub")
    assert Path(paths["publication_validation_report_json"]).exists()
    assert Path(paths["publication_validation_report_md"]).exists()
    assert Path(paths["claim_guard_table"]).exists()
    assert Path(paths["methods_sentence_template"]).exists()

def test_claim_guard_blocks_unsafe_claims():
    rows = build_claim_guard_table()
    blocked = [r for r in rows if r["status"] == "blocked"]
    assert any("true nM binder" in r["unsafe_claim"] for r in blocked)
    assert any("final Kd" in r["unsafe_claim"] for r in blocked)
    assert any("replaces AutoDock" in r["unsafe_claim"] for r in blocked)

def test_publication_readiness_conservative():
    readiness = compute_publication_readiness({}, {}, [])
    assert readiness["publication_readiness_grade"] == "D"
    assert "should not be used for strong claims" in readiness["interpretation"]
