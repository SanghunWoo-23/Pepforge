from __future__ import annotations

from suite_gui.modules import plan_workflow
from suite_gui import plan_input_factory


class _Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class _Gui:
    def __init__(self, **values):
        for name, value in values.items():
            setattr(self, name, _Var(value))


def test_short_sequence_uses_visible_default_aa_eq():
    gui = _Gui(pm_sequence="AEK", coupling_eq="3")
    assert plan_workflow._sequence_aa_eq(gui) == 3.0


def test_long_sequence_uses_same_visible_default_aa_eq():
    gui = _Gui(pm_sequence="GHTYKL", coupling_eq="4")
    assert plan_workflow._sequence_aa_eq(gui) == 4.0


def test_editor_plan_disables_hidden_short_peptide_override():
    gui = _Gui(
        pm_sequence="AEK",
        pm_scale="0.2",
        pm_copies="1",
        pm_loading="0.8",
        pm_chemistry="DIC/HOBt",
        coupling_eq="3",
    )
    plan = plan_input_factory.build_editor_plan_input(gui, "Rink Amide AM", True)
    assert plan.coupling_eq == 3.0
    assert plan.auto_short_peptide_eq is False
