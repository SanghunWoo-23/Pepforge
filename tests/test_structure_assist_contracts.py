
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from suite_gui.docking_workbench_gui import clean_sequence, estimate_properties, parse_peptide_notation, parse_pdb_atoms, generate_peptide_structure_points, run_pose_search


def test_acetyl_parsing_does_not_turn_all_caps_ac_into_modifier():
    assert clean_sequence("Ac-EEMQRR-NH2") == "EEMQRR"
    assert clean_sequence("AcEEMQRR-NH2") == "EEMQRR"
    assert clean_sequence("ACDE-NH2") == "ACDE"


def test_estimate_properties_runs():
    df = estimate_properties("Ac-EEMQRR-NH2")
    assert len(df) > 0


def test_cterm_amide_and_conh2_do_not_become_residues():
    assert clean_sequence("EEMQRR-NH2") == "EEMQRR"
    assert clean_sequence("EEMQRR-CONH2") == "EEMQRR"
    assert parse_peptide_notation("Ac-EEMQRR-NH2")["cterm"] == "NH2"
    assert parse_peptide_notation("EEMQRR-CONH2")["cterm"] == "CONH2"


def test_terminal_chemistry_state_is_reported_without_charge_heuristic():
    free = estimate_properties("EEMQRR")
    amidated = estimate_properties("EEMQRR-NH2")
    acetyl_amide = estimate_properties("Ac-EEMQRR-NH2")

    def text_value(df, key):
        return str(df.loc[df.metric == key, "value"].iloc[0])

    assert text_value(free, "n_terminal_modifier") == "free"
    assert text_value(free, "c_terminal_modifier") == "free acid"
    assert text_value(amidated, "c_terminal_modifier") == "NH2"
    assert text_value(acetyl_amide, "n_terminal_modifier") == "Ac"
    assert text_value(acetyl_amide, "c_terminal_modifier") == "NH2"
    assert "net_charge_approx" not in set(free["metric"])


def test_multiletter_tokens_do_not_inflate_structure_core():
    assert clean_sequence("PEG4-EEMQRR-NH2") == "EEMQRR"
    assert clean_sequence("Ahx-EEMQRR-NH2") == "EEMQRR"
    assert clean_sequence("bAla-EEMQRR-NH2") == "AEEMQRR"
    assert clean_sequence("gAla-EEMQRR-NH2") == "GEEMQRR"


def test_structure_builder_geometry_screening_runs_on_minimal_pdb(tmp_path):
    pdb = tmp_path / "target.pdb"
    pdb.write_text("\n".join([
        "ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00  0.00           C",
        "ATOM      2  CA  GLU A   2       4.000   0.000   0.000  1.00  0.00           C",
        "ATOM      3  CA  LYS A   3       0.000   4.000   0.000  1.00  0.00           C",
        "END",
    ]), encoding="utf-8")
    atoms = parse_pdb_atoms(pdb)
    assert len(atoms) == 3
    pep = generate_peptide_structure_points("Ac-EEMQRR-NH2")
    poses, contacts, best = run_pose_search(atoms, pep, pose_limit=8)
    assert not poses.empty
    assert not best.empty
    assert "pose_rank" in poses.columns
    assert "score_lower_better" not in poses.columns
