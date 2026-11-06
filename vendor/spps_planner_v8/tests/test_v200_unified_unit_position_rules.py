from __future__ import annotations

import os

import pytest


def _rows(tree):
    columns = list(tree["columns"])
    return [dict(zip(columns, tree.item(iid, "values"))) for iid in tree.get_children()]


def _new_gui(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    from suite_gui.modules import plan_workflow as ctl
    ctl.messagebox.showerror = lambda *a, **k: None
    ctl.messagebox.showinfo = lambda *a, **k: None
    from suite_gui.classic_2094_tk_gui import SPPSGui
    monkeypatch.setattr(SPPSGui, "_state_file_path", lambda self: tmp_path / "state.json", raising=False)
    gui = SPPSGui()
    gui.withdraw()
    gui.update_idletasks()
    gui.pm_list.selection_clear(0, "end")
    gui.pm_list.selection_set(0)
    gui.pm_on_double_click()
    gui.update_idletasks()
    return gui


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="Tk GUI test requires DISPLAY")
def test_position_rules_cover_aa_daa_chemical_label_tag_and_linker(monkeypatch, tmp_path):
    gui = _new_gui(monkeypatch, tmp_path)
    try:
        gui.pm_scale.set("1")
        gui.pm_resin.set("Rink Amide AM")
        gui.coupling_eq.set("5")
        gui.position_aa_eq_rules.set("1-20:1.75")
        gui.position_doubling_rules.set("1-20:2")

        cases = {
            "Ac-EEMARR-NH2": "Acetic anhydride (Ac2O)",
            "dA-EEMARR-NH2": "Fmoc-D-Ala-OH",
            "FITC-Ahx-EEMARR-NH2": "FITC isothiocyanate",
            "Biotin-PEG4-EEMARR-NH2": "Biotin acid",
            "His6-Ahx-EEMARR-NH2": "His6 peptide tag macro (HHHHHH)",
        }
        for sequence, expected_unit in cases.items():
            gui.pm_sequence.set(sequence)
            assert gui.pm_generate_selected() is True
            plan = _rows(gui.pm_selected_plan_tree)
            assert any(row["Unit name"] == expected_unit for row in plan)
            # Every written synthesis unit shares one C-terminal position-rule system.
            assert all(row["Unit eq"] == "1.75" for row in plan)
            assert all(row["Repeat"] == "2" for row in plan)

        # Internal linkers are also part of the same position sequence.
        gui.pm_sequence.set("FITC-Ahx-EEMARR-NH2")
        assert gui.pm_generate_selected() is True
        plan = _rows(gui.pm_selected_plan_tree)
        ahx = next(row for row in plan if row["Unit name"] == "Fmoc-6-Ahx-OH")
        assert ahx["Unit eq"] == "1.75"
        assert ahx["Repeat"] == "2"
    finally:
        gui.destroy()
