from peptiforg_core.peptide_conformation import (
    literature_sequence_screen,
    select_top_conformers,
    sequence_conformation_evidence,
)


def aa(sequence):
    return [{"raw": residue, "kind": "std_aa"} for residue in sequence]


def test_amphipathic_heptad_and_beta_descriptors_are_not_probabilities():
    helix = literature_sequence_screen(aa("LEKKALELEKKALE"))
    assert helix["amphipathic_alpha_helix"]["whole_sequence_muH"] is not None
    assert helix["coiled_coil_heptad_compatibility"]["registers_evaluated"] == 7
    beta = literature_sequence_screen(aa("VKVKVK"))
    assert beta["beta_strand_alternation"]["maximal_windows"]
    assert "probabilities" in helix["claim_guard"]


def test_synthesis_aggregation_and_chemical_liability_screens_are_separate():
    screen = literature_sequence_screen(aa("QDGVIITFWYNNQHHCCC"))
    assert screen["spps_difficult_sequence_screen"]["beta_branched_VIT_runs_3plus"]
    assert screen["spps_difficult_sequence_screen"]["aspartimide_contexts"]
    assert screen["aggregation_screen"]["aromatic_runs_3plus"]
    assert screen["chemical_liability_screen"]["n_terminal_glutamine_pyroglutamate_candidate"]
    assert screen["chemical_liability_screen"]["histidine_clusters_2plus"]
    assert screen["cysteine_topology"]["odd_count_warning"]


def test_d_pro_gly_is_reported_without_canonicalizing_d_residue():
    evidence = sequence_conformation_evidence([
        {"raw": "V", "kind": "std_aa"},
        {"raw": "dP", "kind": "d_std_aa"},
        {"raw": "G", "kind": "std_aa"},
        {"raw": "W", "kind": "std_aa"},
    ])
    motif = evidence["literature_sequence_screen"]["turn_and_hairpin_motifs"]
    assert motif["d_pro_gly_candidates"]
    assert evidence["canonical_L_sequence"] == ""
    assert set(evidence["family_support"].values()) == {"geometry_only"}


def test_alpha_beta_gamma_special_case_preserves_parameter_guard():
    screen = literature_sequence_screen([
        {"raw": "A", "kind": "std_aa"},
        {"raw": "gAla", "kind": "linker"},
        {"raw": "A", "kind": "std_aa"},
        {"raw": "A", "kind": "std_aa"},
        {"raw": "bAla", "kind": "linker"},
        {"raw": "A", "kind": "std_aa"},
    ])
    foldamer = screen["alpha_beta_gamma_peptidomimetic"]
    assert foldamer["detected_pattern"] == "αγααβα"
    assert foldamer["ag_a_a_b_a_hexad_repeat_compatibility"]
    assert "not transferred" in foldamer["parameter_guard"]
    assert "cannot be inferred" in foldamer["BH3_design_context"]


def test_top_five_has_explicit_non_physiological_roles():
    rows = [
        {"conf_id": i, "family": family, "energy": float(i)}
        for i, family in enumerate((
            "alpha_helix_like", "turn_rich", "coil_mixed",
            "beta_extended_like", "PPII_like",
        ), 1)
    ]
    selected = select_top_conformers({"conformers": rows}, sequence_conformation_evidence(aa("LEKKALE")))
    assert len(selected) == 5
    assert all(row.get("candidate_role") for row in selected)
    assert all("not a physiological population" in row["role_claim_guard"] for row in selected)
