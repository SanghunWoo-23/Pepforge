from pathlib import Path
import pandas as pd
from suite_gui.docking_workbench_gui import parse_pdb_atoms, run_pose_search, sequence_sequence_interaction_df

PDB_TARGET = """ATOM      1  CA  LYS A   1       0.000   0.000   0.000  1.00  0.00           C
ATOM      2  CA  ASP A   2       4.000   0.000   0.000  1.00  0.00           C
ATOM      3  CA  PHE A   3       8.000   0.000   0.000  1.00  0.00           C
ATOM      4  CA  TYR A   4      12.000   0.000   0.000  1.00  0.00           C
END
"""

def test_receptor_anchored_geometry_search_produces_ranked_contacts(tmp_path):
    p=tmp_path/'target.pdb'; p.write_text(PDB_TARGET)
    atoms=parse_pdb_atoms(p)
    pep=pd.DataFrame([
        {'pep_pos':1,'aa':'E','token':'E','token_class':'std_aa','x':0.0,'y':0.0,'z':0.0},
        {'pep_pos':2,'aa':'R','token':'R','token_class':'std_aa','x':3.8,'y':0.0,'z':0.0},
    ])
    poses,contacts,best=run_pose_search(atoms,pep,'ER',pose_limit=10)
    assert not poses.empty and not contacts.empty and len(best)==2
    assert poses.iloc[0]['pose_rank']==1
    assert 'score_lower_better' not in poses.columns
    assert {'centroid_overlap_warnings','opposite_charge_proximities'}.issubset(poses.columns)

def test_sequence_sequence_mode_is_descriptor_only():
    df=sequence_sequence_interaction_df('MKKLLDEFWY','Ac-EEMQRR-NH2')
    assert 'sequence_descriptor_only' in set(df['value'].astype(str))
    assert not any('score' in str(m).lower() for m in df['metric'])
