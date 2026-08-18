from pathlib import Path

from suite_gui.docking_workbench_gui import (
    canonical_peptide_notation,
    parse_peptide_notation,
    _split_peptide_model_tokens,
    misplaced_nterm_modifier_tokens,
    peptide_token_compatibility_df,
    build_peptide_structure_bundle,
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
    assert [r["token"] for r in rows] == ["FITC", "Cha", "AEEA", "dK", "NH2"]
    assert [r["class"] for r in rows] == ["label", "non_natural_aa", "linker", "d_std_aa", "c_terminal"]


def test_pal_is_nterm_only_by_default_and_internal_pal_is_flagged():
    good = "Pal-Cha-AEEA-dK-NH2"
    bad = "Cha-Pal-AEEA-dK-NH2"
    assert parse_peptide_notation(good)["nterm"] == "Pal"
    assert misplaced_nterm_modifier_tokens(good) == []
    assert misplaced_nterm_modifier_tokens(bad) == ["Pal"]
    df = peptide_token_compatibility_df(bad)
    warning = str(df[df["metric"] == "notation_warnings"].iloc[0]["value"])
    assert "PAL" in warning.upper()
    assert "N-TERMINAL" in warning.upper()


def test_modified_peptide_structure_builder_preserves_tokens_and_exports_atomic_pdb(tmp_path):
    points, paths = build_peptide_structure_bundle(
        "FITC-Cha-AEEA-dK-NH2", tmp_path, name="modified_peptide"
    )
    assert [str(v) for v in points["token"].tolist()] == ["FITC", "Cha", "AEEA", "dK"]
    assert [str(v) for v in points["token_class"].tolist()] == [
        "label", "non_natural_aa", "linker", "d_std_aa"
    ]
    pdb_path = Path(paths["pdb"])
    assert pdb_path.exists()
    pdb_text = pdb_path.read_text(encoding="utf-8", errors="replace")
    assert "ATOM" in pdb_text or "HETATM" in pdb_text
