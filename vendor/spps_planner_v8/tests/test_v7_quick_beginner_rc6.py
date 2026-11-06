from __future__ import annotations

import os
import tkinter as tk

import pytest

from suite_gui.modules import add_peptide_dialog
from suite_gui.release import SPPSGui


class Var:
    def __init__(self, value): self.value = value
    def get(self): return self.value
    def set(self, value): self.value = value


class Gui:
    def __init__(self):
        self.pm_items = []
        self.coupling_eq = Var("5")
        self.default_reagent_eq = Var("5")
        self.default_reagent_count = Var("1")
        self.default_catalyst_eq = Var("5")
        self.default_catalyst_count = Var("1")
        self.default_base_eq = Var("0")
        self.default_base_count = Var("0")
        self.reagent_eq_follows_coupling_eq = Var(True)


def test_add_payload_keeps_step1_visible_values_and_exact_custom_recipe():
    gui = Gui()
    item = add_peptide_dialog.build_item_payload(gui, {
        "project": "P1", "peptide": "pep", "sequence": "Ac-PGHK",
        "scale": "0.1", "copies": "2", "resin": "2-CTC", "loading": "1.39", "lot": "L1",
        "preset": "Custom", "reagent": "HATU", "additive": "HOAt", "base": "DIPEA", "solvent": "DMF",
    })
    assert item["sequence"] == "Ac-PGHK"
    assert item["scale"] == "0.1" and item["copies"] == "2"
    assert item["resin"] == "2-CTC" and item["loading"] == "1.39"
    assert item["chemistry"] == "Manual"
    assert item["default_reagent"] == "HATU"
    assert item["default_catalyst"] == "HOAt"
    assert item["default_base"] == "DIPEA"


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="Tk GUI test requires DISPLAY")
def test_project_add_confirm_creates_item_and_keeps_batch_tab_available():
    app = SPPSGui()
    try:
        app.deiconify(); app.update()
        before = len(app.pm_items)
        startup_blank = before == 1 and not str(app.pm_items[0].get("sequence") or "").strip()
        app.pm_add_button.invoke(); app.update()
        v = app.add_peptide_dialog_vars
        v["sequence"].set("AAAA")
        v["scale"].set("0.2")
        v["copies"].set("1")
        v["resin"].set("Rink Amide AM")
        v["loading"].set("0.8")
        v["preset"].set("HBTU + NMM")
        # Selecting the preset in code does not emit the Tk event; set exact recipe too.
        v["reagent"].set("HBTU"); v["additive"].set(""); v["base"].set("NMM"); v["solvent"].set("DMF")
        app.add_peptide_confirm_button.invoke(); app.update()
        assert len(app.pm_items) == (before if startup_blank else before + 1)
        item = app.pm_items[-1]
        assert item["sequence"] == "AAAA"
        assert item["chemistry"] == "HBTU/NMM"
        assert item["default_base"] == "NMM"
        labels = [str(app.tabs.tab(tab, "text")) for tab in app.tabs.tabs()]
        assert "Batch Manager" in labels
    finally:
        try: app.destroy()
        except tk.TclError: pass
