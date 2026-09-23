"""Pepforge-integrated SPPS Planner V5.0.0 workflow.

The implementation is based on the user's public-data-sanitized SPPS Planner
V5 controller, retained under the ``spps_v4_gui`` compatibility namespace. Pepforge's source-level build excludes LOT controls and the
Batch Manager tab; no widgets or methods are replaced at runtime.
"""
from __future__ import annotations

from pathlib import Path
import os
import tkinter as tk
from tkinter import filedialog

from peptiforg_core.sandbox_runtime import configured_output
from peptiforg_core.ui_helpers import set_pepforge_icon
from peptiforg_core.ui_theme import apply_pepforge_theme
from peptiforg_core.version import PEPFORGE_VERSION
from peptiforg_core.startup_runtime import StartupTrace, mark_window_visible
from spps_v4_gui.release import SPPSGui as _SPPSV5Gui


ROOT = Path(__file__).resolve().parents[1]


def _workflow_handoff_from_env(environ=None) -> dict[str, str]:
    """Return Workflow → SPPS launch values without affecting normal standalone startup."""
    env = os.environ if environ is None else environ
    sequence = str(env.get("PEPFORGE_WORKFLOW_SPPS_SEQUENCE", "") or "").strip()
    if not sequence:
        return {}
    return {
        "project": str(env.get("PEPFORGE_WORKFLOW_SPPS_PROJECT", "") or "").strip(),
        "sequence": sequence,
        "resin": str(env.get("PEPFORGE_WORKFLOW_SPPS_RESIN", "") or "Amide").strip() or "Amide",
        "loading": str(env.get("PEPFORGE_WORKFLOW_SPPS_LOADING", "") or "0.8").strip() or "0.8",
        "scale": str(env.get("PEPFORGE_WORKFLOW_SPPS_SCALE", "") or "400").strip() or "400",
        "apply_loading_calc": str(env.get("PEPFORGE_WORKFLOW_SPPS_APPLY_LOADING", "1") or "1").strip().lower() not in {"0", "false", "no", "off"},
    }


class SPPSGui(_SPPSV5Gui):
    """SPPS Planner V5.0.0 workflow with Pepforge output and visual integration."""

    def __init__(self) -> None:
        self._startup_trace = StartupTrace("spps_planner", ROOT / "workspace" / "spps" / "logs")
        super().__init__()
        self.title(f"Pepforge V{PEPFORGE_VERSION} - SPPS Planner V5.0.0")
        set_pepforge_icon(self)
        apply_pepforge_theme(self)
        mark_window_visible(self, self._startup_trace)
        for name in ("lot_no", "pm_lot"):
            variable = getattr(self, name, None)
            if hasattr(variable, "set"):
                variable.set("")
        # A genuinely new planner is blank because its fresh Project Manager
        # item has an empty sequence.  Do not blank an autosaved/restored item
        # here: saved sequence state must survive closing and reopening.
        self._apply_workflow_handoff()

    def _apply_workflow_handoff(self) -> None:
        handoff = _workflow_handoff_from_env()
        if not handoff:
            return

        sequence = handoff["sequence"]
        resin = handoff["resin"]
        loading = handoff["loading"]
        scale = handoff["scale"]
        apply_loading_calc = bool(handoff.get("apply_loading_calc", True))
        project = handoff["project"]

        for name, value in (("seq", sequence), ("pm_sequence", sequence),
                            ("resin", resin), ("pm_resin", resin),
                            ("loading", loading), ("pm_loading", loading),
                            ("scale", scale), ("pm_scale", scale)):
            variable = getattr(self, name, None)
            if hasattr(variable, "set"):
                try:
                    variable.set(value)
                except (tk.TclError, ValueError, TypeError):
                    # Numeric Tk variables may reject malformed external values;
                    # the Workflow validates them before launch, but keep the
                    # standalone planner defensive for direct environment use.
                    pass

        loading_toggle = getattr(self, "apply_loading_calc", None)
        if hasattr(loading_toggle, "set"):
            loading_toggle.set(apply_loading_calc)

        if project:
            project_path = Path(project)
            for name in ("project_name", "pm_project"):
                variable = getattr(self, name, None)
                if hasattr(variable, "set"):
                    variable.set(project_path.name)
            outdir = getattr(self, "outdir", None)
            if hasattr(outdir, "set"):
                outdir.set(str(project_path / "spps"))

        if isinstance(getattr(self, "pm_items", None), list) and self.pm_items:
            self.pm_items[0].update({
                "project": Path(project).name if project else self.pm_items[0].get("project", ""),
                "sequence": sequence,
                "resin": resin,
                "loading": loading,
                "scale": scale,
                "apply_loading_calc": apply_loading_calc,
            })

    def _default_outdir(self) -> Path:
        return configured_output(ROOT / "outputs" / "spps_planner", "spps")

    def browse_outdir(self) -> None:
        current = str(getattr(self, "outdir", tk.StringVar(value="")).get() or "").strip()
        initial = Path(current).expanduser() if current else self._default_outdir().parent
        selected = filedialog.askdirectory(initialdir=str(initial))
        if selected:
            self.outdir.set(selected)


def main() -> None:
    app = SPPSGui()
    app.mainloop()


def launch() -> None:
    main()


__all__ = ["SPPSGui", "main", "launch", "_workflow_handoff_from_env"]


if __name__ == "__main__":
    launch()
