from pathlib import Path

from apps.hotspot_finder.sequence_hotspot_finder.io_utils import read_fasta_or_sequence
ROOT = Path(__file__).resolve().parents[1]


def test_direct_hotspot_sequence_accepts_visual_line_wrapping():
    records = read_fasta_or_sequence("ACDEFGHIKL\nMNPQRSTVWY")
    assert records == {"direct_input": "ACDEFGHIKLMNPQRSTVWY"}


def test_pde_uses_one_explicit_apply_then_generate_workflow():
    source = (ROOT / "apps/peptide_design_engine/Python/desktop_gui.py").read_text(encoding="utf-8")
    assert 'text="1. Apply Settings"' in source
    assert 'text="2. Generate Candidates"' in source
    assert "def apply_settings(self)" in source
    assert "self.applied_config" in source
    assert "Apply Preset to UI" not in source
    assert 'preset_combo.bind("<<ComboboxSelected>>"' in source


def test_structure_builder_uses_peptide_sequence_user_term():
    source = (ROOT / "suite_gui/pymol_structure_builder_gui.py").read_text(encoding="utf-8")
    assert 'text="Peptide sequence"' in source
    assert 'text="Peptide notation"' not in source


def test_spps_operator_outputs_include_plan_materials_totals_and_checklist():
    source = (ROOT / "spps_v4_gui/classic_base.py").read_text(encoding="utf-8")
    source += (ROOT / "spps_v4_gui/modules/workspace_widgets.py").read_text(encoding="utf-8")
    for label in ("Selected Plan", "Selected Materials", "Total Materials", "Checklist"):
        assert label in source
    assert "pm_selected_total_tree" in source
    common_source = (ROOT / "spps_v4_gui/modules/gui_common.py").read_text(encoding="utf-8")
    assert "selected_total_materials_core" in common_source


def test_spps_starts_without_example_sequence():
    source = (ROOT / "spps_v4_gui/modern_tk_gui.py").read_text(encoding="utf-8")
    default_block = source[source.index("def _default_item"):source.index("def pm_display_name")]
    assert '"sequence": ""' in default_block
    assert '"sequence": "Ac-EEMQRR-NH2"' not in default_block
