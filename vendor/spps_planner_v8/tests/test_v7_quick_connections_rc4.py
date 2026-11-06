from __future__ import annotations

import os
import tkinter as tk

import pytest

from suite_gui.release import SPPSGui


def _add_peptide(app, sequence="Ac-EEMQRR-NH2", preset="HBTU + NMM"):
    app.pm_add_button.invoke(); app.update()
    v = app.add_peptide_dialog_vars
    v["sequence"].set(sequence)
    v["scale"].set("0.2")
    v["copies"].set("1")
    v["resin"].set("Rink Amide AM")
    v["loading"].set("0.8")
    if preset == "HBTU + NMM":
        v["preset"].set(preset); v["reagent"].set("HBTU"); v["additive"].set(""); v["base"].set("NMM"); v["solvent"].set("DMF")
    else:
        v["preset"].set("DIC + HOBt"); v["reagent"].set("DIC"); v["additive"].set("HOBt"); v["base"].set(""); v["solvent"].set("DMF")
    app.add_peptide_confirm_button.invoke(); app.update()


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="Tk GUI test requires DISPLAY")
def test_project_add_then_loading_advisor_receives_cterm_identity():
    app = SPPSGui()
    try:
        app.update_idletasks()
        _add_peptide(app)
        app.pm_generate_selected(); app.update_idletasks()
        window = app.open_loading_advisor(); app.update_idletasks()
        assert window.load_resin.get() == "Rink Amide AM"
        assert window.load_target.get() == "0.8"
        assert window.load_aa.get() == "Fmoc-Arg(Pbf)-OH"
        window.destroy()
    finally:
        try: app.destroy()
        except tk.TclError: pass


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="Tk GUI test requires DISPLAY")
def test_first_project_add_reuses_only_blank_startup_placeholder():
    app = SPPSGui()
    try:
        app.update_idletasks()
        assert len(app.pm_items) == 1
        assert not str(app.pm_items[0].get("sequence") or "").strip()
        _add_peptide(app, sequence="AAAA", preset="DIC + HOBt")
        assert len(app.pm_items) == 1
        assert app.pm_items[0]["sequence"] == "AAAA"
        assert app.pm_current_index() == 0
    finally:
        try: app.destroy()
        except tk.TclError: pass
