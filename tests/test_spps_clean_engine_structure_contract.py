from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "apps" / "spps_planner_app" / "spps_planner" / "engine.py"
CLASSIC = ROOT / "spps_v4_gui" / "classic_base.py"
BATCH = ROOT / "spps_v4_gui" / "modules" / "classic_batch_controller.py"
PLAN = ROOT / "spps_v4_gui" / "modules" / "plan_workflow.py"
PANEL = ROOT / "spps_v4_gui" / "modules" / "project_manager_panel.py"


def _top_level_functions(path: Path) -> dict[str, ast.FunctionDef]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}


def test_engine_has_one_canonical_material_pipeline():
    source = ENGINE.read_text(encoding="utf-8")
    functions = _top_level_functions(ENGINE)
    for fragment in (
        "_V219_", "_V221_", "_V222_", "ORIG_GENERATE",
        "FINAL REPAIR", "patch-stack", "hotfix",
    ):
        assert fragment not in source
    for name in (
        "_recommend_cleavage_preset_initial",
        "_generate_cleavage_cocktail_initial",
        "_plan_summary_initial",
        "_liquid_display_policy",
    ):
        assert name not in functions
    for public_name, core_name in (
        ("generate_step_materials", "_generate_step_materials_core"),
        ("generate_materials", "_generate_materials_core"),
    ):
        calls = {
            call.func.id
            for call in ast.walk(functions[public_name])
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
        }
        assert core_name in calls
        assert not any(name.startswith("_generate_") and "_v2" in name.lower() for name in calls)


def test_classic_controller_has_no_versioned_wrapper_alias_stack():
    classic = CLASSIC.read_text(encoding="utf-8")
    batch = BATCH.read_text(encoding="utf-8")
    for token in ("_v23_", "_v25_", "_v26_", "_old_v26", "_V219_", "_V221_", "_V222_"):
        assert token not in classic
        assert token not in batch
    assert "class ClassicControllerBase(ClassicBatchControllerMixin, ClassicBaseCore)" in classic
    assert "= ClassicBaseCore." not in classic


def test_project_plan_actions_use_stable_widget_references():
    classic = CLASSIC.read_text(encoding="utf-8")
    plan = PLAN.read_text(encoding="utf-8")
    panel = PANEL.read_text(encoding="utf-8")
    for attr in (
        "pm_generate_button", "pm_apply_button", "pm_condition_button",
        "pm_loading_advice_button", "pm_cleavage_advice_button",
        "pm_record_lab_button", "pm_save_session_button",
        "pm_duplicate_button", "pm_delete_button", "pm_export_button",
    ):
        assert f"self.{attr}" in classic
    assert '"pm_generate_button": gui.generate_update_plan' in plan
    assert '"pm_apply_button": gui.apply_change' in plan
    assert '"pm_generate_button": self.generate_update' in panel
    assert '"pm_apply_button": self.apply_change' in panel
    assert 'text == "Generate"' not in plan
    assert 'text == "Apply Change"' not in plan
    assert 'label == "Duplicate"' not in panel


def test_batch_controller_does_not_call_removed_global_wrapper_helpers():
    tree = ast.parse(BATCH.read_text(encoding="utf-8"))
    suspicious = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in {"_format_display_value", "_pm_items_to_batch_rows"}:
                suspicious.append((node.lineno, node.func.id))
    assert suspicious == []
