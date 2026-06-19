import pandas as pd
from suite_gui import docking_workbench_gui as dw


def test_affinity_report_uses_one_kd_unit_and_plausible_delta_g():
    poses = pd.DataFrame([{
        "pose_id": "pose_test",
        "score_lower_better": -8.2,
        "contact_count": 12,
        "clash_count": 1,
        "hydrophobic_contacts": 3,
        "electrostatic_contacts": 2,
        "aromatic_contacts": 1,
        "hydrogen_bond_contacts": 2,
        "min_distance_A": 3.4,
    }])
    summary = dw.affinity_summary_df(poses, pd.DataFrame())
    assert (summary["metric"] == "estimated_ΔG").sum() == 1
    assert (summary["metric"] == "estimated_Kd").sum() == 1
    dg = float(summary.loc[summary.metric == "estimated_ΔG", "value"].iloc[0])
    assert -13.5 <= dg <= -1.0
    unit = summary.loc[summary.metric == "estimated_Kd", "unit"].iloc[0]
    assert unit in {"mM", "uM", "nM", "pM", "M"}


def test_affinity_estimator_penalizes_clashes():
    clean = dw._estimate_delta_g_from_contacts(12, 2, 3, 1, 2, 0, 3.4)
    clashing = dw._estimate_delta_g_from_contacts(12, 2, 3, 1, 2, 6, 1.8)
    assert clean < clashing
