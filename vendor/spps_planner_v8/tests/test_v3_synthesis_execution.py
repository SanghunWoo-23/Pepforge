from __future__ import annotations

from suite_gui import execution_workflow, peptide_item_collection, synthesis_execution


class _Tree:
    def __init__(self, rows):
        self.columns = ("No", "Unit name", "Unit eq", "Repeat", "Note")
        self.rows = {
            str(index): [row.get(column, "") for column in self.columns]
            for index, row in enumerate(rows)
        }

    def __getitem__(self, key):
        assert key == "columns"
        return self.columns

    def get_children(self):
        return tuple(self.rows)

    def item(self, iid, option=None):
        values = tuple(self.rows[iid])
        return values if option == "values" else {"values": values}

    def set(self, iid, column, value=None):
        index = self.columns.index(column)
        if value is None:
            return self.rows[iid][index]
        self.rows[iid][index] = str(value)


class _Gui:
    def __init__(self):
        self.pm_items = [{
            "work_item_id": "work-1",
            "project": "P1",
            "peptide": "Pep1",
            "selected_plan_rows": [],
        }]
        self._v229_active_index = 0
        self.pm_selected_plan_tree = _Tree([
            {
                "No": "1",
                "Unit name": "Fmoc-Gly-OH",
                "Unit eq": "2",
                "Repeat": "1",
                "Note": "",
            },
        ])
        self.apply_calls = 0
        self.autosaves = 0
        self._v3_work_item_window = None

    def apply_change(self):
        self.apply_calls += 1
        return True

    def schedule_autosave(self):
        self.autosaves += 1


def _fixed_ids():
    values = iter(("event-1", "event-2", "event-3"))
    return lambda: next(values)


def test_append_only_event_schema_replay_and_compensating_revert():
    item = {"work_item_id": "work-1"}
    ids = _fixed_ids()
    first = synthesis_execution.append_event(
        item,
        event_type="doubling",
        step_no=7,
        unit="Fmoc-Gly-OH",
        field="Repeat",
        before="1",
        after="2",
        reason="Incomplete coupling",
        operator_note="Kaiser positive",
        clock=lambda: "2026-07-31T10:00:00+00:00",
        id_factory=ids,
    )
    revert = synthesis_execution.append_revert(
        item,
        first,
        reason="Repeat was entered on wrong step",
        clock=lambda: "2026-07-31T10:01:00+00:00",
        id_factory=ids,
    )

    history = synthesis_execution.events(item)
    assert [event["event_type"] for event in history] == ["doubling", "revert"]
    assert history[0]["work_item_id"] == "work-1"
    assert revert["target_event_id"] == "event-1"
    assert revert["before"] == "2"
    assert revert["after"] == "1"
    assert synthesis_execution.current_values(item)[("7", "Repeat")] == "1"
    assert synthesis_execution.latest_reversible_event(item) is None


def test_live_plan_correction_recalculates_then_records_and_persists(monkeypatch):
    gui = _Gui()
    monkeypatch.setattr(
        execution_workflow.plan_workflow,
        "_save_active",
        lambda actual, include_outputs=True: actual.pm_items[0].update(
            selected_plan_rows=[{"No": "1", "Repeat": actual.pm_selected_plan_tree.set("0", "Repeat")}],
        ),
    )

    event = execution_workflow.record_plan_correction(
        gui,
        step_no="1",
        field="Repeat",
        value="2",
        reason="Incomplete coupling",
        operator_note="Kaiser positive",
    )

    assert gui.pm_selected_plan_tree.set("0", "Repeat") == "2"
    assert gui.apply_calls == 1
    assert gui.autosaves == 1
    assert event["event_type"] == "doubling"
    assert event["before"] == "1"
    assert event["after"] == "2"
    assert gui.pm_items[0]["selected_plan_rows"][0]["Repeat"] == "2"
    assert len(gui.pm_items[0]["synthesis_execution"]["events"]) == 1


def test_revert_applies_inverse_plan_value_and_appends_history(monkeypatch):
    gui = _Gui()
    monkeypatch.setattr(
        execution_workflow.plan_workflow, "_save_active", lambda *_a, **_k: None,
    )
    execution_workflow.apply_doubling(
        gui, step_no=1, reason="Incomplete coupling",
    )
    event = execution_workflow.revert_last(
        gui, reason="Correction no longer required",
    )

    assert gui.pm_selected_plan_tree.set("0", "Repeat") == "1"
    assert gui.apply_calls == 2
    assert event["event_type"] == "revert"
    assert event["after"] == "1"
    assert [row["event_type"] for row in synthesis_execution.events(gui.pm_items[0])] == [
        "doubling", "revert",
    ]


def test_step_status_and_actual_material_are_real_ml_ready_records(monkeypatch):
    gui = _Gui()
    monkeypatch.setattr(
        execution_workflow.plan_workflow, "_save_active", lambda *_a, **_k: None,
    )
    status = execution_workflow.record_step_status(
        gui,
        step_no=1,
        status="In Progress",
        operator_note="Started 09:30",
    )
    actual = execution_workflow.record_actual_material(
        gui,
        step_no=1,
        material="Fmoc-Gly-OH",
        amount="12.5",
        amount_unit="mg",
        status="Charged",
        reason="Balance reading",
    )

    assert status["field"] == "step_status"
    assert actual["after"] == {
        "material": "Fmoc-Gly-OH",
        "amount": 12.5,
        "unit": "mg",
        "status": "Charged",
    }
    records = execution_workflow.ml_ready_history(gui)
    assert len(records) == 2
    assert records[0]["work_item_id"] == "work-1"
    assert records[1]["event_type"] == "actual_material"


def test_execution_history_survives_item_copy_but_duplicate_starts_new_run():
    original = peptide_item_collection.blank_item(1)
    synthesis_execution.append_event(
        original,
        event_type="step_status",
        step_no=1,
        unit="Fmoc-Gly-OH",
        field="step_status",
        before="Planned",
        after="Completed",
        reason="Step complete",
    )
    items, index, duplicate = peptide_item_collection.duplicate_item([original], 0)

    assert index == 1
    assert duplicate["work_item_id"] != original["work_item_id"]
    assert "synthesis_execution" not in duplicate
    assert items[0]["synthesis_execution"]["events"]


def test_invalid_actual_amount_and_reason_are_rejected(monkeypatch):
    gui = _Gui()
    monkeypatch.setattr(
        execution_workflow.plan_workflow, "_save_active", lambda *_a, **_k: None,
    )
    try:
        execution_workflow.record_plan_correction(
            gui, step_no=1, field="Repeat", value="2", reason="",
        )
    except ValueError as exc:
        assert "reason" in str(exc).lower()
    else:
        raise AssertionError("missing correction reason must fail")

    try:
        execution_workflow.record_actual_material(
            gui,
            step_no=1,
            material="Fmoc-Gly-OH",
            amount="-1",
            amount_unit="mg",
            status="Charged",
        )
    except ValueError as exc:
        assert "negative" in str(exc).lower()
    else:
        raise AssertionError("negative actual amount must fail")
