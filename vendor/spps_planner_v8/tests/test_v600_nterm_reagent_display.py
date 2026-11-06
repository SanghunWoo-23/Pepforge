from __future__ import annotations

from suite_gui.calculation_context import canonical


def test_legacy_nterm_reagent_names_are_canonicalized():
    assert canonical("Ac") == "Acetic anhydride (Ac2O)"
    assert canonical("Acetic anhydride (Ac2O) for N-terminal acetylation") == "Acetic anhydride (Ac2O)"
    assert canonical("Acetic anhydride (Ac2O) for Ac") == "Acetic anhydride (Ac2O)"
    assert canonical("Acetic acid route for N-terminal acetylation") == "Acetic acid"
    assert canonical("Example reagent for N-terminal modification") == "Example reagent"


def test_compound_db_keeps_nterm_purpose_out_of_reagent_name():
    from spps_planner.database import load_compounds

    compounds = load_compounds()
    nterm = compounds[compounds["Class"].astype(str).str.lower().eq("n-term modifier")]
    names = nterm["Reagent/protected form"].fillna("").astype(str).tolist()
    assert all("for n-terminal" not in name.lower() for name in names)

    ac = compounds[compounds["Token"].astype(str).eq("Ac")].iloc[0]
    assert ac["Reagent/protected form"] == "Acetic anhydride (Ac2O)"

    acoh = compounds[compounds["Token"].astype(str).eq("Acetic acid")].iloc[0]
    assert acoh["Reagent/protected form"] == "Acetic acid"


def test_generated_ac_step_uses_exact_reagent_name_only():
    from spps_planner.engine import PlanInput, generate_step_reagent_plan

    plan = generate_step_reagent_plan(
        PlanInput(
            sequence="Ac-EEMARR-NH2",
            resin="Rink Amide AM",
            scale_mmol=0.1,
            resin_loading_mmol_g=0.5,
        )
    )
    protected = plan["protected_reagent"].fillna("").astype(str).tolist()
    assert "Acetic anhydride (Ac2O)" in protected
    assert not any("for N-terminal" in name for name in protected)
