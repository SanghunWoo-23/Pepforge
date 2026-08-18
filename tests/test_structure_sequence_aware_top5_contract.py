from peptiforg_core.peptide_conformation import (
    select_top_conformers,
    sequence_conformation_evidence,
)


def _tokens(sequence):
    return [{"raw": aa, "kind": "std_aa"} for aa in sequence]


def test_sequence_evidence_detects_helix_charge_spacing_without_probability_claim():
    evidence = sequence_conformation_evidence(_tokens("EEMQRR"))
    assert evidence["canonical_L_sequence"] == "EEMQRR"
    assert evidence["canonical_L_coverage_fraction"] == 1.0
    assert evidence["opposite_charge_i3_i4_pairs"]
    assert "probabilities" in evidence["claim_guard"]


def test_noncanonical_sequence_is_geometry_only_not_canonicalized():
    evidence = sequence_conformation_evidence([
        {"raw": "FITC", "kind": "label"},
        {"raw": "Cha", "kind": "non_natural_aa"},
        {"raw": "AEEA", "kind": "linker"},
        {"raw": "dK", "kind": "d_std_aa"},
    ])
    assert evidence["canonical_L_sequence"] == ""
    assert evidence["modified_or_noncanonical_count"] == 3
    assert set(evidence["family_support"].values()) == {"geometry_only"}


def test_top_five_prefers_family_diversity_and_is_capped():
    rows = [
        {"conf_id": 1, "family": "alpha_helix_like", "energy": 4.0},
        {"conf_id": 2, "family": "alpha_helix_like", "energy": 2.0},
        {"conf_id": 3, "family": "turn_rich", "energy": 3.0},
        {"conf_id": 4, "family": "coil_mixed", "energy": 1.0},
        {"conf_id": 5, "family": "PPII_like", "energy": 5.0},
        {"conf_id": 6, "family": "beta_extended_like", "energy": 6.0},
        {"conf_id": 7, "family": "coil_mixed", "energy": 0.5},
    ]
    evidence = sequence_conformation_evidence(_tokens("EEMQRR"))
    selected = select_top_conformers({"conformers": rows}, evidence, limit=5)
    assert len(selected) == 5
    assert [row["rank"] for row in selected] == [1, 2, 3, 4, 5]
    assert len({row["family"] for row in selected}) == 5
    assert next(row for row in selected if row["family"] == "alpha_helix_like")["conf_id"] == 2
    assert next(row for row in selected if row["family"] == "coil_mixed")["conf_id"] == 7


def test_beta_hairpin_context_requires_turn_and_flanking_strand_features():
    evidence = sequence_conformation_evidence(_tokens("VIGPGTFY"))
    assert evidence["beta_hairpin_context_windows"]
    assert evidence["family_support"]["beta_hairpin_like"] == "retain"
