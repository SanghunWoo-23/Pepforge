"""V8 Project Manager navigation and compact action-bar contract."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_compact_toolbar_preserves_navigation_and_blue_auto_plan_after_apply():
    src = (ROOT / "suite_gui/classic_base.py").read_text(encoding="utf-8")
    section = src.split("actions = ttk.Frame(edit)", 1)[1].split("moved_actions = ttk.Frame(edit)", 1)[0]
    assert "text='Recommendations & Lab History'" in section
    assert "command=self.open_condition_optimizer" in section
    assert "text='Sequence Risk Map'" in section
    assert "text='Save Session Now'" in section
    for duplicate in ("text='Loading Advice'", "text='Cleavage Advice'", "text='Record Lab Data'"):
        assert duplicate not in section
    assert section.index("self.pm_generate_button") < section.index("self.pm_apply_button")
    assert section.index("self.pm_apply_button") < section.index("self.pm_auto_plan_button") < section.index("self.pm_condition_button")
    assert "text='Auto Plan (Optional)'" in section
    assert "style='Accent.TButton'" in section
    assert "self.pm_auto_plan_button.pack(side='left'" in section


def test_single_hub_reaches_all_hidden_shortcuts():
    exp = (ROOT / "suite_gui/modules/experimental_data_panel.py").read_text(encoding="utf-8")
    flow = (ROOT / "suite_gui/experimental_workflow.py").read_text(encoding="utf-8")
    for name in ('self.loading_advisor_tab', 'self.cleavage_advisor_tab', 'self.records_tab',
                 'self.recommend_tab', 'self.advanced_tab'):
        assert name in exp
    assert 'def open_condition_optimizer(' in flow
    assert 'window = open_window(gui)' in flow
    for button in ('text="Add Result"', 'text="Add Issue"', 'text="Final Result"'):
        assert button in exp


def test_lab_history_toolbar_follows_actual_experiment_lifecycle():
    src = (ROOT / "suite_gui/modules/experimental_data_panel.py").read_text(encoding="utf-8")
    section = src.split('top = ttk.Frame(self, padding=', 1)[1].split('runbar = ttk.Frame(', 1)[0]
    controls = ('self.preflight_button', 'self.start_experiment_button',
                'self.add_result_button', 'self.add_issue_button',
                'self.final_result_button', 'self.finish_experiment_button',
                'self.repeat_run_button', 'self.refresh_button',
                'self.data_store_button', 'self.backup_store_button')
    positions = [section.index(name + ' = ttk.Button(') for name in controls]
    assert positions == sorted(positions)
    # Keep the same commands; navigation changes must not change the Run lifecycle.
    for name in ('self._show_preflight', 'self._start_experiment', 'self.record_result',
                 'self.record_issue', 'self._finish_experiment', 'self._repeat_run',
                 'self.refresh_all', 'self._show_data_store', 'self._backup_data_store'):
        assert name in section
