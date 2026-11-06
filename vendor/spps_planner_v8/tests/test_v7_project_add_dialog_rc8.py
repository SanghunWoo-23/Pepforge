from __future__ import annotations

import os
import tkinter as tk
from types import SimpleNamespace

import pytest

from spps_planner import database
from suite_gui import calculation_context, plan_input_factory
from suite_gui.modules import add_peptide_dialog
from suite_gui.release import SPPSGui


class Var:
    def __init__(self, value=""):
        self.value = value
    def get(self):
        return self.value
    def set(self, value):
        self.value = value


def _chem_gui(catalyst: str):
    return SimpleNamespace(
        pm_chemistry=Var("DIC/HOBt"),
        coupling_eq=Var("5"),
        default_reagent=Var("DIC"),
        default_catalyst=Var(catalyst),
        default_base=Var(""),
        default_coupling_solution_solvent=Var("DMF"),
    )


def test_hobt_bottle_forms_are_explicit_and_catalog_is_expanded():
    values = set(add_peptide_dialog.ADDITIVES)
    assert "HOBt (anhydrous)" in values
    assert "HOBt hydrate" in values
    assert {"HOAt", "Oxyma", "Oxyma Pure", "K-Oxyma", "6-Cl-HOBt", "DMAP", "NHS", "Sulfo-NHS"}.issubset(values)
    assert len(values) >= 17


def test_hobt_forms_remain_distinct_through_named_dic_hobt_project_label():
    assert plan_input_factory.chemistry(_chem_gui("HOBt (anhydrous)"))[:4] == (
        "DIC", "HOBt (anhydrous)", "", "DMF"
    )
    assert plan_input_factory.chemistry(_chem_gui("HOBt hydrate"))[:4] == (
        "DIC", "HOBt hydrate", "", "DMF"
    )


def test_reagent_library_has_separate_hobt_form_mw_values():
    lookup = database.reagent_lookup()
    assert float(lookup["HOBt (anhydrous)"]["MW"]) == pytest.approx(135.13)
    assert float(lookup["HOBt hydrate"]["MW"]) == pytest.approx(153.14)

    assert calculation_context.material_lookup("HOBt (anhydrous)")[0] == pytest.approx(135.13)
    assert calculation_context.material_lookup("HOBt hydrate")[0] == pytest.approx(153.14)


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="Tk GUI test requires DISPLAY")
def test_add_dialog_opens_near_center_of_main_planner_window():
    app = SPPSGui()
    try:
        app.geometry("1200x800+120+80")
        app.deiconify(); app.update()
        app.pm_add_button.invoke(); app.update()
        dialog = app.add_peptide_dialog

        parent_cx = app.winfo_rootx() + app.winfo_width() / 2
        parent_cy = app.winfo_rooty() + app.winfo_height() / 2
        dialog_cx = dialog.winfo_rootx() + dialog.winfo_width() / 2
        dialog_cy = dialog.winfo_rooty() + dialog.winfo_height() / 2

        assert abs(dialog_cx - parent_cx) <= 25
        assert abs(dialog_cy - parent_cy) <= 25
    finally:
        try:
            app.destroy()
        except tk.TclError:
            pass
