from __future__ import annotations

import pandas as pd

from suite_gui import material_presentation as presentation


class _Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class _Gui:
    pm_resin = _Var("CTC(합성기)")


def test_resin_labels_preserve_operator_facing_names():
    assert presentation.user_resin_label(_Gui()) == "CTC(합성기)"
    assert presentation.user_resin_label(value="2-CTC") == "2-CTC"
    assert presentation.user_resin_label(value="CTC/Trityl") == "2-CTC"
    assert presentation.user_resin_label(value="") == "Rink Amide AM"


def test_liquid_rules_preserve_explicit_state_and_material_contract():
    assert presentation.is_liquid("DIC")
    assert presentation.is_liquid("unknown", state="solution")
    assert presentation.is_liquid("unknown", cls="Solvent")
    assert presentation.is_liquid("unknown", reagent="DIEA")
    assert not presentation.is_liquid("Fmoc-Ala-OH", state="solid")
    assert not presentation.is_liquid("unknown")


def test_numeric_and_legacy_amount_format_contract():
    assert presentation.numeric("1,234.5") == 1234.5
    assert presentation.numeric("", 7.0) == 7.0
    assert presentation.format_number(3.0) == "3"
    assert presentation.format_number(3.14159, 3) == "3.142"
    assert presentation.extract_ml_from_amount("517 g; 696.765 mL") == 696.765
    assert presentation.extract_ml_from_amount("517 g") == 0.0


def test_operator_table_keeps_liquids_ml_only_and_expands_amino_acids():
    frame = pd.DataFrame([
        {
            "step": 1,
            "material": "DIC",
            "class": "Coupling reagent",
            "planned_g": 2.8,
            "planned_mL": 3.25,
            "unit": "g",
            "total amount": "2.8 g; 3.25 mL",
        },
        {
            "step": 1,
            "material": "A",
            "class": "AA",
            "planned_g": 1.5,
            "unit": "g",
        },
    ])

    result = presentation.clean_operator_table(_Gui(), frame)

    assert result.loc[0, "planned_g"] == ""
    assert result.loc[0, "planned_mL"] == 3.25
    assert result.loc[0, "unit"] == "mL"
    assert result.loc[0, "total amount"] == "3.25 mL"
    assert result.loc[1, "material"] == "Fmoc-Ala-OH"
    assert result.loc[1, "class"] == "AA/Chemical"


def test_protocol_and_total_tables_keep_the_accepted_display_contract():
    frame = pd.DataFrame([
        {"step": "cleavage", "phase": "cleavage", "material": "TFA",
         "class": "Solvent", "planned_mL": 9.5, "unit": "mL"},
        {"step": 1, "phase": "coupling", "material": "DIC",
         "class": "Coupling reagent", "planned_mL": 2.0, "unit": "mL"},
        {"step": "resin", "phase": "resin", "material": "Resin",
         "class": "CTC/Trityl", "planned_g": 1.0, "unit": "g"},
    ])

    ordered = presentation.protocol_order_table(_Gui(), frame)
    total = presentation.total_display_table(_Gui(), frame)

    assert ordered["step"].tolist() == ["resin", 1, "cleavage"]
    assert ordered.iloc[0]["material"] == "CTC(합성기)"
    assert total["material"].tolist() == ["TFA", "DIC", "CTC(합성기)"]
    assert total.iloc[0]["total amount"] == "9.5 mL"
