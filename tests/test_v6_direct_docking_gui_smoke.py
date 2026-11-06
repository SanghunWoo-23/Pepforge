"""Opt-in real Tk + native-docking GUI smoke.

Linux CI: PEPFORGE_GUI_SMOKE=1 xvfb-run -a python -m pytest -q tests/test_v6_direct_docking_gui_smoke.py
Windows: run with an interactive desktop and PEPFORGE_GUI_SMOKE=1.
"""
from pathlib import Path
import os
import time
import pytest
from tests.test_v5_native_docking_v1 import _write_pdb


@pytest.mark.skipif(os.environ.get('PEPFORGE_GUI_SMOKE') != '1', reason='Requires interactive Tk display; explicitly opt in')
def test_direct_file_gui_displays_verified_pose_and_progress(tmp_path, monkeypatch):
    from tkinter import messagebox
    from suite_gui.pymol_structure_builder_gui import PyMOLStructureBuilderGUI
    dialogs = []
    monkeypatch.setattr(messagebox, 'showinfo', lambda *a, **kw: dialogs.append(('info', a)))
    monkeypatch.setattr(messagebox, 'showerror', lambda *a, **kw: dialogs.append(('error', a)))
    monkeypatch.setattr(messagebox, 'showwarning', lambda *a, **kw: dialogs.append(('warning', a)))
    receptor = tmp_path / 'receptor.pdb'; peptide = tmp_path / 'peptide.pdb'
    _write_pdb(receptor, 'A'); _write_pdb(peptide, 'P', offset=(20, 20, 20))
    window = PyMOLStructureBuilderGUI()
    window.withdraw()
    try:
        window.bridge_receptor_path.set(str(receptor))
        window.v6_peptide_source.set('file')
        window.v6_peptide_path.set(str(peptide))
        window.output_dir.set(str(tmp_path / 'run'))
        window.v5_docking_preset.set('fast')
        window.v5_run_md.set(False)
        window.run_v5_full_simulation()
        deadline = time.monotonic() + 55
        while time.monotonic() < deadline:
            window.update()
            if window.shared_native_result_panel.pose_tree.get_children() or window._v5_pipeline_error:
                break
            time.sleep(.06)
        assert window._v5_pipeline_error is None, window._v5_pipeline_error
        assert len(window.shared_native_result_panel.pose_tree.get_children()) >= 1
        assert float(window.docking_progress['value']) == 100.0
        assert not [d for d in dialogs if d[0] == 'error'], dialogs
    finally:
        window.destroy()
