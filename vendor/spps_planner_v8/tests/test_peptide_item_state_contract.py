from __future__ import annotations

from suite_gui import peptide_item_state


class _Var:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class _Listbox:
    def __init__(self):
        self.selected = []
        self.active = None

    def selection_clear(self, *_args):
        self.selected = []

    def selection_set(self, index):
        self.selected.append(int(index))

    def activate(self, index):
        self.active = int(index)


class _Tree:
    def __init__(self, rows=None):
        self.rows = list(rows or [])


class _Adapter:
    @staticmethod
    def _editor_payload(gui):
        return {
            "project": gui.pm_project.get(),
            "sequence": gui.pm_sequence.get(),
            "resin": gui.pm_resin.get(),
            "apply_loading_calc": bool(gui.apply_loading_calc.get()),
            "loading_aa_eq": gui.loading_aa_eq.get(),
            "loading_diea_eq": gui.loading_diea_eq.get(),
        }

    @staticmethod
    def _tree_rows(tree):
        return list(tree.rows)

    @staticmethod
    def _refresh_list_label(gui, index):
        gui.refreshed = index

    @staticmethod
    def _clear_tree(tree):
        if tree is not None:
            tree.rows = []

    @staticmethod
    def _write_rows(tree, rows, *_args):
        if tree is not None:
            tree.rows = list(rows)


class _Gui:
    def __init__(self):
        for name in (
            "pm_project", "pm_peptide", "pm_sequence", "pm_scale",
            "pm_resin", "pm_loading", "pm_lot", "pm_chemistry",
            "pm_copies", "loading_aa_eq", "loading_diea_eq",
            "cleavage_preset", "cleavage_eq_override",
            "cleavage_components_text",
        ):
            setattr(self, name, _Var())
        self.apply_loading_calc = _Var(False)
        self.pm_list = _Listbox()
        self.pm_selected_plan_tree = _Tree()
        self.pm_selected_material_tree = _Tree()
        self.pm_selected_total_tree = _Tree()
        self.progress_tree = _Tree()
        self.pm_cleavage_tree = _Tree()
        self.pm_items = []
        self._v229_active_index = None
        self._v229_switching = False
        self._v229_dirty_columns = {}
        self.autosaves = 0

    def schedule_autosave(self):
        self.autosaves += 1


class _Notebook:
    def __init__(self):
        self.label = "Selected Plan"
        self.callback = None

    def select(self):
        return "current"

    def tab(self, _tab, option):
        assert option == "text"
        return self.label

    def bind(self, _event, callback, add=None):
        assert add == "+"
        self.callback = callback


def _set(gui, name, value):
    getattr(gui, name).set(value)


def test_snapshot_keeps_editor_and_each_output_attached_to_active_item():
    gui = _Gui()
    gui.pm_items = [{"project": "Old"}]
    gui._v229_active_index = 0
    gui.pm_project.set("Project-A")
    gui.pm_sequence.set("AEK")
    gui.pm_selected_plan_tree.rows = [{"No": "1", "Unit name": "Fmoc-Ala-OH"}]
    gui.pm_selected_material_tree.rows = [{"material": "Fmoc-Ala-OH"}]

    peptide_item_state.snapshot(
        gui, _Adapter, lambda current: current._v229_active_index
    )

    item = gui.pm_items[0]
    assert item["project"] == "Project-A"
    assert item["sequence"] == "AEK"
    assert item["selected_plan_rows"][0]["Unit name"] == "Fmoc-Ala-OH"
    assert item["selected_material_rows"][0]["material"] == "Fmoc-Ala-OH"
    assert gui.refreshed == 0


def test_restore_keeps_loading_state_isolated_per_peptide():
    gui = _Gui()
    gui.pm_items = [
        {
            "project": "Direct",
            "sequence": "AEK",
            "resin": "2-CTC",
            "apply_loading_calc": True,
            "loading_aa_eq": "3",
            "loading_diea_eq": "6",
            "selected_plan_rows": [{"No": "1"}],
        },
        {
            "project": "Preloaded",
            "sequence": "RRR",
            "resin": "CTC(합성기)",
            "apply_loading_calc": False,
            "loading_aa_eq": "2",
            "loading_diea_eq": "4",
        },
    ]
    binds = []

    def restore(index):
        peptide_item_state.restore_item(
            gui, index, _Adapter, _set,
            lambda _gui, ns: binds.append(ns), {"source": "test"},
            plan_columns=[], plan_widths={},
            material_columns=[], material_widths={},
            total_columns=[], total_widths={},
            check_columns=[], check_widths={},
        )

    restore(0)
    assert gui.pm_resin.get() == "2-CTC"
    assert gui.apply_loading_calc.get() is True
    assert gui.loading_aa_eq.get() == "3"
    restore(1)
    assert gui.pm_resin.get() == "CTC(합성기)"
    assert gui.apply_loading_calc.get() is False
    assert gui.loading_aa_eq.get() == "2"
    assert gui._v229_active_index == 1
    assert len(binds) == 2


def test_live_sync_updates_only_the_active_item_and_schedules_autosave():
    gui = _Gui()
    gui.pm_items = [{"project": "A"}, {"project": "B"}]
    gui._v229_active_index = 1
    gui.pm_project.set("B-edited")
    gui.pm_sequence.set("RRR")

    peptide_item_state.live_sync(
        gui, _Adapter, lambda current: current._v229_active_index
    )

    assert gui.pm_items[0]["project"] == "A"
    assert gui.pm_items[1]["project"] == "B-edited"
    assert gui.pm_items[1]["sequence"] == "RRR"
    assert gui.autosaves == 1


def test_restore_renders_only_visible_result_tab_until_operator_opens_another():
    gui = _Gui()
    gui.pm_results_notebook = _Notebook()
    gui.pm_items = [{
        "selected_plan_rows": [{"No": "1"}],
        "selected_material_rows": [{"material": "Fmoc-Ala-OH"}],
    }]

    peptide_item_state.restore_item(
        gui, 0, _Adapter, _set, lambda *_args: None, {},
        plan_columns=[], plan_widths={}, material_columns=[], material_widths={},
        total_columns=[], total_widths={}, check_columns=[], check_widths={},
    )

    assert gui.pm_selected_plan_tree.rows == [{"No": "1"}]
    assert gui.pm_selected_material_tree.rows == []
    gui.pm_results_notebook.label = "Selected Materials"
    gui.pm_results_notebook.callback()
    assert gui.pm_selected_material_tree.rows == [{"material": "Fmoc-Ala-OH"}]
