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
def test_repeat_range_applies_on_apply_change_and_supports_3x_4x(monkeypatch, tmp_path):
    gui = _new_gui(monkeypatch, tmp_path)
    try:
        gui.pm_scale.set("1")
        gui.pm_resin.set("Rink Amide AM")
        gui.pm_sequence.set("GHK")
        gui.use_position_aa_eq.set(True)
        gui.position_aa_eq_rules.set("1-3:2")
        gui.use_position_doubling.set(False)

        assert gui.pm_generate_selected() is True
        plan_before = _rows(gui.pm_selected_plan_tree)
        assert all(row["Repeat"] == "1" for row in plan_before)
        one_coupling_solvent = float(plan_before[0]["Solvent mL"])

        # Change only Setup after a Plan already exists, then Apply Change.
        gui.use_position_doubling.set(True)
        gui.position_doubling_rules.set("1-3:3")
        assert gui.pm_apply_change() is True
        gui.update()

        plan = _rows(gui.pm_selected_plan_tree)
        assert all(row["Repeat"] == "3" for row in plan)
        assert all(float(row["Unit mmol"]) == pytest.approx(6.0) for row in plan)
        assert all(float(row["R1 mmol"]) == pytest.approx(6.0) for row in plan)
        assert all(float(row["R2 mmol"]) == pytest.approx(6.0) for row in plan)
        assert all(float(row["Solvent mL"]) == pytest.approx(one_coupling_solvent * 3) for row in plan)

        checklist = _rows(gui.progress_tree)
        lys_ops = [row["operation"] for row in checklist if row["unit"] == "Fmoc-Lys(Boc)-OH"]
        c1 = lys_ops.index("Coupling 1")
        assert lys_ops[c1:c1 + 6] == [
            "Coupling 1", "DMF wash x2",
            "Coupling 2", "DMF wash x2",
            "Coupling 3", "Post-coupling DMF wash x2",
        ]

        materials = _rows(gui.pm_selected_material_tree)
        gly_rows = [row for row in materials if row["material"] == "Fmoc-Gly-OH"]
        assert len(gly_rows) == 3
        assert sum(float(row["planned_mmol"]) for row in gly_rows) == pytest.approx(6.0)
        assert [row["phase"] for row in gly_rows] == ["Coupling 1", "Coupling 2", "Coupling 3"]
        inter = [row for row in materials if row["class"] == "Inter-coupling wash solvent"]
        assert len(inter) == 6  # 2 inter-coupling intervals for each of 3 Plan steps
        assert all(str(row["use_count"]) == "2" for row in inter)
        assert all(float(row["planned_mL"]) == pytest.approx(one_coupling_solvent * 2) for row in inter)

        totals = _rows(gui.pm_selected_total_tree)
        dic_total = next(row for row in totals if row["material"] == "DIC")
        assert float(dic_total["total mmol"]) == pytest.approx(18.0)

        # The numeric rule value is the coupling count, not a hard-coded x2.
        gui.position_doubling_rules.set("1-3:4")
        assert gui.pm_apply_change() is True
        gui.update()
        plan4 = _rows(gui.pm_selected_plan_tree)
        assert all(row["Repeat"] == "4" for row in plan4)
        assert all(float(row["Unit mmol"]) == pytest.approx(8.0) for row in plan4)
        lys_ops4 = [row["operation"] for row in _rows(gui.progress_tree) if row["unit"] == "Fmoc-Lys(Boc)-OH"]
        c1 = lys_ops4.index("Coupling 1")
        assert lys_ops4[c1:c1 + 8] == [
            "Coupling 1", "DMF wash x2",
            "Coupling 2", "DMF wash x2",
            "Coupling 3", "DMF wash x2",
            "Coupling 4", "Post-coupling DMF wash x2",
        ]

        # Unchecking disables the range immediately on Apply Change.
        gui.use_position_doubling.set(False)
        assert gui.pm_apply_change() is True
        gui.update()
        plan1 = _rows(gui.pm_selected_plan_tree)
        assert all(row["Repeat"] == "1" for row in plan1)
        assert all(float(row["Unit mmol"]) == pytest.approx(2.0) for row in plan1)
        assert not any(row["class"] == "Inter-coupling wash solvent" for row in _rows(gui.pm_selected_material_tree))
    finally:
        gui.destroy()


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="Tk GUI test requires DISPLAY")
def test_terminal_repeat_n_continues_original_terminal_reaction_after_last_coupling(monkeypatch, tmp_path):
    gui = _new_gui(monkeypatch, tmp_path)
    try:
        gui.pm_scale.set("1")
        gui.pm_resin.set("Rink Amide AM")
        gui.pm_sequence.set("Ac-EEMARR-NH2")
        gui.use_position_doubling.set(True)
        # Ac is the 7th written synthesis unit from the C-terminus.
        gui.position_doubling_rules.set("7-7:3")
        assert gui.pm_generate_selected() is True
        gui.update()

        plan = _rows(gui.pm_selected_plan_tree)
        terminal = plan[-1]
        assert "Ac2O" in terminal["Unit name"]
        assert terminal["Repeat"] == "3"

        ops = [row["operation"] for row in _rows(gui.progress_tree) if row["unit"] == terminal["Unit name"]]
        c1 = ops.index("Coupling 1")
        assert ops[c1:] == [
            "Coupling 1", "DMF wash x2",
            "Coupling 2", "DMF wash x2",
            "Coupling 3", "Final DMF wash x3", "Final MC/DCM wash x3",
        ]
        assert not any("deprotection" in op.lower() for op in ops[c1:])
    finally:
        gui.destroy()
