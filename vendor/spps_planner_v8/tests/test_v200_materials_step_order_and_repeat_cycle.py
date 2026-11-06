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
def test_materials_and_checklist_follow_exact_repeat_cycle_step_order(monkeypatch, tmp_path):
    gui = _new_gui(monkeypatch, tmp_path)
    try:
        gui.pm_scale.set("1")
        gui.pm_resin.set("Rink Amide AM")
        gui.pm_sequence.set("GHK")
        gui.use_position_aa_eq.set(True)
        gui.position_aa_eq_rules.set("1-3:2")
        gui.use_position_doubling.set(True)
        gui.position_doubling_rules.set("1-2:2,3-3:3")
        assert gui.pm_generate_selected() is True
        gui.update()

        checklist = _rows(gui.progress_tree)
        lys = [r["operation"] for r in checklist if r["unit"] == "Fmoc-Lys(Boc)-OH"]
        assert lys == [
            "Deprotection 1", "Deprotection 2", "DMF wash x6",
            "Coupling 1", "DMF wash x2", "Coupling 2", "Post-coupling DMF wash x2",
        ]
        his = [r["operation"] for r in checklist if r["unit"] == "Fmoc-His(Trt)-OH"]
        assert his == [
            "Deprotection 1", "Deprotection 2", "DMF wash x6",
            "Coupling 1", "DMF wash x2", "Coupling 2", "Post-coupling DMF wash x2",
        ]
        gly = [r["operation"] for r in checklist if r["unit"] == "Fmoc-Gly-OH"]
        assert gly == [
            "Deprotection 1", "Deprotection 2", "DMF wash x6",
            "Coupling 1", "DMF wash x2", "Coupling 2", "DMF wash x2", "Coupling 3",
            "Post-coupling DMF wash x2",
            "Last Fmoc deprotection 1", "Last Fmoc deprotection 2",
            "Final DMF wash x3", "Final MC/DCM wash x3",
        ]

        materials = _rows(gui.pm_selected_material_tree)
        # Materials must be grouped in actual synthesis step order, never with
        # inter-coupling wash rows appended at the bottom of the whole table.
        step1 = [r for r in materials if r["step"] == "1"]
        phases1 = [r["phase"] for r in step1]
        assert phases1[:3] == ["Deprotection", "Deprotection", "DMF wash"]
        assert phases1[3:7] == ["Coupling 1"] * 4
        assert phases1[7] == "DMF wash"
        assert phases1[8:12] == ["Coupling 2"] * 4
        assert phases1[12] == "DMF wash"
        assert step1[2]["class"] == "Pre-coupling wash solvent"
        assert step1[2]["use_count"] == "6"
        assert step1[7]["class"] == "Inter-coupling wash solvent"
        assert step1[7]["use_count"] == "2"
        assert step1[12]["class"] == "Post-coupling wash solvent"
        assert step1[12]["use_count"] == "2"

        # Step 2 must begin only after every Step 1 material/protocol row.
        # Final R1+ also appends cleavage/workup materials because Generate now
        # refreshes every result tab from one calculation snapshot.  Numeric
        # synthesis steps must still remain in strict order; post-synthesis
        # phases are intentionally non-numeric and follow afterward.
        positions = [r["step"] for r in materials if str(r["step"]).isdigit()]
        assert positions == sorted(positions, key=int)
        non_synthesis = [r["step"] for r in materials if r["step"] not in {"resin"} and not str(r["step"]).isdigit()]
        assert all(step in {"cleavage", "workup"} for step in non_synthesis)

        # Split per-coupling material rows must still sum to the Plan total.
        gly_materials = [r for r in materials if r["material"] == "Fmoc-Gly-OH"]
        assert len(gly_materials) == 3
        assert sum(float(r["planned_mmol"]) for r in gly_materials) == pytest.approx(6.0)
    finally:
        gui.destroy()
