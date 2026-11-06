from __future__ import annotations

import os
import tkinter as tk

import pytest

from suite_gui.modules import add_peptide_dialog
from suite_gui.release import SPPSGui


def test_user_recipe_roundtrip_uses_user_data_not_release_tree(tmp_path, monkeypatch):
    monkeypatch.setenv("SPPS_PLANNER_USER_DATA", str(tmp_path))
    recipe = {
        "reagent": "DIC",
        "additive": "HOBt hydrate",
        "base": "",
        "solvent": "DMF",
    }
    saved = add_peptide_dialog._save_user_recipe("Routine hydrate", recipe)
    assert saved["Routine hydrate"] == recipe
    path = add_peptide_dialog._user_recipe_path()
    assert path.parent == tmp_path
    assert path.name == "coupling_recipe_presets.json"
    assert add_peptide_dialog._load_user_recipes()["Routine hydrate"]["additive"] == "HOBt hydrate"

    after = add_peptide_dialog._delete_user_recipe("Routine hydrate")
    assert "Routine hydrate" not in after
    assert add_peptide_dialog._load_user_recipes() == {}


def test_user_recipe_requires_reagent_and_solvent(tmp_path, monkeypatch):
    monkeypatch.setenv("SPPS_PLANNER_USER_DATA", str(tmp_path))
    with pytest.raises(ValueError, match="Coupling reagent"):
        add_peptide_dialog._save_user_recipe("bad", {"reagent": "", "solvent": "DMF"})
    with pytest.raises(ValueError, match="Solvent"):
        add_peptide_dialog._save_user_recipe("bad", {"reagent": "DIC", "solvent": ""})


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="Tk GUI test requires DISPLAY")
def test_my_recipes_loads_exact_bottle_identity_into_add_dialog(tmp_path, monkeypatch):
    monkeypatch.setenv("SPPS_PLANNER_USER_DATA", str(tmp_path))
    add_peptide_dialog._save_user_recipe(
        "Hydrate routine",
        {"reagent": "DIC", "additive": "HOBt hydrate", "base": "", "solvent": "DMF"},
    )
    app = SPPSGui()
    try:
        app.deiconify(); app.update()
        app.pm_add_button.invoke(); app.update()
        values = tuple(app.add_peptide_user_recipe_combo.cget("values"))
        assert "Hydrate routine" in values
        app.add_peptide_user_recipe_var.set("Hydrate routine")
        app.add_peptide_user_recipe_combo.event_generate("<<ComboboxSelected>>")
        app.update()
        v = app.add_peptide_dialog_vars
        assert v["reagent"].get() == "DIC"
        assert v["additive"].get() == "HOBt hydrate"
        assert v["solvent"].get() == "DMF"
        assert v["preset"].get() == "DIC + HOBt hydrate"
        assert app.add_peptide_delete_recipe_button.instate(["!disabled"])
    finally:
        try:
            app.destroy()
        except tk.TclError:
            pass
