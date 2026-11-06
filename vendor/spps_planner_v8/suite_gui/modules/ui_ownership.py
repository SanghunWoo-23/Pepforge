"""Canonical post-construction UI ownership for SPPS Planner V6.

Each legacy module keeps responsibility-specific helpers, but ui_build invokes one
coordinator instead of growing another post-build correction chain.
"""
from __future__ import annotations
from suite_gui.modules import setup_controls, project_manager_workflow, operator_controls, final_plan_adjustments

def finalize(gui, plan_workflow, namespace):
    setup_controls.apply_post_build(gui)
    project_manager_workflow.apply_post_build(gui, plan_workflow, namespace)
    operator_controls.apply_post_build(gui)
    final_plan_adjustments.apply_post_build(gui)

__all__=['finalize']
