from __future__ import annotations

import json

from suite_gui.session_state import SessionStateMixin


class Variable:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class Listbox:
    def curselection(self):
        return (1,)


class SessionHarness(SessionStateMixin):
    def __init__(self, path):
        self.state_file = path
        self.project_name = Variable("Demo-Project")
        self.seq = Variable("Ac-AAAAAA-NH2")
        self.pm_items = [{"project": "Demo-Project", "sequence": "Ac-AAAAAA-NH2"}]
        self.pm_list = Listbox()
        self.synced = 0
        self.closed = 0
        self.logs = []

    def pm_live_sync_selected(self):
        self.synced += 1

    def _batch_rows_from_tree(self):
        return [{"Project": "Demo-Project", "Scale mmol": "0.2"}]

    def _log(self, message):
        self.logs.append(message)

    def destroy(self):
        self.closed += 1


def test_session_state_keeps_the_accepted_json_shape(tmp_path):
    harness = SessionHarness(tmp_path / "session.json")
    state = harness._collect_state()

    assert harness.synced == 1
    assert state["app_version"] == "V8.0.0"
    assert state["selected_pm_index"] == 1
    assert state["pm_items"] == harness.pm_items
    assert state["batch_rows"] == [
        {"Project": "Demo-Project", "Scale mmol": "0.2"}
    ]
    assert state["defaults"]["project_name"] == "Demo-Project"
    assert state["defaults"]["seq"] == "Ac-AAAAAA-NH2"


def test_session_save_is_atomic_and_close_saves_before_destroy(tmp_path):
    path = tmp_path / "session.json"
    harness = SessionHarness(path)

    harness.save_autosave_state()
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["app_version"] == "V8.0.0"
    assert not path.with_suffix(".tmp").exists()

    harness.on_close()
    assert harness.closed == 1
    assert path.exists()


def test_r17_none_active_index_stays_none_across_legacy_aliases():
    from types import SimpleNamespace
    from suite_gui import runtime_state

    gui = SimpleNamespace()
    runtime_state.set_active_index(gui, None)
    assert runtime_state.get_active_index(gui, None) is None
    assert gui._v229_active_index is None
    assert gui._v228_active_index is None
    assert gui._v2097_active_index is None
