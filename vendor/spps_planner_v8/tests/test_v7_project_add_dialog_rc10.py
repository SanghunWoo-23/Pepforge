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


def test_recipe_preview_is_short_and_exact_bottle_form_is_visible():
    text = add_peptide_dialog._recipe_preview(_values())
    assert "DIC + HOBt hydrate" in text
    assert "(no base)" in text
    assert "DMF" in text


def test_live_check_blocks_missing_or_unparseable_sequence_and_bad_numbers():
    ready, summary, _ = add_peptide_dialog._live_check(_values(sequence=""))
    assert not ready and "sequence" in summary.lower()
    ready, summary, note = add_peptide_dialog._live_check(_values(sequence="???"))
    assert not ready and "sequence" in summary.lower()
    assert "No peptide residues" in note
    ready, summary, _ = add_peptide_dialog._live_check(_values(scale="0"))
    assert not ready and "Scale" in summary


def test_live_check_allows_unknown_exact_bottle_name_with_warning():
    ready, summary, note = add_peptide_dialog._live_check(
        _values(additive="Supplier HOBt hydrate batch X")
    )
    assert ready
    assert "3 residues" in summary
    assert "Custom bottle name" in note
    assert "Supplier HOBt hydrate batch X" in note


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="Tk GUI test requires DISPLAY")
def test_add_button_unlocks_only_after_required_fields_are_ready_and_review_updates():
    app = SPPSGui()
    try:
        app.deiconify(); app.update()
        app.pm_add_button.invoke(); app.update()
        assert str(app.add_peptide_confirm_button.cget("state")) == "disabled"
        v = app.add_peptide_dialog_vars
        v["sequence"].set("ACD")
        v["additive"].set("HOBt hydrate")
        app.update()
        assert str(app.add_peptide_confirm_button.cget("state")) == "normal"
        assert "3 residues" in app.add_peptide_ready_summary_var.get()
        assert "HOBt hydrate" in app.add_peptide_recipe_preview_var.get()
        assert "DMF" in app.add_peptide_recipe_preview_var.get()

        v["scale"].set("0")
        app.update()
        assert str(app.add_peptide_confirm_button.cget("state")) == "disabled"
        assert "Scale" in app.add_peptide_ready_summary_var.get()
    finally:
        try:
            app.destroy()
        except tk.TclError:
            pass


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="Tk GUI test requires DISPLAY")
def test_add_dialog_scrolls_from_sequence_entry_mousewheel():
    app = SPPSGui()
    try:
        app.geometry("1200x800+100+50")
        app.deiconify(); app.update()
        app.pm_add_button.invoke(); app.update()
        canvas = app.add_peptide_canvas
        before = canvas.yview()[0]
        focused = app.add_peptide_dialog.focus_get()
        assert focused is not None
        focused.event_generate("<MouseWheel>", delta=-120)
        app.update()
        after = canvas.yview()[0]
        assert after > before
    finally:
        try:
            app.destroy()
        except tk.TclError:
            pass
