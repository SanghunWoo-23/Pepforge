"""Pepforge-integrated SPPS Planner V4 workflow.

The implementation is based on the user's public-data-sanitized SPPS Planner
V4 controller, isolated under ``spps_v4_gui``. Pepforge's source-level build excludes LOT controls and the
Batch Manager tab; no widgets or methods are replaced at runtime.
"""
from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog

from peptiforg_core.sandbox_runtime import configured_output
from peptiforg_core.ui_helpers import set_pepforge_icon
from peptiforg_core.ui_theme import apply_pepforge_theme
from spps_v4_gui.release import SPPSGui as _SPPSV4Gui


ROOT = Path(__file__).resolve().parents[1]


class SPPSGui(_SPPSV4Gui):
    """SPPS Planner V4 workflow with Pepforge output and visual integration."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Pepforge V3.0.0 - SPPS Planner V4")
        set_pepforge_icon(self)
        apply_pepforge_theme(self)
        for name in ("lot_no", "pm_lot"):
            variable = getattr(self, name, None)
            if hasattr(variable, "set"):
                variable.set("")

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


__all__ = ["SPPSGui", "main", "launch"]


if __name__ == "__main__":
    launch()
