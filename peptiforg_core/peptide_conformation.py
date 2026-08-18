from __future__ import annotations

"""Evidence-aware peptide conformational analysis for Pepforge.

This module does not claim to predict one native structure. It interprets an
RDKit conformer ensemble using backbone torsions and simple backbone H-bond
geometry, and reports conformational families that can be used as starting
structures for external validation.

Evidence policy
---------------
* The intrinsic alpha-helix scale for canonical L residues is the Pace & Scholtz
  1998 experimental consensus scale (Biophys J. 75:422-427; PMID 9649402).
* D residues, non-natural residues, linkers and chemical modifiers are never
  assigned invented numerical helix propensities. They reduce evidence coverage
  and are reported separately.
* Alpha/3_10/beta/PPII/turn/coil labels below are geometry classifications of
  generated conformers, not experimental populations or free energies.
"""

from dataclasses import asdict, is_dataclass
from math import cos, isnan, log2, radians, sin, sqrt
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    from rdkit import Chem
    from rdkit.Chem import rdMolTransforms, rdMolAlign
except Exception:  # pragma: no cover
    Chem = None
    rdMolTransforms = None
    rdMolAlign = None

# Experimental consensus relative free-energy scale, kcal/mol, Ala = 0.
# Pace CN, Scholtz JM. Biophys J. 1998;75:422-427. PMID: 9649402.
PACE_SCHOLTZ_HELIX_DDG_KCAL_MOL: Dict[str, float] = {
    "A": 0.00, "L": 0.21, "R": 0.21, "M": 0.24, "K": 0.26,
    "Q": 0.39, "E": 0.40, "I": 0.41, "W": 0.49, "S": 0.50,
    "Y": 0.53, "F": 0.54, "V": 0.61, "H": 0.61, "N": 0.65,
    "T": 0.66, "C": 0.68, "D": 0.69, "G": 1.00,
}

EVIDENCE_REFERENCES = [
    {
        "topic": "classical_alpha_beta_turn_residue_propensity",
        "citation": "Chou PY, Fasman GD. Biochemistry. 1974.",
        "doi": "10.1021/bi00699a001",
    },
    {
        "topic": "canonical_L_alpha_helix_propensity",
        "citation": "Pace CN, Scholtz JM. Biophys J. 1998;75:422-427.",
        "pmid": "9649402",
        "doi": "10.1016/S0006-3495(98)77529-0",
    },
    {
        "topic": "fragment_based_peptide_ensemble_generation",
        "citation": "Maupetit J, Derreumaux P, Tuffery P. Nucleic Acids Res. 2009;37:W498-W503.",
        "pmid": "19433514",
        "doi": "10.1093/nar/gkp323",
    },
    {
        "topic": "beta_hairpin_turn_and_strand_contributions",
        "citation": "Griffiths-Jones SR, Maynard AJ, Searle MS. J Mol Biol. 1999;292:1051-1069.",
        "pmid": "10512702",
        "doi": "10.1006/jmbi.1999.3119",
    },
    {
        "topic": "residue_specific_backbone_phi_psi_preferences",
        "citation": "Jiang F, Han W, Wu YD. J Phys Chem B. 2010;114:5840-5850.",
        "pmid": "20392111",
        "doi": "10.1021/jp909088e",
    },
    {
        "topic": "helix_coil_sequence_context",
        "citation": "Munoz V, Serrano L. Biopolymers. 1997;41:495-509.",
        "pmid": "9095674",
        "doi": "10.1002/(SICI)1097-0282(19970415)41:5<495::AID-BIP2>3.0.CO;2-H",
    },
    {
        "topic": "glu_lys_i3_i4_helix_salt_bridges",
        "citation": "Marqusee S, Baldwin RL. Proc Natl Acad Sci USA. 1987;84:8898-8902.",
        "doi": "10.1073/pnas.84.24.8898",
    },
    {
        "topic": "beta_turn_positional_preferences",
        "citation": "Hutchinson EG, Thornton JM. Protein Sci. 1994;3:2207-2216.",
        "pmid": "7756980",
        "doi": "10.1002/pro.5560031206",
    },
    {
        "topic": "polyproline_II_host_guest_propensity",
        "citation": "Shi Z et al. Proc Natl Acad Sci USA. 2005;102:17964-17968.",
        "pmid": "16330763",
        "doi": "10.1073/pnas.0507123102",
    },
    {
        "topic": "amphipathic_helix_hydrophobic_moment",
        "citation": "Eisenberg D, Weiss RM, Terwilliger TC. Nature. 1982;299:371-374.",
        "doi": "10.1038/299371a0",
    },
    {
        "topic": "amphipathic_helix_hydrophobicity_moment_and_membrane_activity",
        "citation": "Dathe M et al. FEBS Lett. 1997.",
        "doi": "10.1016/S0014-5793(97)00055-0",
    },
    {
        "topic": "coiled_coil_heptad_sequence_pattern",
        "citation": "Lupas A, Van Dyke M, Stock J. Science. 1991;252:1162-1164.",
        "pmid": "2031185",
        "doi": "10.1126/science.252.5009.1162",
    },
    {
        "topic": "sequence_determinants_of_aggregation",
        "citation": "Chiti F et al. Nature. 2003;424:805-808.",
        "pmid": "12917692",
        "doi": "10.1038/nature01891",
    },
    {
        "topic": "tryptophan_zipper_beta_hairpins",
        "citation": "Cochran AG, Skelton NJ, Starovasnik MA. Proc Natl Acad Sci USA. 2001.",
        "doi": "10.1073/pnas.091100898",
    },
    {
        "topic": "turn_residue_control_of_beta_sheet_register",
        "citation": "Effects of Turn Residues in Directing the Formation and Stability of the Beta-Sheet. Protein Sci. 2001.",
        "doi": "10.1110/ps.49001",
    },
    {
        "topic": "proline_glycine_rich_PPII_extended_structure",
        "citation": "Yarawsky AE et al. J Mol Biol. 2017.",
        "doi": "10.1016/j.jmb.2016.11.017",
    },
    {
        "topic": "alpha_beta_gamma_peptide_backbone_pattern_and_helicity",
        "citation": "Shin YH, Gellman SH. J Am Chem Soc. 2018;140:1394-1400.",
        "pmid": "29350033",
        "doi": "10.1021/jacs.7b10868",
    },
    {
        "topic": "BH3_alpha_beta_gamma_helical_peptidomimetics",
        "citation": "Shin YH, Yang H. Chem Commun. 2022;58:945-948.",
        "pmid": "34985060",
        "doi": "10.1039/D1CC05758H",
    },
]

