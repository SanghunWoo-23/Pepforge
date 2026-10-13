from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_primary_launcher_unifies_psb_and_docking():
    src = _read("main_launcher.py")
    assert '"name": "Structure & Docking Studio"' in src
    assert '"group": "HIDDEN"' in src and '"name": "Advanced Docking Review"' in src
    assert 'Advanced Docking Review (legacy)' in src


def test_studio_has_large_multiline_sequence_input_and_scroll_page():
    src = _read("suite_gui/pymol_structure_builder_gui.py")
    assert 'self.sequence_text = tk.Text' in src
    assert 'height=3' in src
    assert 'VerticalPageScroller(self, shell' in src
    assert 'BUILD + DOCK + ANALYZE' in src


def test_standard_wheel_navigation_replaces_middle_button_pan():
    src = _read("peptiforg_core/ui_theme.py")
    section = src[src.index("def bind_page_navigation"):]
    assert '<MouseWheel>' in section
    assert 'bindtags' in section
    assert '<ButtonPress-2>' not in section
    assert '<B2-Motion>' not in section


def test_legacy_dockbench_blank_nested_canvas_removed():
    src = _read("suite_gui/docking_workbench_gui.py")
    assert 'Input (advanced compatibility / review)' in src
    assert 'self._input_canvas=None' in src
    assert 'nested Canvas could render as a large blank viewport' in src


def test_spps_launch_targets_supplied_v7_r2_runtime():
    launcher = _read("main_launcher.py")
    assert 'vendor", "spps_planner_v7_final"' in launcher
    assert 'pepforge_entry.py' in launcher
    assert 'SPPS Planner V7.0.0 FINAL runtime' in launcher
    assert Path("vendor/spps_planner_v7_final/VERSION").read_text(encoding="utf-8").strip() == "V7.0.0"
