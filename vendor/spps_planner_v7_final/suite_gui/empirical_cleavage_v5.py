"""Compatibility import surface for suite_gui.recommendation.empirical_cleavage."""
from suite_gui.recommendation import empirical_cleavage as _impl
import sys as _sys
_sys.modules[__name__] = _impl
