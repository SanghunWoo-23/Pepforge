from __future__ import annotations

import os
import tkinter as tk

import pytest

from suite_gui.modules import add_peptide_dialog
from suite_gui.release import SPPSGui


def _values(**overrides):
    data = {
        "project": "P", "peptide": "Pep", "sequence": "ACD", "scale": "0.2",
        "copies": "1", "resin": "Rink Amide AM", "loading": "0.8", "lot": "L",
        "preset": "DIC + HOBt hydrate", "reagent": "DIC", "additive": "HOBt hydrate",
        "base": "", "solvent": "DMF",
    }
    data.update(overrides)
    return data


def test_filter_choices_finds_exact_bottle_forms_without_mutating_catalog():
    source = add_peptide_dialog._catalog_choices()["additive"]
    filtered = add_peptide_dialog._filter_choices(source, "hobt")
    assert "HOBt (anhydrous)" in filtered
    assert "HOBt hydrate" in filtered
    assert "HOBt monohydrate" in filtered
    assert "Oxyma" not in filtered
    assert add_peptide_dialog._filter_choices(source, "") == source


def test_known_material_in_wrong_recipe_field_produces_advisory_role_warning():
    notes = add_peptide_dialog._role_mismatch_notes(_values(additive="NMM"))
    assert notes
    assert "Additive / catalyst" in notes[0]
    assert "base" in notes[0].lower()
    ready, _, note = add_peptide_dialog._live_check(_values(additive="NMM"))
    assert ready
    assert "Role check" in note


def test_selected_item_recipe_prefers_exact_stored_bottle_identity_and_matches_preset():
    item = {
        "chemistry": "DIC/HOBt",
        "default_reagent": "DIC",
        "default_catalyst": "HOBt hydrate",
        "default_base": "",
        "default_coupling_solution_solvent": "DMF",
    }
    recipe = add_peptide_dialog._item_recipe_values(item)
    assert recipe["additive"] == "HOBt hydrate"
    assert add_peptide_dialog._matching_preset(recipe) == "DIC + HOBt hydrate"


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="Tk GUI test requires DISPLAY")
def test_find_bottle_filters_dropdowns_and_reset_restores_selected_shortcut():
    app = SPPSGui()
    try:
        app.deiconify(); app.update()
        app.pm_add_button.invoke(); app.update()
        v = app.add_peptide_dialog_vars
        app.add_peptide_filter_var.set("hobt")
        app.update()
        additive_values = tuple(app.add_peptide_additive_combo.cget("values"))
        assert "HOBt hydrate" in additive_values
        assert "Oxyma" not in additive_values

        v["additive"].set("Oxyma")
        app.update()
        assert v["preset"].get() == "DIC + Oxyma"
        v["preset"].set("DIC + HOBt hydrate")
        app.add_peptide_reset_preset_button.invoke(); app.update()
        assert v["reagent"].get() == "DIC"
        assert v["additive"].get() == "HOBt hydrate"
    finally:
        try: app.destroy()
        except tk.TclError: pass


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="Tk GUI test requires DISPLAY")
def test_copy_selected_peptide_settings_does_not_copy_sequence_name_or_lot():
    app = SPPSGui()
    try:
        app.deiconify(); app.update()
        # Populate the startup row with exact project-specific synthesis settings.
        app.pm_items[0] = {
            "project": "P1", "peptide": "OLD", "sequence": "ACD", "scale": "0.15",
            "copies": "2", "resin": "2-CTC", "loading": "0.55", "lot": "OLDLOT",
            "chemistry": "DIC/HOBt", "method_label": "DIC + HOBt hydrate",
            "default_reagent": "DIC", "default_catalyst": "HOBt hydrate",
            "default_base": "", "default_coupling_solution_solvent": "DMF", "status": "Ready",
        }
        app.pm_refresh_list(keep_index=0)
        app.pm_list.selection_clear(0, "end"); app.pm_list.selection_set(0); app.pm_list.activate(0)
        app.update()
        app.pm_add_button.invoke(); app.update()
        v = app.add_peptide_dialog_vars
        original_name = v["peptide"].get(); original_lot = v["lot"].get()
        app.add_peptide_copy_settings_button.invoke(); app.update()
        assert v["scale"].get() == "0.15"
        assert v["copies"].get() == "2"
        assert v["resin"].get() == "2-CTC"
        assert v["loading"].get() == "0.55"
        assert v["additive"].get() == "HOBt hydrate"
        assert v["sequence"].get() == ""
        assert v["peptide"].get() == original_name
        assert v["lot"].get() == original_lot
        assert "Copied scale" in app.add_peptide_template_status_var.get()
    finally:
        try: app.destroy()
        except tk.TclError: pass
