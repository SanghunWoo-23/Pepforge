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


def test_terminal_deprotection_classifier_uses_nterm_fmoc_only():
    from suite_gui.modules import plan_workflow as ctl

    for protected in (
        "Fmoc-Gly-OH",
        "N-Fmoc-Gly-OH",
        "Nalpha-Fmoc-Gly-OH",
        "Nα-Fmoc-Gly-OH",
        "Fmoc-6-Ahx-OH",
        "Fmoc-AEEA-OH / Fmoc-amino-PEG acid",
    ):
        assert ctl._has_nterm_temporary_protection(protected), protected

    # Side-chain/acid-labile protecting groups do not trigger the standard
    # terminal piperidine cycle.  A side-chain Fmoc mention alone must also not
    # be mistaken for an N-terminal Fmoc handle.
    for unprotected_nterm in (
        "Ac-Glu(OtBu)-OH",
        "H-Lys(Fmoc)-OH",
        "Boc-Lys(Fmoc)-OH",
        "Fmoc-free Lys(Boc)-OH",
        "Acetic anhydride (Ac2O)",
    ):
        assert not ctl._has_nterm_temporary_protection(unprotected_nterm), unprotected_nterm


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="Tk GUI test requires DISPLAY")
def test_terminal_fmoc_aa_like_linker_gets_final_deprotection(monkeypatch, tmp_path):
    gui = _new_gui(monkeypatch, tmp_path)
    try:
        gui.pm_sequence.set("Ahx-GHTYKL-NH2")
        gui.pm_scale.set("1")
        gui.pm_resin.set("Rink Amide AM")
        assert gui.pm_generate_selected() is True

        plan = _rows(gui.pm_selected_plan_tree)
        assert plan[-1]["Unit name"] == "Fmoc-6-Ahx-OH"

        checklist = _rows(gui.progress_tree)
        last_coupling = max(
            i for i, row in enumerate(checklist)
            if row["unit"] == "Fmoc-6-Ahx-OH" and row["operation"] in {"Coupling / reaction", "Coupling 2", "Coupling 3", "Coupling 4"}
        )
        assert [row["operation"] for row in checklist[last_coupling + 1:last_coupling + 6]] == [
            "Post-coupling DMF wash x2",
            "Last Fmoc deprotection 1",
            "Last Fmoc deprotection 2",
            "Final DMF wash x3",
            "Final MC/DCM wash x3",
        ]
    finally:
        gui.destroy()


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="Tk GUI test requires DISPLAY")
def test_apply_change_custom_n_fmoc_terminal_unit_gets_final_deprotection(monkeypatch, tmp_path):
    gui = _new_gui(monkeypatch, tmp_path)
    try:
        from suite_gui.modules import plan_workflow as ctl

        gui.pm_sequence.set("GHTYKL-NH2")
        gui.pm_scale.set("1")
        gui.pm_resin.set("Rink Amide AM")
        assert gui.pm_generate_selected() is True

        tree = gui.pm_selected_plan_tree
        final_iid = tree.get_children()[-1]
        row = ctl._row_dict(tree, final_iid)
        row["Unit name"] = "N-Fmoc-Gly-OH"
        ctl._write_row(tree, final_iid, row)
        gui._v229_dirty_columns = {final_iid: {"Unit name"}}
        assert gui.pm_apply_change() is True

        checklist = _rows(gui.progress_tree)
        tail_ops = [r["operation"] for r in checklist if r["unit"] == "N-Fmoc-Gly-OH"]
        assert "Last Fmoc deprotection 1" in tail_ops
        assert "Last Fmoc deprotection 2" in tail_ops
        assert tail_ops[-2:] == ["Final DMF wash x3", "Final MC/DCM wash x3"]
    finally:
        gui.destroy()
