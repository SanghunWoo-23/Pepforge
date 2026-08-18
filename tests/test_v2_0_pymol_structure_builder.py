
from pathlib import Path

from peptiforg_core.pymol_structure_builder import (
    tokenize_modified_peptide,
    classify_tokens,
    export_modified_peptide_structure,
)

def test_dash_modified_peptide_tokenization():
    toks = tokenize_modified_peptide("FITC-Cha-AEEA-dK-NH2")
    assert toks == ["FITC", "Cha", "AEEA", "dK", "NH2"]

def test_sidechain_biotin_and_pal_rules():
    toks = classify_tokens("K[Biotin]-AEEA-dK-NH2")
    assert toks[0].cls == "side_chain_modified_residue"
    assert "BIOTIN" in toks[0].token.upper()
    pal = classify_tokens("Pal-EEMQRR-NH2")
    assert pal[0].token == "Pal (palmitoyl)"
    assert pal[0].cls == "n_terminal_modifier"
    internal = classify_tokens("EEM-Pal-QRR-NH2")
    assert any("N-terminal" in t.warning for t in internal if t.raw.upper() == "PAL")

def test_export_pymol_readable_files(tmp_path):
    paths = export_modified_peptide_structure("FITC-Cha-AEEA-dK-NH2", tmp_path, "test_pep")
    for key in ("pdb", "sdf", "pml", "csv"):
        assert Path(paths[key]).exists()
    pdb = Path(paths["pdb"]).read_text(encoding="utf-8")
    assert "PEPFORGE PYMOL-READABLE" in pdb
    assert "not a fully parameterized all-atom structure" in pdb
    assert "REMARK TOKEN" in pdb
