from pathlib import Path


def test_real_pymol_tool_builds_connected_files(tmp_path):
    from peptiforg_core.pymol_structure_builder import export_modified_peptide_structure
    paths = export_modified_peptide_structure("Ac-K(Ahx-Biotin)-LVFF-NH2", tmp_path, "k_ahx_biotin_lvff")
    for key in ["sdf", "pdb", "json", "report", "pml", "token_map"]:
        assert Path(paths[key]).exists(), key
    assert "cif" not in paths


def test_real_pymol_tool_parses_sidechain_and_fitc():
    from peptiforg_core.pymol_structure_builder import classify_tokens
    rows = classify_tokens("Ac-K(FITC)-LVFF-NH2")
    assert any("FITC" in r.token or "FITC" in r.note for r in rows)
    rows2 = classify_tokens("FITC-Cha-AEEA-dK-NH2")
    classes = {r.cls for r in rows2}
    assert "non_natural_aa" in classes or "non_natural_residue" in classes
    assert "linker" in classes
