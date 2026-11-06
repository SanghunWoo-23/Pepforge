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
def test_doubling_changes_real_amounts_materials_checklist_and_totals(monkeypatch, tmp_path):
    """Repeat=2 must be a real second coupling, not a checkbox/Plan-display-only flag."""
    gui = _new_gui(monkeypatch, tmp_path)
    try:
        gui.pm_scale.set("1")
        gui.pm_copies.set("1")
        gui.pm_resin.set("Rink Amide AM")
        gui.pm_sequence.set("GHK")
        gui.solvent_volume_mode.set("resin_factor")
        gui.amide_ml_per_mmol.set("8")
        gui.use_position_aa_eq.set(True)
        gui.position_aa_eq_rules.set("1-3:2")
        gui.use_position_doubling.set(True)
        gui.position_doubling_rules.set("1-3:2")

        assert gui.pm_generate_selected() is True
        gui.update()

        plan = _rows(gui.pm_selected_plan_tree)
        assert len(plan) == 3
        for row in plan:
            assert row["Unit eq"] == "2"
            assert row["Repeat"] == "2"
            # 1 mmol scale × 2 eq × 2 couplings = 4 mmol total prepared/used.
            assert float(row["Unit mmol"]) == pytest.approx(4.0)
            assert float(row["R1 mmol"]) == pytest.approx(4.0)
            assert float(row["R2 mmol"]) == pytest.approx(4.0)
            # 8 mL working volume per coupling × 2 couplings.
            assert float(row["Solvent mL"]) == pytest.approx(16.0)

        materials = _rows(gui.pm_selected_material_tree)
        gly_rows = [r for r in materials if r["material"] == "Fmoc-Gly-OH"]
        assert len(gly_rows) == 2
        assert sum(float(r["planned_mmol"]) for r in gly_rows) == pytest.approx(4.0)
        assert [r["phase"] for r in gly_rows] == ["Coupling 1", "Coupling 2"]
        dic_rows = [r for r in materials if r["material"] == "DIC" and str(r["phase"]).startswith("Coupling")]
        assert len(dic_rows) == 6
        assert all(float(r["planned_mmol"]) == pytest.approx(2.0) for r in dic_rows)

        checklist = _rows(gui.progress_tree)
        for unit in ("Fmoc-Lys(Boc)-OH", "Fmoc-His(Trt)-OH", "Fmoc-Gly-OH"):
            ops = [r["operation"] for r in checklist if r["unit"] == unit]
            assert "Coupling 1" in ops
            assert "DMF wash x2" in ops
            assert "Coupling 2" in ops

        totals = _rows(gui.pm_selected_total_tree)
        dic_total = next(r for r in totals if r["material"] == "DIC")
        hobt_total = next(r for r in totals if r["material"] == "HOBt")
        gly_total = next(r for r in totals if r["material"] == "Fmoc-Gly-OH")
        assert float(dic_total["total mmol"]) == pytest.approx(12.0)
        assert float(hobt_total["total mmol"]) == pytest.approx(12.0)
        assert float(gly_total["total mmol"]) == pytest.approx(4.0)
    finally:
        gui.destroy()
