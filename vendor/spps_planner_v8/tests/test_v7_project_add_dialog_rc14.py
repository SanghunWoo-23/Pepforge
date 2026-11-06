from __future__ import annotations

import os
import tkinter as tk

import pytest

from suite_gui.modules import add_peptide_dialog
from suite_gui.release import SPPSGui


def test_recipe_schema_migrates_and_tracks_recent(tmp_path, monkeypatch):
    monkeypatch.setenv("SPPS_PLANNER_USER_DATA", str(tmp_path))
    add_peptide_dialog._save_user_recipe(
        "Routine A", {"reagent": "DIC", "additive": "HOBt hydrate", "base": "", "solvent": "DMF"}
    )
    add_peptide_dialog._save_user_recipe(
        "Routine B", {"reagent": "HBTU", "additive": "", "base": "NMM", "solvent": "DMF"}
    )
    state = add_peptide_dialog._load_user_recipe_state()
    assert state["recent"][:2] == ["Routine B", "Routine A"]
    add_peptide_dialog._touch_user_recipe("Routine A")
    assert add_peptide_dialog._load_user_recipe_state()["recent"][:2] == ["Routine A", "Routine B"]


def test_recipe_duplicate_detection_and_rename(tmp_path, monkeypatch):
    monkeypatch.setenv("SPPS_PLANNER_USER_DATA", str(tmp_path))
    recipe = {"reagent": "DIC", "additive": "HOBt hydrate", "base": "", "solvent": "DMF"}
    add_peptide_dialog._save_user_recipe("Hydrate routine", recipe)
    recipes = add_peptide_dialog._load_user_recipes()
    assert add_peptide_dialog._find_equivalent_recipe(recipe, recipes) == "Hydrate routine"
    renamed = add_peptide_dialog._rename_user_recipe("Hydrate routine", "DIC hydrate")
    assert "Hydrate routine" not in renamed
    assert renamed["DIC hydrate"] == recipe
    assert add_peptide_dialog._load_user_recipe_state()["recent"][0] == "DIC hydrate"


def test_review_and_edit_change_summary_distinguishes_metadata_from_recalc():
    original = {
        "project": "P1", "peptide": "Pep1", "sequence": "ACDE", "scale": "0.2", "copies": "1",
        "resin": "Rink Amide AM", "loading": "0.8", "lot": "L1", "chemistry": "HBTU/NMM",
        "default_reagent": "HBTU", "default_catalyst": "", "default_base": "NMM",
        "default_coupling_solution_solvent": "DMF",
    }
    values = add_peptide_dialog._dialog_values_from_item(original)
    values["peptide"] = "Pep2"
    changed, recalc = add_peptide_dialog._edit_change_summary(original, values)
    assert changed == ["Peptide name"]
    assert recalc is False

    values["base"] = "DIPEA"
    changed, recalc = add_peptide_dialog._edit_change_summary(original, values)
    assert "Base" in changed
    assert recalc is True
    review = add_peptide_dialog._review_lines(values)
    assert "Peptide: P1 / Pep2" in review
    assert "HBTU + DIPEA" in review


def test_filter_can_match_library_metadata(monkeypatch):
    def fake_details(name):
        if name == "Bottle-X":
            return {"class": "Base", "role": "base", "state": "liquid", "notes": "tertiary amine"}
        return {}
    monkeypatch.setattr(add_peptide_dialog, "_material_details", fake_details)
    assert add_peptide_dialog._filter_choices(("Bottle-X", "Other"), "tertiary") == ("Bottle-X",)
    assert add_peptide_dialog._filter_choices(("Bottle-X", "Other"), "base") == ("Bottle-X",)


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="Tk GUI test requires DISPLAY")
def test_rc14_dialog_exposes_rename_recent_filter_and_review(tmp_path, monkeypatch):
    monkeypatch.setenv("SPPS_PLANNER_USER_DATA", str(tmp_path))
    add_peptide_dialog._save_user_recipe(
        "Hydrate routine", {"reagent": "DIC", "additive": "HOBt hydrate", "base": "", "solvent": "DMF"}
    )
    app = SPPSGui()
    try:
        app.deiconify(); app.update()
        app.pm_add_button.invoke(); app.update()
        assert hasattr(app, "add_peptide_rename_recipe_button")
        assert hasattr(app, "add_peptide_filter_status_var")
        assert hasattr(app, "add_peptide_review_details_var")
        app.add_peptide_user_recipe_var.set("Hydrate routine")
        app.add_peptide_user_recipe_combo.event_generate("<<ComboboxSelected>>")
        app.add_peptide_filter_var.set("hydrate")
        app.update()
        assert app.add_peptide_rename_recipe_button.instate(["!disabled"])
        assert "R " in app.add_peptide_filter_status_var.get()
        app.add_peptide_dialog_vars["sequence"].set("ACDE")
        app.update()
        assert "Sequence: ACDE" in app.add_peptide_review_details_var.get()
    finally:
        try:
            app.destroy()
        except tk.TclError:
            pass


def test_recent_bottles_are_persisted_and_prioritized(tmp_path, monkeypatch):
    monkeypatch.setenv("SPPS_PLANNER_USER_DATA", str(tmp_path))
    recipe = {"reagent": "HBTU", "additive": "HOBt hydrate", "base": "NMM", "solvent": "DMF"}
    recents = add_peptide_dialog._touch_recent_bottles(recipe)
    assert recents["reagent"][0] == "HBTU"
    assert recents["additive"][0] == "HOBt hydrate"
    assert recents["base"][0] == "NMM"
    assert recents["solvent"][0] == "DMF"
    ordered = add_peptide_dialog._prioritize_recent_choices(("DIC", "HBTU", "HATU"), ["HBTU"])
    assert ordered[:2] == ("HBTU", "DIC")


def test_project_manager_display_name_exposes_item_status():
    app = object.__new__(SPPSGui)
    label = SPPSGui.pm_display_name(app, {"project": "P1", "peptide": "Pep1", "lot": "L1", "status": "Calculated"})
    assert label == "[Calculated] P1 | Pep1 | L1"
