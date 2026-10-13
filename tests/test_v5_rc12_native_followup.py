from pathlib import Path
import pandas as pd

from peptiforg_core.quality_preserving_peptide_builder_v1 import build_quality_preserving_peptide
from peptiforg_core.native_docking_v1 import NativeDockingConfig, run_native_docking
from peptiforg_core.docking_result_contract_v1 import normalize_native_docking_result
from peptiforg_core.docking_followup_v1 import select_followup_pose, run_native_docking_followup
from peptiforg_core.native_mechanics_v2 import NativeMechanicsV2Config


def _write_small_receptor(path: Path):
    path.write_text(
        "ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  0.00           N\n"
        "ATOM      2  CA  ALA A   1       1.450   0.000   0.000  1.00  0.00           C\n"
        "ATOM      3  C   ALA A   1       2.050   1.400   0.000  1.00  0.00           C\n"
        "ATOM      4  O   ALA A   1       1.500   2.450   0.000  1.00  0.00           O\n"
        "ATOM      5  CB  ALA A   1       1.900  -0.800   1.200  1.00  0.00           C\n"
        "END\n", encoding="utf-8"
    )


def test_select_followup_pose_prefers_pass_over_warn(tmp_path):
    a=tmp_path/'a.pdb'; b=tmp_path/'b.pdb'; a.write_text('END\n'); b.write_text('END\n')
    norm={'poses':pd.DataFrame([
        {'pose_rank':1,'pose_id':'p1','quality_status':'WARN','pose_pdb':str(a)},
        {'pose_rank':2,'pose_id':'p2','quality_status':'PASS','pose_pdb':str(b)},
    ])}
    chosen=select_followup_pose(norm)
    assert chosen['pose_id']=='p2'


def test_native_followup_runs_mechanics_and_trajectory(tmp_path):
    rec=tmp_path/'rec.pdb'; _write_small_receptor(rec)
    built=build_quality_preserving_peptide('AG',tmp_path/'pep',enable_rdkit=False)
    raw=run_native_docking(rec,built['preferred_structure']['pdb'],tmp_path/'dock',config=NativeDockingConfig(anchor_count=2,rotations_per_anchor=2,max_candidates=12,poses=2,local_refine_steps=0))
    norm=normalize_native_docking_result(raw)
    payload=run_native_docking_followup(norm,tmp_path/'follow',mechanics_config=NativeMechanicsV2Config(steps=4,save_every=2,dt_reduced=0.0001,freeze_receptor=True,peptide_chain='P'))
    assert payload['status'] in {'COMPLETED','TERMINATED_GUARD'}
    assert Path(payload['summary_csv']).exists()
    assert Path(payload['frames_csv']).exists()
    assert Path(tmp_path/'follow'/'native_followup_contract.json').exists()
    mech=payload['native_mechanics']
    assert mech['evidence_grade']=='EXPERIMENTAL_NATIVE_MECHANICS_NOT_PRODUCTION_MD'
    assert mech['native_trajectory_analysis']['status']=='COMPLETED'


def test_workbench_exposes_visible_native_followup_action():
    src=Path('suite_gui/docking_workbench_gui.py').read_text(encoding='utf-8')
    assert 'Run Mechanics + Trajectory' in src
    assert 'def run_native_followup(self):' in src
    assert 'run_native_docking_followup(normalized' in src
    assert 'Dynamics / validation' in src
