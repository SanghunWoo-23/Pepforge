from pepforge_structure_tool.pepforge_core import expand_and_tokenize, tokens_to_smiles, build_structure


def test_pal_d_amino_cterm_amide_is_real_acyl_amide_chain(tmp_path):
    raw = expand_and_tokenize("Pal_dG-dH-dK-NH2")
    assert raw == ["Pal", "dG", "dH", "dK", "NH2"]
    smiles, tokens, warnings, ranges = tokens_to_smiles(raw)
    assert smiles.startswith("CCCCCCCCCCCCCCCC(=O)NCC(=O)")
    assert smiles.endswith("C(=O)N")
    assert "NCCCCCCCCCCCCCCCC(=O)" not in smiles
    assert any(r.token == "Pal" and r.kind == "n_terminal" for r in ranges)
    assert any(r.token == "NH2" and r.kind == "c_terminal_atom" for r in ranges)
    assert warnings == []

    result = build_structure("Pal_dG-dH-dK-NH2", tmp_path, name="pal_dg_dh_dk_nh2", optimize=False, num_confs=1)
    assert result.sdf_path and result.pdb_path and result.meta_path
    assert result.heavy_atoms == 41
