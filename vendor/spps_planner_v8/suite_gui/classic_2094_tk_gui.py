"""Backward-compatible import path for the accepted classic desktop GUI.

New code should import :mod:`suite_gui.release`. This shim remains so existing
scripts using the historical module path continue to work unchanged.
"""
from __future__ import annotations

import sys

from suite_gui import release as _implementation


if __name__ == "__main__":
    _implementation.main()
else:
    # Preserve the historical public import identity without loading patches.
    sys.modules[__name__] = _implementation
