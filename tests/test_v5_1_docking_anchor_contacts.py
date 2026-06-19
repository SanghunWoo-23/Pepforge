
from pathlib import Path
from suite_gui.docking_workbench_gui import parse_pdb_atoms, run_lightweight_docking, sequence_sequence_interaction_df

PDB_TARGET = """ATOM      1  CA  LYS A   1       0.000   0.000   0.000  1.00  0.00           C
ATOM      2  CA  ASP A   2       4.000   0.000   0.000  1.00  0.00           C
ATOM      3  CA  PHE A   3       8.000   0.000   0.000  1.00  0.00           C
ATOM      4  CA  TYR A   4      12.000   0.000   0.000  1.00  0.00           C
END
"""

def test_receptor_anchored_pseudo_docking_produces_contacts(tmp_path):
    p = tmp_path / "target.pdb"
    p.write_text(PDB_TARGET)
    atoms = parse_pdb_atoms(p)
    poses, contacts, pep = run_lightweight_docking(atoms, "Ac-EEMQRR-NH2")
    assert len(poses) >= 1
    assert poses["contact_count"].astype(int).max() >= 1
    assert len(contacts) >= 1
    assert len(pep) == 6

def test_sequence_sequence_mode_remains_labeled_as_heuristic():
    df = sequence_sequence_interaction_df("MKKLLDEFWY", "Ac-EEMQRR-NH2")
    notes = " ".join(df["note"].astype(str).tolist()).lower()
    assert "heuristic" in notes or "no 3d" in notes
