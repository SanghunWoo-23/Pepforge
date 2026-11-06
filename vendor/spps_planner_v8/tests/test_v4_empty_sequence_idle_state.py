from __future__ import annotations

from pathlib import Path

from suite_gui.modules import export_panel

ROOT = Path(__file__).resolve().parents[1]


class _Var:
    def __init__(self, value=""):
        self.value = value
    def get(self):
        return self.value
    def set(self, value):
        self.value = value


class _List:
    def curselection(self):
        return (0,)
    def delete(self, *_args):
        return None
    def insert(self, *_args):
        return None
    def selection_clear(self, *_args):
        return None
    def selection_set(self, *_args):
        return None
    def activate(self, *_args):
        return None
    def see(self, *_args):
        return None


class _Gui:
    def __init__(self):
        self.pm_sequence = _Var("")
        self.pm_items = [{"sequence": "", "status": "Calculated"}]
        self.pm_list = _List()
        self._v2097_active_index = 0
        self.autosaved = False
    def pm_display_name(self, _item):
        return ""
    def pm_update_summary(self):
        return None
    def schedule_autosave(self):
        self.autosaved = True


def test_auto_generate_update_treats_blank_sequence_as_idle(monkeypatch):
    gui = _Gui()
    called = {"core": False, "cleared": False}

    monkeypatch.setattr(export_panel.state, "save_active", lambda _gui: None)
    monkeypatch.setattr(export_panel.state, "refresh_selected_outputs", lambda _gui: called.__setitem__("core", True))
    monkeypatch.setattr(export_panel.state, "clear_selected_outputs", lambda _gui: called.__setitem__("cleared", True))

    result = export_panel.generate_update(gui)

    assert result == {}
    assert called["cleared"] is True
    assert called["core"] is False
    assert gui.pm_items[0]["status"] == "Ready"
    assert gui.autosaved is True


def test_classic_startup_only_builds_plan_when_sequence_exists():
    text = (ROOT / "suite_gui" / "classic_base.py").read_text(encoding="utf-8")
    assert "if startup_sequence:" in text
    assert "self.rebuild_table()" in text
    assert "self.after(300, self.refresh_outputs_from_tree)" in text
