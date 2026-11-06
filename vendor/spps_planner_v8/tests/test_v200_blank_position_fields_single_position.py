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


def test_single_position_parser_and_blank_rule_have_no_hidden_defaults():
    from suite_gui.modules.operator_controls import _parse_ranges

    assert _parse_ranges("7:2", [(4, 6, 2.0)]) == [(7, 7, 2.0)]
    assert _parse_ranges(" 7 : 1.5 ", []) == [(7, 7, 1.5)]
    assert _parse_ranges("1-3:1.5, 7:2", []) == [(1, 3, 1.5), (7, 7, 2.0)]
    assert _parse_ranges("", [(1, 3, 1.5), (4, 6, 2.0)]) == []


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="Tk GUI test requires DISPLAY")
def test_position_rule_fields_start_blank_and_7_colon_2_applies_only_position_7(monkeypatch, tmp_path):
    gui = _new_gui(monkeypatch, tmp_path)
    try:
        # The two highlighted rule fields start visually empty; the example label remains separate.
        assert gui.position_aa_eq_rules.get() == ""
        assert gui.position_doubling_rules.get() == ""

        gui.pm_scale.set("1")
        gui.pm_resin.set("Rink Amide AM")
        gui.pm_sequence.set("Ac-AAAAAA-NH2")
        gui.use_position_doubling.set(True)

        # Blank startup rules do not silently apply any old presets.
        assert gui.pm_generate_selected() is True
        gui.update()
        assert [row["Repeat"] for row in _rows(gui.pm_selected_plan_tree)] == ["1"] * 7

        # A single-position rule must work immediately through Apply Change too.
        gui.position_doubling_rules.set("7:2")
        assert gui.pm_apply_change() is True
        gui.update()

        plan = _rows(gui.pm_selected_plan_tree)
        assert len(plan) == 7
        repeats = [row["Repeat"] for row in plan]
        # Plan is C -> N, so C-term positions 1..7 map in row order; only the N-terminal Ac is position 7.
        assert repeats == ["1", "1", "1", "1", "1", "1", "2"]
        assert "Ac2O" in plan[-1]["Unit name"]
    finally:
        gui.destroy()
