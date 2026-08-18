import pandas as pd
from suite_gui import docking_workbench_gui as dw

def test_interaction_distance_criteria_are_reported():
    df=dw.interaction_distance_criteria_df()
    assert float(df.loc[df.metric=='hydrogen_bond_DA_cutoff','value'].iloc[0])==3.9
    assert float(df.loc[df.metric=='hydrophobic_contact_cutoff','value'].iloc[0])==5.0
    assert set(df['unit'])=={'Angstrom'}

def test_screening_evidence_labels_centroid_proximities_not_hbonds():
    poses=pd.DataFrame([{
        'pose_rank':1,'pose_id':'pose_test','contact_count':12,'centroid_overlap_warnings':1,
        'hydrophobic_proximities':3,'opposite_charge_proximities':2,'aromatic_proximities':1,
        'polar_residue_proximities':2,'min_centroid_distance_A':3.4
    }])
    summary=dw.screening_evidence_df(poses,pd.DataFrame())
    metrics=set(summary['metric'])
    assert 'polar_residue_proximities' in metrics
    assert 'hydrogen_bond_contacts' not in metrics
    assert summary.loc[summary.metric=='internal_Kd','value'].iloc[0]=='not calculated'
