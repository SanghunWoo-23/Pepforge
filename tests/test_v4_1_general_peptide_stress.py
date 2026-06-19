from peptiforg_core.peptide_tokens import parse_peptide_notation, core_sequence, is_cterm_amide
from suite_gui.structure_assist_gui import estimate_properties, clean_sequence, docking_readiness_df, amphipathic_window_df

GENERAL_PEPTIDES = [
    ("EEMQRR-NH2", "EEMQRR", True),
    ("Ac-EEMQRR-NH2", "EEMQRR", True),
    ("KLAKLAKKLAKLAK-NH2", "KLAKLAKKLAKLAK", True),
    ("RGD", "RGD", False),
    ("Ac-KLVFFAE-NH2", "KLVFFAE", True),
    ("FITC-Ahx-RGD-NH2", "RGD", True),
    ("Biotin-PEG4-GGGGS-KRR-NH2", "GGGGSKRR", True),
    ("bAla-EEMQRR-NH2", "AEEMQRR", True),
    ("gAla-EEMQRR-NH2", "GEEMQRR", True),
    ("Sar-EEMQRR-NH2", "GEEMQRR", True),
    ("ACDE-NH2", "ACDE", True),
    ("PALE-NH2", "PALE", True),
]


def test_general_peptide_token_registry_and_structure_stress():
    for seq, expected_core, expected_amide in GENERAL_PEPTIDES:
        parsed = parse_peptide_notation(seq)
        assert parsed.core_sequence == expected_core, (seq, parsed)
        assert core_sequence(seq) == expected_core
        assert is_cterm_amide(seq) is expected_amide
        assert clean_sequence(seq) == expected_core
        props = estimate_properties(seq)
        assert not props.empty
        assert int(props.loc[props.metric == "length", "value"].iloc[0]) == len(expected_core)
        dock = docking_readiness_df(seq)
        assert "docking_readiness_heuristic" in set(dock.metric)
        amph = amphipathic_window_df(seq, window=5)
        assert set(["start", "end", "window_sequence"]).issubset(amph.columns)


def test_no_terminal_or_linker_text_leaks_into_core():
    bad_letters = ["NH2", "CONH2", "PEG4", "AHX", "FITC", "BIOTIN"]
    for seq, _, _ in GENERAL_PEPTIDES:
        core = core_sequence(seq).upper()
        for bad in bad_letters:
            assert bad not in core
