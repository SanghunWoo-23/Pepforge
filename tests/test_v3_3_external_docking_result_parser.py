from pathlib import Path
from peptiforg_core.external_docking_result_parser import parse_vina_smina_text, parse_gnina_text, export_external_docking_import_package

def test_parse_vina_table():
    rows = parse_vina_smina_text("   1        -7.5      0.000      0.000\n   2        -6.9      1.200      2.000\n", "PDE_0001_vina.log")
    assert len(rows) == 2 and rows[0]["score"] == -7.5

def test_parse_gnina_score():
    rows = parse_gnina_text("CNNscore: 0.73 CNNaffinity: 7.1", "candidate_gnina.log")
    assert rows and rows[0]["tool"] == "gnina"

def test_export_external_docking_package(tmp_path):
    (tmp_path/"vina.log").write_text("   1        -7.5      0.000      0.000\n", encoding="utf-8")
    paths = export_external_docking_import_package(tmp_path, tmp_path)
    assert Path(paths["external_docking_scores_normalized"]).exists()
    assert Path(paths["external_docking_import_summary"]).exists()
