from apps.hotspot_finder.sequence_hotspot_finder.engine import analyze_input
from pathlib import Path


def test_hotspot_general_protein_workflow_no_esm(tmp_path: Path):
    seq = "MKWVTFISLLLLFSSAYSRGVFRRDAHKSEVAHRFKDLGEENFKALVLIAFAQYLQQCPFEDHVK"
    out = analyze_input(seq, token_db_path="apps/hotspot_finder/data/token_db.csv", outdir=tmp_path, config={"use_esm": False, "top_n": 10})
    top = out["top_df"]
    assert not top.empty
    assert len(top) <= 10
    assert "hotspot_score" in top.columns
    assert Path(out["top_csv"]).exists()
