import pandas as pd
from suite_gui.docking_workbench_gui import structure_pipeline_df, af3_ready_files, parse_gromacs_xvg


def test_target_sequence_peptide_pdb_branch_is_accepted():
    df = structure_pipeline_df("Sequence", "PDB", "MKTFFVLLL", "", None, None)
    assert not df.empty
    assert "READY_TO_PREPARE" in set(df["status"])
    assert any("TARGET:SEQUENCE + PEPTIDE:PDB" in str(x) or "Target is sequence-only" in str(x) for x in df["note"])


def test_af3_ready_files_extract_sequence_text():
    fasta, esm, js, notes = af3_ready_files("MKTFFV", "Ac-EEMQRR-NH2", None)
    assert ">target_A" in fasta
    assert "EEMQRR" in fasta
    assert "Pepforge_AF3_ready_complex" in js
    assert "ESMFold" in notes


def test_parse_gromacs_xvg_numeric_series(tmp_path):
    p = tmp_path / "rmsd.xvg"
    p.write_text('@ title "RMSD"\n0 0.1\n1 0.2\n2 0.4\n')
    df = parse_gromacs_xvg(p)
    assert int(df.loc[0, "points"]) == 3
    assert float(df.loc[0, "last_value"]) == 0.4
