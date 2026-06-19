from pathlib import Path
from peptiforg_core import rcsb_pdb_bridge as r


def test_infer_rcsb_query_modes():
    assert r.infer_query_mode("1crn") == "pdb_id"
    assert r.infer_query_mode("MKWVTFISLLFLFSSAYSRGVFRRDTHKSEIAHRFKDLGE") == "sequence"
    assert r.infer_query_mode("insulin receptor") == "text"


def test_results_to_rows():
    rows = r.results_to_rows([{"pdb_id":"1CRN","title":"test","experimental_method":"X-RAY","resolution_A":1.5,"match_type":"pdb_id","score":1.0,"source":"mock"}])
    assert rows[0]["pdb_id"] == "1CRN"
    assert rows[0]["method"] == "X-RAY"


def test_download_rcsb_structure_mock(tmp_path, monkeypatch):
    monkeypatch.setattr(r, "_text_get", lambda url: "HEADER MOCK\\nATOM      1  N   GLY A   1       0.0 0.0 0.0\\nEND\\n")
    path = r.download_rcsb_structure("1CRN", tmp_path, "pdb")
    assert Path(path).exists()
    assert "HEADER MOCK" in Path(path).read_text()


def test_normalize_download_format_validation():
    assert r.normalize_pdb_id("1crn") == "1CRN"
    assert r.normalize_pdb_id("bad") == ""
