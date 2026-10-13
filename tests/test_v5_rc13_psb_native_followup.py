from pathlib import Path
import json

from peptiforg_core.quality_preserving_peptide_builder_v1 import build_quality_preserving_peptide
from peptiforg_core.psb_v5_full_pipeline import run_psb_v5_pipeline


def _receptor(path: Path):
    path.write_text(
        "ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  0.00           N\n"
        "ATOM      2  CA  ALA A   1       1.450   0.000   0.000  1.00  0.00           C\n"
        "ATOM      3  C   ALA A   1       2.050   1.400   0.000  1.00  0.00           C\n"
        "ATOM      4  O   ALA A   1       1.500   2.450   0.000  1.00  0.00           O\n"
        "ATOM      5  CB  ALA A   1       1.900  -0.800   1.200  1.00  0.00           C\n"
        "END\n", encoding="utf-8"
    )


def test_psb_native_pipeline_can_run_shared_native_followup(tmp_path):
    rec=tmp_path/'rec.pdb'; _receptor(rec)
    built=build_quality_preserving_peptide('AG',tmp_path/'pep',enable_rdkit=False)
    pep=built['preferred_structure']['pdb']
    meta=tmp_path/'meta.json'
    meta.write_text(json.dumps({
        'input':'AG',
        'top5_conformer_pdb_paths':[pep],
        'conformation_analysis':{'top_conformers':[{'rank':1,'conf_id':1,'family':'native_backbone'}]},
    }),encoding='utf-8')
    payload=run_psb_v5_pipeline(
        meta,rec,tmp_path/'run',model_limit=1,pose_limit_per_model=2,
        docking_backend='native',docking_preset='fast',run_dockbench=False,
        run_native_mechanics_followup=True,native_mechanics_steps=4,execution_mode='offline',
    )
    assert payload['verified_pose_count'] >= 1
    assert payload['status']=='NATIVE_DOCKING_FOLLOWUP_COMPLETED'
    assert len(payload['native_followup_results'])==1
    follow=payload['native_followup_results'][0]
    assert Path(follow['contract_json']).exists()
    assert Path(follow['summary_csv']).exists()
    assert Path(follow['frames_csv']).exists()


def test_psb_gui_exposes_native_followup_controls():
    src=Path('suite_gui/pymol_structure_builder_gui.py').read_text(encoding='utf-8')
    assert 'Run Pepforge Native Mechanics + Trajectory after native docking' in src
    assert 'v5_run_native_followup' in src
    assert 'native_mechanics_steps' in src
