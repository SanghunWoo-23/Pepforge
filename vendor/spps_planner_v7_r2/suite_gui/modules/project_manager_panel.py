"""Stable Project Manager controller for SPPS Planner V6.0.0.

UI controls are bound by explicit widget references and use one controller route.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import gui_common as state
from . import peptide_items
from . import export_panel
from . import cleavage_panel


@dataclass
class ProjectManagerController:
    """Stable action/controller facade for the Project Manager tab."""

    gui: Any

    def normalize(self) -> None:
        """Rebind controls and refresh derived panels without changing UI layout."""
        peptide_items.bind_peptide_items(self.gui)
        cleavage_panel.ensure_cleavage_panel(self.gui)
        self.bind_action_buttons()
        try:
            cleavage_panel.refresh_cleavage_panel(self.gui)
        except Exception:
            pass

    def bind_action_buttons(self) -> None:
        """Bind known Project Manager controls by stable object reference only."""
        bindings = {
            "pm_duplicate_button": self.duplicate_selected,
            "pm_delete_button": self.delete_selected,
            "pm_export_button": self.export_outputs,
            "pm_generate_button": self.generate_update,
            "pm_apply_button": self.apply_change,
        }
        for attr, command in bindings.items():
            widget = getattr(self.gui, attr, None)
            if widget is not None:
                widget.configure(command=command)

    def duplicate_selected(self):
        return peptide_items.duplicate_selected(self.gui)

    def delete_selected(self):
        return peptide_items.delete_selected(self.gui)

    def move_selected_to(self, target: int):
        return peptide_items.move_selected_to(self.gui, target)

    def generate_update(self):
        return export_panel.generate_update(self.gui)

    def apply_change(self):
        callback = getattr(self.gui, "apply_change", None)
        if not callable(callback):
            raise AttributeError("Project Manager Apply Change route is unavailable.")
        return callback()

    def apply_cleavage(self):
        # Cleavage controls are part of the same PlanInput snapshot, so updating
        # selected outputs keeps selected-plan/material exports synchronized.
        return export_panel.generate_update(self.gui)

    def refresh_cleavage(self):
        return cleavage_panel.refresh_cleavage_panel(self.gui)

    def export_outputs(self):
        return export_panel.export_outputs(self.gui)


def get_controller(gui) -> ProjectManagerController:
    controller = getattr(gui, "_pm_controller", None)
    if not isinstance(controller, ProjectManagerController):
        controller = ProjectManagerController(gui)
        setattr(gui, "_pm_controller", controller)
    return controller


def normalize_project_manager(gui) -> ProjectManagerController:
    controller = get_controller(gui)
    controller.normalize()
    return controller
