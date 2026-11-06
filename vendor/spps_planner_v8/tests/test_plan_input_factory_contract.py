from __future__ import annotations

import pytest

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


def test_editor_factory_preserves_scale_copies_and_dic_hobt_defaults():
    gui = _Gui(
        pm_sequence="Ac-AAAAAA-NH2",
        pm_scale="0.2",
        pm_copies="2",
        pm_loading="0.8",
        pm_chemistry="DIC/HOBt",
        coupling_eq="5",
    )

    plan = plan_input_factory.build_editor_plan_input(
        gui, "Rink Amide AM", True
    )

    assert plan.sequence == "Ac-AAAAAA-NH2"
    assert plan.scale_mmol == 0.4
    assert plan.resin_loading_mmol_g == 0.8
    assert plan.default_coupling_reagent == "DIC"
    assert plan.default_catalyst == "HOBt"
    assert plan.default_reaction_solvent == "DMF"
    assert plan.reagent_eq_follows_coupling_eq is True


def test_editor_factory_preserves_legacy_hbtu_nmp_name_but_uses_nmm_semantics():
    gui = _Gui(
        pm_sequence="AEK",
        pm_scale="0",
        pm_copies="1",
        pm_loading="",
        pm_chemistry="HBTU/NMP 10eq",
        default_base="NMM",
        default_coupling_solution_solvent="DMF",
        coupling_eq="10",
    )

    plan = plan_input_factory.build_editor_plan_input(
        gui, "Rink Amide AM", False
    )

    assert plan.scale_mmol == 400.0
    assert gui.pm_scale.get() == "400"
    assert plan.resin_loading_mmol_g == 0.8
    assert gui.pm_loading.get() == ""
    assert plan.default_coupling_reagent == "HBTU"
    assert plan.default_catalyst == ""
    assert plan.default_base == "NMM"
    assert plan.default_reaction_solvent == "DMF"
    assert plan.coupling_eq == 10.0


def test_batch_factory_uses_explicit_batch_conditions():
    gui = _Gui(
        batch_coupling_eq="5",
        batch_hbtu_eq="10",
        default_base="NMM",
        default_coupling_solution_solvent="DMF",
        default_base_eq="5",
        default_base_count="1",
        loading_aa_eq="2",
        loading_diea_eq="4",
    )
    row = {
        "Sequence": "AEK",
        "Copies": 3,
        "Scale mmol": 0.2,
        "Resin": "CTC(합성기)",
        "Loading": 1.39,
        "Chemistry": "HBTU/NMP 10eq",
    }

    plan = plan_input_factory.build_batch_plan_input(gui, row, True)

    assert plan.scale_mmol == pytest.approx(0.6)
    assert plan.resin == "CTC(합성기)"
    assert plan.default_coupling_reagent == "HBTU"
    assert plan.default_catalyst == ""
    assert plan.default_base == "NMM"
    assert plan.default_reaction_solvent == "DMF"
    assert plan.default_reagent_eq == 10.0
    assert plan.reagent_eq_follows_coupling_eq is False
    assert plan.auto_short_peptide_eq is False
