from __future__ import annotations

import json
import os
import tkinter as tk
from pathlib import Path

import pytest

from suite_gui.modules import add_peptide_dialog
from suite_gui.release import SPPSGui


def _recipe(reagent="HBTU", additive="", base="NMM", solvent="DMF"):
    return {"reagent": reagent, "additive": additive, "base": base, "solvent": solvent}


def test_recipe_file_recovers_from_last_good_backup(tmp_path, monkeypatch):
    monkeypatch.setenv("SPPS_PLANNER_USER_DATA", str(tmp_path))
    add_peptide_dialog._save_user_recipe("Routine A", _recipe())
    add_peptide_dialog._save_user_recipe("Routine B", _recipe("DIC", "HOBt hydrate", "", "DMF"))
    path = add_peptide_dialog._user_recipe_path()
    backup = path.with_suffix(path.suffix + ".bak")
    assert backup.exists()
    path.write_text("{broken json", encoding="utf-8")
    state = add_peptide_dialog._load_user_recipe_state()
    assert "Routine A" in state["recipes"]


def test_recipe_export_import_merges_without_overwrite(tmp_path, monkeypatch):
    source = tmp_path / "source"
    target = tmp_path / "target"
    backup = tmp_path / "recipes.json"

    monkeypatch.setenv("SPPS_PLANNER_USER_DATA", str(source))
    add_peptide_dialog._save_user_recipe("Routine", _recipe())
    assert add_peptide_dialog._export_user_recipes(backup) == 1
    payload = json.loads(backup.read_text(encoding="utf-8"))
    assert payload["export_kind"] == "SPPS Planner coupling recipes"
    assert "recent_bottles" not in payload

    monkeypatch.setenv("SPPS_PLANNER_USER_DATA", str(target))
    add_peptide_dialog._save_user_recipe("Routine", _recipe("DIC", "HOBt hydrate", "", "DMF"))
    result = add_peptide_dialog._import_user_recipes(backup)
    assert result == {"added": 1, "renamed": 1, "skipped": 0, "invalid": 0}
    recipes = add_peptide_dialog._load_user_recipes()
    assert recipes["Routine"]["reagent"] == "DIC"
    assert recipes["Routine (imported 2)"]["reagent"] == "HBTU"


def test_recipe_import_skips_equivalent_and_invalid_rows(tmp_path, monkeypatch):
    monkeypatch.setenv("SPPS_PLANNER_USER_DATA", str(tmp_path / "user"))
    add_peptide_dialog._save_user_recipe("Existing", _recipe())
    source = tmp_path / "mixed.json"
    source.write_text(json.dumps({"recipes": {
        "Same chemistry": _recipe(),
        "No solvent": {"reagent": "DIC", "additive": "", "base": "", "solvent": ""},
    }}), encoding="utf-8")
    result = add_peptide_dialog._import_user_recipes(source)
    assert result == {"added": 0, "renamed": 0, "skipped": 1, "invalid": 1}


def test_duplicate_identity_notes_ignore_sequence_and_excluded_edit_row():
    class Gui:
        pm_items = [
            {"project": "P1", "peptide": "Pep1", "lot": "L-001", "sequence": "AAAA"},
            {"project": "P2", "peptide": "Pep2", "lot": "L-002", "sequence": "AAAA"},
        ]
    values = {"project": "p1", "peptide": "pep1", "lot": "l-002", "sequence": "AAAA"}
    notes = add_peptide_dialog._duplicate_project_notes(Gui(), values)
    assert any("Project / peptide name" in x for x in notes)
    assert any("LOT No." in x for x in notes)
    assert all("sequence" not in x.lower() for x in notes)
    assert add_peptide_dialog._duplicate_project_notes(Gui(), {"project": "P1", "peptide": "Pep1", "lot": "L-001"}, 0) == []


def test_blank_solvent_is_blocked_in_live_check_and_payload():
    values = {
        "sequence": "ACDE", "scale": "0.2", "copies": "1", "resin": "Rink Amide AM",
        "loading": "0.8", "reagent": "HBTU", "additive": "", "base": "NMM", "solvent": "",
    }
    ready, summary, note = add_peptide_dialog._live_check(values)
    assert ready is False
    assert "solvent" in summary.lower()
    with pytest.raises(ValueError, match="solvent"):
        add_peptide_dialog.build_item_payload(object(), values)


def test_dialog_snapshot_tracks_user_owned_setup_fields_only():
    values = {key: key for key in ("project", "peptide", "sequence", "scale", "copies", "resin", "loading", "lot", "reagent", "additive", "base", "solvent")}
    snap = add_peptide_dialog._dialog_snapshot(values)
    assert dict(snap)["reagent"] == "reagent"
    values["preset"] = "irrelevant shortcut label"
    assert add_peptide_dialog._dialog_snapshot(values) == snap


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="Tk GUI test requires DISPLAY")
def test_rc15_dialog_exposes_recipe_backup_import_and_unsaved_close(tmp_path, monkeypatch):
    monkeypatch.setenv("SPPS_PLANNER_USER_DATA", str(tmp_path))
    app = SPPSGui()
    try:
        app.deiconify(); app.update()
        app.pm_add_button.invoke(); app.update()
        assert hasattr(app, "add_peptide_backup_recipe_button")
        assert hasattr(app, "add_peptide_import_recipe_button")
        app.add_peptide_dialog_vars["sequence"].set("ACDE")
        app.update()
        assert app.add_peptide_confirm_button.instate(["!disabled"])
    finally:
        try:
            app.add_peptide_dialog.destroy()
        except Exception:
            pass
        try:
            app.destroy()
        except tk.TclError:
            pass


def test_default_names_avoid_existing_pair_and_lot_collision():
    class Gui:
        pm_items = [
            {"project": "Project-002", "peptide": "Peptide-002", "lot": "SPPS-261006-SPPS"},
            {"project": "Project-003", "peptide": "Peptide-003", "lot": "SPPS-261006-SPPS-02"},
        ]
        def _generate_lot_no(self):
            return "SPPS-261006-SPPS"
    project, peptide, lot = add_peptide_dialog._default_names(Gui())
    assert (project, peptide) == ("Project-004", "Peptide-004")
    assert lot == "SPPS-261006-SPPS-03"


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="Tk GUI test requires DISPLAY")
def test_unsaved_close_can_be_cancelled_then_confirmed(tmp_path, monkeypatch):
    monkeypatch.setenv("SPPS_PLANNER_USER_DATA", str(tmp_path))
    app = SPPSGui()
    try:
        app.deiconify(); app.update()
        app.pm_add_button.invoke(); app.update()
        app.add_peptide_dialog_vars["sequence"].set("ACDE")
        app.update()
        monkeypatch.setattr(add_peptide_dialog.messagebox, "askyesno", lambda *a, **k: False)
        app.add_peptide_request_close(); app.update()
        assert app.add_peptide_dialog.winfo_exists()
        monkeypatch.setattr(add_peptide_dialog.messagebox, "askyesno", lambda *a, **k: True)
        app.add_peptide_request_close(); app.update()
        assert not app.add_peptide_dialog.winfo_exists()
    finally:
        try:
            app.destroy()
        except tk.TclError:
            pass
