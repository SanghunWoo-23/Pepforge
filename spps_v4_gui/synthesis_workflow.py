"""Direct Plan generation and Apply Change workflow for V4.0.0.

The historical release reached these operations through two runtime class
patches: the accepted Plan workflow and a final Project Manager wrapper that
synchronised unified unit defaults.  This module preserves that exact order as
ordinary function calls.
"""
from __future__ import annotations

from typing import Any

from spps_v4_gui import calculation_context
from spps_v4_gui.modules import plan_workflow, project_manager_workflow


def _namespace() -> dict[str, Any]:
    return calculation_context.namespace()


def generate(gui: Any, *_args: Any, **_kwargs: Any) -> Any:
    """Generate the visible Plan and every linked result table."""
    project_manager_workflow._sync_modifier_to_aa(gui)
    return plan_workflow.generate(gui, _namespace())


def apply_change(gui: Any, *_args: Any, **_kwargs: Any) -> Any:
    """Apply the current edited Plan to all linked result tables."""
    project_manager_workflow._sync_modifier_to_aa(gui)
    return plan_workflow.apply_change(gui, _namespace())


__all__ = ["apply_change", "generate"]
