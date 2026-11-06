from pathlib import Path
import sqlite3

from suite_gui import experimental_data
from suite_gui.decision_support import attach_evidence_trace
from suite_gui.recommendation import loading


def _add(db: Path, aa: str, value: float, *, aa_eq: float = 2.0, base_eq: float = 4.0, date: str = "2026-01-01"):
    return experimental_data.add_record(
        "loading",
        {
            "date": date,
            "resin_type": "Trityl/2-CTC resin",
            "amino_acid_raw": aa,
            "amino_acid_normalized": aa,
            "aa_eq": aa_eq,
            "base": "DIEA",
            "base_eq": base_eq,
            "loading_time_h": 4.0,
            "loading_rate_mmol_g": value,
            "capping_performed": 1,
            "capping_method": "recorded capping",
        },
        db,
        status="verified",
    )


def test_data_supported_special_loading_aliases_are_canonicalized_without_cross_family_merging():
    assert experimental_data.normalize_amino_acid("Cit") == "Fmoc-Cit-OH"
    assert experimental_data.normalize_amino_acid("Hyp") == "Fmoc-Hyp(tBu)-OH"
    assert experimental_data.normalize_amino_acid("Dab") == "Fmoc-Dab(Boc)-OH"
    assert experimental_data.canonical_amino_acid_key("Cit") != experimental_data.canonical_amino_acid_key("Arg")
    assert experimental_data.canonical_amino_acid_key("Hyp") != experimental_data.canonical_amino_acid_key("Pro")


def test_d_form_shorthand_is_recognized_and_kept_separate_from_l_form():
    for alias in ("dL", "D-L", "D-Leu", "(D)Leu"):
        assert experimental_data.normalize_amino_acid(alias) == "Fmoc-D-Leu-OH"
    for alias in ("dF", "D-Phe", "(D)Phe"):
        assert experimental_data.normalize_amino_acid(alias) == "Fmoc-D-Phe-OH"
    for alias in ("dH", "D-His", "(D)His", "D-His(Trt)"):
        assert experimental_data.normalize_amino_acid(alias) == "Fmoc-D-His(Trt)-OH"
    assert experimental_data.normalize_amino_acid("D-Lys(Boc)") == "Fmoc-D-Lys(Boc)-OH"
    assert experimental_data.normalize_amino_acid("dG") == "dG"  # Gly is achiral; do not invent D-Gly.
    assert experimental_data.canonical_amino_acid_key("D-Leu") != experimental_data.canonical_amino_acid_key("Leu")
    assert experimental_data.describe_amino_acid_identity("D-Leu")["category"] == "D-form"


def test_cit_hyp_and_dab_queries_use_only_exact_normalized_history(tmp_path: Path):
    db = tmp_path / "special.sqlite"
    experimental_data.initialize(db)
    _add(db, "Fmoc-Cit-OH", 0.67, date="2026-01-01")
    _add(db, "Fmoc-Cit-OH", 0.69, date="2026-01-02")
    _add(db, "Fmoc-Hyp(tBu)-OH", 0.80, date="2026-01-03")
    _add(db, "Fmoc-Hyp(tBu)-OH", 0.84, date="2026-01-04")
    _add(db, "Fmoc-Dab(Boc)-OH", 0.54, aa_eq=0.625, base_eq=2.5, date="2026-01-05")

    cit = loading.advise(resin="2-CTC", amino_acid="Cit", aa_eq=2, base_eq=4, loading_time_h=4, target_loading_mmol_g=0.68, db_path=db)
    hyp = loading.advise(resin="2-CTC", amino_acid="Hyp", aa_eq=2, base_eq=4, loading_time_h=4, target_loading_mmol_g=0.82, db_path=db)
    dab = loading.advise(resin="2-CTC", amino_acid="Dab", aa_eq=0.625, base_eq=2.5, loading_time_h=4, target_loading_mmol_g=0.54, db_path=db)

    assert cit["amino_acid_identity"]["normalized"] == "Fmoc-Cit-OH"
    assert cit["exact_evidence_profile"]["exact_record_count"] == 2
    assert hyp["amino_acid_identity"]["normalized"] == "Fmoc-Hyp(tBu)-OH"
    assert hyp["exact_evidence_profile"]["exact_record_count"] == 2
    assert dab["amino_acid_identity"]["normalized"] == "Fmoc-Dab(Boc)-OH"
    assert dab["exact_evidence_profile"]["exact_record_count"] == 1


