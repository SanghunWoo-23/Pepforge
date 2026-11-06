from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_classic_batch_controller_has_no_versioned_wrapper_chain():
    classic = _read("suite_gui/classic_base.py")
    controller = _read("suite_gui/modules/classic_batch_controller.py")
    for token in ("_v23_", "_v25_", "_v26_", "_old_v26", "_V219_", "_V221_", "_V222_"):
        assert token not in classic
        assert token not in controller
    assert "class ClassicControllerBase(ClassicBatchControllerMixin, ClassicBaseCore)" in classic


def test_project_and_plan_action_buttons_use_stable_widget_refs():
    panel = _read("suite_gui/modules/project_manager_panel.py")
    plan = _read("suite_gui/modules/plan_workflow.py")
    classic = _read("suite_gui/classic_base.py")
    assert '"pm_generate_button": self.generate_update' in panel
    assert '"pm_apply_button": self.apply_change' in panel
    assert '"pm_generate_button": gui.generate_update_plan' in plan
    assert '"pm_apply_button": gui.apply_change' in plan
    assert 'text == "Generate"' not in plan
    assert 'text == "Apply Change"' not in plan
    for attr in ("pm_generate_button", "pm_apply_button", "pm_condition_button", "pm_auto_plan_button"):
        assert f"self.{attr}" in classic


def test_recommendation_workflow_uses_stable_namespace():
    workflow = _read("suite_gui/experimental_workflow.py")
    assert "from suite_gui.recommendation import" in workflow
    assert "ml_advisor_v5." not in workflow
    assert "condition_optimizer_v5." not in workflow
    assert "model_registry_v5." not in workflow


def test_new_v6_operator_features_are_real_routes_not_stubs():
    work = _read("suite_gui/work_item_window.py")
    workflow = _read("suite_gui/experimental_workflow.py")
    for label in ("Preflight", "Repeat Run", "Finish Experiment Review", "Export Run Package"):
        assert label in work
    for name in ("def preflight_check", "def finish_review", "def repeat_experiment", "def export_run_package"):
        assert name in workflow
    assert "pass  # TODO" not in workflow


def test_reporting_and_evidence_dialog_are_separate_from_db_and_main_panel():
    data = _read("suite_gui/experimental_data.py")
    reporting = _read("suite_gui/experimental_reporting.py")
    panel = _read("suite_gui/modules/experimental_data_panel.py")
    assert "from suite_gui.experimental_reporting import data_health as report" in data
    assert "def data_health" in reporting
    assert "evidence_detail_dialog.show" in panel
    assert panel.count("Evidence Detail") >= 3
