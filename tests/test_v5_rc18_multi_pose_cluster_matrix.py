from pathlib import Path
import csv
from peptiforg_core.native_result_compare_v1 import multi_pose_comparison_matrix, export_multi_pose_matrix, trajectory_cluster_rmsd_matrix
from peptiforg_core.native_result_review_v1 import build_gain_loss_review, build_cluster_medoid_montage


def _pdb(path, shift=0.0):
    lines=[]; serial=1
    for chain,resi,res,coords in [('A',1,'ALA',[(0,0,0),(1.5,0,0),(2.5,1,0)]),('P',1,'GLY',[(0,4,0),(1.5,4,0),(2.5,5,0)])]:
        for atom,(x,y,z) in zip(['N','CA','C'],coords):
            lines.append(f"ATOM  {serial:5d} {atom:^4s} {res:>3s} {chain}{resi:4d}    {x+shift:8.3f}{y:8.3f}{z:8.3f}  1.00 20.00           C")
            serial+=1
    path.write_text('\n'.join(lines)+'\nEND\n')

def test_multi_pose_and_gain_loss(tmp_path):
    a=tmp_path/'a.pdb'; b=tmp_path/'b.pdb'; _pdb(a,0); _pdb(b,0.4)
    norm={'poses':[{'pose_id':'p1','pose_pdb':str(a),'engine_score':-2,'quality_status':'PASS'},{'pose_id':'p2','pose_pdb':str(b),'engine_score':-1,'quality_status':'PASS'}],
          'evidence':[{'pose_id':'p1','interaction':'hydrophobic','target_residue':'A:1','peptide_residue':'P:1'},{'pose_id':'p2','interaction':'salt_bridge','target_residue':'A:1','peptide_residue':'P:1'}]}
    m=multi_pose_comparison_matrix(norm)
    assert m['pose_ids']==['p1','p2'] and m['ligand_rmsd_A_matrix'][0][1] is not None
    out=export_multi_pose_matrix(norm,tmp_path/'matrix'); assert Path(out['json']).exists()
    art=build_gain_loss_review(norm,tmp_path/'review',pose_a='p1',pose_b='p2'); assert Path(art['pml']).exists()
    txt=Path(art['pml']).read_text(); assert 'green' in txt and 'red' in txt

def test_cluster_matrix_and_montage(tmp_path):
    f0=tmp_path/'f0.pdb'; f1=tmp_path/'f1.pdb'; _pdb(f0,0); _pdb(f1,0.3)
    metrics=tmp_path/'metrics.csv'
    with metrics.open('w',newline='',encoding='utf-8') as fh:
        w=csv.DictWriter(fh,fieldnames=['frame','rmsd_A','rg_A','cluster','source_pdb']); w.writeheader();
        w.writerow({'frame':0,'rmsd_A':0,'rg_A':3,'cluster':0,'source_pdb':str(f0)}); w.writerow({'frame':1,'rmsd_A':0.2,'rg_A':3.1,'cluster':1,'source_pdb':str(f1)})
    follow={'native_mechanics':{'native_trajectory_analysis':{'frame_metrics_csv':str(metrics),'clusters':[{'cluster':0,'medoid_frame':0},{'cluster':1,'medoid_frame':1}]}}}
    m=trajectory_cluster_rmsd_matrix(follow); assert len(m['clusters'])==2 and m['matrix'][0][1] is not None
    art=build_cluster_medoid_montage(follow,tmp_path/'montage'); assert Path(art['pml']).exists() and 'translate' in Path(art['pml']).read_text()
