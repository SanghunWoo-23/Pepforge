"""Public Tk GUI entry point for SPPS Planner V4.0.0."""
from __future__ import annotations
from spps_v4_gui.release import SPPSGui, main, launch

__all__ = ["SPPSGui", "main", "launch"]

if __name__ == "__main__":
    launch()
