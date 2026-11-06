import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "spps_planner_app"))

from spps_planner.engine import PlanInput, generate_step_matrix, plan_summary
from spps_planner.parser import parse_sequence


def test_std_totals_and_regular_wash_order():
    inp = PlanInput(sequence="Ac-AAAAAA-NH2", scale_mmol=0.4)
    m = generate_step_matrix(inp)
    assert round(float(m["dmf_mL"].sum()), 6) == 304.8
    assert round(float(m["piperidine_mL"].sum()), 6) == 11.2
    regular = m[m["phase"].eq("Regular AA coupling")].iloc[0]
    assert int(regular["dmf_wash_x"]) == 2
    assert int(regular["post_dmf_wash_x"]) == 6


def test_short_peptide_uses_2eq_and_longer_uses_5eq():
    short = generate_step_matrix(PlanInput(sequence="Ac-GHKKK-NH2", scale_mmol=0.4))
    aa_short = short[short["phase"].isin(["Loading", "Regular AA coupling"])]
    assert set(aa_short["reagent_eq"].astype(float)) == {2.0}
    assert set(aa_short["reagent_eq_source"]) == {"length_rule_1_5_mer"}

    longer = generate_step_matrix(PlanInput(sequence="Ac-GHKKKA-NH2", scale_mmol=0.4))
    aa_long = longer[longer["phase"].isin(["Loading", "Regular AA coupling"])]
    assert set(aa_long["reagent_eq"].astype(float)) == {5.0}
    assert set(aa_long["reagent_eq_source"]) == {"global_aa"}


def test_branch_sequence_is_not_silently_dropped():
    parsed = parse_sequence("Ac-G-H-K-K-K(GGEP)-NH2")
    assert parsed.core_tokens == ["G", "H", "K", "K", "K"]
    assert parsed.branch_tokens == ["G", "G", "E", "P"]
    m = generate_step_matrix(PlanInput(sequence="Ac-G-H-K-K-K(GGEP)-NH2", scale_mmol=0.4))
    assert "Branch AA coupling" in set(m["phase"])
    assert plan_summary(PlanInput(sequence="Ac-G-H-K-K-K(GGEP)-NH2", scale_mmol=0.4))["branch_count"] == 1


def test_acetylated_amino_acid_modifier_is_parsed_without_runtime_patch():
    parsed = parse_sequence("Ac-Glu(OtBu)-OH-GHTYKL-NH2")
    assert parsed.nterm == "Ac-Glu(OtBu)-OH"
    assert parsed.core_tokens == ["G", "H", "T", "Y", "K", "L"]


def test_free_nterm_final_deprotection_is_counted():
    m = generate_step_matrix(PlanInput(sequence="GHK-NH2", scale_mmol=0.4))
    final = m.iloc[-1]
    assert final["unit"] == "Fmoc removal"
    assert final["phase"] == "Final free N-term deprotection"
    assert int(final["depro_x"]) == 2
    assert int(final["post_dmf_wash_x"]) == 3
    assert int(final["dcm_wash_x"]) == 3


def test_cterm_resin_conflict_warning_and_hbtu_diea_guard():
    summary = plan_summary(PlanInput(sequence="Ac-AAAAAA-OH", resin="Amide", scale_mmol=0.4))
    assert "conflicts" in summary["warnings"]

    m = generate_step_matrix(PlanInput(sequence="Ac-GHK-NH2", scale_mmol=0.4, default_coupling_reagent="HBTU", default_catalyst="HOBt", default_base=""))
    aa = m[m["phase"].isin(["Loading", "Regular AA coupling"])]
    assert set(aa["base"]) == {"DIEA"}
    assert set(aa["catalyst"]) == {""}

from spps_planner.engine import generate_materials, validate_plan, generate_cleavage_cocktail
from spps_planner.export import export_csvs, export_excel


def test_materials_include_auxiliary_reagent_amounts_and_totals():
    mats = generate_materials(PlanInput(sequence="Ac-GHK-NH2", scale_mmol=1.0))
    dmf = mats[mats["material"].eq("DMF")].iloc[0]
    assert float(dmf["planned_mL"]) > 0
    dic = mats[mats["material"].eq("DIC")]
    hobt = mats[mats["material"].eq("HOBt")]
    diea = mats[mats["material"].eq("DIEA")]
    assert not dic.empty and str(dic.iloc[0]["planned_g"]).strip() in {"", "0", "0.0"} and float(dic.iloc[0]["planned_mL"]) > 0 and dic.iloc[0]["unit"] == "mL"
    assert not hobt.empty and float(hobt.iloc[0]["planned_g"]) > 0
    assert not diea.empty and str(diea.iloc[0]["planned_g"]).strip() in {"", "0", "0.0"} and float(diea.iloc[0]["planned_mL"]) > 0 and diea.iloc[0]["unit"] == "mL"


def test_validation_flags_manual_required_generic_label():
    v = validate_plan(PlanInput(sequence="CY5-GHK-NH2", scale_mmol=1.0))
    text = " ".join(v["message"].astype(str).tolist())
    assert "Generic/manual-required" in text or "manual" in text.lower()


def test_export_writes_validation_sheet_and_csv(tmp_path):
    inp = PlanInput(sequence="Ac-GHK-NH2", scale_mmol=1.0)
    export_csvs(inp, tmp_path)
    assert (tmp_path / "validation_warnings.csv").exists()
    assert (tmp_path / "cleavage_cocktail.csv").exists()
    out = tmp_path / "spps_plan.xlsx"
    export_excel(inp, out)
    assert out.exists() and out.stat().st_size > 0


def test_cleavage_cocktail_explicit_function_and_cys_rule():
    std = generate_cleavage_cocktail(PlanInput(sequence="Ac-AAAAAA-NH2", scale_mmol=0.4))
    total = std[std["component"].eq("Total cocktail")].iloc[0]
    assert float(total["recommended_eq"]) == 30.0
    assert float(total["volume_mL"]) > 0
    components = {str(row["component"]): float(row["percent"]) for _, row in std.iterrows() if str(row.get("include", "")).upper() == "YES" and str(row["component"]) != "Total cocktail"}
    assert components == {"TFA": 95.0, "TIS": 2.5, "DW / water": 2.5}

    cys = generate_cleavage_cocktail(PlanInput(sequence="Ac-CCCCCC-NH2", scale_mmol=0.4))
    assert float(cys[cys["component"].eq("Total cocktail")].iloc[0]["recommended_eq"]) == 600.0  # Cys hard rule: 6 x 100 eq; no length-baseline addition


def test_compound_database_has_no_case_duplicate_biotin():
    from spps_planner.database import load_compounds, audit_compound_database
    df = load_compounds()
    norm = df["Token"].fillna("").astype(str).str.strip().str.lower()
    assert norm.eq("biotin").sum() == 1
    audit = audit_compound_database(df)
    assert not ((audit["issue"].astype(str).str.contains("Duplicate token", na=False)) & (audit["item"].astype(str).str.lower().str.contains("biotin", na=False))).any()
