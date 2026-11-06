from __future__ import annotations

import pandas as pd

from suite_gui import catalogs
from spps_planner.database import (
    _migrate_user_compounds_if_needed,
    compound_lookup,
    load_compounds,
    validate_compounds_dataframe,
)
from spps_planner.engine import PlanInput, generate_step_matrix, validate_plan
from spps_planner.parser import parse_sequence


def _catalog_names() -> list[str]:
    return [
        *catalogs.FMOC_AA_VALUES,
        *catalogs.FMOC_D_AA_VALUES,
        *catalogs.FMOC_NON_NATURAL_AA_VALUES,
        *catalogs.FMOC_LINKER_VALUES,
    ]


def test_operator_catalog_contains_only_full_fmoc_bottle_names():
    from suite_gui.classic_base import ClassicBaseCore

    names = _catalog_names()
    assert names
    assert all(name.startswith("Fmoc-") for name in names)
    assert len(names) == len(set(names))
    for shorthand in ("A", "Ala", "R", "Arg", "D-R", "D-Arg", "dR", "PEG4", "Ahx"):
        assert shorthand not in catalogs.UNIT_VALUES
    assert "Fmoc-D-Arg(Pbf)-OH" in names
    assert "Fmoc-Gly-OH" in names
    assert "Fmoc-D-Gly-OH" not in names
    assert ClassicBaseCore.FMOC_LINKER_VALUES == catalogs.FMOC_LINKER_VALUES


def test_legacy_operator_names_migrate_without_changing_sequence_syntax():
    assert catalogs.canonical_unit_name("R") == "Fmoc-Arg(Pbf)-OH"
    assert catalogs.canonical_unit_name("D-R") == "Fmoc-D-Arg(Pbf)-OH"
    assert catalogs.canonical_unit_name("dR") == "Fmoc-D-Arg(Pbf)-OH"
    assert catalogs.canonical_unit_name("dG") == "Fmoc-Gly-OH"
    assert catalogs.canonical_unit_name("PEG4") == "Fmoc-NH-PEG4-CH2COOH"
    assert parse_sequence("GHTYKL-NH2").core_tokens == list("GHTYKL")


def test_every_operator_fmoc_choice_has_an_exact_database_row_and_mw():
    compounds = load_compounds()
    issues = validate_compounds_dataframe(compounds)
    assert issues.empty or not issues["level"].eq("ERROR").any()
    lookup = compound_lookup(compounds)
    forbidden = ("placeholder", "default/proxy", "vendor-specific", "verify exact")
    for name in _catalog_names():
        row = lookup.get(name)
        assert row is not None, name
        assert float(row["Reagent MW (g/mol)"]) > 0, name
        protected = str(row["Reagent/protected form"])
        assert protected == name
        joined = " ".join(str(value).lower() for value in row.values())
        assert not any(marker in joined for marker in forbidden), name


def test_exact_d_aa_and_peg_bottle_names_run_through_parser_and_engine():
    cases = {
        "[Fmoc-D-Arg(Pbf)-OH]-A-NH2": ("Fmoc-D-Arg(Pbf)-OH", 648.77),
        "[Fmoc-NH-PEG4-CH2COOH]-A-NH2": ("Fmoc-NH-PEG4-CH2COOH", 473.5),
        "[Fmoc-β-Ala-OH]-A-NH2": ("Fmoc-β-Ala-OH", 311.33),
    }
    for sequence, (name, mw) in cases.items():
        parsed = parse_sequence(sequence)
        assert parsed.core_tokens[0] == name
        matrix = generate_step_matrix(PlanInput(sequence=sequence, scale_mmol=0.1, resin="Rink Amide AM"))
        row = matrix[matrix["protected_reagent"].eq(name)].iloc[0]
        assert float(row["reagent_mw"]) == mw
        validation = validate_plan(PlanInput(sequence=sequence, scale_mmol=0.1, resin="Rink Amide AM"))
        assert not validation["level"].eq("ERROR").any()
        assert not validation["level"].eq("WARNING").any()


