from pathlib import Path
import json
import pytest

from apps.spps_planner_app.spps_planner.engine import PlanInput, generate_step_matrix


def test_spps_nterm_ac_no_standalone_fmoc_removal_before_ac():
    df = generate_step_matrix(PlanInput(sequence="Ac-EEMQRR-NH2", resin="Amide", scale_mmol=0.4))
    units = df["unit"].astype(str).tolist()
    assert units[-1] in {"Ac", "Acetic acid", "Acetyl"}
    assert units.count("Fmoc removal") == 0
    last = df.iloc[-1]
    assert int(last["depro_x"]) >= 1
    assert int(last["reaction_x"]) >= 1


def test_docking_target_resolver_pdb(tmp_path):
    from suite_gui.docking_workbench_gui import resolve_target_input
    pdb = tmp_path / "target.pdb"
    pdb.write_text(
        "ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00  0.00           C\n"
        "ATOM      2  CA  GLY A   2       3.000   0.000   0.000  1.00  0.00           C\n"
        "END\n",
        encoding="utf-8",
    )
    r = resolve_target_input("PDB", pdb, "")
    assert r["status"] == "ok"
    assert r["mode"] == "PDB"
    assert not r["atoms"].empty


def test_docking_target_resolver_sequence_from_path_field():
    from suite_gui.docking_workbench_gui import resolve_target_input
    r = resolve_target_input("PDB", "MKTAYIAKQRQISFVKSHFSRQDILD", "")
    assert r["status"] == "ok"
    assert r["mode"] == "Sequence"
    assert len(r["sequence"]) >= 10


def test_pymol_export_non_ascii_path_if_rdkit_available(tmp_path):
    pytest.importorskip("rdkit")
    from peptiforg_core.pymol_structure_builder import export_modified_peptide_structure
    out = tmp_path / "한글#path"
    paths = export_modified_peptide_structure("Ac-EEMQRR-NH2", out, "modified_peptide")
    assert Path(paths["sdf"]).exists()
    assert Path(paths["pdb"]).exists()
    assert Path(paths["pml"]).exists()
    assert str(out) in paths["sdf"]
