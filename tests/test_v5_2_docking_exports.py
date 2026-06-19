
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from suite_gui.docking_workbench_gui import peptide_pseudo_model, pseudo_peptide_pdb, analyze_atom_level_contacts


def test_pseudo_pdb_uses_canonical_residue_names():
    df = peptide_pseudo_model("CMP-NH2", "extended")
    pdb = pseudo_peptide_pdb(df)
    assert "CYS" in pdb
    assert "MET" in pdb
    assert "PRO" in pdb
    assert "SEC" not in pdb
    assert "MSE" not in pdb
    assert "HYP" not in pdb


def test_atom_level_contacts_for_imported_pdb_pair(tmp_path):
    target = tmp_path / "target.pdb"
    peptide = tmp_path / "peptide.pdb"
    target.write_text("ATOM      1  CA  ASP A   1       0.000   0.000   0.000  1.00  0.00           C\nEND\n")
    peptide.write_text("ATOM      1  CA  LYS P   1       0.000   0.000   3.500  1.00  0.00           C\nEND\n")
    df = analyze_atom_level_contacts(target, peptide, cutoff_A=4.5)
    assert len(df) >= 1
    assert float(df.iloc[0]["distance_A"]) <= 4.5
    assert df.iloc[0]["contact_class"] in {"contact", "salt_bridge_like", "hydrophobic", "aromatic"}
