"""Compatibility import surface for suite_gui.recommendation.coupling_base."""
from suite_gui.recommendation import coupling_base as _impl
import sys as _sys
_sys.modules[__name__] = _impl
