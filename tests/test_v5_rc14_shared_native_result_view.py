from pathlib import Path
import pandas as pd

from peptiforg_core.docking_result_contract_v1 import combine_normalized_results


def _normalized(model: int):
    return {
        "contract_version":"1.0.0",
        "status":"COMPLETED",
        "engine":"Pepforge Native Docking v1",
        "engine_version":"0.2.0",
        "evidence_grade":"EXPERIMENTAL_NATIVE",
        "claim_guard":"not affinity",
        "poses":pd.DataFrame([{
            "pose_rank":1,"pose_id":"native_pose_01","engine":"Pepforge Native Docking v1",
            "engine_version":"0.2.0","evidence_grade":"EXPERIMENTAL_NATIVE","engine_score":-1.0-model,
            "score_name":"Pepforge Native Docking Score","score_direction":"lower_is_better_within_same_run",
            "quality_status":"PASS","contact_count":4,"clash_count":0,"min_distance_A":2.9,
            "pose_pdb":f"model_{model}.pdb","interaction_evidence_csv":"","claim_guard":"not affinity",
        }]),
        "evidence":pd.DataFrame([{
            "pose_rank":1,"pose_id":"native_pose_01","interaction":"hydrophobic","target_residue":"A:1ALA",
            "peptide_residue":"P:1ALA","target_atoms":"CB","peptide_atoms":"CB","distance_A":4.0,
            "angle_deg":"","plane_angle_deg":"","offset_A":"","vdw_overlap_A":"","geometry_status":"distance_supported",
            "evidence_level":"screening","note":"",
        }]),
    }


def test_combined_result_keeps_models_unique():
    merged=combine_normalized_results([(1,_normalized(1)),(2,_normalized(2))])
    assert len(merged['poses'])==2
    assert set(merged['poses']['pose_id'])=={'m01_native_pose_01','m02_native_pose_01'}
    assert set(merged['evidence']['pose_id'])=={'m01_native_pose_01','m02_native_pose_01'}
    assert list(merged['poses']['model_rank'])==[1,2]
    assert merged['engine']=='Pepforge Native Docking v1'


def test_shared_view_is_used_by_both_guis_and_psb_persists_contract_path():
    root=Path(__file__).resolve().parents[1]
    wb=(root/'suite_gui'/'docking_workbench_gui.py').read_text(encoding='utf-8')
    psb=(root/'suite_gui'/'pymol_structure_builder_gui.py').read_text(encoding='utf-8')
    pipeline=(root/'peptiforg_core'/'psb_v5_full_pipeline.py').read_text(encoding='utf-8')
    panel=(root/'suite_gui'/'shared_native_result_panel.py').read_text(encoding='utf-8')
    assert 'SharedNativeResultPanel' in wb
    assert 'SharedNativeResultPanel' in psb
    assert 'Summary' in panel and 'Poses' in panel and 'Interactions' in panel
    assert 'Mechanics' in panel and 'Trajectory' in panel and 'Provenance' in panel
    assert '"normalized_result": execution.get("normalized_result")' in pipeline
