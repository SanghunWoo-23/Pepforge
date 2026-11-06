from __future__ import annotations

import inspect

from suite_gui.classic_base import ClassicBaseCore
from suite_gui.persistence_workflow import _migrate_volume_defaults
from suite_gui.session_state import DEFAULT_STATE_FIELDS


class _Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


def _gui(**values):
    gui = ClassicBaseCore.__new__(ClassicBaseCore)
    for name, value in values.items():
        setattr(gui, name, _Var(value))
    return gui


def test_removed_global_volume_field_is_not_built_or_persisted():
    source = inspect.getsource(ClassicBaseCore._build_pm_setup_panel)
    assert "'mL per mmol'" not in source
    assert '"mL per mmol"' not in source
    assert "ml_per_mmol" not in DEFAULT_STATE_FIELDS
    assert "amide_ml_per_mmol" in DEFAULT_STATE_FIELDS
    assert "ctc_ml_per_mmol" in DEFAULT_STATE_FIELDS


def test_retained_resin_specific_controls_are_the_only_calculation_source():
    gui = _gui(
        solvent_volume_mode="resin_factor",
        amide_ml_per_mmol="8",
        ctc_ml_per_mmol="4",
        solvent_molarity_m="0.25",
        coupling_eq="5",
        resin="Rink Amide AM",
    )
    assert gui._volume_factor_for_resin("Rink Amide AM") == 8
    assert gui._volume_factor_for_resin("2-CTC") == 4
    assert gui._working_volume_for_scale(0.2, "Rink Amide AM") == 1.6
    assert gui._working_volume_for_scale(0.2, "2-CTC") == 0.8

    gui.solvent_volume_mode.value = "molarity"
    assert gui._volume_factor_for_resin("Rink Amide AM") == 20
    assert gui._working_volume_for_scale(0.2, "Rink Amide AM") == 4


def test_legacy_global_value_migrates_but_modern_values_win():
    assert _migrate_volume_defaults({"ml_per_mmol": 6}) == {
        "amide_ml_per_mmol": 6,
        "ctc_ml_per_mmol": 6,
    }
    assert _migrate_volume_defaults({
        "ml_per_mmol": 6,
        "amide_ml_per_mmol": 8,
        "ctc_ml_per_mmol": 4,
    }) == {
        "amide_ml_per_mmol": 8,
        "ctc_ml_per_mmol": 4,
    }
