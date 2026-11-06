from __future__ import annotations

import os
import tkinter as tk

import pytest

from suite_gui.modules import add_peptide_dialog
from suite_gui.release import SPPSGui


def test_rc7_add_dialog_has_expanded_coupling_catalogs():
    assert {"DIC", "HBTU", "HATU", "HCTU", "TBTU", "TCTU", "PyBOP", "PyAOP", "COMU", "EDC-HCl"}.issubset(set(add_peptide_dialog.COUPLING_REAGENTS))
    assert {"HOBt", "HOAt", "Oxyma", "6-Cl-HOBt"}.issubset(set(add_peptide_dialog.ADDITIVES))
    assert {"NMM", "DIPEA", "DIEA", "TEA", "2,4,6-Collidine"}.issubset(set(add_peptide_dialog.BASES))
    assert "NMP" not in add_peptide_dialog.BASES
    assert "NMP" in add_peptide_dialog.SOLVENTS


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="Tk GUI test requires DISPLAY")
def test_rc7_main_workspace_has_no_quick_tab_and_add_opens_dialog():
    app = SPPSGui()
    try:
        app.deiconify(); app.update()
        labels = [str(app.tabs.tab(tab, "text")) for tab in app.tabs.tabs()]
        assert "Quick Synthesis" not in labels
        assert labels[:2] == ["Project Manager", "Batch Manager"]
        app.pm_add_button.invoke(); app.update()
        win = app.add_peptide_dialog
        assert win.winfo_exists()
        vars_ = app.add_peptide_dialog_vars
        for key in ("sequence", "scale", "copies", "resin", "loading"):
            assert key in vars_
        assert app.add_peptide_base_combo.winfo_ismapped()
        assert app.add_peptide_reagent_combo.winfo_ismapped()
        win.destroy()
    finally:
        try: app.destroy()
        except tk.TclError: pass