def test_user_database_migration_updates_only_old_bundled_defaults(tmp_path):
    bundled_path = tmp_path / "bundled.csv"
    user_path = tmp_path / "user.csv"
    bundled = load_compounds()
    bundled.to_csv(bundled_path, index=False, encoding="utf-8-sig")
    user = bundled.copy()
    peg4 = user["Token"].eq("PEG4")
    user.loc[peg4, "Reagent/protected form"] = "Fmoc-amino-PEG4-acid / vendor-specific"
    user.loc[peg4, "Source used"] = "curated linker policy"
    user = user[~user["Token"].eq("Bpa")].copy()
    pal = user["Token"].eq("Pal")
    user.loc[pal, "Notes"] = "My validated local SOP value"
    user.to_csv(user_path, index=False, encoding="utf-8-sig")

    assert _migrate_user_compounds_if_needed(user_path, bundled_path)
    migrated = pd.read_csv(user_path)
    assert migrated.loc[migrated["Token"].eq("PEG4"), "Reagent/protected form"].iloc[0] == "Fmoc-NH-PEG4-CH2COOH"
    assert migrated["Token"].eq("Bpa").any()
    assert migrated.loc[migrated["Token"].eq("Pal"), "Notes"].iloc[0] == "My validated local SOP value"


def test_restored_and_expanded_operator_catalog_groups_are_visible_without_shorthand():
    assert len(catalogs.AC_AA_VALUES) == 20
    assert "Ac-Ala-OH" in catalogs.UNIT_VALUES
    assert "Ac-Trp(Boc)-OH" in catalogs.UNIT_VALUES
    assert "Fmoc-Cys(Acm)-OH" in catalogs.UNIT_VALUES
    assert "Fmoc-Lys(Dde)-OH" in catalogs.UNIT_VALUES
    assert "Fmoc-D-Lys(ivDde)-OH" in catalogs.UNIT_VALUES
    assert "Fmoc-1-Nal-OH" in catalogs.UNIT_VALUES
    assert "Fmoc-2-Nal-OH" in catalogs.UNIT_VALUES
    assert "Fmoc-D-1-Nal-OH" in catalogs.UNIT_VALUES
    assert "Fmoc-N-Me-Leu-OH" in catalogs.UNIT_VALUES
    assert "5-FAM" in catalogs.UNIT_VALUES
    assert "TAMRA-NHS" in catalogs.UNIT_VALUES
    assert "Biotin-PEG4-NHS" in catalogs.UNIT_VALUES
    assert "His10" in catalogs.UNIT_VALUES
    assert "SpyTag" in catalogs.UNIT_VALUES
    for shorthand in ("Nal", "D-Nal", "MeLeu", "His tag", "FAM dye"):
        assert shorthand not in catalogs.UNIT_VALUES
    assert len(catalogs.UNIT_VALUES) == len(set(catalogs.UNIT_VALUES))


def test_all_new_exact_building_blocks_have_database_rows_and_positive_mw():
    lookup = compound_lookup(load_compounds())
    names = [
        *catalogs.AC_AA_VALUES,
        *catalogs.FMOC_PROTECTED_VARIANT_VALUES,
        *catalogs.FMOC_NON_NATURAL_AA_VALUES,
    ]
    for name in names:
        row = lookup.get(name)
        assert row is not None, name
        assert str(row["Reagent/protected form"]) == name
        assert float(row["Reagent MW (g/mol)"]) > 0
        joined = " ".join(str(value).lower() for value in row.values())
        assert "placeholder" not in joined
        assert "default/proxy" not in joined
        assert "vendor-specific" not in joined


def test_ac_amino_acids_remain_parser_recognised_after_ui_restore():
    parsed = parse_sequence("Ac-Lys(Boc)-OH-A-NH2")
    assert parsed.nterm == "Ac-Lys(Boc)-OH"
    assert parsed.core_tokens == ["A"]
