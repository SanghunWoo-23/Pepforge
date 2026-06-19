from suite_gui.docking_workbench_gui import (
    canonical_peptide_notation,
    parse_peptide_notation,
    _split_peptide_model_tokens,
    misplaced_nterm_modifier_tokens,
    peptide_token_compatibility_df,
    peptide_pseudo_model,
    pseudo_peptide_pdb,
    pseudo_peptide_cif,
)


def test_dash_modified_notation_without_extra_spaces_is_parsed():
    seq = "FITC-Cha-AEEA-dK-NH2"
    assert canonical_peptide_notation(seq) == "FITC-Cha-AEEA-dK-NH2"
    parsed = parse_peptide_notation(seq)
    assert parsed["nterm"] == "FITC"
    assert parsed["cterm"] == "NH2"
    assert "Cha" in parsed["aa_like_tokens"]
    assert "AEEA" in parsed["linker_tokens"]
    rows = _split_peptide_model_tokens(seq)
    assert [r["token"] for r in rows] == ["FITC", "Cha", "AEEA", "dK"]
    assert [r["class"] for r in rows] == ["n_terminal_chemical", "non_natural", "linker", "d_form"]


def test_pal_is_nterm_only_by_default_and_internal_pal_is_flagged():
    good = "Pal-Cha-AEEA-dK-NH2"
    bad = "Cha-Pal-AEEA-dK-NH2"
    assert parse_peptide_notation(good)["nterm"] == "Pal"
    assert misplaced_nterm_modifier_tokens(good) == []
    assert misplaced_nterm_modifier_tokens(bad) == ["Pal"]
    df = peptide_token_compatibility_df(bad)
    warning = df[df["metric"] == "terminal_modifier_warnings"].iloc[0]["value"]
    assert warning == "Pal"


def test_modified_peptide_visualization_exports_are_pymol_readable_and_limited():
    points = peptide_pseudo_model("FITC-Cha-AEEA-dK-NH2")
    pdb = pseudo_peptide_pdb(points)
    cif = pseudo_peptide_cif(points)
    assert "REMARK TOKEN" in pdb
    assert "not a fully parameterized all-atom peptide" in pdb
    assert "ATOM" in pdb
    assert "_pepforge_token.original_token" in cif
    assert "FITC" in cif and "AEEA" in cif
