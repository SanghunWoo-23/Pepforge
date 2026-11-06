from __future__ import annotations

from spps_planner.engine import PlanInput
from suite_gui import resin_profiles


class _Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class _Gui:
    def __init__(self, resin, loading):
        self.pm_resin = _Var(resin)
        self.apply_loading_calc = _Var(loading)


def test_resin_normalization_preserves_distinct_active_profiles():
    assert resin_profiles.normalize_resin("2-CTC") == "2-CTC"
    assert resin_profiles.normalize_resin("CTC(합성기)") == "CTC(합성기)"
    assert resin_profiles.normalize_resin("CTC(합성용)") == "CTC(합성기)"
    assert resin_profiles.normalize_resin("CTC/Trityl") == "2-CTC"
    assert resin_profiles.normalize_resin("") == "Rink Amide AM"


def test_direct_loading_is_only_enabled_for_direct_2_ctc_profile():
    assert resin_profiles.is_direct_resin("2-CTC")
    assert not resin_profiles.is_direct_resin("CTC(합성기)")
    assert not resin_profiles.is_direct_resin("Rink Amide AM")
    assert resin_profiles.item_loading_enabled(
        {"resin": "2-CTC", "apply_loading_calc": True}
    )
    assert not resin_profiles.item_loading_enabled(
        {"resin": "CTC(합성기)", "apply_loading_calc": True}
    )


def test_editor_profile_changes_only_final_resin_loading_fields():
    base = PlanInput(
        sequence="AEK",
        resin="Rink Amide AM",
        scale_mmol=0.4,
        coupling_eq=7.0,
    )
    result = resin_profiles.apply_editor_profile(_Gui("2-CTC", True), base)

    assert result.resin == "2-CTC"
    assert result.apply_resin_loading is True
    assert result.sequence == base.sequence
    assert result.scale_mmol == base.scale_mmol
    assert result.coupling_eq == base.coupling_eq


def test_batch_profile_preserves_per_peptide_loading_equivalents():
    base = PlanInput(sequence="AEK", resin="Rink Amide AM")
    row = {
        "Resin": "2-CTC",
        "_apply_loading_calc": True,
        "_loading_aa_eq": 3.0,
        "_loading_diea_eq": 6.0,
    }
    result = resin_profiles.apply_batch_profile(row, base)

    assert result.resin == "2-CTC"
    assert result.apply_resin_loading is True
    assert result.loading_aa_eq == 3.0
    assert result.loading_diea_eq == 6.0
