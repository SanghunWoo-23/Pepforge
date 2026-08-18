import pandas as pd
from suite_gui.docking_workbench_gui import structure_pipeline_df, af3_ready_files, parse_md_xvg


def test_target_sequence_without_coordinates_blocks_local_3d_screening():
    df = structure_pipeline_df("Sequence", "PDB", "MKTFFVLLL", "", None, None)
    assert not df.empty
    screening = df[df["stage"] == "3_3d_screening"].iloc[0]
    assert screening["status"] == "BLOCKED"
    assert "target coordinates" in str(screening["note"]).lower()


def test_af3_ready_files_extract_sequence_text():
    fasta, esm, js, notes = af3_ready_files("MKTFFV", "Ac-EEMQRR-NH2", None)
    assert ">target_A" in fasta
    assert "EEMQRR" in fasta
    assert "Pepforge_AF3_ready_complex" in js
    assert "ESMFold" in notes


def test_parse_external_md_xvg_numeric_series(tmp_path):
    p = tmp_path / "rmsd.xvg"
    p.write_text('@ title "RMSD"\n0 0.1\n1 0.2\n2 0.4\n')
    df = parse_md_xvg(p)
    assert int(df.loc[0, "points"]) == 3
    assert float(df.loc[0, "last_value"]) == 0.4
