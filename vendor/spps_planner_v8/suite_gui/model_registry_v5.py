"""Compatibility import for the canonical recommendation model registry.

New code must import ``suite_gui.recommendation.model_registry`` or
``suite_gui.recommendation.models``. The historical module name is kept so
older extensions/tests that monkeypatch module internals continue to target
the same canonical module object.
"""
from __future__ import annotations
import sys as _sys
from suite_gui.recommendation import model_registry as _canonical
_sys.modules[__name__] = _canonical
