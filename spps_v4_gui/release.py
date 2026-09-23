"""Canonical SPPS Planner V5.0.0 desktop surface embedded in Pepforge V4.0.0."""
from __future__ import annotations

from spps_v4_gui.controller import SPPSGui, main
from spps_v4_gui.release_contract import validate_release_controller


validate_release_controller(SPPSGui)


def launch() -> None:
    """Launch the statically defined SPPS V5.0.0 controller."""
    main()


__all__ = ["SPPSGui", "main", "launch"]
