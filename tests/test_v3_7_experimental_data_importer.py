from pathlib import Path
import csv
from peptiforg_core.experimental_data_importer import normalize_unit_to_nm, potency_class_from_nm, export_experimental_import_package
from peptiforg_core.candidate_comparison_dashboard import build_candidate_dashboard

def test_unit_normalization():
    assert normalize_unit_to_nm("0.1", "uM") == 100.0
    assert potency_class_from_nm(50) == "strong_nM"

def test_experimental_import_package(tmp_path):
    p = tmp_path / "assay.csv"
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["candidate_id","sequence","target","assay_type","value_type","value","unit"])
        w.writeheader(); w.writerow({"candidate_id":"PDE_0001","sequence":"AAAA","target":"T","assay_type":"SPR","value_type":"Kd","value":"85","unit":"nM"})
    paths = export_experimental_import_package(p, tmp_path)
    assert Path(paths["experimental_candidate_summary"]).exists()
    assert Path(paths["experimental_import_report"]).exists()

def test_dashboard_accepts_experimental_summary(tmp_path):
    design = tmp_path / "design.csv"; exp = tmp_path / "exp_summary.csv"
    with design.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["candidate_id","sequence","total_score"]); w.writeheader(); w.writerow({"candidate_id":"PDE_0001","sequence":"AAAA","total_score":"1"})
    with exp.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["candidate_id","median_nM","potency_class","n"]); w.writeheader(); w.writerow({"candidate_id":"PDE_0001","median_nM":"85","potency_class":"strong_nM","n":"2"})
    rows = build_candidate_dashboard(design_candidates_csv=design, experimental_candidate_summary_csv=exp)
    assert rows[0]["experimental_potency_class"] == "strong_nM"
