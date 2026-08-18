"""Canonical SPPS Planner V4 desktop surface for Pepforge V3.0.0."""
from __future__ import annotations

from spps_v4_gui.controller import SPPSGui, main
from spps_v4_gui.release_contract import validate_release_controller


validate_release_controller(SPPSGui)


def launch() -> None:
    """Launch the statically defined SPPS V4 controller."""
    main()


__all__ = ["SPPSGui", "main", "launch"]
