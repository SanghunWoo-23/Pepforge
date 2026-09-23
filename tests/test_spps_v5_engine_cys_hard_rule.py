from spps_planner.engine import PlanInput, cleavage_eq_suggestion, generate_cleavage_cocktail


def _inp(sequence: str, *, override: float = 0.0, scale: float = 0.1) -> PlanInput:
    return PlanInput(sequence=sequence, scale_mmol=scale, cleavage_eq_override=override)


def test_engine_cys_hard_rule_one_two_three_cys():
    one = cleavage_eq_suggestion(_inp("ECKGHKKKK"))
    two = cleavage_eq_suggestion(_inp("ACEEEGKCHGKK"))
    three = cleavage_eq_suggestion(_inp("ACCCGG"))
    assert one["cleavage_eq"] == 100.0
    assert two["cleavage_eq"] == 200.0
    assert three["cleavage_eq"] == 300.0
    assert "Cys hard rule" in one["source"]
    assert "Cys hard rule" in two["source"]
    assert "Cys hard rule" in three["source"]


def test_engine_cys_rule_bypasses_length_baseline():
    # 9mer would otherwise be 40 eq, but one Cys is exactly 100 eq, not 140.
    rec = cleavage_eq_suggestion(_inp("ECKGHKKKK"))
    assert rec["length_tokens"] == 9
    assert rec["cys_count"] == 1
    assert rec["cleavage_eq"] == 100.0


def test_engine_manual_override_is_not_double_counted_for_cys():
    # Advisor/manual values arrive through cleavage_eq_override. The engine must
    # use that value exactly and never add another 100 eq/Cys on top of it.
    rec = cleavage_eq_suggestion(_inp("ECKGHKKKK", override=100.0))
    assert rec["cleavage_eq"] == 100.0
    assert rec["source"] == "manual_override"


def test_generated_cocktail_uses_same_cys_eq():
    table = generate_cleavage_cocktail(_inp("ACEEEGKCHGKK", scale=0.1))
    total = table.loc[table["component"] == "Total cocktail"].iloc[0]
    assert float(total["recommended_eq"]) == 200.0
    assert float(total["volume_mL"]) == 20.0
