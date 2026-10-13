from __future__ import annotations

"""Pepforge bridge for the vendored SPPS Planner V7.0.0 FINAL R2 runtime.

The SPPS planner remains its own application/runtime.  This bridge only applies
optional Pepforge workflow handoff values before entering the exact V7 R2 UI.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for p in (ROOT, ROOT / "apps" / "spps_planner_app"):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)


def _handoff() -> dict[str, str]:
    seq = str(os.environ.get("PEPFORGE_WORKFLOW_SPPS_SEQUENCE", "") or "").strip()
    if not seq:
        return {}
    return {
        "project": str(os.environ.get("PEPFORGE_WORKFLOW_SPPS_PROJECT", "") or "").strip(),
        "sequence": seq,
        "resin": str(os.environ.get("PEPFORGE_WORKFLOW_SPPS_RESIN", "Amide") or "Amide").strip() or "Amide",
        "loading": str(os.environ.get("PEPFORGE_WORKFLOW_SPPS_LOADING", "0.8") or "0.8").strip() or "0.8",
        "scale": str(os.environ.get("PEPFORGE_WORKFLOW_SPPS_SCALE", "400") or "400").strip() or "400",
    }


def _safe_set(gui, name: str, value: str) -> None:
    var = getattr(gui, name, None)
    if hasattr(var, "set"):
        try:
            var.set(value)
        except Exception:
            pass


def main() -> None:
    from suite_gui.release import SPPSGui

    gui = SPPSGui()
    values = _handoff()
    if values:
        seq = values["sequence"]
        for name in ("seq", "pm_sequence"):
            _safe_set(gui, name, seq)
        for name in ("resin", "pm_resin"):
            _safe_set(gui, name, values["resin"])
        for name in ("loading", "pm_loading"):
            _safe_set(gui, name, values["loading"])
        for name in ("scale", "pm_scale"):
            _safe_set(gui, name, values["scale"])
        project = values.get("project", "")
        if project:
            project_name = Path(project).name
            for name in ("project_name", "pm_project"):
                _safe_set(gui, name, project_name)
        # V7 R2 owns the visible Project Manager state.  Refresh only through
        # its public/controller methods when available; no monkey patching.
        for method_name in ("refresh_project_manager", "refresh_project_tree"):
            method = getattr(gui, method_name, None)
            if callable(method):
                try:
                    method()
                except Exception:
                    pass
                break
    gui.mainloop()


if __name__ == "__main__":
    main()
