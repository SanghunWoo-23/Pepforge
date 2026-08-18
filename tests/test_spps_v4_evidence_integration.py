from pathlib import Path

from spps_planner.engine import (
    PlanInput,
    generate_cleavage_cocktail,
    generate_step_reagent_plan,
    validate_plan,
)
from spps_planner.parser import parse_sequence
from spps_v4_gui import experimental_data, ml_advisor_v4


def _loading_record(db: Path, amino_acid: str, status: str):
    return experimental_data.add_record(
        "loading",
        {
            "resin_type": "Trityl/2-CTC resin",
            "amino_acid_raw": amino_acid,
            "amino_acid_normalized": amino_acid,
            "aa_eq": 2,
            "base": "DIEA",
            "base_eq": 4,
            "loading_time_h": 4,
            "loading_rate_mmol_g": 0.52,
        },
        db,
        status=status,
    )


def _cleavage_record(db: Path, *, sequence="Ac-AAAAAA-NH2", product="Demo", other="{}"):
    return experimental_data.add_record(
        "cleavage",
        {
            "product": product,
            "sequence": sequence,
            "scale_mmol": 100,
            "tfa_ml": 2850,
            "tis_ml": 0,
            "water_ml": 150,
            "other_scavengers_json": other,
            "cleavage_eq": 30,
            "cleavage_time_h": 3,
        },
        db,
        status="verified",
    )


def test_process_times_do_not_change_stoichiometry():
    base = PlanInput(sequence="AEK", resin="2-CTC", apply_resin_loading=True, loading_aa_eq=2, loading_diea_eq=4)
    timed = PlanInput(sequence="AEK", resin="2-CTC", apply_resin_loading=True, loading_aa_eq=2, loading_diea_eq=4, loading_time_h=4)
    a = generate_step_reagent_plan(base).iloc[0]
    b = generate_step_reagent_plan(timed).iloc[0]
    assert a["planned_reagent_mmol"] == b["planned_reagent_mmol"]
    assert "time=4 h" in str(b["note"])


def test_confirmed_ac_eemqrr_contract_and_literature_guidance_remain_active():
    plan_input = PlanInput(sequence="Ac-EEMQRR-NH2", scale_mmol=0.5)
    cocktail = generate_cleavage_cocktail(plan_input)
    rows = cocktail[cocktail["component"].isin(["TFA", "DW / water"])]
    assert dict(zip(rows["component"], rows["volume_mL"])) == {"TFA": 14.25, "DW / water": 0.75}
    assert "TIS" not in set(cocktail["component"])
    guidance = validate_plan(plan_input)
    assert any(str(value).startswith("literature/") for value in guidance["area"])


def test_parser_keeps_chemistry_tags_linkers_and_case_tolerant_terminal_aliases():
    parsed = parse_sequence("[His6]-[FITC]-ACD-[PEG4]-NH2")
    assert parsed.core_tokens == ["FITC", "A", "C", "D", "PEG4"]
    assert parse_sequence("AC-EEMQRR-NH2").nterm == "Ac"
    assert parse_sequence("PAL-EEMQRR-NH2").nterm == "Pal"
    assert parse_sequence("A-C-NH2").core_tokens[:2] == ["A", "C"]
    assert parse_sequence("P-A-L-NH2").core_tokens[:3] == ["P", "A", "L"]


def test_loading_apply_requires_reviewed_exact_history(tmp_path):
    db = tmp_path / "experimental.sqlite"
    _loading_record(db, "Fmoc-Arg(Pbf)-OH", "parsed")
    parsed = ml_advisor_v4.loading_advice(
        "Trityl/2-CTC resin", "Fmoc-Arg(Pbf)-OH",
        target_loading_mmol_g=0.52, db_path=db, include_parsed=True,
    )
    assert parsed["recommended_condition"] is None
    _loading_record(db, "Fmoc-Lys(Boc)-OH", "verified")
    verified = ml_advisor_v4.loading_advice(
        "Trityl/2-CTC resin", "Fmoc-Lys(Boc)-OH",
        target_loading_mmol_g=0.52, db_path=db, include_parsed=True,
    )
    assert verified["recommended_condition"]["apply_allowed"] is True


def test_cleavage_is_sequence_first_and_empty_sequence_blocks_apply(tmp_path):
    db = tmp_path / "experimental.sqlite"
    _cleavage_record(db)
    same_sequence = ml_advisor_v4.cleavage_advice(
        product="Unrelated label", sequence="Ac-AAAAAA-NH2",
        resin="Rink Amide", scale_mmol=500, db_path=db,
    )
    condition = same_sequence["recommended_condition"]
    assert condition["condition_source"] == "exact_lab_record"
    assert condition["composition_pct"] == {"TFA": 95.0, "Water": 5.0}
    missing = ml_advisor_v4.cleavage_advice(
        product="Demo", sequence="", resin="Rink Amide", scale_mmol=1, db_path=db,
    )
    assert missing["recommended_condition"] is None


def test_unknown_recorded_cocktail_component_blocks_exact_record_apply(tmp_path):
    db = tmp_path / "experimental.sqlite"
    _cleavage_record(db, sequence="Ac-GGGGGG-NH2", product="Blocked", other='{"Unknown scavenger": 1}')
    result = ml_advisor_v4.cleavage_advice(
        product="Blocked", sequence="Ac-GGGGGG-NH2",
        resin="Rink Amide", scale_mmol=1, db_path=db,
    )
    assert result["recommended_condition"].get("condition_source") != "exact_lab_record"
