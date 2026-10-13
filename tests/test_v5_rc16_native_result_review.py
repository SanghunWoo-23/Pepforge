from pathlib import Path
import pandas as pd

from peptiforg_core.native_result_review_v1 import build_pose_review, build_pose_comparison, build_trajectory_review


def _pdb(path: Path, shift=0.0):
    path.write_text(
        f"ATOM      1  CA  ALA A   1       {shift:6.3f}   0.000   0.000  1.00  0.00           C\n"
        f"ATOM      2  CA  GLY P   1       {3+shift:6.3f}   0.000   0.000  1.00  0.00           C\nEND\n",
        encoding="utf-8",
    )


def test_pose_review_and_comparison_artifacts(tmp_path):
    p1=tmp_path/'p1.pdb'; p2=tmp_path/'p2.pdb'; _pdb(p1); _pdb(p2,1.0)
    norm={
        'poses': pd.DataFrame([
            {'pose_id':'native_pose_01','pose_pdb':str(p1)},
            {'pose_id':'native_pose_02','pose_pdb':str(p2)},
        ]),
        'evidence': pd.DataFrame([
            {'pose_id':'native_pose_01','interaction':'hydrogen_bond','target_residue':'A:1ALA','peptide_residue':'P:1GLY','distance_A':3.1},
            {'pose_id':'native_pose_01','interaction':'hydrophobic','target_residue':'A:1ALA','peptide_residue':'P:1GLY','distance_A':4.0},
        ])
    }
    r=build_pose_review(norm,tmp_path/'review',pose_id='native_pose_01',visible_interactions=['hydrogen_bond'])
    assert Path(r['pml']).exists() and Path(r['evidence_csv']).exists()
    ev=pd.read_csv(r['evidence_csv']); assert list(ev['interaction'])==['hydrogen_bond']
    c=build_pose_comparison(norm,tmp_path/'compare',pose_a='native_pose_01',pose_b='native_pose_02')
    text=Path(c['pml']).read_text(encoding='utf-8')
    assert 'pose_A' in text and 'pose_B' in text


def test_trajectory_review_uses_source_frame(tmp_path):
    f0=tmp_path/'frame0.pdb'; f1=tmp_path/'frame1.pdb'; _pdb(f0); _pdb(f1,0.2)
    metrics=tmp_path/'metrics.csv'
    pd.DataFrame([
        {'frame':0,'source_pdb':str(f0),'rmsd_A':0.0,'rg_A':1.5,'cluster':1},
        {'frame':1,'source_pdb':str(f1),'rmsd_A':0.2,'rg_A':1.5,'cluster':1},
    ]).to_csv(metrics,index=False)
    follow={'native_mechanics':{'native_trajectory_analysis':{'frame_metrics_csv':str(metrics),'clusters':[{'medoid_frame':1}]}}}
    r=build_trajectory_review(follow,tmp_path/'traj',frame=None)
    assert r['frame']=='1'
    assert Path(r['pml']).exists()


def test_shared_viewer_rc16_controls_present():
    root=Path(__file__).resolve().parents[1]
    text=(root/'suite_gui'/'shared_native_result_panel.py').read_text(encoding='utf-8')
    for token in ['Interaction filter','Set compare A','Set compare B','Open A/B comparison','3D review','Open selected frame','Open medoid frame']:
        assert token in text
