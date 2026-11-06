from __future__ import annotations

from pathlib import Path
import pandas as pd

from spps_planner.engine import PlanInput, generate_materials, generate_step_materials, generate_step_matrix
from suite_gui.calculation_context import canonical, material_lookup


def _last(sequence: str):
    frame = generate_step_matrix(PlanInput(sequence=sequence, scale_mmol=1.0, resin="Rink Amide AM", resin_loading_mmol_g=0.7))
    return frame.iloc[-1]


def test_ac_terminal_unit_uses_exact_canonical_ac2o_name():
    row = _last("Ac-EEMARR-NH2")
    assert row["unit"] == "Ac"
    assert row["protected_reagent"] == "Acetic anhydride (Ac2O)"
    assert float(row["reagent_mw"]) == 102.09


def test_terminal_purpose_prose_is_not_part_of_material_identity():
    expected = {
        "Pal-EEMARR-NH2": "Palmitic acid",
        "Myr-EEMARR-NH2": "Myristic acid",
        "Gal-EEMARR-NH2": "Gallic acid",
        "Nic-EEMARR-NH2": "Nicotinic acid",
        "Caf-EEMARR-NH2": "Caffeic acid",
        "Biotin-EEMARR-NH2": "Biotin acid",
        "FAM-EEMARR-NH2": "FAM",
        "CY5-EEMARR-NH2": "CY5",
        "DOTA-EEMARR-NH2": "DOTA",
    }
    forbidden = (" for n-terminal", " coupling", " / ", "generic /", " route /", " default ")
    for sequence, reagent in expected.items():
        value = str(_last(sequence)["protected_reagent"])
        assert value == reagent, (sequence, value)
        low = value.lower()
        assert not any(text in low for text in forbidden), (sequence, value)


def test_legacy_terminal_names_canonicalize_for_saved_projects():
    assert canonical("Acetic anhydride (Ac2O) for N-terminal acetylation") == "Acetic anhydride (Ac2O)"
    assert canonical("Acetic anhydride (Ac2O) for Ac") == "Acetic anhydride (Ac2O)"
    assert canonical("Palmitic acid / palmitoyl coupling") == "Palmitic acid"
    assert canonical("Biotin acid / default biotinylation acid form") == "Biotin acid"
    mw, density = material_lookup("Acetic anhydride (Ac2O) for N-terminal acetylation")
    assert mw == 102.09
    assert density == 1.08


def test_nterm_modifier_source_forms_are_clean_material_names():
    db_path = Path(__file__).resolve().parents[1] / "apps" / "spps_planner_app" / "data" / "compounds.csv"
    frame = pd.read_csv(db_path)
    rows = frame[frame["Class"].astype(str).str.lower().eq("n-term modifier")]
    forbidden = (" for n-terminal", " coupling", "generic /", " route /", "vendor-form required", " succinyl cap", "biotinylation acid form")
    for _, row in rows.iterrows():
        value = str(row.get("Reagent/protected form", "") or "")
        low = value.lower()
        assert not any(text in low for text in forbidden), (row.get("Token"), value)


def test_generated_terminal_cap_does_not_write_purpose_note():
    for sequence in (
        "Ac-EEMARR-NH2",
        "Pal-EEMARR-NH2",
        "Myr-EEMARR-NH2",
        "Gal-EEMARR-NH2",
        "Nic-EEMARR-NH2",
        "Caf-EEMARR-NH2",
        "Biotin-EEMARR-NH2",
        "FAM-EEMARR-NH2",
        "CY5-EEMARR-NH2",
        "DOTA-EEMARR-NH2",
    ):
        row = _last(sequence)
        assert str(row["phase"]) == "Last / N-term cap"
        assert str(row["note"] or "").strip() == "", (sequence, row["note"])


def test_all_supported_terminal_prefixes_keep_generated_fields_clean():
    db_path = Path(__file__).resolve().parents[1] / "apps" / "spps_planner_app" / "data" / "compounds.csv"
    frame = pd.read_csv(db_path)
    accepted_classes = {"n-term modifier", "label", "tag", "base chem", "chemical"}
    rows = frame[
        frame["Class"].astype(str).str.lower().isin(accepted_classes)
        & frame["Active?"].astype(str).str.lower().eq("yes")
    ]
    forbidden = (
        " for n-terminal",
        "generic / vendor-form required",
        " route /",
        " palmitoyl coupling",
        " myristoyl coupling",
        " stearoyl coupling",
        " oleoyl coupling",
        " nicotinoyl coupling",
        " caffeoyl coupling",
        " galloyl coupling",
        " benzoyl coupling",
        " succinyl cap",
        " biotinylation acid form",
    )
    checked = 0
    for token in rows["Token"].astype(str):
        token = token.strip()
        if not token:
            continue
        generated = generate_step_matrix(
            PlanInput(
                sequence=f"{token}-EEMARR-NH2",
                scale_mmol=0.2,
                resin="Rink Amide AM",
                resin_loading_mmol_g=0.7,
            )
        )
        row = generated.iloc[-1]
        if str(row.get("phase", "")) != "Last / N-term cap":
            continue
        checked += 1
        for field in ("protected_reagent", "coupling_reagent"):
            value = str(row.get(field, "") or "")
            low = value.lower()
            assert not any(text in low for text in forbidden), (token, field, value)
        assert str(row.get("note", "") or "").strip() == "", (token, row.get("note"))
        assert str(row.get("additive", "") or "").strip() == "", (token, row.get("additive"))
    assert checked >= 50


def test_ac_terminal_material_tables_keep_note_and_warning_blank():
    inp = PlanInput(
        sequence="Ac-EEMARR-NH2",
        scale_mmol=0.2,
        resin="Rink Amide AM",
        resin_loading_mmol_g=0.7,
    )
    step_materials = generate_step_materials(inp)
    step_rows = step_materials[step_materials["material"].astype(str).eq("Acetic anhydride (Ac2O)")]
    assert len(step_rows) == 1
    assert str(step_rows.iloc[0].get("note", "") or "").strip() == ""

    totals = generate_materials(inp)
    total_rows = totals[totals["reagent"].astype(str).eq("Acetic anhydride (Ac2O)")]
    assert len(total_rows) == 1
    assert str(total_rows.iloc[0].get("warning", "") or "").strip() == ""
    assert float(total_rows.iloc[0]["MW"]) == 102.09
    assert float(total_rows.iloc[0]["density_g_mL"]) == 1.08
