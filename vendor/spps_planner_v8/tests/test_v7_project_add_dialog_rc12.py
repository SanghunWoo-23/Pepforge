from __future__ import annotations

import os
import tkinter as tk

import pytest

from suite_gui.modules import add_peptide_dialog
from suite_gui.release import SPPSGui


def _item(**overrides):
    data = {
        "work_item_id": "keep-me",
        "project": "P1", "peptide": "Pep1", "sequence": "ACD", "scale": "0.2",
        "copies": "1", "resin": "Rink Amide AM", "loading": "0.8", "lot": "L1",
        "chemistry": "DIC/HOBt", "method_label": "DIC + HOBt hydrate", "status": "Calculated",
        "default_reagent": "DIC", "default_reagent_eq": "5", "default_reagent_count": "1",
        "default_catalyst": "HOBt hydrate", "default_catalyst_eq": "5", "default_catalyst_count": "1",
        "default_base": "", "default_base_eq": "0", "default_base_count": "0",
        "default_coupling_solution_solvent": "DMF", "coupling_eq": "5",
        "reagent_eq_follows_coupling_eq": "True",
        "selected_plan_rows": [{"No": 1}],
        "selected_material_rows": [{"material": "DIC"}],
        "selected_total_rows": [{"material": "DIC"}],
        "selected_checklist_rows": [{"done": False}],
        "selected_cleavage_rows": [{"component": "TFA"}],
    }
    data.update(overrides)
    return data


def test_dialog_values_from_item_loads_exact_saved_bottle_form():
    values = add_peptide_dialog._dialog_values_from_item(_item())
    assert values["sequence"] == "ACD"
    assert values["additive"] == "HOBt hydrate"
    assert values["preset"] == "DIC + HOBt hydrate"


def test_replace_project_item_preserves_identity_and_invalidates_stale_outputs_when_plan_changes():
    class Gui:
        def __init__(self):
            self.pm_items = [_item()]

    gui = Gui()
    changed = dict(_item(sequence="ACE", selected_plan_rows=[]))
    # Put cached outputs back into the incoming payload to prove the replace path
    # actively clears them when the planning signature changed.
    changed["selected_plan_rows"] = [{"No": 99}]
    updated = add_peptide_dialog._replace_project_item(gui, 0, changed)
    assert updated["work_item_id"] == "keep-me"
    assert updated["sequence"] == "ACE"
    assert updated["status"] == "Ready"
    for key in add_peptide_dialog._CACHED_OUTPUT_FIELDS:
        assert key not in updated


def test_replace_project_item_keeps_cached_outputs_for_metadata_only_change():
    class Gui:
        def __init__(self):
            self.pm_items = [_item()]

    gui = Gui()
    renamed = dict(_item(project="Renamed", peptide="Pep-new", lot="L2"))
    updated = add_peptide_dialog._replace_project_item(gui, 0, renamed)
    assert updated["project"] == "Renamed"
    assert updated["selected_plan_rows"] == [{"No": 1}]
    assert updated["status"] == "Calculated"


def test_replace_project_item_preserves_custom_eq_when_recipe_is_unchanged():
    class Gui:
        def __init__(self):
            self.pm_items = [_item(coupling_eq="7", default_reagent_eq="7", default_catalyst_eq="7")]

    gui = Gui()
    incoming = _item(sequence="ACE", coupling_eq="5", default_reagent_eq="5", default_catalyst_eq="5")
    updated = add_peptide_dialog._replace_project_item(gui, 0, incoming)
    assert updated["sequence"] == "ACE"
    assert updated["coupling_eq"] == "7"
    assert updated["default_reagent_eq"] == "7"
    assert updated["default_catalyst_eq"] == "7"
    assert updated["status"] == "Ready"
    assert "selected_plan_rows" not in updated


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="Tk GUI test requires DISPLAY")
def test_edit_setup_reuses_add_dialog_updates_same_row_and_clears_stale_results():
    app = SPPSGui()
    try:
        app.deiconify(); app.update()
        app.pm_items[0] = _item()
        app.pm_refresh_list(keep_index=0)
        app.pm_list.selection_clear(0, "end")
        app.pm_list.selection_set(0); app.pm_list.activate(0)
        app.update()

        assert hasattr(app, "pm_edit_setup_button")
        app.pm_edit_setup_button.invoke(); app.update()
        assert app.add_peptide_dialog_mode == "edit"
        assert app.add_peptide_dialog_item_index == 0
        values = app.add_peptide_dialog_vars
        assert values["sequence"].get() == "ACD"
        assert values["additive"].get() == "HOBt hydrate"
        assert app.add_peptide_confirm_button.cget("text") == "Save changes"

        values["additive"].set("HOBt (anhydrous)")
        app.update()
        assert values["preset"].get() == "DIC + HOBt (anhydrous)"
        app.add_peptide_confirm_button.invoke(); app.update()

        assert len(app.pm_items) == 1
        saved = app.pm_items[0]
        assert saved["work_item_id"] == "keep-me"
        assert saved["default_catalyst"] == "HOBt (anhydrous)"
        assert saved["status"] == "Ready"
        assert "selected_plan_rows" not in saved
    finally:
        try:
            app.destroy()
        except tk.TclError:
            pass
