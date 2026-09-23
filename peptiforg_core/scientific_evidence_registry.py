from __future__ import annotations

"""Central scientific-evidence registry for Pepforge V4.0.0.

The registry records where a rule/descriptor came from and, equally important,
what the rule does *not* establish.  It is deliberately metadata-first: no
paper is converted into a probability, confidence score, or experimental claim.
"""

from pathlib import Path
from typing import Any, Iterable
import csv
import json

EVIDENCE_REGISTRY_VERSION = "1.2.0"

_EVIDENCE: list[dict[str, Any]] = [
    {
        "evidence_id": "STRUCT_PEPTIDEBUILDER_2013",
        "feature": "explicit_phi_psi_backbone_seed_generation",
        "evidence_type": "software_method_and_geometry_construction_reference",
        "scope": "canonical_L_linear_search_seed",
        "citation": "Tien MZ, Sydykova DK, Meyer AG, Wilke CO. PeptideBuilder. PeerJ. 2013;1:e80.",
        "pmid": "",
        "doi": "10.7717/peerj.80",
        "claim_guard": "Pepforge implements the explicit phi/psi seed concept internally on its own chemistry graph; the external PeptideBuilder package is not a required dependency and a seed is not a native-state prediction.",
    },
    {
        "evidence_id": "STRUCT_HELIX_CAP_AURORA_ROSE_1998",
        "feature": "helix_cap_position_context",
        "evidence_type": "structural_review",
        "scope": "N_C_terminal_context_for_short_helices",
        "citation": "Aurora R, Rose GD. Helix capping. Protein Sci. 1998;7:21-38.",
        "pmid": "9514257",
        "doi": "",
        "claim_guard": "Terminal context modifies sequence interpretation; it is not a folding probability.",
    },
    {
        "evidence_id": "STRUCT_BETA_CONTEXT_MINOR_KIM_1994",
        "feature": "beta_sheet_context_and_edge_interpretation",
        "evidence_type": "experimental_propensity_context",
        "scope": "context_dependent_beta_sheet_sequence_evidence",
        "citation": "Minor DL Jr, Kim PS. Nature. 1994;371:264-267.",
        "pmid": "",
        "doi": "10.1038/371264a0",
        "claim_guard": "Beta-face and edge descriptors remain contextual sequence evidence until structure is measured or otherwise validated.",
    },
    {
        "evidence_id": "STRUCT_HELIX_PACE_SCHOLTZ_1998",
        "feature": "alpha_helix_propensity",
        "evidence_type": "experimental_scale",
        "scope": "canonical_L_residue_helix_propensity",
        "citation": "Pace CN, Scholtz JM. Biophys J. 1998;75:422-427.",
        "pmid": "9649402",
        "doi": "10.1016/S0006-3495(98)77529-0",
        "claim_guard": "Residue propensity evidence; not a peptide folding probability or structure assignment.",
    },
    {
        "evidence_id": "STRUCT_PPII_BROWN_ZONDLO_2012",
        "feature": "PPII_propensity_and_pro_aromatic_context",
        "evidence_type": "experimental_host_guest_scale",
        "scope": "proline_rich_PPII_context",
        "citation": "Brown AM, Zondlo NJ. Biochemistry. 2012;51:5041-5051.",
        "pmid": "22667692",
        "doi": "10.1021/bi3002924",
        "claim_guard": "Context-dependent propensity evidence; not a universal free-energy scale for every peptide environment.",
    },
    {
        "evidence_id": "STRUCT_DPRO_GLY_HAIRPIN",
        "feature": "DPro_Gly_beta_hairpin_turn_seed",
        "evidence_type": "experimental_structure_design_evidence",
        "scope": "literature_guided_search_seed",
        "citation": "D-Pro-Gly is an established beta-hairpin nucleating motif in designed peptides.",
        "pmid": "12537479;12899617",
        "doi": "10.1021/ja028938a;10.1021/bi034403y",
        "claim_guard": "The motif may seed a search basin; Pepforge still requires post-relaxation measured hairpin geometry.",
    },
    {
        "evidence_id": "STRUCT_AIB_GLY_TURN_2007",
        "feature": "Aib_Gly_type_I_prime_turn_seed",
        "evidence_type": "experimental_NMR_structure_evidence",
        "scope": "literature_guided_search_seed",
        "citation": "Masterson LR et al. Biopolymers. 2007.",
        "pmid": "17427180",
        "doi": "10.1002/bip.20738",
        "claim_guard": "Aib-Gly is handled explicitly; Aib is not silently replaced by Ala.",
    },
    {
        "evidence_id": "STRUCT_COILED_COIL_HEPTAD",
        "feature": "coiled_coil_heptad_compatibility",
        "evidence_type": "review_and_thermodynamic_design_evidence",
        "scope": "a_d_core_and_e_g_edge_descriptors",
        "citation": "Mason JM, Arndt KM. Methods Mol Biol. 2007;352:79-98.",
        "pmid": "17041258",
        "doi": "",
        "claim_guard": "Heptad compatibility does not assign oligomeric state; partner/assembly evidence is required.",
    },
    {
        "evidence_id": "INTERACTION_MANUAL_CUTOFF_GUIDE_2026",
        "feature": "protein_peptide_interaction_manual_screening",
        "evidence_type": "operator_screening_policy",
        "scope": "conservative_PyMOL_manual_profile",
        "citation": "Pepforge R&D Protein/Peptide Interaction Cut-off Guide, 2026-08-27; underlying methods include PLIP, PIC/PICCOLO, MolProbity/Probe.",
        "pmid": "",
        "doi": "",
        "claim_guard": "Screening cutoffs must be reported with the chosen profile; distance alone is insufficient for directional interactions.",
    },
    {
        "evidence_id": "INTERACTION_PLIP_TOOL_PROFILE",
        "feature": "protein_ligand_interaction_tool_compatible_profile",
        "evidence_type": "software_configuration_reference",
        "scope": "wider_PLIP_like_screening_profile",
        "citation": "PLIP documentation/configuration; tool-compatible cutoffs are intentionally distinct from the conservative manual profile.",
        "pmid": "",
        "doi": "",
        "claim_guard": "Tool-compatible thresholds are not automatically interchangeable with a manually curated Methods cutoff.",
    },
    {
        "evidence_id": "VALIDATION_ADVERSARIAL_EVIDENCE_2025",
        "feature": "selection_vs_independent_evidence_separation",
        "evidence_type": "binder_design_validation_strategy",
        "scope": "adversarial_or_orthogonal_review_concept",
        "citation": "EvoBind2, Communications Chemistry (2025).",
        "pmid": "",
        "doi": "10.1038/s42004-025-01601-3",
        "claim_guard": "Pepforge separates selection-driving and challenge evidence; same-backend challenge sampling is not called fully orthogonal validation.",
    },
    {
        "evidence_id": "ENSEMBLE_PEPFLOW_2024",
        "feature": "peptide_conformational_ensemble_review",
        "evidence_type": "peptide_ensemble_method_context",
        "scope": "ensemble_importance_and_sampling_context",
        "citation": "PepFlow, Nature Machine Intelligence (2024).",
        "pmid": "",
        "doi": "10.1038/s42256-024-00860-4",
        "claim_guard": "Pepforge sampling basin occupancy is a generated-sample descriptor, not a thermodynamic population or folding probability.",
    },
    {
        "evidence_id": "INTERFACE_BINDCRAFT_2025",
        "feature": "interface_quality_multi_descriptor_review",
        "evidence_type": "binder_design_interface_filter_context",
        "scope": "separate_interface_geometry_descriptors",
        "citation": "BindCraft, Nature (2025).",
        "pmid": "",
        "doi": "10.1038/s41586-025-09429-6",
        "claim_guard": "Pepforge reports separate interface descriptors and does not invent a Rosetta shape-complementarity or affinity score.",
    },
    {
        "evidence_id": "BETA_EDGE_PAIRING_2025",
        "feature": "exposed_beta_edge_pairing_opportunity",
        "evidence_type": "structure_conditioned_beta_pairing_design_context",
        "scope": "report_only_exposed_beta_edge_opportunity",
        "citation": "Targeting beta-strand pairing with RFdiffusion, Nature Communications (2025).",
        "pmid": "",
        "doi": "10.1038/s41467-025-67866-3",
        "claim_guard": "A beta-edge candidate is a review opportunity, not a binding-site prediction or proof of beta-pair formation.",
    },
    {
        "evidence_id": "SPPS_AGGREGATION_COMPOSITION_2026",
        "feature": "SPPS_aggregation_composition_context",
        "evidence_type": "AFPS_literature_context",
        "scope": "limited_canonical_peptide_AFPS_evidence",
        "citation": "Tamas et al. Amino acid composition drives aggregation during peptide synthesis. Nature Chemistry (2026).",
        "pmid": "",
        "doi": "10.1038/s41557-026-02090-0",
        "claim_guard": "Qualitative literature evidence only; no universal aggregation probability and no automatic pseudoproline substitution.",
    },
    {
        "evidence_id": "PROTONATION_SENSITIVITY_2026",
        "feature": "protonation_sensitive_structure_and_interaction_review",
        "evidence_type": "MD_literature_context",
        "scope": "sequence_level_review_flag",
        "citation": "Protonation-dependent helical-peptide MD study (2026).",
        "pmid": "42267453",
        "doi": "",
        "claim_guard": "Pepforge flags ionizable contexts but does not infer pKa values, microstates, or pH-dependent folded fractions.",
    },
]


def registry() -> list[dict[str, Any]]:
    return [dict(row) for row in _EVIDENCE]


def evidence_for_feature(feature: str) -> list[dict[str, Any]]:
    key = str(feature or "").strip().lower()
    return [row for row in registry() if key in str(row.get("feature", "")).lower() or key == str(row.get("evidence_id", "")).lower()]


def get_evidence(evidence_id: str) -> dict[str, Any] | None:
    key = str(evidence_id or "").strip()
    return next((row for row in registry() if row["evidence_id"] == key), None)


def export_registry(output_dir: str | Path) -> dict[str, str]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows = registry()
    json_path = out / "scientific_evidence_registry.json"
    csv_path = out / "scientific_evidence_registry.csv"
    json_path.write_text(json.dumps({"version": EVIDENCE_REGISTRY_VERSION, "records": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    return {"registry_json": str(json_path), "registry_csv": str(csv_path)}


__all__ = ["EVIDENCE_REGISTRY_VERSION", "registry", "evidence_for_feature", "get_evidence", "export_registry"]