def test_d_form_advisor_never_borrows_corresponding_l_form_history(tmp_path: Path):
    db = tmp_path / "stereo.sqlite"
    experimental_data.initialize(db)
    _add(db, "Fmoc-Leu-OH", 0.70, date="2026-01-01")
    _add(db, "Fmoc-Leu-OH", 0.72, date="2026-01-02")
    _add(db, "Fmoc-D-Leu-OH", 0.86, date="2026-01-03")

    d_result = loading.advise(resin="2-CTC", amino_acid="dL", aa_eq=2, base_eq=4, loading_time_h=4, target_loading_mmol_g=0.86, db_path=db)
    l_result = loading.advise(resin="2-CTC", amino_acid="L", aa_eq=2, base_eq=4, loading_time_h=4, target_loading_mmol_g=0.71, db_path=db)

    assert d_result["amino_acid_identity"]["stereochemistry"] == "D"
    assert d_result["exact_evidence_profile"]["exact_record_count"] == 1
    assert l_result["exact_evidence_profile"]["exact_record_count"] == 2
    assert {row["amino_acid_normalized"] for row in d_result["evidence"]} == {"Fmoc-D-Leu-OH"}

def test_observed_identity_picklist_is_derived_from_records_and_canonicalized():
    rows = [
        {"amino_acid_normalized": "Cit"},
        {"amino_acid_raw": "D-Leu"},
        {"amino_acid_normalized": "Fmoc-D-Leu-OH"},
        {"amino_acid_raw": ""},
    ]
    assert experimental_data.observed_loading_amino_acid_identities(rows) == [
        "Fmoc-Cit-OH", "Fmoc-D-Leu-OH"
    ]


def test_lookup_key_migration_rekeys_legacy_d_form_alias_without_mutating_raw_history(tmp_path: Path):
    db = tmp_path / "legacy.sqlite"
    experimental_data.initialize(db)
    record_id = _add(db, "Fmoc-D-Leu-OH", 0.86)["record_id"]
    with sqlite3.connect(db) as con:
        con.execute(
            "UPDATE loading_records SET amino_acid_raw='D-Leu', amino_acid_normalized='D-Leu', amino_acid_key='d-leu' WHERE record_id=?",
            (record_id,),
        )
        con.execute(
            "INSERT INTO experimental_meta(meta_key,meta_value) VALUES('lookup_backfill_version','1') "
            "ON CONFLICT(meta_key) DO UPDATE SET meta_value='1'"
        )
    experimental_data._INITIALIZED_DB_PATHS.clear()
    experimental_data.initialize(db)
    with sqlite3.connect(db) as con:
        row = con.execute(
            "SELECT amino_acid_raw,amino_acid_normalized,amino_acid_key FROM loading_records WHERE record_id=?",
            (record_id,),
        ).fetchone()
        version = con.execute(
            "SELECT meta_value FROM experimental_meta WHERE meta_key='lookup_backfill_version'"
        ).fetchone()[0]
    assert row[0] == "D-Leu"
    assert row[1] == "D-Leu"  # raw historical normalized text is preserved
    assert row[2] == experimental_data.canonical_amino_acid_key("D-Leu")
    assert int(version) == experimental_data._LOOKUP_BACKFILL_VERSION


def test_observed_repeated_condition_trace_is_exact_experimental_match(tmp_path: Path):
    db = tmp_path / "trace.sqlite"
    experimental_data.initialize(db)
    _add(db, "Fmoc-Cit-OH", 0.67, date="2026-01-01")
    _add(db, "Fmoc-Cit-OH", 0.69, date="2026-01-02")
    result = loading.advise(
        resin="2-CTC", amino_acid="Cit", aa_eq=2, base_eq=4, loading_time_h=4,
        target_loading_mmol_g=0.68, db_path=db,
    )
    traced = attach_evidence_trace(result)
    assert traced["target_recommendation"]["recommendation_kind"] == "OBSERVED REPEATED CONDITION"
    assert traced["evidence_trace"]["source"] == "Exact experimental match"



def test_chemistry_default_trace_is_default_not_similarity(tmp_path: Path):
    db = tmp_path / "default.sqlite"
    experimental_data.initialize(db)
    result = loading.advise(
        resin="2-CTC", amino_acid="Dab", aa_eq=2, base_eq=4, loading_time_h=4,
        target_loading_mmol_g=0.60, db_path=db,
    )
    traced = attach_evidence_trace(result)
    assert traced["target_recommendation"]["recommendation_kind"] == "CHEMISTRY DEFAULT"
    assert traced["evidence_trace"]["source"] == "Default fallback"
    assert traced["evidence_trace"]["evidence_count"] == 0
