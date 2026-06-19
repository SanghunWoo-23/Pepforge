from pathlib import Path
import pandas as pd
from suite_gui import docking_workbench_gui as dw


def test_d_form_non_natural_chemical_tokens_do_not_block_modeling():
    seq = "Pal-dA-[Hyp]-PEG8-Cit-EEMQRR-NH2"
    model = dw.peptide_pseudo_model(seq)
    compat = dw.peptide_token_compatibility_df(seq)
    assert not model.empty
    assert int(compat.loc[compat.metric == "d_form_beads", "value"].iloc[0]) >= 1
    assert int(compat.loc[compat.metric == "non_natural_beads", "value"].iloc[0]) >= 1
    assert int(compat.loc[compat.metric == "linker_beads", "value"].iloc[0]) >= 1


def test_sequence_target_peptide_pdb_pose_search_runs(tmp_path):
    pep = tmp_path / "pep.pdb"
    pep.write_text("""ATOM      1  CA  GLU P   1       0.000   0.000   0.000  1.00  0.00           C
ATOM      2  CA  GLU P   2       3.800   0.000   0.000  1.00  0.00           C
ATOM      3  CA  ARG P   3       7.600   0.000   0.000  1.00  0.00           C
END
""")
    target_atoms = dw.target_sequence_pseudo_atoms("MKWVTFISLLFLFSSAYSRGVFRRDTHKSEIAHRFKDLGE")
    pep_points = dw.pdb_to_peptide_points(pep)
    poses, contacts, model = dw.run_pose_search(target_atoms, pep_points, "EER")
    summary = dw.affinity_summary_df(poses, contacts)
    assert not poses.empty
    assert not model.empty
    assert not summary.empty
    assert not summary.astype(str).apply(lambda col: col.str.contains("-like|PRODIGY-like|Vina-like|GROMACS-like", case=False, regex=True)).any().any()


def test_legacy_aliases_still_available():
    assert dw.run_vina_like_pose_search is dw.run_pose_search
    assert dw.prodigy_like_summary_df is dw.affinity_summary_df
    assert dw.gromacs_like_md_summary_label is dw.dynamics_summary_label
