from pathlib import Path
import tempfile
import pytest

from suite_gui import experimental_data, ml_advisor_v5
from suite_gui.empirical_cleavage_v5 import generic_length_eq, operator_anchor


def _db(tmp_path):
    path = tmp_path / "empirical.sqlite3"
    experimental_data.initialize(path)
    return path


def test_v5_short_generic_peptide_stays_at_or_below_20eq_without_tis(tmp_path):
    db = _db(tmp_path)
    result = ml_advisor_v5.cleavage_recommendation(sequence="AAAAA", resin="Amide", scale_mmol=0.2, db_path=db)
    rec = result["recommended_condition"]
    assert rec["condition_source"] == "empirical_v5_fallback"
    assert rec["cleavage_eq"] <= 20.0
    assert rec["composition_pct"] == {"TFA": 95.0, "Water": 5.0}
    assert rec["scaled_total_ml"] == pytest.approx(0.2 * rec["cleavage_eq"])


def test_v5_length_baseline_is_monotonic_and_longer_sequences_increase():
    values = [generic_length_eq(n) for n in range(1, 23)]
    assert values == sorted(values)
    assert generic_length_eq(5) == 20.0
    assert generic_length_eq(6) == 30.0
    assert generic_length_eq(15) == 80.0
    assert generic_length_eq(22) == 100.0


def test_v5_longer_generic_peptide_uses_tis_fallback(tmp_path):
    db = _db(tmp_path)
    result = ml_advisor_v5.cleavage_recommendation(sequence="AAAAAAAA", resin="Amide", scale_mmol=0.2, db_path=db)
    rec = result["recommended_condition"]
    assert rec["cleavage_eq"] >= 35.0
    assert rec["composition_pct"] == {"TFA": 95.0, "TIS": 2.5, "Water": 2.5}


def test_private_operator_anchor_when_bundled():
    anchor_path = Path(__file__).resolve().parents[1] / "apps" / "spps_planner_app" / "data" / "experimental_seed" / "cleavage_empirical_anchors_seed.csv"
    if not anchor_path.is_file():
        pytest.skip("Public build intentionally has no private cleavage anchors")
    ghk = operator_anchor("ghk", scale_mmol=0.2)
    assert ghk is not None
    assert ghk["cleavage_eq"] == 18.0
    assert ghk["composition_pct"] == {"TFA": 95.0, "Water": 5.0}
    ac = operator_anchor("ac-eemqrr-nh2", scale_mmol=0.2)
    assert ac is not None and ac["cleavage_eq"] == 30.0
