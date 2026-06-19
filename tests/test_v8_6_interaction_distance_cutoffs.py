import pandas as pd
from suite_gui import docking_workbench_gui as dw


def test_interaction_distance_criteria_are_reported():
    df = dw.interaction_distance_criteria_df()
    assert float(df.loc[df.metric == "hydrogen_bond_DA_cutoff", "value"].iloc[0]) == 3.9
    assert float(df.loc[df.metric == "hydrophobic_contact_cutoff", "value"].iloc[0]) == 5.0
    assert set(df["unit"]) == {"Angstrom"}


def test_affinity_report_includes_hbond_and_hydrophobic_cutoffs():
    poses = pd.DataFrame([{
        "pose_id": "pose_test",
        "score_lower_better": -8.2,
        "contact_count": 12,
        "clash_count": 1,
        "hydrophobic_contacts": 3,
        "hydrogen_bond_contacts": 2,
        "electrostatic_contacts": 2,
        "aromatic_contacts": 1,
        "min_distance_A": 3.4,
    }])
    summary = dw.affinity_summary_df(poses, pd.DataFrame())
    assert "hydrogen_bond_contacts" in set(summary["metric"])
    assert "hydrogen_bond_DA_cutoff" in set(summary["metric"])
    assert "hydrophobic_contact_cutoff" in set(summary["metric"])
    assert (summary[summary.metric == "estimated_Kd"].shape[0]) == 1
