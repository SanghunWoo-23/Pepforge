from __future__ import annotations

import os
from pathlib import Path

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
    return gui, ctl


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="Tk GUI test requires DISPLAY")
def test_apply_change_preserves_direct_2ctc_loading_row_while_applying_other_plan_edits(monkeypatch, tmp_path):
    gui, ctl = _new_gui(monkeypatch, tmp_path)
    try:
        gui.pm_sequence.set("GHK")
        gui.pm_scale.set("1")
        gui.pm_resin.set("2-CTC")
        gui.pm_chemistry.set("DIC/HOBt")
        gui.apply_loading_calc.set(True)
        gui.loading_aa_eq.set("2")
        gui.loading_diea_eq.set("4")
        assert gui.pm_generate_selected() is True
        gui.update_idletasks()

        tree = gui.pm_selected_plan_tree
        first_iid, second_iid, *_ = tree.get_children()
        loading_before = ctl._row_dict(tree, first_iid)
        assert "direct loading" in loading_before["Note"].lower()
        assert loading_before["Reagent 1"] == ""
        assert loading_before["Reagent 2 / catalyst"] == ""
        assert loading_before["Base"] == "DIEA"
        assert loading_before["Coupling solvent"] == "DCM"

        # Edit a normal coupling row, then apply the whole Plan.  The first
        # direct-loading row must not be rebuilt with ordinary DIC/HOBt chemistry.
        normal = ctl._row_dict(tree, second_iid)
        normal["Unit eq"] = "2.5"
        ctl._write_row(tree, second_iid, normal)
        gui._v229_dirty_columns = {second_iid: {"Unit eq"}}
        assert gui.pm_apply_change() is True
        gui.update_idletasks()

        loading_after = ctl._row_dict(tree, first_iid)
        for column in (
            "Unit name", "Unit eq", "Unit mmol", "Unit amount",
            "Reagent 1", "R1 eq", "R1 mmol", "R1 amount",
            "Reagent 2 / catalyst", "R2 eq", "R2 mmol", "R2 amount",
            "Base", "Base eq", "Base mmol", "Base amount",
            "Coupling solvent", "Solvent mL", "Repeat", "Note",
        ):
            assert loading_after[column] == loading_before[column], column
        assert loading_after["Reagent 1"] == ""
        assert loading_after["Reagent 2 / catalyst"] == ""
        assert ctl._row_dict(tree, second_iid)["Unit eq"] == "2.5"

        step_one_materials = [
            row for row in _rows(gui.pm_selected_material_tree)
            if str(row.get("step", "")) == str(loading_after["No"])
        ]
        names = {str(row.get("material", "")) for row in step_one_materials}
        assert "DIEA" in names
        assert "DIC" not in names
        assert "HOBt" not in names

        checklist = _rows(gui.progress_tree)
        first_reaction = next(
            row for row in checklist
            if row["unit"] == loading_after["Unit name"] and row["operation"] == "Coupling / reaction"
        )
        assert "R1=  eq" in first_reaction["note"]
        assert "R2=  eq" in first_reaction["note"]
        assert "Base=DIEA" in first_reaction["note"]

        if hasattr(gui, "project_outdir"):
            gui.project_outdir.set(str(tmp_path))
        elif hasattr(gui, "outdir"):
            gui.outdir.set(str(tmp_path))
        exported = gui.export_outputs()
        assert exported is not None and Path(exported).exists()
    finally:
        gui.destroy()

@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="Tk GUI test requires DISPLAY")
def test_terminal_plan_edit_on_2ctc_keeps_loading_and_applies_ac_glu_final_std(monkeypatch, tmp_path):
    gui, ctl = _new_gui(monkeypatch, tmp_path)
    try:
        gui.pm_sequence.set("Ac-EEMARR")
        gui.pm_scale.set("1")
        gui.pm_resin.set("2-CTC")
        gui.pm_chemistry.set("DIC/HOBt")
        gui.apply_loading_calc.set(True)
        assert gui.pm_generate_selected() is True
        gui.update_idletasks()

        tree = gui.pm_selected_plan_tree
        first_iid = tree.get_children()[0]
        final_iid = tree.get_children()[-1]
        loading_before = ctl._row_dict(tree, first_iid)

        final = ctl._row_dict(tree, final_iid)
        final["Unit name"] = "Ac-Glu(OtBu)-OH"
        ctl._write_row(tree, final_iid, final)
        gui._v229_dirty_columns = {final_iid: {"Unit name"}}
        assert gui.pm_apply_change() is True
        gui.update_idletasks()

        loading_after = ctl._row_dict(tree, first_iid)
        assert loading_after == loading_before
        assert loading_after["Reagent 1"] == ""
        assert loading_after["Reagent 2 / catalyst"] == ""
        assert loading_after["Base"] == "DIEA"

        final_after = ctl._row_dict(tree, final_iid)
        assert final_after["Unit name"] == "Ac-Glu(OtBu)-OH"
        checklist = _rows(gui.progress_tree)
        final_coupling = max(
            index for index, row in enumerate(checklist)
            if row["unit"] == "Ac-Glu(OtBu)-OH" and row["operation"] in {"Coupling / reaction", "Coupling 2"}
        )
        assert [row["operation"] for row in checklist[final_coupling + 1:final_coupling + 3]] == [
            "Final DMF wash x3",
            "Final MC/DCM wash x3",
        ]
        assert not any("deprotection" in row["operation"].lower() for row in checklist[final_coupling + 1:])
    finally:
        gui.destroy()
