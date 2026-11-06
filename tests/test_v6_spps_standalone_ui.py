"""V6 independent SPPS V8 window and adjacent structure/sequence UI contracts."""
from pathlib import Path
import ast
import sys
import os
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_standalone_v8_public_entry_and_pepforge_versions():
    assert (ROOT / 'vendor/spps_planner_v8/main_launcher.py').is_file()
    assert (ROOT / 'VERSION.txt').read_text(encoding='utf-8').strip() == 'V6.0.0'
    assert (ROOT / 'vendor/spps_planner_v8/VERSION.txt').read_text(encoding='utf-8').strip() == 'V8.0.0'


def test_launch_dispatches_spps_to_normal_window_not_setparent():
    code = (ROOT / 'main_launcher.py').read_text(encoding='utf-8')
    ast.parse(code)
    assert 'run_spps_planner()  # same standalone-window model' in code
    assert 'EmbeddedSppsWorkspace' not in code
    assert 'SetParent(' not in code
    assert 'companion = exe_dir / "SPPS_Planner" / "SPPS_Planner.exe"' in code
    assert 'subprocess.Popen(' in code


def test_docking_inputs_receptor_and_peptide_each_have_pdb_and_sequence():
    code = (ROOT / 'suite_gui/pymol_structure_builder_gui.py').read_text(encoding='utf-8')
    ast.parse(code)
    assert 'text="Receptor"' in code and 'text="Peptide"' in code
    assert 'self.docking_peptide_sequence = ttk.Entry(peptide_box, textvariable=self.sequence_var)' in code
    assert code.index('receptor_box =') < code.index('peptide_box =') < code.index('v5_box =')


def test_public_never_contains_private_seed_files():
    vendor = ROOT / 'vendor/spps_planner_v8'
    if (vendor / 'PRIVATE_DATA_POLICY.md').exists():
        pytest.skip("private edition intentionally contains internal data")
    for name in ('PRIVATE_DATA_POLICY.md', 'DO_NOT_PUBLISH_PRIVATE_BUILD.md',
                 'cleavage_empirical_anchors_seed.csv', 'loading_history_seed.csv'):
        if (ROOT / 'PUBLIC_DATA_POLICY.md').is_file():
            assert not list(vendor.rglob(name))


@pytest.mark.skipif(sys.platform == 'win32' or not os.environ.get('DISPLAY'),
                    reason='Tk smoke requires Xvfb or X11')
def test_studio_one_window_cross_tab_sequence_sync():
    import tkinter as tk
    from tkinter import ttk
    from suite_gui.pymol_structure_builder_gui import PyMOLStructureBuilderGUI
    window = PyMOLStructureBuilderGUI()
    try:
        assert len(window.studio_tabs.tabs()) == 3
        window.sequence_var.set('Ac-EEMQRR-NH2')
        window.update_idletasks()
        assert window.docking_peptide_sequence.get() == 'Ac-EEMQRR-NH2'
        window.studio_tabs.select(1)
        window.docking_peptide_sequence.delete(0, 'end')
        window.docking_peptide_sequence.insert(0, 'dK')
        window.update_idletasks()
        assert window.sequence_var.get() == 'dK'
        window.studio_tabs.select(0)
        window.update_idletasks()
        assert window.sequence_text.get('1.0', 'end-1c') == 'dK'
    finally:
        window.destroy()
