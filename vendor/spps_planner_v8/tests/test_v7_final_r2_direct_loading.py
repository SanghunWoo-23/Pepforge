from __future__ import annotations

import os
import tkinter as tk

import pytest

from suite_gui.modules import add_peptide_dialog
from suite_gui.release import SPPSGui


class _Var:
    def __init__(self, value=""):
        self.value = value
    def get(self):
        return self.value


class _GuiDefaults:
    coupling_eq = _Var("5")
    default_reagent_eq = _Var("5")
    default_reagent_count = _Var("1")
    default_catalyst_eq = _Var("5")
    default_catalyst_count = _Var("1")
    default_base_eq = _Var("0")
    default_base_count = _Var("0")
    reagent_eq_follows_coupling_eq = _Var("True")
    loading_aa_eq = _Var("2")
    loading_diea_eq = _Var("4")
    loading_time_h = _Var("")


def _values(resin: str, direct: str):
    return {
        "project": "P", "peptide": "Pep", "sequence": "ACDE", "scale": "0.2",
        "copies": "1", "resin": resin, "loading": "0.8", "lot": "L-1",
        "apply_loading_calc": direct, "loading_aa_eq": "2", "loading_diea_eq": "4",
        "loading_time_h": "", "preset": "DIC + HOBt (anhydrous)", "reagent": "DIC",
        "additive": "HOBt (anhydrous)", "base": "", "solvent": "DMF",
    }


def test_direct_loading_payload_is_allowed_only_for_2ctc():
    ctc = add_peptide_dialog.build_item_payload(_GuiDefaults(), _values("2-CTC", "1"))
    assert ctc["apply_loading_calc"] is True
    assert ctc["loading_aa_eq"] == "2"
    assert ctc["loading_diea_eq"] == "4"

    rink = add_peptide_dialog.build_item_payload(_GuiDefaults(), _values("Rink Amide AM", "1"))
    assert rink["apply_loading_calc"] is False

    synthesizer = add_peptide_dialog.build_item_payload(_GuiDefaults(), _values("CTC(합성기)", "1"))
    assert synthesizer["apply_loading_calc"] is False


def test_legacy_2ctc_item_without_flag_defaults_to_direct_loading_in_edit_values():
    values = add_peptide_dialog._dialog_values_from_item({
        "project": "P", "peptide": "Pep", "sequence": "ACD", "scale": "0.2",
        "copies": "1", "resin": "2-CTC", "loading": "0.8",
        "default_reagent": "DIC", "default_catalyst": "HOBt (anhydrous)",
        "default_base": "", "default_coupling_solution_solvent": "DMF",
    })
    assert values["apply_loading_calc"] == "1"


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="Tk GUI test requires DISPLAY")
def test_add_dialog_auto_checks_loading_only_for_2ctc(tmp_path, monkeypatch):
    monkeypatch.setenv("SPPS_PLANNER_USER_DATA", str(tmp_path))
    app = SPPSGui()
    try:
        app.deiconify(); app.update()
        app.pm_add_button.invoke(); app.update()
        v = app.add_peptide_dialog_vars
        assert v["resin"].get() == "Rink Amide AM"
        assert v["apply_loading_calc"].get() == "0"
        assert app.add_peptide_direct_loading_check.instate(["disabled"])

        v["resin"].set("2-CTC"); app.update()
        assert v["apply_loading_calc"].get() == "1"
        assert app.add_peptide_direct_loading_check.instate(["!disabled"])
        assert "checked automatically" in app.add_peptide_direct_loading_status_var.get()

        # Operator can still override an exceptional already-loaded 2-CTC bottle.
        v["apply_loading_calc"].set("0"); app.update()
        assert v["apply_loading_calc"].get() == "0"

        v["resin"].set("CTC(합성기)"); app.update()
        assert v["apply_loading_calc"].get() == "0"
        assert app.add_peptide_direct_loading_check.instate(["disabled"])
    finally:
        try:
            app.destroy()
        except tk.TclError:
            pass
