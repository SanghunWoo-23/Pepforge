from __future__ import annotations

from pathlib import Path
import importlib.util
import json

import numpy as np
import pytest

from peptiforg_core.simulation_protocol import build_simulation_protocol
from peptiforg_core.structure_consensus import compare_structures


def test_simulation_protocol_structure_guided_and_interaction_only():
    guided = build_simulation_protocol("VRLLREFQEIC", design_mode="STRUCTURE_GUIDED", preferred_structure="ALPHA_HELIX")
    assert guided["minimum_independent_replicates"] == 3
    assert guided["start_state_plan"][0]["state"] == "requested_structure_psb"
    assert len(guided["force_field_sensitivity_candidates"]) >= 2
    interaction = build_simulation_protocol("VRLLREFQEIC", design_mode="INTERACTION_ONLY", preferred_structure="ALPHA_HELIX")
    assert interaction["preferred_structure"] == "NONE"
    assert interaction["start_state_plan"][0]["state"] == "best_clash_free_psb"


def test_structure_consensus_exact_sequence_guard_and_identical_model(tmp_path):
    mdtraj = pytest.importorskip("mdtraj")
    topology = mdtraj.Topology()
    chain = topology.add_chain()
    xyz=[]
    for i, name in enumerate(["ALA", "GLY", "LEU", "SER"]):
        res=topology.add_residue(name, chain, resSeq=i+1)
        for atom_name, element, offset in [("N",mdtraj.element.nitrogen,0.0),("CA",mdtraj.element.carbon,0.12),("C",mdtraj.element.carbon,0.24),("O",mdtraj.element.oxygen,0.32)]:
            topology.add_atom(atom_name, element, res)
            xyz.append([i*0.35+offset,0.0,0.0])
    traj=mdtraj.Trajectory(np.asarray([xyz],dtype=np.float32),topology)
    a=tmp_path/"a.pdb"; b=tmp_path/"b.pdb"; traj.save_pdb(str(a)); traj.save_pdb(str(b))
    result=compare_structures(a,b,tmp_path/"out",name="same")
    assert result["ca_rmsd_A"] < 1e-5
    assert Path(result["zip_path"]).exists()


def test_pde_exports_literature_and_simulation_readiness_fields():
    root=Path(__file__).resolve().parents[1]
    engine=root/"apps"/"peptide_design_engine"/"Python"/"peptide_engine.py"
    spec=importlib.util.spec_from_file_location("pde_sim_test",engine); module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    module.CONFIG["PDE_OBJECTIVE_MODE"]="STRUCTURE_GUIDED"
    module.CONFIG["PREFERRED_STRUCTURE"]="ALPHA_HELIX"
    row=module.candidate_row(list("VRLLREFQEIC"),1,[list("VRLLREFQEIC")])
    assert row["simulation_minimum_independent_replicates"] == 3
    assert "extended_or_independent_challenge" in row["simulation_initial_state_plan"]
    assert row["wimley_white_interface_deltaG_sum_kcal_mol"] is not None
    # This is metadata/reporting; NSGA objectives remain the explicit design-mode contract.
    assert "objective_structure_preference" in row


def test_v4_gui_exposes_static_structure_tools_but_not_md_trajectory_button():
    source=(Path(__file__).resolve().parents[1]/"suite_gui"/"pymol_structure_builder_gui.py").read_text(encoding="utf-8")
    assert 'text="Analyze Trajectory"' not in source
    assert 'text="Compare Structures"' in source
