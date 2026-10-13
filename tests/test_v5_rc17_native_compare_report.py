from pathlib import Path
import json
import pandas as pd

from peptiforg_core.native_result_compare_v1 import compare_poses, trajectory_cluster_summary, export_review_report


def _complex(path: Path, pep_shift: float = 0.0):
    lines=[]; serial=1
    atoms=[
        ('N','ALA','A',1,(0,0,0),'N'),('CA','ALA','A',1,(1.4,0,0),'C'),('C','ALA','A',1,(2.5,0.8,0),'C'),('O','ALA','A',1,(3.6,0.5,0),'O'),
        ('N','GLY','P',1,(2.0+pep_shift,3.0,0),'N'),('CA','GLY','P',1,(3.0+pep_shift,3.0,0),'C'),('C','GLY','P',1,(4.0+pep_shift,3.0,0),'C'),('O','GLY','P',1,(5.0+pep_shift,3.0,0),'O')]
    for name,res,chain,resi,(x,y,z),el in atoms:
        lines.append(f"ATOM  {serial:5d} {name:^4s} {res:>3s} {chain}{resi:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00          {el:>2s}")
        serial+=1
    path.write_text('\n'.join(lines)+'\nEND\n',encoding='utf-8')


def test_pose_quantitative_comparison_and_gain_loss(tmp_path):
    a=tmp_path/'a.pdb'; b=tmp_path/'b.pdb'; _complex(a,0); _complex(b,1.0)
    norm={
        'engine':'Pepforge Native Docking v1',
        'poses':pd.DataFrame([
            {'pose_id':'A','pose_pdb':str(a),'engine_score':-3.0,'quality_status':'PASS'},
            {'pose_id':'B','pose_pdb':str(b),'engine_score':-2.0,'quality_status':'PASS'}]),
        'evidence':pd.DataFrame([
            {'pose_id':'A','interaction':'hydrogen_bond','target_residue':'A:1ALA','peptide_residue':'P:1GLY'},
            {'pose_id':'A','interaction':'hydrophobic','target_residue':'A:1ALA','peptide_residue':'P:1GLY'},
            {'pose_id':'B','interaction':'hydrogen_bond','target_residue':'A:1ALA','peptide_residue':'P:1GLY'},
            {'pose_id':'B','interaction':'salt_bridge','target_residue':'A:1ALA','peptide_residue':'P:1GLY'}])}
    r=compare_poses(norm,'A','B')
    assert 0.95 < r['geometry']['ligand_rmsd_A'] < 1.05
    assert r['interactions']['shared_interactions']==1
    assert abs(r['interactions']['contact_jaccard']-(1/3)) < 1e-9
    assert len(r['interactions']['gained_in_b'])==1
    assert len(r['interactions']['lost_from_a'])==1


def test_cluster_summary_and_report_export(tmp_path):
    metrics=tmp_path/'frames.csv'
    pd.DataFrame([
        {'frame':0,'rmsd_A':0.0,'rg_A':5.0,'cluster':1,'source_pdb':'x0.pdb'},
        {'frame':1,'rmsd_A':0.2,'rg_A':5.2,'cluster':1,'source_pdb':'x1.pdb'},
        {'frame':2,'rmsd_A':1.1,'rg_A':5.5,'cluster':2,'source_pdb':'x2.pdb'},
    ]).to_csv(metrics,index=False)
    follow={'native_mechanics':{'native_trajectory_analysis':{'frame_metrics_csv':str(metrics),'clusters':[{'cluster':1,'medoid_frame':0},{'cluster':2,'medoid_frame':2}]}}}
    rows=trajectory_cluster_summary(follow)
    assert len(rows)==2 and rows[0]['frame_count']==2
    a=tmp_path/'a.pdb'; b=tmp_path/'b.pdb'; _complex(a,0); _complex(b,0.5)
    norm={'engine':'native','poses':pd.DataFrame([{'pose_id':'A','pose_pdb':str(a)},{'pose_id':'B','pose_pdb':str(b)}]),'evidence':pd.DataFrame([])}
    art=export_review_report(norm,[follow],tmp_path/'report',pose_a='A',pose_b='B')
    assert Path(art['markdown']).exists() and Path(art['json']).exists() and Path(art['cluster_csv']).exists()
    payload=json.loads(Path(art['json']).read_text(encoding='utf-8'))
    assert 'pose_comparison' in payload and len(payload['trajectory_clusters'])==2


def test_rc17_viewer_controls_present():
    root=Path(__file__).resolve().parents[1]
    text=(root/'suite_gui'/'shared_native_result_panel.py').read_text(encoding='utf-8')
    for token in ['Compare metrics','Export review report','Open slider frame','contact_jaccard','gained_in_b','lost_from_a']:
        assert token in text


def test_cluster_medoid_comparison_artifact(tmp_path):
    from peptiforg_core.native_result_review_v1 import build_cluster_medoid_comparison
    f0=tmp_path/'f0.pdb'; f1=tmp_path/'f1.pdb'; _complex(f0,0); _complex(f1,0.5)
    metrics=tmp_path/'m.csv'
    pd.DataFrame([{'frame':0,'rmsd_A':0.0,'rg_A':5.0,'cluster':1,'source_pdb':str(f0)},{'frame':1,'rmsd_A':0.5,'rg_A':5.2,'cluster':2,'source_pdb':str(f1)}]).to_csv(metrics,index=False)
    follow={'native_mechanics':{'native_trajectory_analysis':{'frame_metrics_csv':str(metrics),'clusters':[{'cluster':1,'medoid_frame':0},{'cluster':2,'medoid_frame':1}]}}}
    art=build_cluster_medoid_comparison(follow,tmp_path/'medoids')
    assert Path(art['pml']).exists() and Path(art['manifest']).exists()
    text=Path(art['pml']).read_text(encoding='utf-8')
    assert 'cluster_1_medoid' in text and 'cluster_2_medoid' in text
