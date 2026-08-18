"""Explicit SPPS V4 UI construction pipeline for Pepforge V3.0.0.

The accepted interface used to be assembled by nested ``_build`` wrappers.
This module preserves the same order as ordinary function calls.  Nothing in
this file assigns methods to a GUI class at runtime.
"""
from __future__ import annotations

import json
from typing import Any

from spps_v4_gui import calculation_context, custom_db_workflow, experimental_workflow
from spps_v4_gui.v3_menu import install_menu
from spps_v4_gui import ui_system
from spps_v4_gui.classic_base import ClassicControllerBase
from spps_v4_gui.modules import (
    final_plan_adjustments,
    plan_workflow,
    project_manager_workflow,
    release_ui,
    setup_controls,
    operator_controls,
    workspace_widgets as workbench,
)


TITLE = "SPPS Planner V4.0.0"


def build_base_interface(gui: Any) -> None:
    """Build the retained classic widgets once, without any wrapper chain."""
    gui._v229_ns = calculation_context.namespace()
    gui._v228_ns = gui._v229_ns
    gui._v229_switching = True
    try:
        ClassicControllerBase._build(gui)
    finally:
        gui._v229_switching = False


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
    setup_controls.apply_post_build(gui)
    project_manager_workflow.apply_post_build(gui, plan_workflow, namespace)
    operator_controls.apply_post_build(gui)
    final_plan_adjustments.apply_post_build(gui)


def apply_final_release_ui(gui: Any) -> None:
    """Apply the fixed SPPS V4 identity, resin list, and cleavage controls."""
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
    """Restore the real Custom DB tab and its persisted values."""
    _load_custom_materials(gui)

    def restore_and_pin() -> None:
        _restore_custom_tab(gui)
        _pin_setup_button(gui)

    restore_and_pin()
    try:
        gui.after_idle(restore_and_pin)
        for delay in (120, 450):
            gui.after(delay, restore_and_pin)
    except Exception:
        pass


def bind_direct_workspace_actions(gui: Any) -> None:
    """Route retained Project/session buttons through the controller."""
    commands = {
        "Export": gui.export_outputs,
        "Save Session Now": gui.save_autosave_state,
        "Save Project": gui.save_project,
        "Load Project": gui.load_project,
    }
    for widget in workbench._walk(gui):
        if not isinstance(widget, workbench.ttk.Button):
            continue
        try:
            command = commands.get(str(widget.cget("text")).strip())
            if command is not None:
                widget.configure(command=command)
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
    "initialize_experimental_data",
]
