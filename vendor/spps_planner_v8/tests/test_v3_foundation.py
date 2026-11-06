from __future__ import annotations

from pathlib import Path

from suite_gui import project_workflow
from suite_gui.controller import SPPSGui
from suite_gui.work_item_window import _tree_rows, _write_rows


ROOT = Path(__file__).resolve().parents[1]


class _Tree:
    def __init__(self, columns, rows=()):
        self.columns = tuple(columns)
        self.rows = {str(index): tuple(row) for index, row in enumerate(rows)}

    def __getitem__(self, key):
        assert key == "columns"
        return self.columns

    def get_children(self):
        return tuple(self.rows)

    def item(self, iid, option=None):
        values = self.rows[iid]
        return values if option == "values" else {"values": values}

    def delete(self, iid):
        del self.rows[iid]

    def insert(self, _parent, _where, values):
        self.rows[str(len(self.rows))] = tuple(values)


def test_v3_identity_is_separate_and_consistent():
    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() == "V8.0.0"
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "V8.0.0"
    assert SPPSGui.TITLE == "SPPS Planner V8.0.0"
    assert callable(SPPSGui.open_work_item)


def test_work_item_double_click_restores_then_opens_window(monkeypatch):
    events = []
    gui = object()
    monkeypatch.setattr(
        project_workflow.project_manager_workflow,
        "double_click",
        lambda actual, workflow, namespace, event: events.append(
            ("restore", actual, event),
        ) or "break",
    )
    monkeypatch.setattr(project_workflow, "_namespace", lambda: {})

    import suite_gui.work_item_window as work_item_window

    monkeypatch.setattr(
        work_item_window,
        "open_selected",
        lambda actual: events.append(("window", actual)) or "break",
    )
    assert project_workflow.open_selected(gui, "event") == "break"
    assert events == [("restore", gui, "event"), ("window", gui)]


def test_work_item_table_projection_preserves_real_rows():
    source = _Tree(
        ("No", "Unit name", "Repeat"),
        (("1", "Fmoc-Gly-OH", "2"), ("2", "Fmoc-Lys(Boc)-OH", "1")),
    )
    rows = _tree_rows(source)
    target = _Tree(("No", "Unit name", "Repeat"), (("old", "old", "old"),))
    _write_rows(target, rows)
    assert _tree_rows(target) == [
        {"No": "1", "Unit name": "Fmoc-Gly-OH", "Repeat": "2"},
        {"No": "2", "Unit name": "Fmoc-Lys(Boc)-OH", "Repeat": "1"},
    ]


def test_v3_menu_contains_only_functional_workflow_groups():
    source = (ROOT / "suite_gui" / "menu.py").read_text(encoding="utf-8")
    for label in (
        "File", "Edit", "Project", "Synthesis", "View", "Data / ML", "Help",
        "Open Selected Work Item", "Generate Plan", "Apply Change",
        "Save Project", "Load Project", "Export Current Work",
        "Open Run / Corrections",
        "Open Outcome / ML", "Build Reviewed Dataset",
        "Save Project As...", "Open Recent Project...",
        "Export Data Workbook...", "Import Data Workbook...", "Open Data / HPLC",
        "Open Risk Review", "Display Density", "Keyboard Shortcuts",
    ):
        assert label in source
    assert "placeholder" not in source.lower()


def test_list_double_click_routes_through_v3_controller():
    source = (
        ROOT / "suite_gui" / "modules" / "plan_workflow.py"
    ).read_text(encoding="utf-8")
    assert 'bind("<Double-Button-1>", gui.pm_on_double_click' in source


def test_work_item_has_real_stage_two_and_stage_three_workspaces():
    source = (ROOT / "suite_gui" / "work_item_window.py").read_text(encoding="utf-8")
    for label in (
        "Run / Corrections", "Apply Doubling (Repeat=2)", "Record Actual",
        "Outcome / ML", "Save Reviewed Outcome", "Build Dataset Version",
        "Train Reviewed Data", "Predict Active Item",
        "Data / HPLC", "New Run", "Activate Selected", "Save / Update HPLC",
        "Import HPLC CSV/XLSX", "Export Data Workbook", "Import Data Workbook",
        "Risk Review", "Save Assessment Version", "Acknowledge Selected",
    ):
        assert label in source
    assert "placeholder" not in source.lower()
