from __future__ import annotations

from pathlib import Path

from apps.spps_planner_app.spps_planner.engine import PlanInput, generate_materials, generate_step_materials


def test_v4_psb_does_not_expose_md_trajectory_button():
    root = Path(__file__).resolve().parents[1]
    source = (root / "suite_gui" / "pymol_structure_builder_gui.py").read_text(encoding="utf-8")
    assert 'text="Analyze Trajectory"' not in source
    assert "def analyze_md_trajectory_files" not in source
    assert 'text="Analyze Structures"' in source
    assert 'text="Compare Structures"' in source


def test_workflow_sequence_save_button_is_in_header_not_text_box():
    root = Path(__file__).resolve().parents[1]
    source = (root / "peptiforg_core" / "workflow_gui.py").read_text(encoding="utf-8")
    assert "seq_header = ttk.Frame(seq_section)" in source
    assert 'ttk.Button(seq_header, text="Save sequence to project"' in source
    assert 'ttk.Button(seqbox, text="Save sequence to project"' not in source


def test_spps_material_pipeline_has_no_version_stacked_wrappers():
    root = Path(__file__).resolve().parents[1]
    source = (root / "apps" / "spps_planner_app" / "spps_planner" / "engine.py").read_text(encoding="utf-8")
    forbidden = (
        "_V219_ORIG_GENERATE_STEP_MATERIALS", "_V221_ORIG_GENERATE_STEP_MATERIALS",
        "_V222_ORIG_GENERATE_STEP_MATERIALS", "_generate_step_materials_v219",
        "_generate_step_materials_v221", "_generate_step_materials_v222",
        "_generate_materials_v219", "_generate_materials_v221", "_generate_materials_v222",
    )
    assert not any(token in source for token in forbidden)
    assert "raw = _generate_step_materials_core(inp, compounds, rules)" in source
    assert "raw = _generate_materials_core(inp, compounds, rules)" in source


def test_flattened_material_pipeline_preserves_operator_contract():
    inp = PlanInput(sequence="Ac-EEMQRR-NH2", resin="Amide", scale_mmol=0.4, resin_loading_mmol_g=0.8)
    steps = generate_step_materials(inp)
    totals = generate_materials(inp)
    assert list(steps.head(2)["material"]) == ["Amide", "DMF"]
    assert "Acetic anhydride (Ac2O)" in set(steps["material"].astype(str))
    assert "Fmoc-Arg(Pbf)-OH" in set(totals["material"].astype(str))
    assert "R" not in set(totals["material"].astype(str))
    dic = totals[totals["material"].astype(str).eq("DIC")].iloc[0]
    assert dic["unit"] == "mL"
    assert str(dic["planned_g"]) == ""
