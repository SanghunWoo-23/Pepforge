"""Canonical SPPS Planner V6 UI construction pipeline.

The accepted interface is assembled through explicit construction stages.
Nothing in this file assigns methods to a GUI class at runtime, and final
behavior is owned by explicit widget/controller references rather than labels.
"""
from __future__ import annotations
from suite_gui.runtime_state import set_switching, set_calculation_namespace

import json
from typing import Any

from suite_gui import batch_workflow, calculation_context, custom_db_workflow, experimental_workflow
from suite_gui.menu import install_menu
from suite_gui import ui_system
from suite_gui.classic_base import ClassicControllerBase
from suite_gui.modules import (
    plan_workflow,
    project_manager_workflow,
    release_ui,
    add_peptide_dialog,
    workspace_widgets as workbench,
    ui_ownership,
)


TITLE = "SPPS Planner V7.0.0 Final"


def build_base_interface(gui: Any) -> None:
    """Build the retained classic widgets once, without any wrapper chain."""
    set_calculation_namespace(gui, calculation_context.namespace())
    set_switching(gui, True)
    try:
        ClassicControllerBase._build(gui)
    finally:
        set_switching(gui, False)


def apply_plan_workspace(gui: Any) -> None:
    """Install the accepted editable Plan/Materials/Checklist workspace."""
    namespace = calculation_context.namespace()
    try:
        workbench._cancel_pending_legacy_jobs(gui)
    except Exception:
        pass
    workbench._hide_non_workbench_tabs(gui)
    plan_workflow._normalize_title(gui)
    plan_workflow._install_result_tabs(gui, namespace)
    plan_workflow._install_action_buttons(gui, namespace)
    plan_workflow._install_loading_controls(gui)
    plan_workflow._install_eq_follow_control(gui)
    plan_workflow._rename_editor_loading(gui)
    plan_workflow._install_traces(gui)
    plan_workflow._load_items_only(gui)
    plan_workflow._bind_item_actions(gui, namespace)
    plan_workflow._clear_editor_and_outputs(gui)
    try:
        workbench._cancel_pending_legacy_jobs(gui)
    except Exception:
        pass


def apply_operator_workspace(gui: Any) -> None:
    """Apply the four accepted operator-facing UI corrections in order."""
    namespace = calculation_context.namespace()
    ui_ownership.finalize(gui, plan_workflow, namespace)
    add_peptide_dialog.configure_add_button(gui)


def apply_final_release_ui(gui: Any) -> None:
    """Apply the current release identity, resin list, and cleavage controls."""
    release_ui.apply_post_build(gui, calculation_context.namespace())


def _session_path(gui: Any):
    try:
        return plan_workflow._session_path(gui)
    except Exception:
        return getattr(gui, "state_file", None)


def _load_custom_materials(gui: Any) -> None:
    try:
        custom_db_workflow.initialize(gui)
        path = _session_path(gui)
        if path is not None and path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            custom = payload.get("custom_materials", {}) if isinstance(payload, dict) else {}
            if isinstance(custom, dict):
                gui.custom_materials = custom
    except Exception:
        pass


def _restore_custom_tab(gui: Any) -> None:
    try:
        gui.restore_custom_db_tab()
        custom_db_workflow.refresh_setup_comboboxes(gui)
    except Exception:
        pass


def _pin_setup_button(gui: Any) -> None:
    try:
        button = getattr(gui, "setup_toggle_btn", None)
        if button is not None:
            button.configure(width=10)
    except Exception:
        pass


def apply_custom_database_ui(gui: Any) -> None:
    """Restore Custom DB exactly once after the setup notebook exists."""
    _load_custom_materials(gui)
    _restore_custom_tab(gui)
    _pin_setup_button(gui)


def bind_direct_workspace_actions(gui: Any) -> None:
    """Bind retained actions through construction-time widget references only."""
    bindings = {
        "setup_export_button": gui.export_outputs,
        "setup_load_project_button": gui.load_project,
        "pm_export_button": gui.export_outputs,
        "pm_load_project_button": gui.load_project,
        "pm_save_session_button": gui.save_autosave_state,
        "batch_generate_button": gui.refresh_batch_workspace_preview,
        "batch_sync_button": gui.sync_batch_from_projects,
        "batch_save_session_button": gui.save_autosave_state,
    }
    for attr, command in bindings.items():
        widget = getattr(gui, attr, None)
        if widget is not None:
            widget.configure(command=command)
    save_project = getattr(gui, "pm_save_project_button", None)
    if save_project is not None:
        save_project.configure(command=gui.save_project)


def initialize_batch_manager(gui: Any) -> None:
    """Initialize the Project-driven Batch cache once during UI construction."""
    try:
        batch_workflow.initialize(gui)
    except Exception as exc:
        try:
            gui._log(f"Batch Manager initialization warning: {exc}\n")
        except Exception:
            pass

def initialize_experimental_data(gui: Any) -> None:
    """Create/open the V4 experimental DB without altering planner/project state."""
    try:
        experimental_workflow.initialize(gui)
    except Exception as exc:
        try:
            gui._log(f"Experimental DB initialization warning: {exc}\n")
        except Exception:
            pass

def build_ui(gui: Any) -> None:
    """Build the complete accepted UI through explicit, testable stages."""
    build_base_interface(gui)
    apply_plan_workspace(gui)
    apply_operator_workspace(gui)
    apply_final_release_ui(gui)
    apply_custom_database_ui(gui)
    bind_direct_workspace_actions(gui)
    initialize_batch_manager(gui)
    initialize_experimental_data(gui)
    # Startup policy: keep saved Project Manager entries available, but do not
    # paint a previous project's Plan/Materials/Checklist/Cleavage into a new
    # session before the operator explicitly restores that item.
    try:
        plan_workflow._clear_editor_and_outputs(gui)
    except Exception:
        # Non-GUI pipeline contract tests may pass an inert sentinel object.
        # A real SPPSGui has already constructed the editor/output widgets here.
        pass
    ui_system.apply_theme(gui, "Standard")
    ui_system.fit_window(gui)
    ui_system.bind_shortcuts(gui)
    install_menu(gui)


__all__ = [
    "TITLE",
    "apply_custom_database_ui",
    "apply_final_release_ui",
    "apply_operator_workspace",
    "apply_plan_workspace",
    "bind_direct_workspace_actions",
    "build_base_interface",
    "build_ui",
    "initialize_batch_manager",
    "initialize_experimental_data",
]
