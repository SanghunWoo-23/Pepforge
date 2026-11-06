from __future__ import annotations

import pandas as pd

from suite_gui import batch_workflow
from suite_gui.modules import plan_workflow


def test_batch_refresh_reuses_unchanged_calculation(monkeypatch):
    gui = type("Gui", (), {})()
    gui.pm_items = [{"project": "P", "peptide": "A", "sequence": "ACD"}]
    calls = []

    def calculate(_gui):
        calls.append("calculate")
        return {
            "AA stock": pd.DataFrame(), "Resin loading": pd.DataFrame(),
            "Coupling reagents": pd.DataFrame(),
            "Catalyst/additive": pd.DataFrame(), "Solvents": pd.DataFrame(),
            "Chemicals": pd.DataFrame(), "Summary": pd.DataFrame(),
        }

    monkeypatch.setattr(batch_workflow, "calculate", calculate)
    batch_workflow.refresh(gui)
    batch_workflow.refresh(gui)
    assert calls == ["calculate"]

    gui.pm_items[0]["sequence"] = "RRR"
    batch_workflow.refresh(gui)
    assert calls == ["calculate", "calculate"]


def test_batch_refresh_requests_are_coalesced(monkeypatch):
    class Gui:
        def __init__(self):
            self.callbacks = {}
            self.cancelled = []
            self.next_id = 0

        def after(self, _delay, callback):
            self.next_id += 1
            self.callbacks[self.next_id] = callback
            return self.next_id

        def after_cancel(self, identifier):
            self.cancelled.append(identifier)
            self.callbacks.pop(identifier, None)

    gui = Gui()
    calls = []
    monkeypatch.setattr(
        batch_workflow, "refresh",
        lambda _gui, force=False: calls.append(force) or {},
    )

    batch_workflow.request_refresh(gui)
    batch_workflow.request_refresh(gui)
    assert gui.cancelled == [1]
    assert len(gui.callbacks) == 1
    gui.callbacks[2]()
    assert calls == [False]


def test_editor_variable_changes_schedule_one_live_sync(monkeypatch):
    class Gui:
        def __init__(self):
            self.callback = None
            self._v3_live_sync_after_id = None

        def after_idle(self, callback):
            self.callback = callback
            return "idle-1"

    gui = Gui()
    calls = []
    monkeypatch.setattr(plan_workflow, "_live_sync", lambda _gui: calls.append(1))

    plan_workflow._schedule_live_sync(gui)
    plan_workflow._schedule_live_sync(gui)
    assert calls == []
    gui.callback()
    assert calls == [1]


def test_hidden_batch_is_invalidated_without_recalculation(monkeypatch):
    class Tabs:
        def select(self):
            return "project"

        def tab(self, _selected, _option):
            return "Project Manager"

    gui = type("Gui", (), {})()
    gui.tabs = Tabs()
    gui._v3_batch_signature = ("old",)
    gui._v225_batch_tables = {"Summary": pd.DataFrame()}
    calls = []
    monkeypatch.setattr(
        batch_workflow, "request_refresh",
        lambda *_args, **_kwargs: calls.append(1),
    )

    result = batch_workflow.invalidate_and_refresh_if_visible(gui)

    assert gui._v3_batch_signature is None
    assert calls == []
    assert result is gui._v225_batch_tables


def test_visible_batch_schedules_one_recalculation(monkeypatch):
    class Tabs:
        def select(self):
            return "batch"

        def tab(self, _selected, _option):
            return "Batch Manager"

    gui = type("Gui", (), {})()
    gui.tabs = Tabs()
    calls = []
    monkeypatch.setattr(
        batch_workflow, "request_refresh",
        lambda _gui, **kwargs: calls.append(kwargs) or {"ok": True},
    )

    result = batch_workflow.invalidate_and_refresh_if_visible(gui, delay_ms=25)

    assert calls == [{"delay_ms": 25, "force": False}]
    assert result == {"ok": True}
