from apps.spps_planner_app.spps_planner.engine import (
    PlanInput,
    cleavage_eq_suggestion,
    generate_cleavage_cocktail,
    recommend_cleavage_preset,
)


def test_ac_eemqrr_auto_is_30_eq_tfa95_dw5_without_tis():
    inp = PlanInput(
        sequence="Ac-EEMQRR-NH2",
        resin="Amide",
        scale_mmol=0.5,
        cleavage_preset="AUTO",
    )
    assert cleavage_eq_suggestion(inp)["cleavage_eq"] == 30.0
    assert recommend_cleavage_preset(inp)["preset"] == "DEFAULT_TFA_WATER"
    frame = generate_cleavage_cocktail(inp)
    rows = {str(row.component): row for _, row in frame.iterrows()}
    assert float(rows["TFA"]["percent"]) == 95.0
    assert float(rows["DW / water"]["percent"]) == 5.0
    assert "TIS" not in rows
    assert float(rows["Total cocktail"]["volume_mL"]) == 15.0
