from apps.spps_planner_app.spps_planner.engine import PlanInput, generate_step_matrix, generate_detailed_operations, generate_materials
from apps.spps_planner_app.spps_planner.export import export_excel, export_csvs
from peptiforg_core.project_io import new_project, load_project, safe_name
from pathlib import Path


def _ops(inp):
    return generate_detailed_operations(inp)


def test_regular_cycle_wash_order_is_depro6_coupling_post2():
    m = generate_step_matrix(PlanInput(sequence="EEMQRR-NH2", scale_mmol=300))
    regular = m[m.phase == "Regular AA coupling"]
    assert not regular.empty
    assert set(regular.dmf_wash_x.astype(int)) == {6}
    assert set(regular.post_dmf_wash_x.astype(int)) == {2}


def test_final_free_nterm_has_no_editable_fmoc_removal_unit():
    m = generate_step_matrix(PlanInput(sequence="EEMQRR-NH2", scale_mmol=300))
    assert "Fmoc removal" not in set(m.unit.astype(str))
    assert list(m.unit.astype(str))[-1] == "E"


def test_ac_row_carries_final_depro_wash_without_dcm_final_wash():
    m = generate_step_matrix(PlanInput(sequence="Ac-EEMQRR-NH2", scale_mmol=300))
    ac = m[m.unit == "Ac"].iloc[-1]
    assert int(ac.depro_x) == 2
    assert int(ac.dmf_wash_x) == 6
    assert int(ac.reaction_x) == 1
    assert int(ac.post_dmf_wash_x) == 0
    assert int(ac.dcm_wash_x) == 0
    assert "Fmoc removal" not in set(m.unit.astype(str))


def test_fmoc_removal_is_not_counted_as_material_reagent():
    mat = generate_materials(PlanInput(sequence="EEMQRR-NH2", scale_mmol=300))
    assert "Fmoc removal" not in set(mat.material.astype(str))
    assert not ((mat.material.astype(str) == "DIC") & mat.source.astype(str).str.contains("Final deprotection", na=False)).any()


def test_project_workflow_save_load_and_export(tmp_path: Path):
    project_dir = new_project("Acetyl HexaPeptide-3(AHP-3)", "Ac-EEMQRR-NH2", base_dir=tmp_path)
    assert safe_name("Acetyl HexaPeptide-3(AHP-3)") in project_dir.name
    project = load_project(project_dir)
    assert project["input_sequence"] == "Ac-EEMQRR-NH2"
    inp = PlanInput(sequence="Ac-EEMQRR-NH2", scale_mmol=300)
    export_dir = project_dir / "exports"
    export_csvs(inp, export_dir)
    export_excel(inp, export_dir / "spps_plan.xlsx")
    assert (export_dir / "spps_plan.xlsx").exists()
    assert (export_dir / "printable_synthesis_checklist.csv").exists()
    assert (export_dir / "raw_material_use.csv").exists()
