from __future__ import annotations

import os
from tkinter import ttk

import pytest


def _walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _walk(child)


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
def test_setup_ui_and_custom_db_are_preserved(monkeypatch, tmp_path):
    gui = _new_gui(monkeypatch, tmp_path)
    try:
        gui.deiconify()
        gui.update()
        for widget in _walk(gui):
            if isinstance(widget, ttk.Button) and str(widget.cget("text")) == "Show setup" and widget.winfo_viewable():
                widget.invoke()
                break
        gui.update()

        assert any(
            isinstance(widget, ttk.Button)
            and str(widget.cget("text")) == "Hide setup"
            and widget.winfo_viewable()
            for widget in _walk(gui)
        )

        tab_sets = []
        for widget in _walk(gui):
            if isinstance(widget, ttk.Notebook):
                tab_sets.append([str(widget.tab(tab, "text")) for tab in widget.tabs()])
        assert ["Loading", "Unit defaults", "Reagents", "Solvents / Wash", "Branch / Tools", "Output", "Custom DB"] in tab_sets

        frame_texts = [
            str(widget.cget("text"))
            for widget in _walk(gui)
            if isinstance(widget, ttk.LabelFrame)
        ]
        assert "Position rules from C-terminus" in frame_texts
        assert "Position rules from N-terminus" not in frame_texts
    finally:
        gui.destroy()


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="Tk GUI test requires DISPLAY")
def test_cterm_ranges_count_the_written_cterm_residue_for_direct_2ctc(monkeypatch, tmp_path):
    gui = _new_gui(monkeypatch, tmp_path)
    try:
        gui.pm_sequence.set("ACDEFGH")
        gui.pm_scale.set("1")
        gui.pm_resin.set("2-CTC")
        # Position-rule fields now intentionally start blank.  Enter the
        # historical rules explicitly here so this regression continues to
        # verify the direct-2CTC C-terminal offset behavior itself.
        gui.position_aa_eq_rules.set("1-3:1.5, 4-6:2")
        gui.position_doubling_rules.set("4-6:2")
        assert gui.pm_generate_selected() is True
        plan = _rows(gui.pm_selected_plan_tree)

        # H is the directly loaded C-terminal residue (position 1) and is not a
        # coupling row. The visible coupling rows therefore begin at position 2.
        assert [(row["Unit name"], row["Unit eq"], row["Repeat"]) for row in plan] == [
            ("Fmoc-Gly-OH", "1.5", "1"),  # C-term position 2
            ("Fmoc-Phe-OH", "1.5", "1"),  # C-term position 3
            ("Fmoc-Glu(OtBu)-OH", "2", "2"),  # position 4
            ("Fmoc-Asp(OtBu)-OH", "2", "2"),  # position 5
            ("Fmoc-Cys(Trt)-OH", "2", "2"),  # position 6
            ("Fmoc-Ala-OH", "5", "1"),  # position 7: existing fallback unchanged
        ]
    finally:
        gui.destroy()


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="Tk GUI test requires DISPLAY")
def test_ghk_terminal_sequence_matches_operator_std(monkeypatch, tmp_path):
    gui = _new_gui(monkeypatch, tmp_path)
    try:
        gui.pm_sequence.set("GHK")
        gui.pm_scale.set("1000")
        gui.pm_resin.set("2-CTC")
        gui.pm_chemistry.set("DIC/HOBt")
        assert gui.pm_generate_selected() is True

        plan = _rows(gui.pm_selected_plan_tree)
        assert [row["Unit name"] for row in plan] == ["Fmoc-His(Trt)-OH", "Fmoc-Gly-OH"]
        assert not any("Fmoc removal" in row["Unit name"] for row in plan)

        checklist = _rows(gui.progress_tree)
        gly_coupling = max(i for i, row in enumerate(checklist) if row["operation"] == "Coupling / reaction" and row["unit"] == "Fmoc-Gly-OH")
        assert [row["operation"] for row in checklist[gly_coupling + 1:gly_coupling + 6]] == [
            "Post-coupling DMF wash x2",
            "Last Fmoc deprotection 1",
            "Last Fmoc deprotection 2",
            "Final DMF wash x3",
            "Final MC/DCM wash x3",
        ]
        assert not any(row["operation"] == "DMF wash x6" for row in checklist[gly_coupling + 1:])

        materials = _rows(gui.pm_selected_material_tree)
        final_step = str(plan[-1]["No"])
        final_materials = [row for row in materials if str(row["step"]) == final_step]
        assert any(row["material"] == "Piperidine" and row["phase"] == "Last deprotection" for row in final_materials)
        assert not any(row["class"] == "Post-deprotection wash solvent" for row in final_materials)
        assert any(row["material"] == "DMF" and row["class"] == "Final wash solvent" and str(row["use_count"]) == "3" for row in final_materials)
        assert any(row["material"] == "MC/DCM" and row["class"] == "Final wash solvent" and str(row["use_count"]) == "3" for row in final_materials)
    finally:
        gui.destroy()


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="Tk GUI test requires DISPLAY")
def test_acetylation_terminal_sequence_matches_operator_std(monkeypatch, tmp_path):
    gui = _new_gui(monkeypatch, tmp_path)
    try:
        gui.pm_sequence.set("Ac-EEMARR-NH2")
        gui.pm_scale.set("1")
        gui.pm_resin.set("Rink Amide AM")
        gui.pm_chemistry.set("DIC/HOBt")
        assert gui.pm_generate_selected() is True

        plan = _rows(gui.pm_selected_plan_tree)
        assert plan[-1]["Unit name"] == "Acetic anhydride (Ac2O)"
        checklist = _rows(gui.progress_tree)
        acetylation = max(i for i, row in enumerate(checklist) if row["operation"] == "Coupling / reaction" and "Ac2O" in row["unit"])
        assert [row["operation"] for row in checklist[acetylation + 1:acetylation + 3]] == [
            "Final DMF wash x3",
            "Final MC/DCM wash x3",
        ]
        assert not any(row["operation"] == "Post-acetylation DMF wash x2" for row in checklist[acetylation + 1:])
        assert not any("deprotection" in row["operation"].lower() for row in checklist[acetylation + 1:])

        materials = _rows(gui.pm_selected_material_tree)
        final_step = str(plan[-1]["No"])
        final_materials = [row for row in materials if str(row["step"]) == final_step]
        assert not any(row["class"] == "Post-coupling wash solvent" for row in final_materials)
        assert any(row["material"] == "DMF" and row["class"] == "Final wash solvent" and str(row["use_count"]) == "3" for row in final_materials)
        assert any(row["material"] == "MC/DCM" and row["class"] == "Final wash solvent" and str(row["use_count"]) == "3" for row in final_materials)
    finally:
        gui.destroy()


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="Tk GUI test requires DISPLAY")
def test_ac_glu_terminal_sequence_matches_operator_std(monkeypatch, tmp_path):
    gui = _new_gui(monkeypatch, tmp_path)
    try:
        from suite_gui.modules import plan_workflow as ctl

        gui.pm_sequence.set("EEMARR-NH2")
        gui.pm_scale.set("1")
        gui.pm_resin.set("Rink Amide AM")
        gui.pm_chemistry.set("DIC/HOBt")
        assert gui.pm_generate_selected() is True

        tree = gui.pm_selected_plan_tree
        final_iid = tree.get_children()[-1]
        row = ctl._row_dict(tree, final_iid)
        row["Unit name"] = "Ac-Glu(OtBu)-OH"
        ctl._write_row(tree, final_iid, row)
        gui._v229_dirty_columns = {final_iid: {"Unit name"}}
        assert gui.pm_apply_change() is True

        checklist = _rows(gui.progress_tree)
        final_coupling = max(
            i for i, row in enumerate(checklist)
            if row["unit"] == "Ac-Glu(OtBu)-OH" and row["operation"] in {"Coupling / reaction", "Coupling 2"}
        )
        assert [row["operation"] for row in checklist[final_coupling + 1:final_coupling + 3]] == [
            "Final DMF wash x3",
            "Final MC/DCM wash x3",
        ]
        assert not any(row["operation"] in {"DMF wash x2", "Post-coupling DMF wash x2"} for row in checklist[final_coupling + 1:])
        assert not any("deprotection" in row["operation"].lower() for row in checklist[final_coupling + 1:])
        assert not any(row["operation"] == "DMF wash x6" for row in checklist[final_coupling + 1:])

        materials = _rows(gui.pm_selected_material_tree)
        final_step = str(_rows(gui.pm_selected_plan_tree)[-1]["No"])
        final_materials = [row for row in materials if str(row["step"]) == final_step]
        assert not any(row["phase"] == "Post-coupling deprotection" for row in final_materials)
        assert not any(row["class"] == "Post-coupling wash solvent" for row in final_materials)
        assert any(row["material"] == "DMF" and row["class"] == "Final wash solvent" and str(row["use_count"]) == "3" for row in final_materials)
        assert any(row["material"] == "MC/DCM" and row["class"] == "Final wash solvent" and str(row["use_count"]) == "3" for row in final_materials)
    finally:
        gui.destroy()
