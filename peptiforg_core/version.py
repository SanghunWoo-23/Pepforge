from __future__ import annotations

"""Canonical Pepforge suite version.

User-facing release surfaces import this value instead of repeating a version
literal. Component versions remain independent from the Pepforge suite version.
"""

PEPFORGE_VERSION = "5.0.0"
PEPFORGE_RELEASE_NAME = "Integrated Structure, Docking & Synthesis Workflow"


def version_string(prefix: str = "Pepforge") -> str:
    return f"{prefix} V{PEPFORGE_VERSION}"
