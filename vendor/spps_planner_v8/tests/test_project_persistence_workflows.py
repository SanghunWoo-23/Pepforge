from __future__ import annotations

import ast
from pathlib import Path

from suite_gui import persistence_workflow
from suite_gui.controller import SPPSGui


ROOT = Path(__file__).resolve().parents[1]


class _Var:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class _Listbox:
    def __init__(self):
        self.rows = []
        self.selected = ()

    def delete(self, first, last=None):
        if last == "end":
            self.rows.clear()
        elif isinstance(first, int) and 0 <= first < len(self.rows):
            self.rows.pop(first)

    def insert(self, _where, value):
        self.rows.append(value)

    def selection_clear(self, _first, _last=None):
        self.selected = ()

    def selection_set(self, index):
        self.selected = (int(index),)

    def activate(self, _index):
        return None

    def curselection(self):
        return self.selected


class _Gui:
    def __init__(self, path):
        self._path = path
        self.pm_items = [{
            "project": "P1",
            "peptide": "Pep1",
            "sequence": "GHK",
            "resin": "Rink Amide AM",
        }]
        self._v229_active_index = 0
        self.pm_list = _Listbox()
        self.coupling_eq = _Var("5")
        self.position_doubling_rules = _Var("7:2")
        self.custom_materials = {"AA/Chemical": [{"name": "AEEA"}]}
        self.project_outdir = _Var(str(path.parent / "project"))
        self._autosave_after_id = None
        self._restoring_state = False
        self.after_calls = []

    def _state_file_path(self):
        return self._path

    def pm_display_name(self, item):
        return f"{item.get('project', '')} | {item.get('peptide', '')}"

    def after(self, delay, callback):
        self.after_calls.append((delay, callback))
        return "after-1"

    def after_cancel(self, _token):
        return None


def test_session_round_trip_preserves_items_defaults_and_custom_db(
    monkeypatch, tmp_path,
):
    path = tmp_path / "spps_planner_session_v1.json"
    source = _Gui(path)
    source.pm_items[0]["work_item_id"] = "work-1"
    source.pm_items[0]["synthesis_execution"] = {
        "schema_version": 1,
        "events": [{
            "event_id": "event-1",
            "event_type": "doubling",
            "step_no": "2",
            "field": "Repeat",
            "before": "1",
            "after": "2",
        }],
    }
    source.pm_items[0]["ml_review"] = {
        "schema_version": 1,
        "revision": 1,
        "current": {
            "reviewed": True,
            "included": True,
            "actual_yield_percent": 71.2,
        },
        "versions": [{"revision": 1, "version_id": "review-1"}],
    }
    monkeypatch.setattr(
        persistence_workflow.plan_workflow,
        "_save_active",
        lambda *_args, **_kwargs: None,
    )

    assert persistence_workflow.save_autosave_state(source) == path
    saved = persistence_workflow.state_persistence.read_json_object(path)
    assert saved["app_version"] == "V8.0.0"
    assert saved["pm_items"][0]["sequence"] == "GHK"
    assert saved["defaults"]["coupling_eq"] == "5"
    assert saved["defaults"]["position_doubling_rules"] == "7:2"
    assert saved["custom_materials"] == source.custom_materials
    assert saved["pm_items"][0]["synthesis_execution"]["events"][0]["after"] == "2"

    restored = _Gui(path)
    restored.pm_items = []
    restored.coupling_eq.set("2")
    restored.position_doubling_rules.set("")
    restored.custom_materials = {}
    assert persistence_workflow.load_autosave_state(restored) == path
    assert restored.pm_items[0]["sequence"] == "GHK"
    assert restored.coupling_eq.get() == "5"
    assert restored.position_doubling_rules.get() == "7:2"
    assert restored.custom_materials == source.custom_materials
    assert restored.pm_items[0]["work_item_id"] == "work-1"
    assert (
        restored.pm_items[0]["synthesis_execution"]["events"][0]["event_id"]
        == "event-1"
    )
    assert restored.pm_items[0]["ml_review"]["current"]["actual_yield_percent"] == 71.2
    assert restored.pm_items[0]["ml_review"]["versions"][0]["version_id"] == "review-1"


