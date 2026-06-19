from suite_gui.docking_workbench_gui import parse_pdb_atoms, peptide_pseudo_model, run_builtin_md_lite


def test_builtin_md_lite_generates_frames():
    pdb = """ATOM      1  CA  ASP A   1       0.000   0.000   0.000  1.00  0.00           C
ATOM      2  CA  LEU A   2       4.000   0.000   0.000  1.00  0.00           C
END
"""
    import tempfile, pathlib
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d) / "target.pdb"
        p.write_text(pdb)
        atoms = parse_pdb_atoms(p)
        pep = peptide_pseudo_model("KLV", "extended")
        summary, frames, final_model, traj = run_builtin_md_lite(atoms, pep, steps=20, sample_every=5)
        assert not summary.empty
        assert not frames.empty
        assert not final_model.empty
        assert "MODEL" in traj
