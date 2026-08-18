import pandas as pd
from suite_gui import docking_workbench_gui as dw

def _poses():
    return pd.DataFrame([{
        'pose_rank':1,'pose_id':'pose_test','conformation':'structure_builder_rigid_body','orientation':'forward_N_to_C',
        'contact_count':12,'centroid_overlap_warnings':1,'hydrophobic_proximities':3,'opposite_charge_proximities':2,
        'aromatic_proximities':1,'polar_residue_proximities':2,'min_centroid_distance_A':3.4,
        'rotation_z_deg':0.,'translation_x_A':0.,'translation_y_A':0.,'translation_z_A':0.,
        'center_x_A':0.,'center_y_A':0.,'center_z_A':0.,'note':'test'
    }])

def test_internal_screening_report_does_not_fabricate_delta_g_or_kd():
    summary=dw.screening_evidence_df(_poses(),pd.DataFrame())
    assert summary.loc[summary.metric=='internal_delta_G','value'].iloc[0]=='not calculated'
    assert summary.loc[summary.metric=='internal_Kd','value'].iloc[0]=='not calculated'
    assert 'geometry_rank_score' not in set(summary['metric'])

def test_weighted_contact_to_affinity_estimator_is_removed():
    assert not hasattr(dw,'_estimate_delta_g_from_contacts')
