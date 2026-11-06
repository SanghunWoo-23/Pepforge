from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_experimental_history_remains_reachable_from_primary_recommendations_hub():
    editor = (ROOT / 'suite_gui' / 'classic_base.py').read_text(encoding='utf-8')
    panel = (ROOT / 'suite_gui' / 'modules' / 'experimental_data_panel.py').read_text(encoding='utf-8')
    workflow = (ROOT / 'suite_gui' / 'experimental_workflow.py').read_text(encoding='utf-8')
    assert "text='Recommendations & Lab History'" in editor
    assert 'command=self.open_condition_optimizer' in editor
    assert 'def open_condition_optimizer(' in workflow
    assert 'window = open_window(gui)' in workflow
    assert 'self.records_tab' in panel
    assert 'text="Add Result"' in panel


def test_v4_startup_explicitly_clears_previous_outputs_after_initialization():
    text = (ROOT / 'suite_gui' / 'ui_build.py').read_text(encoding='utf-8')
    init_pos = text.index('initialize_experimental_data(gui)')
    clear_pos = text.index('plan_workflow._clear_editor_and_outputs(gui)', init_pos)
    theme_pos = text.index('ui_system.apply_theme(gui, "Standard")', clear_pos)
    assert init_pos < clear_pos < theme_pos


def test_checklist_progress_is_reset_when_outputs_are_cleared():
    text = (ROOT / 'suite_gui' / 'peptide_item_state.py').read_text(encoding='utf-8')
    assert 'gui.checklist_progress_var.set(0.0)' in text
    assert 'Progress: 0/0 (0.0%)' in text
