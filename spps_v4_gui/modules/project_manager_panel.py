"""Project Manager controller for SPPS Planner V4.0.0.

This module centralizes Project Manager actions behind an explicit controller
object so GUI buttons call one stable, testable route.
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
        for widget in state.walk_widgets(self.gui):
            try:
                if widget.winfo_class() not in ("TButton", "Button"):
                    continue
                label = str(widget.cget("text") or "").strip()
                if label == "Duplicate":
                    widget.configure(command=self.duplicate_selected)
                elif label == "Delete":
                    widget.configure(command=self.delete_selected)
                elif label in {"Export", "Save"}:
                    widget.configure(command=self.export_outputs)
                elif label.startswith("Generate / Update"):
                    widget.configure(command=self.generate_update)
                elif label == "Apply cleavage":
                    widget.configure(command=self.apply_cleavage)
            except Exception:
                continue

    def duplicate_selected(self):
        return peptide_items.duplicate_selected(self.gui)

    def delete_selected(self):
        return peptide_items.delete_selected(self.gui)

    def move_selected_to(self, target: int):
        return peptide_items.move_selected_to(self.gui, target)

    def generate_update(self):
        return export_panel.generate_update(self.gui)

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