def test_project_loader_migrates_removed_ctc_alias(monkeypatch, tmp_path):
    path = tmp_path / "project_manager_state.json"
    persistence_workflow.state_persistence.atomic_write_json(path, {
        "app_version": "V7.0.0",
        "selected_pm_index": 0,
        "pm_items": [{
            "project": "Old",
            "peptide": "Saved",
            "sequence": "GHK",
            "resin": "CTC(합성용)",
        }],
        "defaults": {},
    })
    gui = _Gui(tmp_path / "session.json")
    monkeypatch.setattr(
        persistence_workflow.plan_workflow,
        "_save_active",
        lambda *_args, **_kwargs: None,
    )

    assert persistence_workflow.load_project(gui, path) == path
    assert gui.pm_items[0]["resin"] == "CTC(합성기)"
    assert gui.pm_list.rows == ["Old | Saved"]


def test_project_save_detects_external_conflict_and_save_as_preserves_both(monkeypatch, tmp_path):
    gui = _Gui(tmp_path / "session.json")
    monkeypatch.setattr(
        persistence_workflow.plan_workflow, "_save_active", lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(persistence_workflow.messagebox, "showerror", lambda *_a, **_k: None)
    monkeypatch.setattr(persistence_workflow.messagebox, "showinfo", lambda *_a, **_k: None)
    first = persistence_workflow.save_project(gui, show=False)
    assert first is not None and first.is_file()
    first.write_text('{"external_edit": true}', encoding="utf-8")

    assert persistence_workflow.save_project(gui, show=False) is None
    assert persistence_workflow.state_persistence.read_json_object(first)["external_edit"] is True

    alternate = tmp_path / "project" / "conflict_copy.json"
    assert persistence_workflow.save_project_as(gui, alternate, show=False) == alternate
    assert persistence_workflow.state_persistence.read_json_object(alternate)["project_revision"] == 2


def test_project_load_recovers_last_good_backup(monkeypatch, tmp_path):
    path = tmp_path / "project_manager_state.json"
    valid = {
        "app_version": "V7.0.0", "project_id": "p-recover", "project_revision": 3,
        "selected_pm_index": 0, "defaults": {},
        "pm_items": [{"project": "Recovered", "peptide": "Pep", "sequence": "GHK", "resin": "Rink Amide AM"}],
    }
    persistence_workflow.state_persistence.atomic_write_json(path.with_suffix(".json.bak"), valid)
    path.write_text("{broken", encoding="utf-8")
    gui = _Gui(tmp_path / "session.json")
    monkeypatch.setattr(
        persistence_workflow.plan_workflow, "_save_active", lambda *_args, **_kwargs: None,
    )
    assert persistence_workflow.load_project(gui, path) == path
    assert gui._project_id == "p-recover"
    assert gui._project_revision == 3
    assert gui.pm_items[0]["project"] == "Recovered"


def test_stage_five_controller_routes_are_direct_and_do_not_use_super():
    source_path = ROOT / "suite_gui" / "controller.py"
    tree = ast.parse(
        source_path.read_text(encoding="utf-8"),
        filename=str(source_path),
    )
    controller = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "SPPSGui"
    )
    routes = {
        "pm_on_select",
        "pm_on_double_click",
        "open_work_item",
        "pm_add_peptide",
        "pm_duplicate_peptide",
        "pm_delete_peptide",
        "save_project",
        "load_project",
        "_collect_state",
        "save_autosave_state",
        "schedule_autosave",
        "load_autosave_state",
        "calculate_batch_tables",
        "refresh_batch_workspace_preview",
        "export_batch_tables",
    }
    methods = {
        node.name: ast.unparse(node)
        for node in controller.body
        if isinstance(node, ast.FunctionDef) and node.name in routes
    }
    assert set(methods) == routes
    assert all("super()" not in source for source in methods.values())


def test_stage_five_controller_aliases_reach_direct_services(monkeypatch):
    calls = []
    gui = object.__new__(SPPSGui)
    from suite_gui import batch_workflow, project_workflow

    monkeypatch.setattr(
        project_workflow, "add",
        lambda actual, item=None: calls.append(("add", actual, item)),
    )
    monkeypatch.setattr(
        persistence_workflow, "save_project",
        lambda actual, show=True: calls.append(("save", actual, show)),
    )
    monkeypatch.setattr(
        batch_workflow, "refresh",
        lambda actual: calls.append(("batch", actual)),
    )

    gui.pm_add_peptide({"sequence": "GHK"})
    gui.save_project(False)
    gui.refresh_batch_workspace_preview()
    assert [entry[0] for entry in calls] == ["add", "save", "batch"]
