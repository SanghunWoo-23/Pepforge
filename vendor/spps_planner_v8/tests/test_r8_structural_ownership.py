from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_r8_custom_db_restore_is_single_owner_without_timed_reassertion() -> None:
    source = _source("suite_gui/ui_build.py")
    start = source.index("def apply_custom_database_ui")
    end = source.index("def bind_direct_workspace_actions", start)
    body = source[start:end]
    assert "after_idle" not in body
    assert "gui.after(" not in body
    assert body.count("_restore_custom_tab(gui)") == 1


def test_r8_workspace_command_routing_does_not_scan_visible_button_text() -> None:
    source = _source("suite_gui/ui_build.py")
    start = source.index("def bind_direct_workspace_actions")
    end = source.index("def initialize_batch_manager", start)
    body = source[start:end]
    assert 'cget("text")' not in body
    assert "workbench._walk" not in body
    assert '"pm_export_button"' in body
    assert '"batch_generate_button"' in body


def test_r8_custom_db_uses_explicit_setup_notebook_reference() -> None:
    source = _source("suite_gui/custom_db_workflow.py")
    start = source.index("def _setup_notebook")
    end = source.index("def restore_tab", start)
    body = source[start:end]
    assert 'getattr(gui, "pm_setup_notebook", None)' in body
    assert "winfo_children" not in body
    assert 'tab(tab_id, "text")' not in source[source.index("def restore_tab"):source.index("def load_selected", source.index("def restore_tab"))] if "def load_selected" in source[source.index("def restore_tab"):] else True


def test_r8_plan_toolbar_uses_explicit_button_references() -> None:
    source = _source("suite_gui/modules/plan_workflow.py")
    start = source.index("def _install_plan_toolbar")
    end = source.index("def _install_action_buttons", start)
    body = source[start:end]
    assert 'cget("text")' not in body
    assert 'getattr(gui, "pm_plan_delete_button", None)' in body


def test_active_v6_architecture_docs_do_not_claim_v3_controller_identity() -> None:
    for relative in ("suite_gui/ui_build.py", "suite_gui/controller.py", "suite_gui/release.py"):
        source = _source(relative)
        assert "Direct V3.0.0 desktop controller" not in source
        assert "Canonical SPPS Planner V3.0.0" not in source
        assert "Explicit V3.0.0 UI construction pipeline" not in source


def test_r8_runtime_state_is_version_neutral_with_legacy_alias_sync() -> None:
    from types import SimpleNamespace
    from suite_gui.runtime_state import get_active_index, set_active_index, is_switching, set_switching

    gui = SimpleNamespace(_v229_active_index=2, _v229_switching=False)
    assert get_active_index(gui) == 2
    assert gui.planner_ui_state.active_index == 2
    set_active_index(gui, 4)
    assert gui.planner_ui_state.active_index == 4
    assert gui._v229_active_index == 4
    set_switching(gui, True)
    assert is_switching(gui) is True
    assert gui._v229_switching is True


def test_r8_primary_active_index_paths_use_runtime_state_owner() -> None:
    for relative in (
        "suite_gui/execution_workflow.py",
        "suite_gui/data_workflow.py",
        "suite_gui/ml_workflow.py",
        "suite_gui/persistence_workflow.py",
        "suite_gui/modules/plan_workflow.py",
        "suite_gui/modules/project_manager_workflow.py",
    ):
        source = _source(relative)
        assert 'getattr(gui, "_v229_active_index"' not in source


def test_model_registry_has_version_neutral_canonical_owner():
    root = Path(__file__).resolve().parents[1]
    models = (root / "suite_gui/recommendation/models.py").read_text(encoding="utf-8")
    advisor = (root / "suite_gui/ml_advisor_v5.py").read_text(encoding="utf-8")
    compat = (root / "suite_gui/model_registry_v5.py").read_text(encoding="utf-8")
    assert "model_registry_v5 as _backend" not in models
    assert "from suite_gui.recommendation import model_registry" in advisor
    assert "_sys.modules[__name__] = _canonical" in compat


def test_legacy_model_registry_import_is_same_canonical_module():
    from suite_gui import model_registry_v5
    from suite_gui.recommendation import model_registry
    assert model_registry_v5 is model_registry


def test_v228_and_v229_runtime_aliases_share_stable_owner():
    from types import SimpleNamespace
    from suite_gui.runtime_state import (
        get_active_index, set_active_index, is_switching, set_switching,
        get_calculation_namespace, set_calculation_namespace,
    )
    gui = SimpleNamespace(_v228_active_index=2, _v228_switching=True)
    assert get_active_index(gui) == 2
    assert is_switching(gui) is True
    set_active_index(gui, 4)
    set_switching(gui, False)
    assert gui._v228_active_index == gui._v229_active_index == 4
    assert gui._v228_switching is gui._v229_switching is False
    ns = {"engine": object()}
    set_calculation_namespace(gui, ns)
    assert get_calculation_namespace(gui) is ns
    assert gui._v228_ns is gui._v229_ns is ns


def test_active_workspace_no_longer_depends_on_v228_state_names():
    root = Path(__file__).resolve().parents[1]
    workspace = (root / "suite_gui/modules/workspace_widgets.py").read_text(encoding="utf-8")
    for legacy in ("_v228_active_index", "_v228_switching", "_v228_ns"):
        assert legacy not in workspace
