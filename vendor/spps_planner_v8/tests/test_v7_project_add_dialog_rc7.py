from __future__ import annotations

import os
import tkinter as tk
from types import SimpleNamespace

import pytest

from suite_gui import plan_input_factory
from suite_gui.release import SPPSGui


class Var:
    def __init__(self, value=""): self.value = value
    def get(self): return self.value
    def set(self, value): self.value = value


def _chem_gui(label, reagent, additive, base, solvent="DMF"):
    return SimpleNamespace(
        pm_chemistry=Var(label), coupling_eq=Var("5"),
        default_reagent=Var(reagent), default_catalyst=Var(additive),
        default_base=Var(base), default_coupling_solution_solvent=Var(solvent),
    )


def test_named_methods_do_not_collapse_to_wrong_additive_or_base():
    gui = _chem_gui("DIC/Oxyma", "DIC", "Oxyma", "")
    assert plan_input_factory.chemistry(gui)[:4] == ("DIC", "Oxyma", "", "DMF")

    gui = _chem_gui("HBTU/HOBt/DIPEA", "HBTU", "HOBt", "DIPEA")
    assert plan_input_factory.chemistry(gui)[:4] == ("HBTU", "HOBt", "DIPEA", "DMF")


def _confirm_dialog(app, *, sequence, preset, reagent, additive, base, solvent="DMF"):
    app.pm_add_button.invoke(); app.update()
    v = app.add_peptide_dialog_vars
    v["sequence"].set(sequence); v["scale"].set("0.2"); v["copies"].set("1")
    v["resin"].set("Rink Amide AM"); v["loading"].set("0.8")
    v["preset"].set(preset); v["reagent"].set(reagent); v["additive"].set(additive)
    v["base"].set(base); v["solvent"].set(solvent)
    app.add_peptide_confirm_button.invoke(); app.update()


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="Tk GUI test requires DISPLAY")
def test_add_recipe_does_not_change_batch_solution_defaults():
    app = SPPSGui()
    try:
        app.deiconify(); app.update()
        names = ("batch_solution_conc", "batch_coupling_eq", "batch_hbtu_eq", "batch_hbtu_conc", "batch_nmm_eq", "batch_nmm_conc")
        before = {name: str(getattr(app, name).get()) for name in names}
        _confirm_dialog(app, sequence="AAAA", preset="Custom", reagent="HATU", additive="HOAt", base="DIPEA")
        after = {name: str(getattr(app, name).get()) for name in names}
        assert after == before
        assert app.pm_items[0]["default_reagent"] == "HATU"
        assert app.pm_items[0]["default_catalyst"] == "HOAt"
        assert app.pm_items[0]["default_base"] == "DIPEA"
    finally:
        try: app.destroy()
        except tk.TclError: pass


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="Tk GUI test requires DISPLAY")
def test_recipe_is_restored_when_switching_project_items():
    app = SPPSGui()
    try:
        app.deiconify(); app.update()
        _confirm_dialog(app, sequence="AAAA", preset="HBTU + NMM", reagent="HBTU", additive="", base="NMM")
        _confirm_dialog(app, sequence="GGGG", preset="Custom", reagent="HATU", additive="HOAt", base="DIPEA")
        assert len(app.pm_items) == 2

        app.pm_list.selection_clear(0, "end"); app.pm_list.selection_set(0); app.pm_list.activate(0)
        app.pm_on_double_click(); app.update()
        assert app.default_reagent.get() == "HBTU"
        assert app.default_base.get() == "NMM"

        app.pm_list.selection_clear(0, "end"); app.pm_list.selection_set(1); app.pm_list.activate(1)
        app.pm_on_double_click(); app.update()
        assert app.default_reagent.get() == "HATU"
        assert app.default_catalyst.get() == "HOAt"
        assert app.default_base.get() == "DIPEA"
    finally:
        try: app.destroy()
        except tk.TclError: pass
