from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_spps_primary_tabs_are_compact():
    src = (ROOT / "suite_gui" / "spps_tk_gui.py").read_text(encoding="utf-8")
    assert 'self._build_calculator_tab()' not in src
    assert 'self.material_tree = self._tree_in_frame(step_box' in src
    assert 'self.tabs.add(fr, text="Project")' in src
    assert 'sheets.add(transfer_box, text="Transfer")' in src

def test_reset_widths_targets_summary_trees():
    src = (ROOT / "suite_gui" / "spps_tk_gui.py").read_text(encoding="utf-8")
    for name in ["live_usage_tree", "material_tree", "aa_summary_tree", "reagent_summary_tree", "solvent_summary_tree", "progress_tree"]:
        assert name in src
