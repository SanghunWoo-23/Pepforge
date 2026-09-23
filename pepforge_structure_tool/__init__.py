from __future__ import annotations

"""Lightweight public package facade for the Pepforge Structure Tool.

Importing the package no longer imports RDKit-backed generation code. The core
is loaded on first access to a build/analysis function so GUI shells can paint
before scientific backends are needed.
"""

from .version import VERSION, STRUCTURE_TOOL_VERSION

_LAZY_EXPORTS = {
    "build_structure", "build_batch", "read_batch_csv", "describe_parse",
    "environment_report", "supported_token_table", "template_manifest",
    "audit_template_files",
}


def __getattr__(name: str):
    if name in _LAZY_EXPORTS:
        from . import pepforge_core
        return getattr(pepforge_core, name)
    raise AttributeError(name)


__all__ = ["VERSION", "STRUCTURE_TOOL_VERSION", *_LAZY_EXPORTS]
