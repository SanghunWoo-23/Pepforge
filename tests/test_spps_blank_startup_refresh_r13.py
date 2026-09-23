from __future__ import annotations

from spps_v4_gui.classic_base import ClassicControllerBase


class Var:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value


class EmptyTree:
    def get_children(self):
        return ()


class BlankRefreshGui:
    tree = EmptyTree()
    pm_sequence = Var("")
    # Deliberately stale legacy state: the visible blank must still win.
    seq = Var("OLD")

    def recalculate_row(self, _child):
        raise AssertionError("no row should be recalculated")

    def tree_rows(self):
        return []

    def rebuild_table(self):
        raise AssertionError("blank idle/startup refresh must not invoke the parser")

    def _sequence_for_implicit_refresh(self):
        return ClassicControllerBase._sequence_for_implicit_refresh(self)


def test_blank_visible_sequence_blocks_implicit_rebuild_even_with_stale_legacy_seq():
    gui = BlankRefreshGui()
    assert gui._sequence_for_implicit_refresh() == ""
    assert ClassicControllerBase.refresh_outputs_from_tree(gui) is None


def test_implicit_refresh_uses_legacy_seq_only_without_project_manager_editor():
    class LegacyGui:
        seq = Var("GHK")

    gui = LegacyGui()
    assert ClassicControllerBase._sequence_for_implicit_refresh(gui) == "GHK"


def test_nonempty_project_manager_sequence_is_visible_to_implicit_refresh():
    class ProjectManagerGui:
        pm_sequence = Var(" GHK ")
        seq = Var("")

    gui = ProjectManagerGui()
    assert ClassicControllerBase._sequence_for_implicit_refresh(gui) == "GHK"
