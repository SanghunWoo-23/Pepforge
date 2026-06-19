from pathlib import Path
import csv

from peptiforg_core.candidate_comparison_dashboard import build_candidate_dashboard, export_candidate_dashboard


def test_build_candidate_dashboard_from_design(tmp_path):
    design = tmp_path / "design.csv"
    with design.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["candidate_id","sequence","total_score"])
        w.writeheader()
        w.writerow({"candidate_id":"PDE_0001","sequence":"AAAA","total_score":"3.2"})
    rows = build_candidate_dashboard(design_candidates_csv=design)
    assert rows
    assert rows[0]["candidate_id"] == "PDE_0001"
    assert "dashboard_score" in rows[0]


def test_dashboard_merges_external_and_exports(tmp_path):
    design = tmp_path / "design.csv"
    ext = tmp_path / "external.csv"
    with design.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["candidate_id","sequence","total_score"])
        w.writeheader()
        w.writerow({"candidate_id":"PDE_0001","sequence":"AAAA","total_score":"3.2"})
    with ext.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["candidate_id","tool","score","direction","normalized_group_rank"])
        w.writeheader()
        w.writerow({"candidate_id":"PDE_0001","tool":"vina","score":"-7.5","direction":"lower_better","normalized_group_rank":"1"})
    paths = export_candidate_dashboard(tmp_path, design_candidates_csv=design, external_docking_scores_csv=ext)
    assert Path(paths["candidate_comparison_dashboard_csv"]).exists()
    assert Path(paths["candidate_comparison_dashboard_md"]).exists()
    assert Path(paths["candidate_dashboard_top_svg"]).exists()
