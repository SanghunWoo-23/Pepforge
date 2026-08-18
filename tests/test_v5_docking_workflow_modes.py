from pathlib import Path
import pandas as pd
from suite_gui.docking_workbench_gui import sequence_sequence_interaction_df, parse_pdb_atoms, run_pose_search, analyze_pdb_pdb_contacts

PDB_TARGET='''ATOM      1  CA  LYS A   1       0.000   0.000   0.000  1.00  0.00           C\nATOM      2  CA  ASP A   2       4.000   0.000   0.000  1.00  0.00           C\nATOM      3  CA  PHE A   3       8.000   0.000   0.000  1.00  0.00           C\nEND\n'''
PDB_PEP='''ATOM      1  CA  ARG P   1       1.000   0.000   0.000  1.00  0.00           C\nATOM      2  CA  GLU P   2       5.000   0.000   0.000  1.00  0.00           C\nEND\n'''

def test_sequence_sequence_mode_returns_descriptors_only():
    df=sequence_sequence_interaction_df('MKKLLDEFWY','Ac-EEMQRR-NH2')
    assert 'mode' in set(df['metric'])
    assert 'sequence_descriptor_only' in set(df['value'].astype(str))

def test_pdb_sequence_local_geometry_search(tmp_path):
    p=tmp_path/'target.pdb'; p.write_text(PDB_TARGET)
    atoms=parse_pdb_atoms(p)
    pep=pd.DataFrame([{'pep_pos':1,'aa':'E','token':'E','token_class':'std_aa','x':0.,'y':0.,'z':0.}, {'pep_pos':2,'aa':'R','token':'R','token_class':'std_aa','x':3.8,'y':0.,'z':0.}])
    poses,contacts,best=run_pose_search(atoms,pep,'ER')
    assert not poses.empty and {'pose_rank','pose_id','contact_count'}.issubset(poses.columns)
    assert 'score_lower_better' not in poses.columns

def test_pdb_pdb_contact_analysis(tmp_path):
    t=tmp_path/'target.pdb'; t.write_text(PDB_TARGET)
    p=tmp_path/'peptide.pdb'; p.write_text(PDB_PEP)
    poses,contacts=analyze_pdb_pdb_contacts(t,p)
    assert poses.iloc[0]['pose_id']=='imported_pdb'
    assert poses.iloc[0]['pose_rank']==1
    assert 'distance_A' in contacts.columns
