"""Pepforge V6.0.0 regression for the supplied SPPS Planner V8 style fix.

This guards against an important cross-window Tk style collision: opening the
Recommendations/Lab History window must not change Project Manager Plan table
headings or row heights. The embedded vendor's own Tk smoke test exercises the
runtime behavior when a display is available.
"""
from __future__ import annotations

import ast
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / 'vendor' / 'spps_planner_v8'


def test_v8_treeview_fix_is_present_and_does_not_touch_global_styles():
    source = (VENDOR / 'suite_gui/modules/experimental_data_panel.py').read_text(encoding='utf-8')
    ast.parse(source)
    assert 'style.configure("SPPS.History.Treeview"' in source
    assert 'style.configure("SPPS.History.Treeview.Heading"' in source
    assert 'style="SPPS.History.Treeview"' in source
    assert 'style.configure("Treeview"' not in source
    assert 'style.configure("Treeview.Heading"' not in source


def test_v8_upstream_regression_is_preserved():
    source = (VENDOR / 'tests/test_v8_recommendations_style_isolation.py').read_text(encoding='utf-8')
    ast.parse(source)
    assert 'test_history_styles_do_not_override_main_plan_headers' in source
    assert 'test_recommendation_panel_never_configures_global_treeview_style' in source


def test_versions_and_normal_window_launcher_are_preserved():
    assert (ROOT / 'VERSION.txt').read_text(encoding='utf-8').strip() == 'V6.0.0'
    assert (VENDOR / 'VERSION.txt').read_text(encoding='utf-8').strip() == 'V8.0.0'
    launcher = (ROOT / 'main_launcher.py').read_text(encoding='utf-8')
    assert 'companion = exe_dir / "SPPS_Planner" / "SPPS_Planner.exe"' in launcher
    assert 'EmbeddedSppsWorkspace' not in launcher
    assert 'SetParent(' not in launcher


def test_vendor_public_does_not_ship_private_seed():
    if (VENDOR / 'DO_NOT_PUBLISH_PRIVATE_BUILD.md').exists():
        pytest.skip('Private source edition; only public releases must exclude private data')
    forbidden = {
        'DO_NOT_PUBLISH_PRIVATE_BUILD.md', 'PRIVATE_DATA_POLICY.md',
        'cleavage_empirical_anchors_seed.csv', 'loading_history_seed.csv',
    }
    assert not any(p.name in forbidden for p in VENDOR.rglob('*') if p.is_file())
