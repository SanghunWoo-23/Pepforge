"""Auto Plan uses existing chemistry engine and does not silently invent cleavage inputs."""
import pytest
from suite_gui.auto_plan_option_v8 import preview_inputs


def test_preview_is_deterministic_and_non_mutating():
    data = preview_inputs("Ac-EEMQRR-NH2", "0.2", "Rink Amide AM", "0.8", "HBTU/NMM", "1")
    assert data["residues"] == 6
    assert data["resin_g"] == pytest.approx(0.25)
    assert data["tfa_eq"] == 30


def test_cysteine_tfa_rule_no_double_count():
    data = preview_inputs("ACCC", 0.1, "Rink Amide AM", 0.8, "DIC/HOBt", 1)
    assert data["tfa_eq"] == 300


@pytest.mark.parametrize("sequence,scale,loading,copies", [
    ("", 0.2, 0.8, 1), ("GHK", 0, 0.8, 1),
    ("GHK", 0.2, 0, 1), ("GHK", 0.2, 0.8, 0),
    ("GHK", "nan", 0.8, 1),
])
def test_invalid_input_blocked(sequence, scale, loading, copies):
    with pytest.raises(ValueError):
        preview_inputs(sequence, scale, "Rink Amide AM", loading, "DIC/HOBt", copies)
