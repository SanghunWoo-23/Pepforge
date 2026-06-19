
from pathlib import Path
import pandas as pd
from suite_gui.docking_workbench_gui import (
    sequence_sequence_interaction_df,
    parse_pdb_atoms,
    run_lightweight_docking,
    analyze_pdb_pdb_contacts,
)

PDB_TARGET = """ATOM      1  CA  LYS A   1       0.000   0.000   0.000  1.00  0.00           C
ATOM      2  CA  ASP A   2       4.000   0.000   0.000  1.00  0.00           C
ATOM      3  CA  PHE A   3       8.000   0.000   0.000  1.00  0.00           C
END
"""
PDB_PEP = """ATOM      1  CA  ARG P   1       1.000   0.000   0.000  1.00  0.00           C
ATOM      2  CA  GLU P   2       5.000   0.000   0.000  1.00  0.00           C
END
"""

def test_sequence_sequence_mode_returns_heuristic():
    df = sequence_sequence_interaction_df("MKKLLDEFWY", "Ac-EEMQRR-NH2")
    assert "interaction_heuristic_score" in set(df["metric"])


def test_pdb_sequence_lightweight_docking(tmp_path):
    p = tmp_path / "target.pdb"
    p.write_text(PDB_TARGET)
    atoms = parse_pdb_atoms(p)
    poses, contacts, pep = run_lightweight_docking(atoms, "EEMQRR")
    assert len(poses) >= 1
    assert set(["pose_id", "score_lower_better", "contact_count"]).issubset(poses.columns)
    assert len(pep) == 6


def test_pdb_pdb_contact_analysis(tmp_path):
    t = tmp_path / "target.pdb"; t.write_text(PDB_TARGET)
    p = tmp_path / "peptide.pdb"; p.write_text(PDB_PEP)
    poses, contacts = analyze_pdb_pdb_contacts(t, p)
    assert poses.iloc[0]["pose_id"] == "imported_pdb"
    assert "distance_A" in contacts.columns
