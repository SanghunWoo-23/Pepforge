from __future__ import annotations

"""Canonical Pepforge suite version.

User-facing release surfaces import this value instead of repeating a version
literal. Component versions (for example SPPS Planner V4) remain independent.
"""

PEPFORGE_VERSION = "4.0.0"
PEPFORGE_RELEASE_NAME = "Scientific Context, Structure & Simulation Design"


def version_string(prefix: str = "Pepforge") -> str:
    return f"{prefix} V{PEPFORGE_VERSION}"
