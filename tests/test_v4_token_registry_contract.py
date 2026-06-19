from peptiforg_core.peptide_tokens import parse_peptide_notation, core_sequence, is_cterm_amide

def test_ac_vs_acde():
    p = parse_peptide_notation("ACDE-NH2")
    assert p.nterm == ""
    assert p.core_sequence == "ACDE"
    assert p.cterm == "NH2"

def test_acetylated_peptide():
    p = parse_peptide_notation("Ac-EEMQRR-NH2")
    assert p.nterm == "Ac"
    assert p.core_sequence == "EEMQRR"
    assert is_cterm_amide("Ac-EEMQRR-NH2")

def test_compact_ac_allowed():
    p = parse_peptide_notation("AcEEMQRR-NH2")
    assert p.nterm == "Ac"
    assert p.core_sequence == "EEMQRR"

def test_conh2_not_residue():
    assert core_sequence("EEMQRR-CONH2") == "EEMQRR"
    assert is_cterm_amide("EEMQRR-CONH2")

def test_linkers_not_decomposed():
    assert core_sequence("PEG4-EEMQRR-NH2") == "EEMQRR"
    assert core_sequence("Ahx-EEMQRR-NH2") == "EEMQRR"

def test_aa_like_surrogates():
    assert core_sequence("bAla-EEMQRR-NH2") == "AEEMQRR"
    assert core_sequence("gAla-EEMQRR-NH2") == "GEEMQRR"
    assert core_sequence("Sar-EEMQRR-NH2") == "GEEMQRR"

def test_pale_not_pal_modifier():
    p = parse_peptide_notation("PALE-NH2")
    assert p.nterm == ""
    assert p.core_sequence == "PALE"
