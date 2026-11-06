from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "suite_gui" / "modules" / "experimental_data_panel.py"


def text():
    return SRC.read_text(encoding="utf-8")


def test_advisors_sync_and_auto_analyze_when_opened():
    src = text()
    assert 'self._sync_advisor_from_planner("loading" if loading else "cleavage")' in src
    assert 'self._schedule(0, self.run_loading_advisor if loading else self.run_cleavage_advisor, idle=True)' in src
    assert 'self._pending_after_ids' in src


def test_loading_apply_is_one_click_regenerate():
    src = text()
    assert 'Review & Apply Exact Record + Generate' in src
    assert 'generated = self.gui.generate_update_plan()' in src
    assert 'Run Generate to recalculate' not in src


def test_cleavage_apply_is_one_click_apply_change():
    src = text()
    assert 'Review & Apply Exact Product + Apply Change' in src
    assert 'changed = self.gui.apply_change()' in src
    assert 'Use the existing Apply Change flow' not in src
