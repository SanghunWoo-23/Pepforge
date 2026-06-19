from pathlib import Path

from peptiforg_core.all_atom_md_preparation_bridge import export_all_atom_md_preparation_bridge


def test_v2_3_md_preparation_bridge_exports(tmp_path: Path):
    paths = export_all_atom_md_preparation_bridge("FITC-Cha-AEEA-dK-NH2", tmp_path, "fitc_cha")
    assert Path(paths["all_atom_md_preparation_bridge_dir"]).exists()
    assert Path(paths["openmm_template"]).exists()
    assert Path(paths["gromacs_template"]).exists()
    assert Path(paths["force_field_parameterization_checklist"]).exists()
    assert Path(paths["external_md_result_import_schema"]).exists()
    assert Path(paths["md_claim_guard_table"]).exists()


def test_v2_3_md_claim_guard_blocks_replacement_claims(tmp_path: Path):
    paths = export_all_atom_md_preparation_bridge("Pal-EEMQRR-NH2", tmp_path, "pal_eemqrr")
    text = Path(paths["md_claim_guard_table"]).read_text(encoding="utf-8-sig")
    assert "Pepforge replaces GROMACS/AMBER/OpenMM" in text
    assert "blocked" in text
    assert "external run" in text or "external validation" in text
