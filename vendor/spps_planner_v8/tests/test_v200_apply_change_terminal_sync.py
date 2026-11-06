from __future__ import annotations

import os
from pathlib import Path
from tkinter import ttk

import pandas as pd
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
    gui.geometry("1600x1000+0+0")
    gui.update()
    gui.pm_list.selection_clear(0, "end")
    gui.pm_list.selection_set(0)
    gui.pm_on_double_click()
    gui.update()
    return gui


def _visible_button(gui, text):
    buttons = [
        widget
        for widget in _walk(gui)
        if isinstance(widget, ttk.Button)
        and str(widget.cget("text")).strip() == text
        and widget.winfo_viewable()
        and widget.winfo_toplevel() is gui
    ]
    assert len(buttons) == 1
    return buttons[0]


def _edit_last_unit_with_visible_editor(gui, value):
    tree = gui.pm_selected_plan_tree
    final_iid = tree.get_children()[-1]
    tree.selection_set(final_iid)
    tree.focus(final_iid)
    tree.see(final_iid)
    gui.update()

    _visible_button(gui, "Edit Unit name").invoke()
    gui.update()
    editor = getattr(tree, "_v229_editor", None)
    assert editor is not None and editor.winfo_exists()
    editor.set(value)
    editor.event_generate("<Return>")
    gui.update()


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="Tk GUI test requires DISPLAY")
def test_visible_plan_edit_then_apply_change_rebuilds_terminal_protocol_and_export(monkeypatch, tmp_path):
    gui = _new_gui(monkeypatch, tmp_path)
    try:
        gui.pm_sequence.set("Ac-EEMARR-NH2")
        gui.pm_scale.set("1")
        gui.pm_resin.set("Rink Amide AM")
        gui.pm_chemistry.set("DIC/HOBt")
        assert gui.pm_generate_selected() is True
        gui.update()

        _edit_last_unit_with_visible_editor(gui, "Ac-Glu(OtBu)-OH")
        _visible_button(gui, "Apply Change").invoke()
        gui.update()

        plan = _rows(gui.pm_selected_plan_tree)
        assert plan[-1]["Unit name"] == "Ac-Glu(OtBu)-OH"
        assert "Ac2O" not in plan[-1]["Note"]
        assert "coupling -> final DMF wash x3" in plan[-1]["Note"]
        assert "no deprotection" in plan[-1]["Note"]

        checklist = _rows(gui.progress_tree)
        final_coupling = max(
            index
            for index, row in enumerate(checklist)
            if row["unit"] == "Ac-Glu(OtBu)-OH" and row["operation"] == "Coupling / reaction"
        )
        assert [row["operation"] for row in checklist[final_coupling + 1:final_coupling + 3]] == [
            "Final DMF wash x3",
            "Final MC/DCM wash x3",
        ]
        assert not any(
            row["operation"] in {"Post-coupling DMF wash x2", "DMF wash x2"}
            or "deprotection" in row["operation"].lower()
            for row in checklist[final_coupling + 1:]
        )
        assert not any(
            row["operation"] == "DMF wash x6"
            for row in checklist[final_coupling + 1:]
        )

        materials = _rows(gui.pm_selected_material_tree)
        final_step = str(plan[-1]["No"])
        final_materials = [row for row in materials if str(row["step"]) == final_step]
        assert not any(row["phase"] == "Post-coupling deprotection" for row in final_materials)
        assert not any(row["class"] == "Post-coupling wash solvent" for row in final_materials)
        assert any(
            row["material"] == "DMF" and row["class"] == "Final wash solvent" and str(row["use_count"]) == "3"
            for row in final_materials
        )
        assert any(
            row["material"] == "MC/DCM" and row["class"] == "Final wash solvent" and str(row["use_count"]) == "3"
            for row in final_materials
        )

        if hasattr(gui, "project_outdir"):
            gui.project_outdir.set(str(tmp_path))
        elif hasattr(gui, "outdir"):
            gui.outdir.set(str(tmp_path))
        exported = gui.export_outputs()
        assert exported is not None and Path(exported).exists()
        export_plan = pd.read_excel(exported, sheet_name="01_SELECTED_PLAN_VISIBLE")
        export_checklist = pd.read_excel(exported, sheet_name="04_SELECTED_CHECKLIST")
        assert str(export_plan.iloc[-1]["Unit name"]) == "Ac-Glu(OtBu)-OH"
        exported_ops = export_checklist["operation"].astype(str).tolist()
        exported_final = max(
            i
            for i, row in export_checklist.iterrows()
            if str(row.get("unit", "")) == "Ac-Glu(OtBu)-OH" and str(row.get("operation", "")) == "Coupling / reaction"
        )
        assert exported_ops[exported_final + 1:exported_final + 3] == [
            "Final DMF wash x3",
            "Final MC/DCM wash x3",
        ]
        assert not any(
            op in {"Post-coupling DMF wash x2", "DMF wash x2"}
            or "deprotection" in op.lower()
            for op in exported_ops[exported_final + 1:]
        )
    finally:
        gui.destroy()


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="Tk GUI test requires DISPLAY")
def test_open_cell_editor_is_committed_before_apply_change(monkeypatch, tmp_path):
    gui = _new_gui(monkeypatch, tmp_path)
    try:
        gui.pm_sequence.set("Ac-EEMARR-NH2")
        gui.pm_scale.set("1")
        gui.pm_resin.set("Rink Amide AM")
        assert gui.pm_generate_selected() is True
        gui.update()

        tree = gui.pm_selected_plan_tree
        final_iid = tree.get_children()[-1]
        tree.see(final_iid)
        gui.update()
        x, y, width, height = tree.bbox(final_iid, "#2")
        for _ in range(2):
            tree.event_generate("<ButtonPress-1>", x=x + width // 2, y=y + height // 2)
            tree.event_generate("<ButtonRelease-1>", x=x + width // 2, y=y + height // 2)
            gui.update()
        editor = getattr(tree, "_v229_editor", None)
        assert editor is not None and editor.winfo_exists()
        editor.set("Ac-Glu(OtBu)-OH")

        # Do not press Return and do not move focus first. Apply Change itself
        # must commit the active editor and rebuild all linked outputs.
        _visible_button(gui, "Apply Change").invoke()
        gui.update()
        assert _rows(tree)[-1]["Unit name"] == "Ac-Glu(OtBu)-OH"
        final_rows = _rows(gui.progress_tree)
        final_coupling = max(
            i for i, row in enumerate(final_rows)
            if row["unit"] == "Ac-Glu(OtBu)-OH" and row["operation"] in {"Coupling / reaction", "Coupling 2"}
        )
        after_coupling = final_rows[final_coupling + 1:]
        assert [row["operation"] for row in after_coupling[:2]] == [
            "Final DMF wash x3",
            "Final MC/DCM wash x3",
        ]
        assert not any("deprotection" in row["operation"].lower() for row in after_coupling)
    finally:
        gui.destroy()


def test_visible_snapshot_diff_marks_unit_name_without_tk():
    from types import SimpleNamespace
    from suite_gui.modules import plan_workflow as ctl

    class FakeTree:
        def __init__(self):
            self._rows = {"row-1": ["1", "Ac-Glu(OtBu)-OH", "245.32", ""]}
            self._columns = ["No", "Unit name", "MW", "Density(g/mL)"]

        def get_children(self):
            return ("row-1",)

        def __getitem__(self, key):
            if key == "columns":
                return self._columns
            raise KeyError(key)

        def item(self, iid, option=None, **kwargs):
            if "values" in kwargs:
                self._rows[iid] = list(kwargs["values"])
            if option == "values":
                return tuple(self._rows[iid])
            return {"values": tuple(self._rows[iid])}

    gui = SimpleNamespace(
        _v229_active_index=0,
        _v229_dirty_columns={},
        pm_selected_plan_tree=FakeTree(),
        pm_items=[{
            "selected_plan_rows": [{
                "No": "1",
                "Unit name": "Acetic anhydride (Ac2O)",
                "MW": "102.09",
                "Density(g/mL)": "1.08",
            }]
        }],
    )
    ctl._mark_visible_plan_edits(gui)
    assert "Unit name" in gui._v229_dirty_columns["row-1"]


def test_commit_editor_calls_direct_callback_without_tk_event_queue():
    from types import SimpleNamespace
    from suite_gui.modules import plan_workflow as ctl

    called = []

    class FakeEditor:
        def winfo_exists(self):
            return True

        def _v229_commit(self):
            called.append(True)

    tree = SimpleNamespace(_v229_editor=FakeEditor())
    gui = SimpleNamespace(pm_selected_plan_tree=tree)
    ctl._commit_editor(gui)
    assert called == [True]
