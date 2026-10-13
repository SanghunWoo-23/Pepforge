"""Backward-compatible V3 import path. Canonical menu implementation: suite_gui.menu."""
from suite_gui import menu as _canonical
install_menu = _canonical.install_menu
_select_result_tab = _canonical._select_result_tab
__all__ = ["install_menu"]
