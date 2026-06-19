from pathlib import Path

from peptiforg_core.binding_site_selector import (
    select_binding_site,
    export_binding_site_selection_package,
    parse_seed_residues,
)


PDB = """HEADER TEST
ATOM      1  N   GLY A   1       0.000   0.000   0.000  1.00 10.00           N
ATOM      2  CA  GLY A   1       1.000   0.000   0.000  1.00 10.00           C
ATOM      3  N   TYR A   2       2.000   0.000   0.000  1.00 10.00           N
ATOM      4  CA  TYR A   2       3.000   0.000   0.000  1.00 10.00           C
ATOM      5  N   LYS B   1      20.000   0.000   0.000  1.00 10.00           N
ATOM      6  CA  LYS B   1      21.000   0.000   0.000  1.00 10.00           C
HETATM    7  C1  LIG A 101       2.500   1.500   0.000  1.00 10.00           C
END
"""


def test_seed_parser():
    assert parse_seed_residues("A:12 B34 56") == [("A","12"), ("B","34"), ("","56")]


def test_binding_site_selector_ligand_and_chain(tmp_path):
    p = tmp_path / "target.pdb"
    p.write_text(PDB)
    result = select_binding_site(p, selected_chains=["A"], ligand_cutoff_A=4.0)
    assert result["summary"]["ligand_or_cofactor_count"] == 1
    assert result["summary"]["final_selected_residue_count"] >= 1
    assert all(r["chain"] == "A" for r in result["selected_site_rows"])


def test_binding_site_export_package(tmp_path):
    p = tmp_path / "target.pdb"
    p.write_text(PDB)
    paths = export_binding_site_selection_package(p, tmp_path, selected_chains=["A"])
    assert Path(paths["selected_binding_site_residues"]).exists()
    assert Path(paths["binding_site_selection_pml"]).exists()
