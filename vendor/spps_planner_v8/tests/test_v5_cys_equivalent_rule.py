from suite_gui.empirical_cleavage_v5 import cys_equivalent_override, empirical_fallback
from suite_gui.ml_advisor_v5 import _inject_empirical_condition


def test_one_cys_is_exactly_100_eq_regardless_of_length():
    rec = cys_equivalent_override("ECKGHKKKK", scale_mmol=0.2)
    assert rec["cleavage_eq"] == 100.0
    assert rec["empirical_estimate"]["cys_count"] == 1
    assert rec["scaled_total_ml"] == 20.0


def test_two_cys_is_exactly_200_eq_not_length_plus_200():
    rec = empirical_fallback("ACEEEGKCHGKK", scale_mmol=0.2)
    assert rec["cleavage_eq"] == 200.0
    assert rec["cleavage_eq_range"] == [200.0, 200.0]
    assert rec["empirical_estimate"]["cys_count"] == 2
    assert rec["scaled_total_ml"] == 40.0


def test_cys_rule_outranks_an_existing_exact_history_condition():
    existing = {
        "recommended_condition": {"cleavage_eq": 30.0, "condition_source": "exact_lab_record", "apply_allowed": True},
        "warnings": [],
    }
    out = _inject_empirical_condition(existing, sequence="ECKGHKKKK", resin="Rink Amide", scale_mmol=0.1, db_path=None)
    assert out["recommended_condition"]["cleavage_eq"] == 100.0
    assert out["recommended_condition"]["condition_source"] == "operator_cys_rule"
    assert out["confidence"] == "HIGH"


def test_non_cys_still_uses_length_model():
    rec = empirical_fallback("AAAAA", scale_mmol=0.2, db_path=None)
    assert rec["cleavage_eq"] <= 20.0
    assert rec["condition_source"] == "empirical_v5_fallback"
