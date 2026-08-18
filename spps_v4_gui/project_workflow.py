"""Direct project workflow routes for SPPS Planner V4.0.0."""
from __future__ import annotations

from typing import Any

from spps_v4_gui import calculation_context
from spps_v4_gui.modules import plan_workflow, project_manager_workflow


def _namespace() -> dict[str, Any]:
    return calculation_context.namespace()


def select(gui: Any, event: Any = None) -> Any:
    return project_manager_workflow.single_select(
        gui, plan_workflow, _namespace(), event,
    )


def open_selected(gui: Any, event: Any = None) -> Any:
    result = project_manager_workflow.double_click(
        gui, plan_workflow, _namespace(), event,
    )
    from spps_v4_gui.work_item_window import open_selected as open_window

    open_window(gui)
    return result


def add(gui: Any, item: Any = None) -> Any:
    return plan_workflow.add_item(gui, item)


def duplicate(gui: Any) -> Any:
    return plan_workflow.duplicate_item(gui)


def delete(gui: Any) -> Any:
    return project_manager_workflow.delete_items(
        gui, plan_workflow, _namespace(),
    )


__all__ = ["add", "delete", "duplicate", "open_selected", "select"]
