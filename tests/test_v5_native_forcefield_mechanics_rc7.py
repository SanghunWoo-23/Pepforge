from pathlib import Path
import json
import numpy as np

from peptiforg_core.native_peptide_builder_v1 import export_native_backbone
from peptiforg_core.native_topology_v1 import build_native_topology
from peptiforg_core.native_forcefield_v2 import NativeParameterSet, evaluate_native_forcefield
from peptiforg_core.native_mechanics_v2 import NativeMechanicsV2Config, run_native_mechanics_v2


def test_native_forcefield_has_provenance_and_terms(tmp_path):
    built=export_native_backbone("EEMQRR",tmp_path/"b")
    top=build_native_topology(built["pdb"])
    prm=NativeParameterSet()
    force,terms=evaluate_native_forcefield(top,top.coordinates_A,prm)
    assert force.shape==top.coordinates_A.shape
    assert np.isfinite(force).all()
    assert {"bond","angle","torsion_14_proxy","lj_proxy","electrostatic_proxy","total_reduced_score"} <= set(terms)
    meta=prm.metadata()
    assert "not a validated force field" in meta["claim_guard"].lower()
    assert "provenance" in meta


def test_native_forcefield_responds_to_overlap(tmp_path):
    built=export_native_backbone("AAAA",tmp_path/"b")
    top=build_native_topology(built["pdb"])
    _,base=evaluate_native_forcefield(top,top.coordinates_A)
    xyz=top.coordinates_A.copy()
    # Move one nonbonded atom close to another; score should change strongly but remain finite.
    xyz[-1]=xyz[0]+np.array([0.25,0.0,0.0])
    f,bad=evaluate_native_forcefield(top,xyz)
    assert np.isfinite(f).all()
    assert np.isfinite(bad["total_reduced_score"])
    assert abs(bad["total_reduced_score"]-base["total_reduced_score"])>1e-6


def test_native_mechanics_v2_exports_restart_and_analysis(tmp_path):
    built=export_native_backbone("EEMQRR",tmp_path/"b")
    result=run_native_mechanics_v2(built["pdb"],tmp_path/"m",config=NativeMechanicsV2Config(steps=12,save_every=4,dt_reduced=0.0002))
    assert result["status"] in {"COMPLETED","TERMINATED_GUARD"}
    assert Path(result["final_pdb"]).exists()
    assert Path(result["restart_state"]).exists()
    assert result["parameter_set"]["name"]=="PEPFORGE_NATIVE_TRANSPARENT_V2"
    assert result["native_trajectory_analysis"]["status"]=="COMPLETED"
    assert result["evidence_grade"]=="EXPERIMENTAL_NATIVE_MECHANICS_NOT_PRODUCTION_MD"


def test_native_mechanics_v2_restart(tmp_path):
    built=export_native_backbone("AGGA",tmp_path/"b")
    a=run_native_mechanics_v2(built["pdb"],tmp_path/"a",config=NativeMechanicsV2Config(steps=3,save_every=3,dt_reduced=0.0001))
    b=run_native_mechanics_v2(built["pdb"],tmp_path/"c",config=NativeMechanicsV2Config(steps=2,save_every=2,dt_reduced=0.0001),restart_state=a["restart_state"])
    state=json.loads(Path(b["restart_state"]).read_text())
    assert state["step"]==5
