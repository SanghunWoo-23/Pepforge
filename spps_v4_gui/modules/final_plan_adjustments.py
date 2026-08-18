"""Combined final parser, resin, and checklist adjustments.

This replaces two consecutive class-build wrappers with one equivalent layer.
"""
from __future__ import annotations

from spps_v4_gui.modules.final_ui_adjustments import (
    _compact_checklist,
    _restore_resin_widgets,
)


APP_VERSION = "V4.0.0"
VERSION_LABEL = "SPPS Planner V4.0.0"

def apply_post_build(gui):
    _restore_resin_widgets(gui)
    _compact_checklist(gui)
    try:
        gui.title(VERSION_LABEL)
    except Exception:
        pass
__all__ = ["apply_post_build"]