PEPTIDE_KINDS = {"std_aa", "d_std_aa", "non_natural_aa", "sidechain_label_aa"}

# Eisenberg consensus hydrophobicity values.  They are used only for the
# dimensionless hydrophobic-moment descriptor; no activity threshold is made.
EISENBERG_HYDROPHOBICITY: Dict[str, float] = {
    "A": 0.25, "C": 0.04, "D": -0.72, "E": -0.62, "F": 0.61,
    "G": 0.16, "H": -0.40, "I": 0.73, "K": -1.10, "L": 0.53,
    "M": 0.26, "N": -0.64, "P": -0.07, "Q": -0.69, "R": -1.76,
    "S": -0.26, "T": -0.18, "V": 0.54, "W": 0.37, "Y": 0.02,
}
HYDROPHOBIC = set("AVILMFWY")
POLAR_OR_CHARGED = set("STNQDEKRH")


def _runs(sequence: str, accepted: set, minimum: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    start = None
    for i, aa in enumerate(sequence + "!"):
        if aa in accepted and start is None:
            start = i
        elif aa not in accepted and start is not None:
            if i - start >= minimum:
                out.append({"positions": [start + 1, i], "sequence": sequence[start:i]})
            start = None
    return out


def _motifs(sequence: str, patterns: Iterable[str]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for pattern in patterns:
        start = 0
        while True:
            pos = sequence.find(pattern, start)
            if pos < 0:
                break
            out.append({"motif": pattern, "positions": [pos + 1, pos + len(pattern)]})
            start = pos + 1
    return sorted(out, key=lambda row: (row["positions"][0], row["motif"]))


def _hydrophobic_moment(sequence: str, angle_deg: float = 100.0) -> Optional[float]:
    if not sequence or any(aa not in EISENBERG_HYDROPHOBICITY for aa in sequence):
        return None
    x = sum(EISENBERG_HYDROPHOBICITY[aa] * cos(radians(i * angle_deg)) for i, aa in enumerate(sequence))
    y = sum(EISENBERG_HYDROPHOBICITY[aa] * sin(radians(i * angle_deg)) for i, aa in enumerate(sequence))
    return sqrt(x * x + y * y) / len(sequence)


def literature_sequence_screen(rows: Iterable[Any]) -> Dict[str, Any]:
    """Deterministic sequence descriptors; never a structure/activity predictor."""
    tokens = [_row(row) for row in rows]
    peptide = [r for r in tokens if str(r.get("kind", "")) in PEPTIDE_KINDS | {"linker"}]
    architecture = []
    for index, row in enumerate(peptide, 1):
        raw = str(row.get("raw", ""))
        lowered = raw.lower().replace("-", "").replace("_", "")
        if lowered in {"bala", "betaala", "βala"} or lowered.startswith(("beta2", "beta3", "β2", "β3")):
            backbone = "beta"
        elif lowered in {"gala", "gaba", "gammaala", "γala"} or lowered.startswith(("gamma", "γ")):
            backbone = "gamma"
        elif str(row.get("kind", "")) in {"std_aa", "d_std_aa", "sidechain_label_aa", "non_natural_aa"}:
            backbone = "alpha_or_unspecified"
        else:
            backbone = "linker_or_unspecified"
        architecture.append({"position": index, "token": raw, "backbone_class": backbone})
    compact_pattern = "".join({"alpha_or_unspecified": "α", "beta": "β", "gamma": "γ"}.get(r["backbone_class"], "?") for r in architecture)
    mixed_backbone = any(r["backbone_class"] in {"beta", "gamma"} for r in architecture)
    full_l = bool(peptide) and all(str(r.get("kind", "")) == "std_aa" for r in peptide)
    sequence = "".join(str(r.get("raw", "")) for r in peptide) if full_l else ""
    n = len(sequence)

    moment_windows: List[Dict[str, Any]] = []
    if n:
        width = min(11, n)
        if width >= 5:
            for i in range(n - width + 1):
                value = _hydrophobic_moment(sequence[i:i + width])
                moment_windows.append({"positions": [i + 1, i + width], "sequence": sequence[i:i + width], "muH": round(float(value), 4)})
    moment_windows.sort(key=lambda row: (-row["muH"], row["positions"][0]))

    heptads: List[Dict[str, Any]] = []
    if n >= 14:
        letters = "abcdefg"
        for offset in range(7):
            core = edge = 0
            assignments = []
            for i, aa in enumerate(sequence):
                register = letters[(i + offset) % 7]
                if register in "ad" and aa in HYDROPHOBIC:
                    core += 1
                if register in "eg" and aa in set("DEKR"):
                    edge += 1
                assignments.append(register)
            heptads.append({"offset": offset, "registers": "".join(assignments), "hydrophobic_at_a_d": core, "charged_at_e_g": edge})
        heptads.sort(key=lambda row: (-row["hydrophobic_at_a_d"], -row["charged_at_e_g"], row["offset"]))

    alternating: List[Dict[str, Any]] = []
    for width in range(6, n + 1):
        for i in range(n - width + 1):
            fragment = sequence[i:i + width]
            classes = ["H" if aa in HYDROPHOBIC else "P" if aa in POLAR_OR_CHARGED else "X" for aa in fragment]
            if "X" not in classes and all(classes[j] != classes[j - 1] for j in range(1, len(classes))):
                alternating.append({"positions": [i + 1, i + width], "sequence": fragment, "pattern": "".join(classes)})
    # Retain maximal non-duplicate starts to keep exports readable.
    alternating = sorted(alternating, key=lambda row: (row["positions"][0], -len(row["sequence"])))
    maximal_alt = []
    seen_starts = set()
    for row in alternating:
        if row["positions"][0] not in seen_starts:
            maximal_alt.append(row); seen_starts.add(row["positions"][0])

    counts = {aa: sequence.count(aa) for aa in set(sequence)} if sequence else {}
    entropy = -sum((count / n) * log2(count / n) for count in counts.values()) if n else None
    cys_n = sequence.count("C")
    first_3, last_3 = sequence[:3], sequence[-3:]
    return {
        "status": "ok" if full_l else "limited_by_modified_or_noncanonical_tokens",
        "claim_guard": "descriptors and screening flags are not native-state, activity, aggregation-rate, or synthesis-success probabilities",
        "alpha_beta_gamma_peptidomimetic": {
            "detected_pattern": compact_pattern,
            "per_position": architecture,
            "mixed_beta_gamma_backbone_detected": mixed_backbone,
            "ag_a_a_b_a_hexad_repeat_compatibility": bool(compact_pattern and compact_pattern.replace("?", "").startswith("αγααβα")),
            "BH3_design_context": "supported as an explicit design annotation only; BH3 mimicry or Bcl-2-family binding cannot be inferred from backbone pattern alone",
            "parameter_guard": "Pace-Scholtz alpha-residue values and canonical alpha-helix seed torsions are not transferred to beta/gamma residues",
            "evidence": ["PMID:29350033", "PMID:34985060"],
        },
        "amphipathic_alpha_helix": {
            "method": "Eisenberg hydrophobic moment at 100 degrees/residue (approximately 3.6 residues/turn)",
            "whole_sequence_muH": round(float(_hydrophobic_moment(sequence)), 4) if sequence else None,
            "highest_11_or_shorter_residue_window": moment_windows[0] if moment_windows else None,
            "same_face_i3_i4_note": "i/i+3 and i/i+4 relationships are reported separately; muH is a descriptor without a universal activity cutoff",
        },
        "coiled_coil_heptad_compatibility": {
            "best_register": heptads[0] if heptads else None,
            "registers_evaluated": len(heptads),
            "interpretation": "a/d hydrophobic and e/g charged counts are compatibility descriptors, not a coiled-coil assignment",
        },
        "beta_strand_alternation": {"maximal_windows": maximal_alt, "interpretation": "alternation is sequence evidence only; folding requires structural validation"},
        "turn_and_hairpin_motifs": {
            "canonical_motifs": _motifs(sequence, ("PG", "DG", "NG", "SG")),
            "d_pro_gly_candidates": [],
            "tryptophan_count": sequence.count("W"),
            "trp_zipper_sequence_candidate": bool(sequence.count("W") >= 4 and _motifs(sequence, ("PG", "DG", "NG", "SG"))),
            "trp_zipper_note": "Trp count alone cannot establish cross-strand Trp-zipper geometry",
        },
        "beta_edge_negative_design": {
            "n_terminal_edge_breaker_or_charge": [aa for aa in sequence[:2] if aa in set("PDEKR")],
            "c_terminal_edge_breaker_or_charge": [aa for aa in sequence[-2:] if aa in set("PDEKR")],
            "interpretation": "terminal Pro/charge is an edge-capping descriptor only; actual beta-sheet edge exposure requires structure",
        },
        "aggregation_screen": {
            "hydrophobic_runs_4plus": _runs(sequence, HYDROPHOBIC, 4),
            "aromatic_runs_3plus": _runs(sequence, set("FWY"), 3),
            "NQ_runs_3plus": _runs(sequence, set("NQ"), 3),
            "sidechain_charge_balance_KR_minus_DE": sum(sequence.count(aa) for aa in "KR") - sum(sequence.count(aa) for aa in "DE") if sequence else None,
            "sequence_shannon_entropy_bits": round(entropy, 4) if entropy is not None else None,
            "maximum_single_residue_fraction": round(max(counts.values()) / n, 4) if n else None,
        },
        "spps_difficult_sequence_screen": {
            "beta_branched_VIT_runs_3plus": _runs(sequence, set("VIT"), 3),
            "aspartimide_contexts": _motifs(sequence, ("DG", "DN", "DS")),
            "ser_thr_count": sum(sequence.count(aa) for aa in "ST"),
        },
        "chemical_liability_screen": {
            "n_terminal_glutamine_pyroglutamate_candidate": bool(sequence.startswith("Q")),
            "asparagine_positions": [i + 1 for i, aa in enumerate(sequence) if aa == "N"],
            "histidine_clusters_2plus": _runs(sequence, {"H"}, 2),
            "histidine_note": "protonation and metal coordination depend on pH, partners, and conditions",
        },
        "cysteine_topology": {
            "cysteine_count": cys_n if sequence else None,
            "odd_count_warning": bool(cys_n % 2) if sequence else False,
            "multiple_pairing_ambiguity_warning": bool(cys_n >= 4),
            "claim_guard": "sequence count cannot determine disulfide connectivity",
        },
        "helix_dipole_context": {
            "acidic_in_n_terminal_3": sum(first_3.count(aa) for aa in "DE"),
            "basic_in_c_terminal_3": sum(last_3.count(aa) for aa in "KR"),
            "interpretation": "terminal charge placement is contextual evidence, not proof of helix stabilization",
        },
    }


def _row(obj: Any) -> Dict[str, Any]:
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, dict):
        return dict(obj)
    return {k: getattr(obj, k) for k in dir(obj) if not k.startswith("_")}


def canonical_l_helix_evidence(tokens: Iterable[Any]) -> Dict[str, Any]:
    """Summarize only directly supported canonical-L helix propensity evidence.

    Lower mean delta-delta-G is more helix-favorable *within this experimental
    scale*. It is not converted into a helix probability.
    """
    used: List[Dict[str, Any]] = []
    unsupported: List[Dict[str, Any]] = []
    peptide_n = 0
    for token in tokens:
        t = _row(token)
        kind = str(t.get("kind", ""))
        raw = str(t.get("raw", ""))
        if kind not in PEPTIDE_KINDS:
            continue
        peptide_n += 1
        if kind == "std_aa" and raw in PACE_SCHOLTZ_HELIX_DDG_KCAL_MOL:
            used.append({"token": raw, "ddg_kcal_mol": PACE_SCHOLTZ_HELIX_DDG_KCAL_MOL[raw]})
        else:
            unsupported.append({"token": raw, "kind": kind, "reason": "no Pace-Scholtz canonical-L value assigned"})
    mean_ddg = (sum(x["ddg_kcal_mol"] for x in used) / len(used)) if used else None
    return {
        "scale": "Pace-Scholtz 1998 canonical L-residue helix propensity",
        "interpretation": "lower mean delta-delta-G is more intrinsically alpha-helix-favorable; not a population estimate",
        "mean_ddg_kcal_mol": mean_ddg,
        "supported_residues": len(used),
        "peptide_like_residues": peptide_n,
        "evidence_coverage_fraction": (len(used) / peptide_n) if peptide_n else 0.0,
        "per_residue": used,
        "unsupported_or_noncanonical": unsupported,
        "reference_pmid": "9649402",
    }


def sequence_conformation_evidence(tokens: Iterable[Any]) -> Dict[str, Any]:
    """Return transparent, qualitative sequence evidence for ensemble ranking.

    This is deliberately not a secondary-structure predictor and does not emit
    probabilities.  It identifies literature-supported sequence features that
    make generated backbone families worth retaining.  Non-canonical chemistry
    lowers coverage instead of being silently replaced by canonical residues.
    """
    rows = [_row(token) for token in tokens]
    # Linkers interrupt the canonical peptide backbone evidence even when they
    # are not treated as amino-acid residues by the torsion classifier.
    sequence_kinds = PEPTIDE_KINDS | {"linker"}
    peptide = [r for r in rows if str(r.get("kind", "")) in sequence_kinds]
    canonical = [str(r.get("raw", "")) for r in peptide if str(r.get("kind", "")) == "std_aa"]
    full_canonical = len(canonical) == len(peptide) and bool(peptide)
    sequence = "".join(canonical) if full_canonical else ""
    n = len(peptide)

    opposite_pairs: List[Dict[str, Any]] = []
    like_charge_pairs: List[Dict[str, Any]] = []
    if full_canonical:
        positive, negative = set("KR"), set("DE")
        for i, aa in enumerate(sequence):
            for spacing in (3, 4):
                j = i + spacing
                if j >= len(sequence):
                    continue
                bb = sequence[j]
                item = {"positions": [i + 1, j + 1], "residues": aa + bb, "spacing": f"i,i+{spacing}"}
                if (aa in positive and bb in negative) or (aa in negative and bb in positive):
                    opposite_pairs.append(item)
                elif (aa in positive and bb in positive) or (aa in negative and bb in negative):
                    like_charge_pairs.append(item)

    helix = canonical_l_helix_evidence(rows)
    breakers = []
    if full_canonical:
        breakers = [{"position": i + 1, "residue": aa} for i, aa in enumerate(sequence) if aa in "PG"]

    # Beta-hairpin evidence is contextual: a turn-compatible central window
    # plus strand-compatible flanks.  These residue sets are qualitative and
    # are never exposed as experimental probabilities or free energies.
    turn_windows: List[Dict[str, Any]] = []
    strand_set = set("VIFYWTL")
    turn_set = set("GPNDST")
    if full_canonical and n >= 7:
        for start in range(1, n - 4):
            center = sequence[start:start + 4]
            left = sequence[:start]
            right = sequence[start + 4:]
            turn_count = sum(aa in turn_set for aa in center)
            flank_count = sum(aa in strand_set for aa in left[-3:] + right[:3])
            if turn_count >= 2 and flank_count >= 2 and left and right:
                turn_windows.append({
                    "positions": [start + 1, start + 4],
                    "sequence": center,
                    "turn_compatible_residues": turn_count,
                    "strand_compatible_flank_residues": flank_count,
                })

    pro_positions = [i + 1 for i, aa in enumerate(sequence) if aa == "P"] if full_canonical else []
    family_support: Dict[str, str] = {
        "coil_mixed": "retain",
        "turn_rich": "retain" if turn_windows or n <= 8 else "contextual",
        "PPII_like": "retain" if pro_positions else "contextual",
        "PPII_seed_candidate": "retain" if pro_positions else "contextual",
        "beta_hairpin_like": "retain" if turn_windows else "contextual",
        "beta_extended_like": "contextual",
        "beta_extended_seed_candidate": "contextual",
        "3_10_helix_like": "retain" if n >= 4 and not breakers else "contextual",
        "3_10_helix_seed_candidate": "retain" if n >= 4 and not breakers else "contextual",
        "alpha_helix_like": "retain" if n >= 5 and not breakers and helix.get("evidence_coverage_fraction") == 1.0 else "contextual",
        "alpha_helix_seed_candidate": "retain" if n >= 5 and not breakers and helix.get("evidence_coverage_fraction") == 1.0 else "contextual",
        "helical_backbone_like": "retain" if n >= 5 and not breakers else "contextual",
    }
    literature = literature_sequence_screen(rows)
    # D-Pro is outside the canonical-L metrics, but an explicit dP-G pair can
    # still be reported as a motif candidate without assigning a propensity.
    peptide_raw = [str(r.get("raw", "")) for r in peptide]
    dpg = [
        {"positions": [i + 1, i + 2], "tokens": [peptide_raw[i], peptide_raw[i + 1]]}
        for i in range(max(0, len(peptide_raw) - 1))
        if peptide_raw[i].lower() == "dp" and peptide_raw[i + 1] == "G"
    ]
    literature["turn_and_hairpin_motifs"]["d_pro_gly_candidates"] = dpg

    if not full_canonical:
        family_support = {family: "geometry_only" for family in family_support}

    return {
        "status": "ok" if peptide else "unavailable",
        "method": "qualitative literature-evidence screen used to retain diverse generated conformer families",
        "claim_guard": "family support labels are ranking evidence, not physiological-state probabilities or experimental secondary-structure assignments",
        "peptide_residue_count": n,
        "canonical_L_sequence": sequence,
        "canonical_L_coverage_fraction": (len(canonical) / n) if n else 0.0,
        "modified_or_noncanonical_count": n - len(canonical),
        "helix_propensity_evidence": helix,
        "helix_breaker_positions": breakers,
        "opposite_charge_i3_i4_pairs": opposite_pairs,
        "like_charge_i3_i4_pairs": like_charge_pairs,
        "beta_hairpin_context_windows": turn_windows,
        "proline_positions_for_PPII_context": pro_positions,
        "literature_sequence_screen": literature,
        "family_support": family_support,
    }


def evidence_guided_family_plan(
    sequence_evidence: Dict[str, Any],
    profile: str = "evidence_fast",
) -> Dict[str, Any]:
    """Return an auditable family-search order for a PSB build preset.

    The plan changes search/selection priority; it is not a probability model.
    Only evidence already exposed by :func:`sequence_conformation_evidence` is
    used, so modified residues never inherit an invented canonical propensity.
    """
    evidence = dict(sequence_evidence or {})
    support = dict(evidence.get("family_support") or {})
    profile_name = str(profile or "evidence_fast")
    profile_budgets = {
        "evidence_fast": {"etkdg_multiplier": 1, "embedding_retries": 2, "rmsd_threshold_A": 0.75},
        "evidence_balanced": {"etkdg_multiplier": 2, "embedding_retries": 3, "rmsd_threshold_A": 1.00},
        "evidence_thorough": {"etkdg_multiplier": 3, "embedding_retries": 4, "rmsd_threshold_A": 1.25},
    }
    budget = dict(profile_budgets.get(profile_name, profile_budgets["evidence_fast"]))
    reasons: Dict[str, List[str]] = {}

    def note(family: str, reason: str) -> None:
        reasons.setdefault(family, []).append(reason)

    if evidence.get("helix_breaker_positions"):
        note("turn_rich", "Pro/Gly helix-breaker context")
        note("PPII_like", "Pro/Gly context keeps extended alternatives visible")
    elif float((evidence.get("helix_propensity_evidence") or {}).get("evidence_coverage_fraction") or 0.0) == 1.0:
        note("alpha_helix_like", "complete canonical-L helix-propensity coverage")
        note("3_10_helix_like", "short right-handed helical alternative")
    if evidence.get("beta_hairpin_context_windows"):
        note("beta_hairpin_like", "turn-compatible center with strand-compatible flanks")
    if evidence.get("proline_positions_for_PPII_context"):
        note("PPII_like", "sequence contains Pro in a PPII-relevant context")
    literature = dict(evidence.get("literature_sequence_screen") or {})
    if (literature.get("beta_strand_alternation") or {}).get("maximal_windows"):
        note("beta_extended_like", "alternating hydrophobic/polar beta-strand descriptor")
    if (literature.get("amphipathic_alpha_helix") or {}).get("highest_11_or_shorter_residue_window"):
        note("alpha_helix_like", "amphipathic-helix hydrophobic-moment window evaluated")
    note("coil_mixed", "unstructured/mixed reference family retained for comparison")

    family_evidence = {
        "alpha_helix_like": ["PMID:9649402", "DOI:10.1073/pnas.84.24.8898", "DOI:10.1038/299371a0"],
        "3_10_helix_like": ["PMID:20392111"],
        "beta_hairpin_like": ["PMID:10512702", "DOI:10.1073/pnas.091100898", "DOI:10.1110/ps.49001"],
        "beta_extended_like": ["DOI:10.1021/bi00699a001", "DOI:10.1038/nature01891"],
        "PPII_like": ["PMID:16330763", "DOI:10.1016/j.jmb.2016.11.017"],
        "turn_rich": ["PMID:7756980", "DOI:10.1110/ps.49001"],
        "coil_mixed": ["PMID:19433514"],
        "alpha_beta_gamma_peptidomimetic": ["PMID:29350033", "PMID:34985060"],
    }

    canonical_order = [
        "alpha_helix_seed_candidate", "alpha_helix_like",
        "3_10_helix_seed_candidate", "3_10_helix_like",
        "beta_hairpin_like", "beta_extended_seed_candidate", "beta_extended_like",
        "PPII_seed_candidate", "PPII_like", "turn_rich", "coil_mixed",
    ]
    priority = sorted(
        canonical_order,
        key=lambda family: (
            {"retain": 0, "contextual": 1, "geometry_only": 2}.get(str(support.get(family)), 3),
            0 if family in reasons else 1,
            canonical_order.index(family),
        ),
    )
    return {
        "profile": profile_name,
        "family_priority": priority,
        "family_reasons": reasons,
        "family_evidence": family_evidence,
        "budget": budget,
        "claim_guard": "Search priority is literature-guided ordinal evidence, not an in-vivo population or native-structure probability.",
    }


def select_top_conformers(
    conformation_analysis: Dict[str, Any],
    sequence_evidence: Dict[str, Any],
    limit: int = 5,
    pairwise_rmsd: Optional[Dict[Tuple[int, int], float]] = None,
    minimum_rmsd_A: float = 1.0,
    family_priority: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Select up to ``limit`` diverse representatives using ordinal evidence.

    Selection order is: sequence-supported family representatives, contextual
    family representatives, then remaining low-energy conformers.  Energy is
    used only within the same molecule and never converted to a population.
    """
    rows = [dict(r) for r in (conformation_analysis or {}).get("conformers", [])]
    support = dict((sequence_evidence or {}).get("family_support", {}))
    priority = {"retain": 0, "contextual": 1, "geometry_only": 2}

    def energy_key(row: Dict[str, Any]) -> Tuple[int, float, int]:
        value = row.get("energy")
        valid = isinstance(value, (int, float)) and not isnan(float(value))
        return (0 if valid else 1, float(value) if valid else float("inf"), int(row.get("conf_id", 0)))

    families: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        families.setdefault(str(row.get("family", "coil_mixed")), []).append(row)
    representatives = []
    for family, candidates in families.items():
        rep = min(candidates, key=energy_key)
        rep["sequence_support"] = support.get(family, "contextual")
        representatives.append(rep)
    family_order = {family: index for index, family in enumerate(family_priority or [])}
    representatives.sort(key=lambda r: (
        priority.get(str(r.get("sequence_support")), 3),
        family_order.get(str(r.get("family", "")), len(family_order)),
    ) + energy_key(r))

    selected: List[Dict[str, Any]] = []
    used = set()
    def is_distinct(row: Dict[str, Any]) -> bool:
        if not selected or not pairwise_rmsd:
            return True
        cid = int(row.get("conf_id", -1))
        distances = [pairwise_rmsd.get(tuple(sorted((cid, int(old.get("conf_id", -1)))))) for old in selected]
        known = [float(value) for value in distances if isinstance(value, (int, float))]
        return not known or min(known) >= float(minimum_rmsd_A)

    for row in representatives:
        if len(selected) >= max(1, int(limit)):
            break
        if not is_distinct(row):
            continue
        row = dict(row)
        row["selection_reason"] = "lowest force-field energy representative of this conformational family passing the RMSD diversity threshold"
        selected.append(row); used.add(int(row.get("conf_id", -1)))
    if len(selected) < max(1, int(limit)):
        for row in sorted(rows, key=energy_key):
            cid = int(row.get("conf_id", -1))
            if cid in used:
                continue
            if not is_distinct(row):
                continue
            item = dict(row)
            item["sequence_support"] = support.get(str(item.get("family", "")), "contextual")
            item["selection_reason"] = "next low-energy conformer after family-diverse representatives"
            selected.append(item); used.add(cid)
            if len(selected) >= max(1, int(limit)):
                break
    # Very short or highly constrained peptides may not contain five structures
    # above the diversity threshold. Preserve the requested top-five contract,
    # but mark threshold relaxation explicitly instead of hiding it.
    if len(selected) < max(1, int(limit)):
        for row in sorted(rows, key=energy_key):
            cid = int(row.get("conf_id", -1))
            if cid in used:
                continue
            item = dict(row)
            item["sequence_support"] = support.get(str(item.get("family", "")), "contextual")
            item["selection_reason"] = "RMSD threshold relaxed to fill the requested top-five set; inspect structural similarity"
            selected.append(item); used.add(cid)
            if len(selected) >= max(1, int(limit)):
                break
    for rank, row in enumerate(selected, 1):
        row["rank"] = rank
        family = str(row.get("family", ""))
        if rank == 1:
            role = "leading_sequence_and_geometry_supported_candidate"
        elif rank == 2:
            role = "alternative_low_energy_family_candidate"
        elif "turn" in family or "hairpin" in family:
            role = "turn_or_hairpin_family_candidate"
        elif "beta_extended" in family or "coil" in family:
            role = "extended_or_coil_family_candidate"
        elif rank == max(1, int(limit)):
            role = "diversity_completion_candidate"
        else:
            role = "additional_conformational_family_candidate"
        row["candidate_role"] = role
        row["role_claim_guard"] = "ordinal screening role only; not a physiological population, kinetic state, or target-bound assignment"
    return selected


def pairwise_conformer_rmsd(mol) -> Dict[Tuple[int, int], float]:
    """Return symmetry-aware heavy-atom conformer RMSD values when available."""
    if mol is None or rdMolAlign is None:
        return {}
    ids = [int(conf.GetId()) for conf in mol.GetConformers()]
    out: Dict[Tuple[int, int], float] = {}
    for pos, left in enumerate(ids):
        for right in ids[pos + 1:]:
            try:
                value = float(rdMolAlign.GetBestRMS(mol, mol, prbId=left, refId=right))
            except Exception:
                continue
            out[(min(left, right), max(left, right))] = value
    return out


def _atom_range_tuple(r: Any) -> Tuple[int, int, str, str]:
    x = _row(r)
    return (
        int(x.get("heavy_start_1based", 0)) - 1,
        int(x.get("heavy_end_1based", 0)) - 1,
        str(x.get("token", "")),
        str(x.get("kind", "")),
    )


def _find_backbone_atoms(mol, atom_ranges: Iterable[Any]) -> List[Dict[str, Any]]:
    """Infer N, CA, C, O for peptide-like units from their known atom ranges."""
    residues: List[Dict[str, Any]] = []
    for r in atom_ranges:
        start, end, token, kind = _atom_range_tuple(r)
        if kind not in PEPTIDE_KINDS or start < 0 or end < start:
            continue
        ids = set(range(start, end + 1))
        atoms = [mol.GetAtomWithIdx(i) for i in ids]
        nitrogens = [a for a in atoms if a.GetAtomicNum() == 7]
        carbonyl_c = []
        for a in atoms:
            if a.GetAtomicNum() != 6:
                continue
            has_double_o = any(
                b.GetOtherAtom(a).GetAtomicNum() == 8 and float(b.GetBondTypeAsDouble()) >= 1.9
                for b in a.GetBonds()
            )
            if has_double_o:
                carbonyl_c.append(a)
        if not nitrogens or not carbonyl_c:
            residues.append({"token": token, "kind": kind, "N": None, "CA": None, "C": None, "O": None})
            continue
        # Backbone N is normally the first N in the monomer range. For Lys/Arg etc.
        # this avoids selecting the side-chain amine/guanidino nitrogens.
        n_atom = min(nitrogens, key=lambda a: a.GetIdx())
        c_atom = max(carbonyl_c, key=lambda a: a.GetIdx())
        n_neighbors = {a.GetIdx(): a for a in n_atom.GetNeighbors() if a.GetIdx() in ids and a.GetAtomicNum() == 6}
        c_neighbors = {a.GetIdx(): a for a in c_atom.GetNeighbors() if a.GetIdx() in ids and a.GetAtomicNum() == 6}
        common = set(n_neighbors).intersection(c_neighbors)
        ca_atom = n_neighbors[min(common)] if common else None
        o_atom = None
        for b in c_atom.GetBonds():
            other = b.GetOtherAtom(c_atom)
            if other.GetAtomicNum() == 8 and float(b.GetBondTypeAsDouble()) >= 1.9:
                o_atom = other
                break
        residues.append({
            "token": token, "kind": kind,
            "N": n_atom.GetIdx(), "CA": ca_atom.GetIdx() if ca_atom else None,
            "C": c_atom.GetIdx(), "O": o_atom.GetIdx() if o_atom else None,
        })
    return residues


def _angle(conf, a: int, b: int, c: int, d: int) -> Optional[float]:
    try:
        return float(rdMolTransforms.GetDihedralDeg(conf, int(a), int(b), int(c), int(d)))
    except Exception:
        return None


def _wrap(deg: float) -> float:
    x = float(deg)
    while x <= -180.0:
        x += 360.0
    while x > 180.0:
        x -= 360.0
    return x


def classify_phi_psi(phi: Optional[float], psi: Optional[float]) -> str:
    """Coarse Ramachandran basin label for conformer interpretation.

    Boundaries are deliberately broad, transparent geometry bins. They are not
    residue-specific probabilities. 3_10 versus alpha is resolved later using
    i->i+3 versus i->i+4 backbone contact geometry.
    """
    if phi is None or psi is None:
        return "terminal_or_unresolved"
    phi, psi = _wrap(phi), _wrap(psi)
    if -100 <= phi <= -30 and -85 <= psi <= 20:
        return "right_handed_helical"
    if -100 <= phi <= -40 and 90 <= psi <= 180:
        return "PPII_like"
    if -180 <= phi <= -90 and (90 <= psi <= 180 or -180 <= psi <= -120):
        return "beta_extended"
    if 30 <= phi <= 100 and -20 <= psi <= 100:
        return "left_handed_or_turn_like"
    return "coil_other"


def _distance(conf, a: int, b: int) -> float:
    pa = conf.GetAtomPosition(int(a)); pb = conf.GetAtomPosition(int(b))
    dx = pa.x - pb.x; dy = pa.y - pb.y; dz = pa.z - pb.z
    return float((dx * dx + dy * dy + dz * dz) ** 0.5)


def _backbone_contact_counts(conf, residues: List[Dict[str, Any]], cutoff_A: float = 3.5) -> Dict[str, int]:
    alpha = 0
    h310 = 0
    nonlocal_hb = 0
    for i, ri in enumerate(residues):
        oi = ri.get("O")
        if oi is None:
            continue
        for j, rj in enumerate(residues):
            if j <= i + 1 or rj.get("N") is None:
                continue
            if _distance(conf, oi, rj["N"]) <= float(cutoff_A):
                sep = j - i
                if sep == 4:
                    alpha += 1
                elif sep == 3:
                    h310 += 1
                elif sep >= 3:
                    nonlocal_hb += 1
    return {"alpha_i_i4_contacts": alpha, "helix310_i_i3_contacts": h310, "nonlocal_backbone_contacts": nonlocal_hb}


def analyze_conformer_ensemble(mol, atom_ranges: Iterable[Any], energy_records: Optional[List[Dict[str, Any]]] = None, conformer_sources: Optional[Dict[int, str]] = None) -> Dict[str, Any]:
    if Chem is None or rdMolTransforms is None or mol is None:
        return {"status": "unavailable", "reason": "RDKit unavailable"}
    residues = _find_backbone_atoms(mol, atom_ranges)
    if len(residues) < 2:
        return {"status": "unavailable", "reason": "fewer than two resolved peptide-like residues"}
    energy_by_id = {int(e.get("conf_id")): e.get("energy") for e in (energy_records or []) if e.get("conf_id") is not None}
    rows: List[Dict[str, Any]] = []
    residue_rows: List[Dict[str, Any]] = []
    for conf in mol.GetConformers():
        cid = int(conf.GetId())
        states: List[str] = []
        torsions: List[Tuple[Optional[float], Optional[float]]] = []
        for i, r in enumerate(residues):
            phi = None
            psi = None
            if i > 0 and all(x is not None for x in (residues[i-1].get("C"), r.get("N"), r.get("CA"), r.get("C"))):
                phi = _angle(conf, residues[i-1]["C"], r["N"], r["CA"], r["C"])
            if i < len(residues)-1 and all(x is not None for x in (r.get("N"), r.get("CA"), r.get("C"), residues[i+1].get("N"))):
                psi = _angle(conf, r["N"], r["CA"], r["C"], residues[i+1]["N"])
            state = classify_phi_psi(phi, psi)
            torsions.append((phi, psi)); states.append(state)
            residue_rows.append({"conf_id": cid, "residue_index": i + 1, "token": r["token"], "phi_deg": phi, "psi_deg": psi, "basin": state})
        resolved = [s for s in states if s != "terminal_or_unresolved"]
        n = max(1, len(resolved))
        frac = {s: resolved.count(s) / n for s in set(resolved)}
        contacts = _backbone_contact_counts(conf, residues)
        helical_fraction = frac.get("right_handed_helical", 0.0)
        beta_fraction = frac.get("beta_extended", 0.0)
        ppii_fraction = frac.get("PPII_like", 0.0)
        turn_fraction = frac.get("left_handed_or_turn_like", 0.0)

        source = (conformer_sources or {}).get(cid, "ETKDG")
        if source == "alpha_seed":
            family = "alpha_helix_seed_candidate"
        elif source == "3_10_seed":
            family = "3_10_helix_seed_candidate"
        elif source == "beta_extended_seed":
            family = "beta_extended_seed_candidate"
        elif source == "PPII_seed":
            family = "PPII_seed_candidate"
        elif contacts["alpha_i_i4_contacts"] > contacts["helix310_i_i3_contacts"] and contacts["alpha_i_i4_contacts"] > 0 and helical_fraction >= 0.35:
            family = "alpha_helix_like"
        elif contacts["helix310_i_i3_contacts"] > 0 and contacts["helix310_i_i3_contacts"] >= contacts["alpha_i_i4_contacts"] and helical_fraction >= 0.30:
            family = "3_10_helix_like"
        elif contacts["nonlocal_backbone_contacts"] >= 2 and beta_fraction + ppii_fraction >= 0.30:
            family = "beta_hairpin_like"
        elif beta_fraction >= 0.40:
            family = "beta_extended_like"
        elif ppii_fraction >= 0.40:
            family = "PPII_like"
        elif turn_fraction >= 0.25:
            family = "turn_rich"
        elif helical_fraction >= 0.40:
            family = "helical_backbone_like"
        else:
            family = "coil_mixed"
        rows.append({
            "conf_id": cid,
            "source": source,
            "family": family,
            "energy": energy_by_id.get(cid),
            "resolved_backbone_positions": len(resolved),
            "helical_basin_fraction": round(helical_fraction, 4),
            "beta_extended_fraction": round(beta_fraction, 4),
            "PPII_fraction": round(ppii_fraction, 4),
            "turn_like_fraction": round(turn_fraction, 4),
            **contacts,
        })

    family_counts: Dict[str, int] = {}
    representatives: List[Dict[str, Any]] = []
    for row in rows:
        family_counts[row["family"]] = family_counts.get(row["family"], 0) + 1
    for family in sorted(family_counts):
        candidates = [r for r in rows if r["family"] == family]
        with_energy = [r for r in candidates if isinstance(r.get("energy"), (int, float))]
        rep = min(with_energy, key=lambda x: x["energy"]) if with_energy else candidates[0]
        representatives.append(dict(rep))
    return {
        "status": "ok",
        "method": "geometry classification of generated conformers using phi/psi basins plus backbone O...N contact patterns",
        "claim_guard": "family counts are sampling outcomes from this generated ensemble, not experimental populations or thermodynamic probabilities",
        "conformer_count": len(rows),
        "peptide_like_residue_count": len(residues),
        "family_counts": family_counts,
        "family_fraction_of_generated_ensemble": {k: v / max(1, len(rows)) for k, v in family_counts.items()},
        "representatives": representatives,
        "conformers": rows,
        "residue_torsions": residue_rows,
    }

CANONICAL_L_BACKBONE_SEEDS: Dict[str, Tuple[float, float]] = {
    # Representative backbone basins used only to seed conformational search.
    # They are not probabilities or fitted energies.
    "alpha_seed": (-63.0, -42.0),
    "3_10_seed": (-57.0, -30.0),
    "beta_extended_seed": (-135.0, 135.0),
    "PPII_seed": (-75.0, 145.0),
}


def add_canonical_l_backbone_seed_conformers(mol, atom_ranges: Iterable[Any]) -> Dict[int, str]:
    """Add canonical-L backbone-basin seed conformers to an existing molecule.

    Seeds guarantee that the search evaluates major backbone basins even when
    stochastic ETKDG sampling misses one. They are added only when every
    peptide-like unit is canonical L (Gly included); D/non-natural/side-chain
    modified residues are deliberately not forced into L-peptide torsions.
    """
    if Chem is None or rdMolTransforms is None or mol is None or mol.GetNumConformers() == 0:
        return {}
    ranges = [_row(r) for r in atom_ranges]
    peptide_ranges = [r for r in ranges if str(r.get("kind", "")) in PEPTIDE_KINDS]
    if not peptide_ranges or any(str(r.get("kind", "")) != "std_aa" for r in peptide_ranges):
        return {}
    residues = _find_backbone_atoms(mol, ranges)
    if len(residues) < 3:
        return {}
    template = mol.GetConformer(0)
    out: Dict[int, str] = {}
    for label, (phi_target, psi_target) in CANONICAL_L_BACKBONE_SEEDS.items():
        conf = Chem.Conformer(template)
        try:
            for i, r in enumerate(residues):
                if i > 0 and all(x is not None for x in (residues[i-1].get("C"), r.get("N"), r.get("CA"), r.get("C"))):
                    rdMolTransforms.SetDihedralDeg(conf, residues[i-1]["C"], r["N"], r["CA"], r["C"], float(phi_target))
                if i < len(residues)-1 and all(x is not None for x in (r.get("N"), r.get("CA"), r.get("C"), residues[i+1].get("N"))):
                    rdMolTransforms.SetDihedralDeg(conf, r["N"], r["CA"], r["C"], residues[i+1]["N"], float(psi_target))
            cid = int(mol.AddConformer(conf, assignId=True))
            out[cid] = label
        except Exception:
            continue
    return out
