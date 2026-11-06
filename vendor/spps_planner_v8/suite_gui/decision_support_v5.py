"""Compatibility import surface for suite_gui.recommendation.decision_support."""
from suite_gui.recommendation import decision_support as _impl
import sys as _sys
_sys.modules[__name__] = _impl
