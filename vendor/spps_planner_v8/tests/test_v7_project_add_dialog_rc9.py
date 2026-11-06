from __future__ import annotations

import os
import tkinter as tk

import pytest

from suite_gui.modules import add_peptide_dialog
from suite_gui.release import SPPSGui


def test_add_dialog_catalog_choices_are_driven_by_verified_reagent_library():
    choices = add_peptide_dialog._catalog_choices()
    assert {"DIC", "HBTU", "HATU", "COMU", "EDC-HCl"}.issubset(set(choices["reagent"]))
    assert {"HOBt (anhydrous)", "HOBt hydrate", "HOBt monohydrate", "HOAt", "Oxyma Pure", "K-Oxyma", "6-Cl-HOBt", "HOSu"}.issubset(set(choices["additive"]))
    assert {"NMM", "DIPEA", "DIEA", "TEA"}.issubset(set(choices["base"]))
    assert {"DMF", "NMP", "DCM", "ACN", "THF", "DMSO"}.issubset(set(choices["solvent"]))
    # Deprotection-only catalyst rows must not leak into the coupling picker.
    assert "Pd(PPh3)4" not in choices["additive"]
    assert "Hydrazine" not in choices["additive"]


def test_material_summary_makes_hobt_bottle_form_difference_visible():
    anhydrous, bad1 = add_peptide_dialog._material_summary({
        "reagent": "DIC", "additive": "HOBt (anhydrous)", "base": "", "solvent": "DMF",
    })
    hydrate, bad2 = add_peptide_dialog._material_summary({
        "reagent": "DIC", "additive": "HOBt hydrate", "base": "", "solvent": "DMF",
    })
    assert not bad1 and not bad2
    assert "135.13" in anhydrous
    assert "153.14" in hydrate
    assert anhydrous != hydrate
    mono, bad3 = add_peptide_dialog._material_summary({"reagent": "DIC", "additive": "HOBt monohydrate", "base": "", "solvent": "DMF"})
    assert not bad3 and "153.14" in mono


def test_unknown_exact_bottle_name_is_preserved_as_custom_in_payload():
    class Var:
        def __init__(self, value=""): self.value = value
        def get(self): return self.value
    class Gui:
        coupling_eq = Var("5")
        default_reagent_eq = Var("5")
        default_reagent_count = Var("1")
        default_catalyst_eq = Var("5")
        default_catalyst_count = Var("1")
        default_base_eq = Var("0")
        default_base_count = Var("0")
        reagent_eq_follows_coupling_eq = Var("True")
    payload = add_peptide_dialog.build_item_payload(Gui(), {
        "project": "P", "peptide": "X", "sequence": "ACD", "scale": "0.2",
        "copies": "1", "resin": "Rink Amide AM", "loading": "0.8", "lot": "L",
        "preset": "Custom", "reagent": "My exact activator bottle", "additive": "My catalyst hydrate",
        "base": "NMM", "solvent": "DMF",
    })
    assert payload["chemistry"] == "Manual"
    assert payload["method_label"] == "Custom"
    assert payload["default_reagent"] == "My exact activator bottle"
    assert payload["default_catalyst"] == "My catalyst hydrate"


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="Tk GUI test requires DISPLAY")
def test_add_dialog_allows_typing_exact_bottle_names_and_updates_live_summary():
    app = SPPSGui()
    try:
        app.deiconify(); app.update()
        app.pm_add_button.invoke(); app.update()
        assert str(app.add_peptide_reagent_combo.cget("state")) == "normal"
        assert str(app.add_peptide_additive_combo.cget("state")) == "normal"
        v = app.add_peptide_dialog_vars
        v["additive"].set("HOBt hydrate"); app.update()
        assert "153.14" in app.add_peptide_material_summary_var.get()
        assert "not the anhydrous" in app.add_peptide_hobt_note_var.get()
        v["additive"].set("Custom supplier additive form"); app.update()
        assert "custom bottle name" in app.add_peptide_material_summary_var.get()
        v["sequence"].set("ACD")
        app.add_peptide_confirm_button.invoke(); app.update()
        assert app.pm_items[0]["default_catalyst"] == "Custom supplier additive form"
    finally:
        try: app.destroy()
        except tk.TclError: pass
