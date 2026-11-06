from __future__ import annotations

import json
import os
import tkinter as tk

import pytest

from suite_gui.modules import add_peptide_dialog
from suite_gui.release import SPPSGui


def _recipe(reagent="HBTU", additive="", base="NMM", solvent="DMF"):
    return {"reagent": reagent, "additive": additive, "base": base, "solvent": solvent}


def test_favorite_recipe_roundtrip_rename_delete(tmp_path, monkeypatch):
    monkeypatch.setenv("SPPS_PLANNER_USER_DATA", str(tmp_path))
    add_peptide_dialog._save_user_recipe("Routine", _recipe())
    enabled, favorites = add_peptide_dialog._toggle_user_recipe_favorite("Routine")
    assert enabled is True and favorites == ["Routine"]
    assert add_peptide_dialog._load_user_recipe_state()["favorites"] == ["Routine"]

    add_peptide_dialog._rename_user_recipe("Routine", "Daily HBTU")
    assert add_peptide_dialog._load_user_recipe_state()["favorites"] == ["Daily HBTU"]

    enabled, favorites = add_peptide_dialog._toggle_user_recipe_favorite("Daily HBTU")
    assert enabled is False and favorites == []
    add_peptide_dialog._toggle_user_recipe_favorite("Daily HBTU")
    add_peptide_dialog._delete_user_recipe("Daily HBTU")
    assert add_peptide_dialog._load_user_recipe_state()["favorites"] == []


def test_recipe_backup_import_preserves_favorite_intent(tmp_path, monkeypatch):
    source = tmp_path / "source"
    target = tmp_path / "target"
    backup = tmp_path / "recipes.json"
    monkeypatch.setenv("SPPS_PLANNER_USER_DATA", str(source))
    add_peptide_dialog._save_user_recipe("Pinned", _recipe())
    add_peptide_dialog._toggle_user_recipe_favorite("Pinned")
    add_peptide_dialog._export_user_recipes(backup)
    payload = json.loads(backup.read_text(encoding="utf-8"))
    assert payload["favorites"] == ["Pinned"]

    monkeypatch.setenv("SPPS_PLANNER_USER_DATA", str(target))
    result = add_peptide_dialog._import_user_recipes(backup)
    assert result["added"] == 1
    assert add_peptide_dialog._load_user_recipe_state()["favorites"] == ["Pinned"]


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="Tk GUI test requires DISPLAY")
def test_final_dialog_exposes_favorite_recipe_control(tmp_path, monkeypatch):
    monkeypatch.setenv("SPPS_PLANNER_USER_DATA", str(tmp_path))
    add_peptide_dialog._save_user_recipe("Routine", _recipe())
    app = SPPSGui()
    try:
        app.deiconify(); app.update()
        app.pm_add_button.invoke(); app.update()
        assert hasattr(app, "add_peptide_favorite_recipe_button")
        app.add_peptide_user_recipe_var.set("Routine")
        app.update()
        assert app.add_peptide_favorite_recipe_button.instate(["!disabled"])
    finally:
        try:
            app.add_peptide_dialog.destroy()
        except Exception:
            pass
        try:
            app.destroy()
        except tk.TclError:
            pass
