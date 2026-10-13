from pathlib import Path
import pandas as pd

from peptiforg_core.docking_result_contract_v1 import (
    normalize_native_docking_result, evidence_to_workbench_contacts,
    normalized_to_workbench_poses, export_normalized_result,
)


def test_native_result_normalizes_and_exports(tmp_path: Path):
    ev = tmp_path / "ev.csv"
    pd.DataFrame([{
        "interaction":"salt_bridge","target_residue":"A:2LYS","peptide_residue":"P:4GLU",
        "target_atoms":"NZ","peptide_atoms":"OE1/OE2","distance_A":3.2,
        "angle_deg":"","plane_angle_deg":"","offset_A":"","vdw_overlap_A":"",
        "geometry_status":"opposite_charge_group_centers","evidence_level":"geometry_supported","note":"direct",
    }]).to_csv(ev,index=False)
    payload={
        "status":"COMPLETED","engine":"Pepforge Native Docking v1","version":"0.2.0",
        "evidence_grade":"EXPERIMENTAL_NATIVE","claim_guard":"not affinity",
        "poses":[{"rank":1,"pepforge_native_score":-2.5,"clash_count":0,"min_distance_A":2.8,
                  "contact_count":7,"pose_pdb":str(tmp_path/'pose.pdb'),"interaction_evidence_csv":str(ev),
                  "quality_gate":{"status":"PASS"}}],
    }
    n=normalize_native_docking_result(payload)
    assert len(n["poses"])==1 and len(n["evidence"])==1
    assert n["poses"].iloc[0]["quality_status"]=="PASS"
    contacts=evidence_to_workbench_contacts(n["evidence"])
    assert contacts.iloc[0]["interaction"]=="salt_bridge"
    assert contacts.iloc[0]["target_chain"]=="A"
    workposes=normalized_to_workbench_poses(n)
    assert workposes.iloc[0]["opposite_charge_proximities"]==1
    paths=export_normalized_result(n,tmp_path/"export")
    assert all(Path(p).exists() for p in paths.values())

def test_workbench_defaults_to_native_engine_and_uses_shared_contract():
    root=Path(__file__).resolve().parents[1]
    src=(root/'suite_gui'/'docking_workbench_gui.py').read_text(encoding='utf-8')
    assert 'self.docking_engine=tk.StringVar(value="Pepforge Native")' in src
    assert 'values=["Pepforge Native","Legacy Geometry Screen"]' in src
    assert 'run_native_docking(target_path, pep_path' in src
    assert 'normalize_native_docking_result(raw)' in src
    assert 'export_normalized_result(normalized' in src
    assert 'Run Docking / Screening' in src

def test_psb_pipeline_exports_shared_native_contract():
    root=Path(__file__).resolve().parents[1]
    src=(root/'peptiforg_core'/'psb_v5_full_pipeline.py').read_text(encoding='utf-8')
    assert 'normalize_native_docking_result(native)' in src
    assert 'export_normalized_result(normalized_native' in src
    assert 'docking_result_contract_version' in src
