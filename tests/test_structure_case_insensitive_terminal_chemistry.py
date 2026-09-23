from pepforge_structure_tool.pepforge_core import expand_and_tokenize


def test_acetyl_accepts_title_and_uppercase_notation():
    assert expand_and_tokenize("Ac-EEMQRR-NH2")[0] == "Ac"
    assert expand_and_tokenize("AC-EEMQRR-NH2")[0] == "Ac"


def test_palmitoyl_accepts_title_and_uppercase_notation():
    assert expand_and_tokenize("Pal-EEMQRR-NH2")[0] == "Pal"
    assert expand_and_tokenize("PAL-EEMQRR-NH2")[0] == "Pal"


def test_common_chemical_abbreviations_are_case_tolerant():
    cases = {
        "MYR": "Myr",
        "GAL": "Gal",
        "CAF": "Caf",
        "NIC": "Nic",
    }
    for text, expected in cases.items():
        assert expand_and_tokenize(f"{text}-EEMQRR-NH2")[0] == expected


def test_explicit_residue_separators_remove_modifier_ambiguity():
    assert expand_and_tokenize("A-C-NH2")[:2] == ["A", "C"]
    assert expand_and_tokenize("P-A-L-NH2")[:3] == ["P", "A", "L"]


def test_pseudo_bridge_does_not_strip_ac_from_plain_acde():
    from peptiforg_core.peptide_target_complex_builder import _clean_sequence
    assert _clean_sequence("ACDE-NH2") == "ACDE"


def test_pseudo_bridge_rejects_explicit_d_or_internal_modified_chemistry():
    from peptiforg_core.peptide_target_complex_builder import _clean_sequence
    import pytest
    with pytest.raises(ValueError):
        _clean_sequence("Pal-dG-dH-dK-NH2")
    with pytest.raises(ValueError):
        _clean_sequence("Ac-AEEA-GHK-NH2")
