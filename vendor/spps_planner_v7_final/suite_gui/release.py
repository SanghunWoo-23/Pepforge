"""Canonical SPPS Planner V6 desktop release surface."""
from __future__ import annotations

from suite_gui.controller import SPPSGui, main
from suite_gui.release_contract import validate_release_controller


validate_release_controller(SPPSGui)


def launch() -> None:
    """Launch the statically defined V3.0.0 controller."""
    main()


__all__ = ["SPPSGui", "main", "launch"]
