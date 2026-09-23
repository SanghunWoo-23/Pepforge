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
    from rdkit.Chem import rdMolTransforms, rdMolAlign, AllChem
except Exception:  # pragma: no cover
    Chem = None
    rdMolTransforms = None
    rdMolAlign = None
    AllChem = None

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
        "topic": "explicit_phi_psi_backbone_seed_generation",
        "citation": "Tien MZ, Sydykova DK, Meyer AG, Wilke CO. PeptideBuilder: A simple Python library to generate model peptides. PeerJ. 2013;1:e80.",
        "doi": "10.7717/peerj.80",
        "claim_guard": "Pepforge applies the published explicit phi/psi seed concept to its own chemistry graph; it does not bundle or claim to execute the external PeptideBuilder package.",
    },
    {
        "topic": "helix_capping_position_context",
        "citation": "Aurora R, Rose GD. Helix capping. Protein Sci. 1998;7:21-38.",
        "pmid": "9514257",
        "claim_guard": "Terminal/cap context modifies interpretation of helix breakers; it is not a folding probability.",
    },
    {
        "topic": "proline_position_dependence_in_alpha_helices",
        "citation": "Kim MK, Kang YK. Positional preference of proline in alpha-helices. Protein Sci. 1999.",
        "pmid": "10422838",
        "claim_guard": "A terminal/cap Pro is not treated identically to an internal Pro; generated geometry still requires validation.",
    },
    {
        "topic": "beta_sheet_context_dependence",
        "citation": "Minor DL Jr, Kim PS. Context is a major determinant of beta-sheet propensity. Nature. 1994;371:264-267.",
        "doi": "10.1038/371264a0",
        "claim_guard": "Sequence beta-face/edge descriptors are contextual evidence only and do not assign a sheet population.",
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
    {
        "topic": "helix_N_cap_and_N_terminal_acetylation",
        "citation": "Chakrabartty A, Doig AJ, Baldwin RL. Proc Natl Acad Sci USA. 1993;90:11332-11336.",
        "pmid": "8248248",
        "doi": "10.1073/pnas.90.23.11332",
    },
    {
        "topic": "PPII_residue_propensity_and_proline_aromatic_cis_trans_risk",
        "citation": "Brown AM, Zondlo NJ. Biochemistry. 2012;51:5041-5051.",
        "pmid": "22667692",
        "doi": "10.1021/bi3002924",
    },
    {
        "topic": "dPro_Gly_type_II_prime_beta_hairpin_nucleation",
        "citation": "Stanger HE, Gellman SH. J Am Chem Soc. 1998;120:4236-4237.",
        "doi": "10.1021/ja973704q",
    },
    {
        "topic": "Aib_Gly_type_I_prime_beta_turn_nucleation",
        "citation": "Masterson LR et al. Biopolymers. 2007;88:746-753.",
        "pmid": "17427180",
        "doi": "10.1002/bip.20738",
    },
    {
        "topic": "beta_turn_CA_i_i3_geometry_definition",
        "citation": "Wilmot CM, Thornton JM. J Mol Biol. 1988;203:221-232.",
        "pmid": "3184187",
        "doi": "10.1016/0022-2836(88)90103-9",
    },
    {
        "topic": "coiled_coil_a_d_core_and_e_g_specificity",
        "citation": "Mason JM, Muller KM, Arndt KM. Methods Mol Biol. 2007;352:35-70.",
        "pmid": "17041258",
        "doi": "10.1385/1-59745-187-8:35",
    }
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
    helix_breaker_context = {"internal": [], "terminal_or_cap_adjacent": [], "glycine_runs_2plus": []}
    if full_canonical:
        for i, aa in enumerate(sequence):
            if aa not in "PG":
                continue
            row = {"position": i + 1, "residue": aa}
            breakers.append(row)
            # Literature-aware context: Pro/Gly near the first/last two residues
            # is not treated identically to the same residue in the helix core.
            # This changes only ranking evidence, never a measured structure call.
            if i < 2 or i >= max(0, n - 2):
                helix_breaker_context["terminal_or_cap_adjacent"].append(row)
            else:
                helix_breaker_context["internal"].append(row)
        helix_breaker_context["glycine_runs_2plus"] = _runs(sequence, {"G"}, 2)

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
    ppii_favorable_nonpro_positions = [i + 1 for i, aa in enumerate(sequence) if aa in set("LAMKREQ")] if full_canonical else []
    ppii_pro_aromatic_adjacencies = [
        {"positions": [i + 1, i + 2], "residues": sequence[i:i+2]}
        for i in range(max(0, len(sequence)-1))
        if (sequence[i] == "P" and sequence[i+1] in "FYW") or (sequence[i+1] == "P" and sequence[i] in "FYW")
    ] if full_canonical else []
    ppii_context_supported = bool(pro_positions or (n and len(ppii_favorable_nonpro_positions) / max(1, n) >= 0.45))
    nterm_acetylated = any(str(r.get("raw", "")) == "Ac" for r in rows)
    ncap_context = "acetylated_N_cap_effect_cancelled" if nterm_acetylated else (
        "Asn_favorable" if sequence.startswith("N") else "Gly_favorable" if sequence.startswith("G") else "Gln_unfavorable" if sequence.startswith("Q") else "not_specifically_ranked_here"
    ) if full_canonical and sequence else "not_available"
    coiled_best = {"heptad_offset": None, "a_d_hydrophobic_fraction": 0.0, "e_g_charged_fraction": 0.0, "Leu_at_d_count": 0, "Ile_at_a_count": 0, "buried_polar_core_count": 0}
    if full_canonical and sequence:
        best_score = -1.0
        for offset in range(min(7, len(sequence))):
            core_total = edge_total = core_hyd = edge_charge = leu_d = ile_a = buried_polar = 0
            for i, aa in enumerate(sequence):
                pos = (i - offset) % 7
                if pos in (0, 3):
                    core_total += 1
                    core_hyd += int(aa in set("LIVMFA"))
                    leu_d += int(pos == 3 and aa == "L")
                    ile_a += int(pos == 0 and aa == "I")
                    buried_polar += int(aa in set("DENQKRHST"))
                elif pos in (4, 6):
                    edge_total += 1
                    edge_charge += int(aa in set("DEKR"))
            core_score = core_hyd / max(1, core_total)
            edge_score = edge_charge / max(1, edge_total)
            score = 0.72 * core_score + 0.28 * edge_score
            if score > best_score:
                best_score = score
                coiled_best = {"heptad_offset": offset, "a_d_hydrophobic_fraction": round(core_score,4), "e_g_charged_fraction": round(edge_score,4), "Leu_at_d_count": leu_d, "Ile_at_a_count": ile_a, "buried_polar_core_count": buried_polar}
    local_charge_patches: List[Dict[str, Any]] = []
    if full_canonical and n:
        window = min(5, n)
        for start in range(0, n - window + 1):
            frag = sequence[start:start + window]
            pos_n = sum(aa in "KR" for aa in frag)
            neg_n = sum(aa in "DE" for aa in frag)
            if max(pos_n, neg_n) >= max(2, window - 2):
                local_charge_patches.append({
                    "positions": [start + 1, start + window],
                    "sequence": frag,
                    "positive_count": pos_n,
                    "negative_count": neg_n,
                    "net_sidechain_charge_proxy": pos_n - neg_n,
                })

    beta_faces = {"odd_positions": [], "even_positions": [], "odd_hydrophobic_fraction": None, "even_hydrophobic_fraction": None}
    if full_canonical and n:
        odd = [(i + 1, aa) for i, aa in enumerate(sequence) if (i + 1) % 2 == 1]
        even = [(i + 1, aa) for i, aa in enumerate(sequence) if (i + 1) % 2 == 0]
        beta_faces["odd_positions"] = [{"position": pos, "residue": aa, "hydrophobic": aa in HYDROPHOBIC} for pos, aa in odd]
        beta_faces["even_positions"] = [{"position": pos, "residue": aa, "hydrophobic": aa in HYDROPHOBIC} for pos, aa in even]
        beta_faces["odd_hydrophobic_fraction"] = round(sum(aa in HYDROPHOBIC for _, aa in odd) / max(1, len(odd)), 4)
        beta_faces["even_hydrophobic_fraction"] = round(sum(aa in HYDROPHOBIC for _, aa in even) / max(1, len(even)), 4)

    internal_breakers = list(helix_breaker_context.get("internal") or [])
    structured_context = bool(
        (n >= 5 and not internal_breakers and helix.get("evidence_coverage_fraction") == 1.0)
        or turn_windows
        or pro_positions
    )
    family_support: Dict[str, str] = {
        # Coil remains visible as an ensemble alternative, but it no longer
        # outranks coherent structure evidence merely because it is always
        # present in a small ETKDG sample.
        "coil_mixed": "contextual" if structured_context else "retain",
        "turn_rich": "retain" if turn_windows or n <= 8 else "contextual",
        "PPII_like": "retain" if ppii_context_supported and not ppii_pro_aromatic_adjacencies else "contextual",
        "PPII_seed_candidate": "retain" if ppii_context_supported and not ppii_pro_aromatic_adjacencies else "contextual",
        "beta_hairpin_like": "retain" if turn_windows else "contextual",
        "beta_extended_like": "contextual",
        "beta_extended_seed_candidate": "contextual",
        "3_10_helix_like": "retain" if n >= 4 and not internal_breakers else "contextual",
        "3_10_helix_seed_candidate": "retain" if n >= 4 and not internal_breakers else "contextual",
        "alpha_helix_like": "retain" if n >= 5 and not internal_breakers and helix.get("evidence_coverage_fraction") == 1.0 else "contextual",
        "alpha_helix_seed_candidate": "retain" if n >= 5 and not internal_breakers and helix.get("evidence_coverage_fraction") == 1.0 else "contextual",
        "helical_backbone_like": "retain" if n >= 5 and not internal_breakers else "contextual",
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
        "helix_breaker_context": helix_breaker_context,
        "local_charge_patches": local_charge_patches,
        "beta_face_context": beta_faces,
        "opposite_charge_i3_i4_pairs": opposite_pairs,
        "like_charge_i3_i4_pairs": like_charge_pairs,
        "beta_hairpin_context_windows": turn_windows,
        "proline_positions_for_PPII_context": pro_positions,
        "nonproline_positions_for_PPII_context": ppii_favorable_nonpro_positions,
        "PPII_pro_aromatic_cis_trans_risk": ppii_pro_aromatic_adjacencies,
        "N_cap_context": ncap_context,
        "N_terminal_acetylated": bool(nterm_acetylated),
        "coiled_coil_heptad_evidence": coiled_best,
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
        "evidence_fast": {"etkdg_multiplier": 1, "embedding_retries": 2, "rmsd_threshold_A": 0.75, "guided_seed_variants": 0},
        "evidence_balanced": {"etkdg_multiplier": 2, "embedding_retries": 3, "rmsd_threshold_A": 1.00, "guided_seed_variants": 1},
        "evidence_thorough": {"etkdg_multiplier": 3, "embedding_retries": 4, "rmsd_threshold_A": 1.25, "guided_seed_variants": 2},
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
        note("alpha_helix_seed_candidate", "canonical-L alpha backbone seed retained for evidence-guided search")
        note("3_10_helix_like", "short right-handed helical alternative")
        note("3_10_helix_seed_candidate", "canonical-L 3_10 backbone seed retained as a right-handed helical alternative")
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


def preferred_structure_families(preferred_structure: Optional[str]) -> List[str]:
    """Map a PDE structure preference to PSB conformer families.

    This mapping controls *selection* only. It does not fabricate a family for
    conformers whose measured geometry does not match the requested basin.
    """
    key = str(preferred_structure or "NONE").upper().strip()
    mapping = {
        "ALPHA_HELIX": ["alpha_helix_seed_candidate", "alpha_helix_like", "helical_backbone_like"],
        "AMPHIPATHIC_ALPHA": ["alpha_helix_seed_candidate", "alpha_helix_like", "helical_backbone_like"],
        "HELIX_310": ["3_10_helix_seed_candidate", "3_10_helix_like", "helical_backbone_like"],
        "BETA_HAIRPIN": ["beta_hairpin_like"],
        "BETA_STRAND": ["beta_extended_seed_candidate", "beta_extended_like"],
        "PPII_EXTENDED": ["PPII_seed_candidate", "PPII_like"],
        "TURN_RICH": ["turn_rich", "beta_hairpin_like"],
        # PSB is a monomer conformer generator, not a multimeric coiled-coil
        # predictor. For this PDE intent it can only assess helical
        # preorganization of the peptide chain.
        "COILED_COIL": ["alpha_helix_seed_candidate", "alpha_helix_like", "helical_backbone_like"],
    }
    return list(mapping.get(key, []))


def preferred_structure_seed_labels(preferred_structure: Optional[str]) -> List[str]:
    """Return curated canonical-L seed basins appropriate for a PDE intent."""
    key = str(preferred_structure or "NONE").upper().strip()
    mapping = {
        "ALPHA_HELIX": ["alpha_seed"],
        "AMPHIPATHIC_ALPHA": ["alpha_seed"],
        "HELIX_310": ["3_10_seed"],
        "BETA_STRAND": ["beta_extended_seed"],
        "PPII_EXTENDED": ["PPII_seed"],
        "COILED_COIL": ["alpha_seed"],
    }
    return list(mapping.get(key, []))



def requested_structure_audit(
    preferred_structure: Optional[str],
    design_mode: Optional[str],
    selected: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Describe what PSB can and cannot claim for a PDE structure request."""
    mode = str(design_mode or "BALANCED").upper().strip()
    requested = str(preferred_structure or "NONE").upper().strip()
    active = mode != "INTERACTION_ONLY" and requested not in {"", "NONE"}
    families = preferred_structure_families(requested) if active else []
    seed_labels = preferred_structure_seed_labels(requested) if active else []
    selected_rows = list(selected or [])
    matched = sum(bool(row.get("requested_structure_match")) for row in selected_rows)
    fallback = sum(bool(row.get("selection_fallback")) for row in selected_rows)
    limitations: List[str] = []
    if requested in {"BETA_HAIRPIN", "TURN_RICH"}:
        limitations.append(
            "No invented exact torsion template is imposed for the family in general. Exact turn-basin search seeds are used only when an explicit literature-supported motif (dPro-Gly or Aib-Gly) is present; PSB still requires measured post-relaxation C-alpha turn/backbone-contact geometry and reports explicit fallback when the requested family is not found."
        )
    if requested == "COILED_COIL":
        limitations.append(
            "PSB is a monomer conformer generator; this request assesses helical preorganization only and does not predict oligomeric coiled-coil assembly."
        )
    if requested == "AMPHIPATHIC_ALPHA":
        limitations.append(
            "Backbone selection uses alpha-helical geometry; amphipathic organization remains sequence/context evidence rather than a separate multimeric 3D proof."
        )
    if mode == "INTERACTION_ONLY":
        limitations.append("Interaction Only disables preferred-fold selection; structure metadata may still be reported but is not an optimization objective.")
    return {
        "design_mode": mode,
        "requested_structure": requested,
        "structure_request_active": active,
        "requested_families": families,
        "curated_seed_labels": seed_labels,
        "exact_curated_seed_available": bool(seed_labels),
        "selected_count": len(selected_rows),
        "requested_family_match_count": matched,
        "fallback_count": fallback,
        "limitations": limitations,
        "claim_guard": "Requested-family matching is a geometry/sampling audit, not experimental validation, native-state probability, or solution-state population evidence.",
    }

def select_top_conformers(
    conformation_analysis: Dict[str, Any],
    sequence_evidence: Dict[str, Any],
    limit: int = 5,
    pairwise_rmsd: Optional[Dict[Tuple[int, int], float]] = None,
    minimum_rmsd_A: float = 1.0,
    family_priority: Optional[List[str]] = None,
    preferred_structure: Optional[str] = None,
    design_mode: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Rank physically usable conformers without artificial family diversity.

    If PDE supplied a preferred structure, PSB first returns clash-free
    conformers from that requested geometry family. If fewer than ``limit`` are
    available, clash-free fallback conformers may be appended and are labelled
    explicitly. Severe-clash conformers are not used merely to fill Top-5.

    In Interaction Only / no-preference mode, structure-family diversity is not
    an objective; low-clash geometry and within-molecule force-field energy
    drive the ranking. ``pairwise_rmsd`` is retained for reporting/backward API
    compatibility but is intentionally not a selection constraint.
    """
    rows = [dict(r) for r in (conformation_analysis or {}).get("conformers", [])]
    support = dict((sequence_evidence or {}).get("family_support", {}))
    support_order = {"retain": 0, "contextual": 1, "geometry_only": 2}
    target_families = set(preferred_structure_families(preferred_structure))
    mode = str(design_mode or "").upper().strip()
    structure_active = bool(target_families) and mode != "INTERACTION_ONLY"

    def severe_count(row: Dict[str, Any]) -> int:
        value = row.get("severe_steric_clashes")
        return int(value) if isinstance(value, (int, float)) else 0

    def geometry_key(row: Dict[str, Any]) -> Tuple[int, int, float]:
        severe = severe_count(row)
        overlaps = row.get("nonbonded_vdw_overlaps")
        ratio = row.get("minimum_nonbonded_vdw_ratio")
        overlap_i = int(overlaps) if isinstance(overlaps, (int, float)) else 0
        ratio_f = float(ratio) if isinstance(ratio, (int, float)) else 1.0
        return (severe, overlap_i, -ratio_f)

    def energy_key(row: Dict[str, Any]) -> Tuple[int, float, int]:
        value = row.get("energy")
        valid = isinstance(value, (int, float)) and not isnan(float(value))
        return (0 if valid else 1, float(value) if valid else float("inf"), int(row.get("conf_id", 0)))

    family_order = {family: index for index, family in enumerate(family_priority or [])}

    preferred_key = str(preferred_structure or "NONE").upper().strip()

    def requested_structure_geometry_key(row: Dict[str, Any]) -> Tuple[float, ...]:
        """Rank measured geometry inside an already requested structure family.

        This is intentionally evaluated before generic soft-overlap/energy terms
        so an alpha-family conformer with coherent i->i+4 backbone geometry is
        not displaced by a lower-energy but poorly organized alpha-labelled seed.
        """
        alpha = float(row.get("alpha_i_i4_contacts") or 0.0)
        h310 = float(row.get("helix310_i_i3_contacts") or 0.0)
        nonlocal_hb = float(row.get("nonlocal_backbone_contacts") or 0.0)
        helix = float(row.get("helical_basin_fraction") or 0.0)
        beta = float(row.get("beta_extended_fraction") or 0.0)
        ppii = float(row.get("PPII_fraction") or 0.0)
        turn = float(row.get("turn_like_fraction") or 0.0)
        if preferred_key in {"ALPHA_HELIX", "AMPHIPATHIC_ALPHA", "COILED_COIL"}:
            return (-alpha, -helix, h310)
        if preferred_key == "HELIX_310":
            return (-h310, -helix, alpha)
        if preferred_key == "BETA_HAIRPIN":
            beta_turn = float(row.get("beta_turn_CA_i_i3_contacts") or 0.0)
            return (-beta_turn, -nonlocal_hb, -beta, -turn)
        if preferred_key == "BETA_STRAND":
            return (-beta, -nonlocal_hb)
        if preferred_key == "PPII_EXTENDED":
            return (-ppii, -beta)
        if preferred_key == "TURN_RICH":
            return (-turn, -nonlocal_hb)
        return (0.0,)

    def evidence_key(row: Dict[str, Any]) -> Tuple[int, int]:
        fam = str(row.get("family", ""))
        return (
            support_order.get(str(support.get(fam, "contextual")), 3),
            family_order.get(fam, len(family_order)),
        )

    clean_rows = [r for r in rows if severe_count(r) == 0]
    selected: List[Dict[str, Any]] = []
    used: set[int] = set()

    def append_rows(candidates: List[Dict[str, Any]], *, fallback: bool, reason: str) -> None:
        for row in candidates:
            if len(selected) >= max(1, int(limit)):
                break
            cid = int(row.get("conf_id", -1))
            if cid in used:
                continue
            item = dict(row)
            fam = str(item.get("family", ""))
            item["sequence_support"] = support.get(fam, "contextual")
            item["requested_structure_match"] = bool(target_families and fam in target_families)
            item["selection_fallback"] = bool(fallback)
            item["selection_reason"] = reason
            selected.append(item)
            used.add(cid)

    if structure_active:
        requested = [r for r in clean_rows if str(r.get("family", "")) in target_families]
        requested.sort(key=lambda r: requested_structure_geometry_key(r) + geometry_key(r) + evidence_key(r) + energy_key(r))
        append_rows(
            requested,
            fallback=False,
            reason="clash-free conformer matching the PDE-requested structure family; ranked by requested-family backbone geometry, then steric geometry/evidence and within-molecule force-field energy",
        )
        if len(selected) < max(1, int(limit)):
            fallback_rows = [r for r in clean_rows if str(r.get("family", "")) not in target_families]
            fallback_rows.sort(key=lambda r: geometry_key(r) + evidence_key(r) + energy_key(r))
            append_rows(
                fallback_rows,
                fallback=True,
                reason="explicit clash-free fallback because fewer valid conformers matched the PDE-requested structure family",
            )
    else:
        # Interaction Only intentionally ignores preferred-fold diversity.
        # For a standalone/no-preference build, sequence evidence is a weak
        # tie-breaker after steric quality; it does not force one-per-family.
        if mode == "INTERACTION_ONLY":
            clean_rows.sort(key=lambda r: geometry_key(r) + energy_key(r))
            reason = "structure-agnostic clash-free geometry candidate for downstream interaction analysis"
        else:
            clean_rows.sort(key=lambda r: (severe_count(r),) + evidence_key(r) + geometry_key(r)[1:] + energy_key(r))
            reason = "clash-free sequence-evidence-prioritized geometry candidate; no artificial conformer-family diversity constraint"
        append_rows(clean_rows, fallback=False, reason=reason)

    for rank, row in enumerate(selected, 1):
        row["rank"] = rank
        if structure_active and row.get("requested_structure_match"):
            role = "requested_structure_family_candidate"
        elif structure_active:
            role = "explicit_structure_fallback_candidate"
        elif mode == "INTERACTION_ONLY":
            role = "interaction_ready_geometry_candidate"
        else:
            role = "geometry_quality_candidate"
        row["candidate_role"] = role
        row["role_claim_guard"] = (
            "Screening/ranking label only; not a physiological population, native-state probability, "
            "binding affinity, or molecular-dynamics result."
        )
    return selected


def pairwise_conformer_rmsd(mol) -> Dict[Tuple[int, int], float]:
    """Return aligned identity-mapped heavy-atom RMSD between conformers.

    All conformers belong to the same explicit molecular graph, so enumerating
    symmetry permutations is unnecessary and can become extremely expensive for
    long lipidated/modified peptides.  Identity atom mapping is deterministic,
    does not invent atom correspondence, and keeps the calculation auditable.
    """
    if mol is None or rdMolAlign is None:
        return {}
    ids = [int(conf.GetId()) for conf in mol.GetConformers()]
    heavy_map = [(int(atom.GetIdx()), int(atom.GetIdx())) for atom in mol.GetAtoms() if int(atom.GetAtomicNum()) > 1]
    if len(heavy_map) < 2:
        return {}
    out: Dict[Tuple[int, int], float] = {}
    for pos, left in enumerate(ids):
        for right in ids[pos + 1:]:
            try:
                value, _transform = rdMolAlign.GetAlignmentTransform(
                    mol, mol, prbCid=left, refCid=right, atomMap=heavy_map, maxIters=50
                )
                value = float(value)
            except Exception:
                continue
            out[(min(left, right), max(left, right))] = value
    return out


def preferred_canonical_seed_labels(family_priority: Optional[List[str]] = None) -> List[str]:
    """Map evidence-ranked families onto already curated canonical-L basins.

    Hairpin/turn evidence is intentionally not converted into invented exact
    torsions.  It may affect ranking and ETKDG budget, while only the four
    existing canonical-L seed basins are steered explicitly.
    """
    out: List[str] = []
    for family in family_priority or []:
        text = str(family)
        label = None
        if text.startswith("alpha_helix"):
            label = "alpha_seed"
        elif text.startswith("3_10_helix"):
            label = "3_10_seed"
        elif text.startswith("beta_extended"):
            label = "beta_extended_seed"
        elif text.startswith("PPII"):
            label = "PPII_seed"
        if label and label not in out:
            out.append(label)
    return out


def assess_top_conformer_diversity(
    selected: List[Dict[str, Any]],
    pairwise_rmsd: Optional[Dict[Tuple[int, int], float]],
    requested_threshold_A: float,
) -> Dict[str, Any]:
    """Audit the selected ensemble without turning diversity into a biology claim."""
    selected = list(selected or [])
    ids = [int(row.get("conf_id", -1)) for row in selected]
    distances: List[float] = []
    for i, left in enumerate(ids):
        for right in ids[i + 1:]:
            value = (pairwise_rmsd or {}).get(tuple(sorted((left, right))))
            if isinstance(value, (int, float)):
                distances.append(float(value))
    minimum = min(distances) if distances else None
    unique_families = len({str(row.get("family", "")) for row in selected if row.get("family")})
    threshold = max(0.0, float(requested_threshold_A))
    if len(selected) <= 1:
        status = "insufficient_for_pairwise_audit"
    elif minimum is not None and minimum >= threshold and unique_families >= min(3, len(selected)):
        status = "strong"
    elif minimum is not None and minimum >= threshold * 0.5 and unique_families >= min(2, len(selected)):
        status = "moderate"
    else:
        status = "relaxed"
    return {
        "status": status,
        "selected_count": len(selected),
        "unique_family_count": unique_families,
        "minimum_pairwise_rmsd_A": round(float(minimum), 4) if minimum is not None else None,
        "requested_rmsd_threshold_A": threshold,
        "pairwise_values_count": len(distances),
        "metric": "identity-mapped heavy-atom aligned RMSD within one molecular graph",
        "claim_guard": "Search-quality audit only; not evidence of solution-state populations, native structure, or target-bound states.",
    }


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
    beta_turn_ca = 0
    for i in range(len(residues)):
        ri = residues[i]
        # Standard beta-turn geometric screen: C-alpha(i) ... C-alpha(i+3) < 7 A.
        jturn = i + 3
        if jturn < len(residues) and ri.get("CA") is not None and residues[jturn].get("CA") is not None:
            if _distance(conf, ri["CA"], residues[jturn]["CA"]) < 7.0:
                beta_turn_ca += 1
        for j in range(i + 2, len(residues)):
            rj = residues[j]
            sep = j - i
            forward = ri.get("O") is not None and rj.get("N") is not None and _distance(conf, ri["O"], rj["N"]) <= float(cutoff_A)
            reverse = rj.get("O") is not None and ri.get("N") is not None and _distance(conf, rj["O"], ri["N"]) <= float(cutoff_A)
            # Local helix contacts are directional along sequence.
            if forward and sep == 4:
                alpha += 1
            elif forward and sep == 3:
                h310 += 1
            elif forward and sep >= 3:
                nonlocal_hb += 1
            # Antiparallel hairpins can satisfy the opposite O(j)...N(i)
            # direction; count it as nonlocal backbone contact without
            # misclassifying it as a local alpha/3_10 contact.
            if reverse and sep >= 3:
                nonlocal_hb += 1
    return {
        "alpha_i_i4_contacts": alpha,
        "helix310_i_i3_contacts": h310,
        "nonlocal_backbone_contacts": nonlocal_hb,
        "beta_turn_CA_i_i3_contacts": beta_turn_ca,
    }

def steric_clash_audit(
    mol,
    conf_id: int,
    severe_ratio: float = 0.75,
    overlap_ratio: float = 0.90,
) -> Dict[str, Any]:
    """Screen non-bonded heavy-atom steric overlaps for one conformer.

    Pairs separated by one or two covalent bonds are excluded. Distances are
    compared with RDKit periodic-table van-der-Waals radii. This is a geometry
    quality screen, not a physical free-energy or experimental clash score.
    """
    if Chem is None or mol is None or mol.GetNumConformers() == 0:
        return {"status": "unavailable"}
    try:
        conf = mol.GetConformer(int(conf_id))
        topo = Chem.GetDistanceMatrix(mol)
        periodic = Chem.GetPeriodicTable()
        severe = 0
        overlaps = 0
        minimum_ratio = None
        worst: List[Dict[str, Any]] = []
        atoms = [a for a in mol.GetAtoms() if int(a.GetAtomicNum()) > 1]
        for pos, left in enumerate(atoms):
            i = int(left.GetIdx())
            ri = float(periodic.GetRvdw(int(left.GetAtomicNum())) or 1.7)
            pi = conf.GetAtomPosition(i)
            for right in atoms[pos + 1:]:
                j = int(right.GetIdx())
                if float(topo[i, j]) <= 2.0:
                    continue
                rj = float(periodic.GetRvdw(int(right.GetAtomicNum())) or 1.7)
                pj = conf.GetAtomPosition(j)
                dx, dy, dz = pi.x - pj.x, pi.y - pj.y, pi.z - pj.z
                distance = sqrt(dx * dx + dy * dy + dz * dz)
                denom = max(0.1, ri + rj)
                ratio = distance / denom
                minimum_ratio = ratio if minimum_ratio is None else min(minimum_ratio, ratio)
                if ratio < float(overlap_ratio):
                    overlaps += 1
                if ratio < float(severe_ratio):
                    severe += 1
                    worst.append({
                        "atom_i": i, "atom_j": j,
                        "elements": f"{left.GetSymbol()}-{right.GetSymbol()}",
                        "distance_A": round(distance, 4),
                        "vdw_ratio": round(ratio, 4),
                    })
        worst.sort(key=lambda row: (row["vdw_ratio"], row["distance_A"]))
        return {
            "status": "ok",
            "severe_steric_clashes": int(severe),
            "nonbonded_vdw_overlaps": int(overlaps),
            "minimum_nonbonded_vdw_ratio": round(float(minimum_ratio), 4) if minimum_ratio is not None else None,
            "severe_ratio_threshold": float(severe_ratio),
            "overlap_ratio_threshold": float(overlap_ratio),
            "worst_severe_pairs": worst[:10],
            "claim_guard": "Geometry screen only; not a molecular-mechanics free energy or experimental clash probability.",
        }
    except Exception as exc:
        return {"status": "unavailable", "reason": str(exc)}


def relax_canonical_seed_conformers(
    mol,
    atom_ranges: Iterable[Any],
    seed_sources: Dict[int, str],
    max_iters: int = 300,
    torsion_window_deg: float = 12.0,
) -> List[Dict[str, Any]]:
    """Relax canonical-L torsion seeds without erasing their intended basin.

    Stage 1 optimizes side chains with N/CA/C/O backbone atoms fixed. Stage 2
    releases the full structure while constraining each current phi/psi torsion
    to a small window. MMFF94 is preferred when fully parameterized; UFF is the
    explicit fallback. The routine is used only for canonical-L seeds already
    produced by :func:`add_canonical_l_backbone_seed_conformers`.
    """
    if Chem is None or AllChem is None or rdMolTransforms is None or mol is None or not seed_sources:
        return []
    residues = _find_backbone_atoms(mol, atom_ranges)
    if len(residues) < 3:
        return []
    try:
        use_mmff = bool(AllChem.MMFFHasAllMoleculeParams(mol))
        mmff_props = AllChem.MMFFGetMoleculeProperties(mol) if use_mmff else None
    except Exception:
        use_mmff, mmff_props = False, None

    def make_ff(cid: int):
        if use_mmff and mmff_props is not None:
            return AllChem.MMFFGetMoleculeForceField(mol, mmff_props, confId=int(cid))
        return AllChem.UFFGetMoleculeForceField(mol, confId=int(cid))

    records: List[Dict[str, Any]] = []
    side_iters = max(100, min(500, int(max_iters)))
    global_iters = max(200, min(1000, int(max_iters) * 2))
    for cid, source in seed_sources.items():
        cid = int(cid)
        conf = mol.GetConformer(cid)
        phi_psi_constraints: List[Tuple[Tuple[int, int, int, int], float]] = []
        for i, residue in enumerate(residues):
            if i > 0 and all(x is not None for x in (residues[i-1].get("C"), residue.get("N"), residue.get("CA"), residue.get("C"))):
                ids = (int(residues[i-1]["C"]), int(residue["N"]), int(residue["CA"]), int(residue["C"]))
                phi_psi_constraints.append((ids, float(rdMolTransforms.GetDihedralDeg(conf, *ids))))
            if i < len(residues) - 1 and all(x is not None for x in (residue.get("N"), residue.get("CA"), residue.get("C"), residues[i+1].get("N"))):
                ids = (int(residue["N"]), int(residue["CA"]), int(residue["C"]), int(residues[i+1]["N"]))
                phi_psi_constraints.append((ids, float(rdMolTransforms.GetDihedralDeg(conf, *ids))))
        try:
            ff = make_ff(cid)
            if ff is None:
                raise ValueError("force field unavailable")
            for residue in residues:
                for key in ("N", "CA", "C", "O"):
                    if residue.get(key) is not None:
                        ff.AddFixedPoint(int(residue[key]))
            ff.Minimize(maxIts=side_iters)

            ff2 = make_ff(cid)
            if ff2 is None:
                raise ValueError("force field unavailable after side-chain relaxation")
            for ids, target in phi_psi_constraints:
                lo, hi = float(target) - float(torsion_window_deg), float(target) + float(torsion_window_deg)
                if use_mmff:
                    ff2.MMFFAddTorsionConstraint(*ids, False, lo, hi, 100.0)
                else:
                    ff2.UFFAddTorsionConstraint(*ids, False, lo, hi, 100.0)
            not_converged = int(ff2.Minimize(maxIts=global_iters))

            # Conditional final side-chain polish: only spend another
            # minimization cycle when the constrained seed still has a severe
            # clash or a very short non-bonded heavy-atom contact.
            audit_pre = steric_clash_audit(mol, cid)
            needs_polish = bool(int(audit_pre.get("severe_steric_clashes") or 0) > 0) or (
                isinstance(audit_pre.get("minimum_nonbonded_vdw_ratio"), (int, float))
                and float(audit_pre.get("minimum_nonbonded_vdw_ratio")) < 0.80
            )
            final_not_converged = 0
            relaxation_label = "backbone-fixed side-chain relaxation + phi/psi-constrained whole-structure relaxation"
            if needs_polish:
                ff3 = make_ff(cid)
                if ff3 is None:
                    raise ValueError("force field unavailable during final side-chain polish")
                for residue in residues:
                    for key in ("N", "CA", "C", "O"):
                        if residue.get(key) is not None:
                            ff3.AddFixedPoint(int(residue[key]))
                final_not_converged = int(ff3.Minimize(maxIts=max(80, side_iters // 2)))
                energy = float(ff3.CalcEnergy())
                relaxation_label += " + conditional final backbone-fixed side-chain polish"
            else:
                energy = float(ff2.CalcEnergy())
            audit = steric_clash_audit(mol, cid)
            records.append({
                "conf_id": cid, "energy": energy, "not_converged": max(not_converged, final_not_converged),
                "source": str(source),
                "relaxation": relaxation_label,
                "force_field": "MMFF94" if use_mmff else "UFF",
                "torsion_window_deg": float(torsion_window_deg),
                "severe_steric_clashes_after_relaxation": audit.get("severe_steric_clashes"),
            })
        except Exception as exc:
            records.append({
                "conf_id": cid, "energy": None, "not_converged": None, "source": str(source),
                "relaxation": "failed", "force_field": "MMFF94" if use_mmff else "UFF",
                "warning": str(exc),
            })
    return records


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
        if str(source).startswith("alpha_seed"):
            family = "alpha_helix_seed_candidate"
        elif str(source).startswith("3_10_seed"):
            family = "3_10_helix_seed_candidate"
        elif str(source).startswith("beta_extended_seed"):
            family = "beta_extended_seed_candidate"
        elif str(source).startswith("PPII_seed"):
            family = "PPII_seed_candidate"
        elif str(source).startswith("3_10_Aib_explicit_seed"):
            family = "3_10_helix_seed_candidate"
        elif contacts["alpha_i_i4_contacts"] > contacts["helix310_i_i3_contacts"] and contacts["alpha_i_i4_contacts"] > 0 and helical_fraction >= 0.35:
            family = "alpha_helix_like"
        elif contacts["helix310_i_i3_contacts"] > 0 and contacts["helix310_i_i3_contacts"] >= contacts["alpha_i_i4_contacts"] and helical_fraction >= 0.30:
            family = "3_10_helix_like"
        elif contacts["beta_turn_CA_i_i3_contacts"] >= 1 and contacts["nonlocal_backbone_contacts"] >= 1 and beta_fraction + ppii_fraction >= 0.25:
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
        clash = steric_clash_audit(mol, cid)
        rows.append({
            "conf_id": cid,
            "source": source,
            "family": family,
            "energy": energy_by_id.get(cid),
            "severe_steric_clashes": clash.get("severe_steric_clashes"),
            "nonbonded_vdw_overlaps": clash.get("nonbonded_vdw_overlaps"),
            "minimum_nonbonded_vdw_ratio": clash.get("minimum_nonbonded_vdw_ratio"),
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


def add_literature_turn_seed_conformers(
    mol,
    atom_ranges: Iterable[Any],
    preferred_structure: Optional[str] = None,
    variants: int = 4,
) -> Dict[int, str]:
    """Add local beta-turn search seeds only for explicit supported motifs.

    dPro-Gly is sampled around a representative type II' turn basin and Aib-Gly
    around a representative type I' basin. These torsions are search hypotheses;
    the resulting conformer is called a hairpin only after relaxation and measured
    C-alpha turn/backbone-contact geometry. No D/non-natural residue is converted
    to a canonical surrogate.
    """
    if Chem is None or rdMolTransforms is None or mol is None or mol.GetNumConformers() == 0:
        return {}
    requested = str(preferred_structure or "NONE").upper()
    if requested not in {"BETA_HAIRPIN", "TURN_RICH"}:
        return {}
    residues = _find_backbone_atoms(mol, atom_ranges)
    if len(residues) < 4:
        return {}
    motifs = []
    for i in range(len(residues)-1):
        a, b = str(residues[i].get("token", "")), str(residues[i+1].get("token", ""))
        if a.lower() == "dp" and b == "G":
            motifs.append((i, "dProGly_typeIIprime", (60.0, -120.0), (-80.0, 0.0)))
        elif a == "Aib" and b == "G":
            motifs.append((i, "AibGly_typeIprime", (60.0, 30.0), (90.0, 0.0)))
    if not motifs:
        return {}
    template = mol.GetConformer(0)
    out: Dict[int, str] = {}

    def set_residue_phi_psi(conf, idx: int, phi: float, psi: float) -> int:
        applied = 0
        r = residues[idx]
        if idx > 0 and all(x is not None for x in (residues[idx-1].get("C"), r.get("N"), r.get("CA"), r.get("C"))):
            try:
                rdMolTransforms.SetDihedralDeg(conf, residues[idx-1]["C"], r["N"], r["CA"], r["C"], float(phi)); applied += 1
            except Exception:
                pass
        if idx < len(residues)-1 and all(x is not None for x in (r.get("N"), r.get("CA"), r.get("C"), residues[idx+1].get("N"))):
            try:
                rdMolTransforms.SetDihedralDeg(conf, r["N"], r["CA"], r["C"], residues[idx+1]["N"], float(psi)); applied += 1
            except Exception:
                pass
        return applied

    for motif_idx, label, first_angles, second_angles in motifs:
        for variant in range(max(1, int(variants))):
            conf = Chem.Conformer(template)
            delta = (variant // 2 + 1) * 5.0 if variant else 0.0
            sign = -1.0 if variant % 2 else 1.0
            applied = 0

            # For an explicit beta-hairpin request, do not leave the flanking
            # strands as arbitrary ETKDG torsions. Seed only the *search* with
            # beta-extended arms around the literature-supported turn motif.
            # The final family call is still made exclusively from measured
            # post-relaxation geometry (turn C-alpha distance, nonlocal
            # backbone contacts, and beta-like phi/psi content).
            if requested == "BETA_HAIRPIN":
                flank_delta = (0.0 if variant == 0 else (4.0 + 2.0 * (variant // 2))) * sign
                for ridx in range(len(residues)):
                    if ridx in {motif_idx, motif_idx + 1}:
                        continue
                    applied += set_residue_phi_psi(
                        conf, ridx, -135.0 + flank_delta, 135.0 - flank_delta
                    )

            applied += set_residue_phi_psi(
                conf, motif_idx, first_angles[0] + sign*delta, first_angles[1] - sign*delta
            )
            applied += set_residue_phi_psi(
                conf, motif_idx+1, second_angles[0] - sign*delta, second_angles[1] + sign*delta
            )
            if applied <= 0:
                continue
            try:
                cid = int(mol.AddConformer(conf, assignId=True))
                out[cid] = f"beta_turn_{label}_seed_v{variant+1}"
            except Exception:
                pass
    return out


def add_explicit_aib_310_seed_conformers(
    mol,
    atom_ranges: Iterable[Any],
    preferred_structure: Optional[str] = None,
    variants: int = 3,
) -> Dict[int, str]:
    """Sample a 3_10-like basin for sequences composed only of canonical-L/Aib units.

    Aib is handled explicitly as Aib; it is never replaced by Ala or assigned a
    canonical Pace-Scholtz value. Final 3_10 classification still requires measured
    phi/psi and i->i+3 backbone contact geometry after relaxation.
    """
    if Chem is None or rdMolTransforms is None or mol is None or mol.GetNumConformers() == 0:
        return {}
    if str(preferred_structure or "NONE").upper() != "HELIX_310":
        return {}
    ranges = [_row(r) for r in atom_ranges]
    peptide = [r for r in ranges if str(r.get("kind", "")) in PEPTIDE_KINDS]
    if not peptide or not any(str(r.get("raw", r.get("token", ""))) == "Aib" or str(r.get("token", "")) == "Aib" for r in peptide):
        return {}
    if any(not (str(r.get("kind", "")) == "std_aa" or str(r.get("token", r.get("raw", ""))) == "Aib" or str(r.get("raw", "")) == "Aib") for r in peptide):
        return {}
    residues = _find_backbone_atoms(mol, ranges)
    if len(residues) < 3:
        return {}
    template = mol.GetConformer(0)
    out: Dict[int, str] = {}
    for variant in range(max(1, int(variants))):
        conf = Chem.Conformer(template)
        delta = 0.0 if variant == 0 else 6.0 * ((variant + 1)//2) * (-1.0 if variant % 2 == 0 else 1.0)
        applied = 0
        for i, r in enumerate(residues):
            if i > 0 and all(x is not None for x in (residues[i-1].get("C"), r.get("N"), r.get("CA"), r.get("C"))):
                try:
                    rdMolTransforms.SetDihedralDeg(conf, residues[i-1]["C"], r["N"], r["CA"], r["C"], -57.0 + delta); applied += 1
                except Exception:
                    pass
            if i < len(residues)-1 and all(x is not None for x in (r.get("N"), r.get("CA"), r.get("C"), residues[i+1].get("N"))):
                try:
                    rdMolTransforms.SetDihedralDeg(conf, r["N"], r["CA"], r["C"], residues[i+1]["N"], -30.0 - delta); applied += 1
                except Exception:
                    pass
        if applied:
            try:
                cid = int(mol.AddConformer(conf, assignId=True)); out[cid] = f"3_10_Aib_explicit_seed_v{variant+1}"
            except Exception:
                pass
    return out

CANONICAL_L_BACKBONE_SEEDS: Dict[str, Tuple[float, float]] = {
    # Representative backbone basins used only to seed conformational search.
    # They are not probabilities or fitted energies.
    "alpha_seed": (-63.0, -42.0),
    "3_10_seed": (-57.0, -30.0),
    "beta_extended_seed": (-135.0, 135.0),
    "PPII_seed": (-75.0, 145.0),
}


def _circular_abs_diff_deg(value: float, target: float) -> float:
    return abs(((float(value) - float(target) + 180.0) % 360.0) - 180.0)


def canonical_seed_target_for_source(source: str) -> Optional[Tuple[str, float, float]]:
    """Recover the deterministic target basin used to create a canonical seed."""
    text = str(source or "")
    label = next((key for key in CANONICAL_L_BACKBONE_SEEDS if text.startswith(key)), None)
    if label is None:
        return None
    phi_target, psi_target = CANONICAL_L_BACKBONE_SEEDS[label]
    import re as _re
    match = _re.search(r"_guided_variant(\d+)$", text)
    if match:
        number = int(match.group(1))
        delta = 7.5 * number
        sign = -1.0 if (number - 1) % 2 else 1.0
        phi_target += sign * delta
        psi_target -= sign * delta
    return label, float(phi_target), float(psi_target)


def backbone_seed_fidelity_audit(
    mol,
    atom_ranges: Iterable[Any],
    seed_sources: Dict[int, str],
    tolerance_deg: float = 35.0,
) -> Dict[str, Any]:
    """Measure post-relaxation fidelity of explicit canonical phi/psi search seeds.

    This diagnostic is deliberately geometric. A seed may drift out of its
    starting basin after minimization; Pepforge reports that drift rather than
    continuing to call the model an alpha/beta/PPII seed by construction.
    """
    if Chem is None or rdMolTransforms is None or mol is None or not seed_sources:
        return {"status": "unavailable", "records": []}
    residues = _find_backbone_atoms(mol, atom_ranges)
    records: List[Dict[str, Any]] = []
    for cid, source in sorted(seed_sources.items()):
        target = canonical_seed_target_for_source(source)
        if target is None:
            continue
        label, phi_target, psi_target = target
        try:
            conf = mol.GetConformer(int(cid))
        except Exception:
            continue
        diffs: List[float] = []
        evaluated = 0
        within = 0
        per_residue: List[Dict[str, Any]] = []
        for i, residue in enumerate(residues):
            phi = psi = None
            if i > 0 and all(x is not None for x in (residues[i-1].get("C"), residue.get("N"), residue.get("CA"), residue.get("C"))):
                phi = _angle(conf, residues[i-1]["C"], residue["N"], residue["CA"], residue["C"])
            if i < len(residues)-1 and all(x is not None for x in (residue.get("N"), residue.get("CA"), residue.get("C"), residues[i+1].get("N"))):
                psi = _angle(conf, residue["N"], residue["CA"], residue["C"], residues[i+1]["N"])
            phi_diff = _circular_abs_diff_deg(phi, phi_target) if phi is not None else None
            psi_diff = _circular_abs_diff_deg(psi, psi_target) if psi is not None else None
            local = [x for x in (phi_diff, psi_diff) if x is not None]
            if local:
                evaluated += 1
                diffs.extend(local)
                ok = all(x <= float(tolerance_deg) for x in local)
                within += int(ok)
                per_residue.append({
                    "residue_index": i + 1,
                    "token": residue.get("token"),
                    "phi_deg": round(float(phi), 3) if phi is not None else None,
                    "psi_deg": round(float(psi), 3) if psi is not None else None,
                    "phi_abs_error_deg": round(float(phi_diff), 3) if phi_diff is not None else None,
                    "psi_abs_error_deg": round(float(psi_diff), 3) if psi_diff is not None else None,
                    "within_tolerance": bool(ok),
                })
        records.append({
            "conf_id": int(cid),
            "source": source,
            "seed_family": label,
            "target_phi_deg": phi_target,
            "target_psi_deg": psi_target,
            "evaluated_residues": evaluated,
            "residues_within_tolerance": within,
            "within_tolerance_fraction": round(within / evaluated, 4) if evaluated else None,
            "mean_abs_torsion_error_deg": round(sum(diffs) / len(diffs), 3) if diffs else None,
            "per_residue": per_residue,
        })
    return {
        "status": "available" if records else "not_applicable",
        "method": "post-relaxation phi/psi comparison against the deterministic explicit search seed",
        "tolerance_deg": float(tolerance_deg),
        "records": records,
        "claim_guard": "Seed fidelity is a geometry diagnostic only; it is not a folding probability, free energy, or experimental validation.",
        "provenance": "Explicit phi/psi backbone construction concept: Tien et al., PeptideBuilder, PeerJ 2013, doi:10.7717/peerj.80. Pepforge uses its own RDKit chemistry graph and relaxation path.",
    }


def add_canonical_l_backbone_seed_conformers(
    mol,
    atom_ranges: Iterable[Any],
    preferred_labels: Optional[List[str]] = None,
    variants_per_preferred: int = 0,
) -> Dict[int, str]:
    """Add curated canonical-L backbone-basin search seeds.

    All four historical basins remain represented.  Evidence may increase
    sampling around an already defined basin with small deterministic torsion
    perturbations.  No canonical-alpha torsion is transferred to D,
    non-natural, linker, or side-chain-modified peptide units.
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
    preferred = [label for label in (preferred_labels or []) if label in CANONICAL_L_BACKBONE_SEEDS]
    ordered_labels = preferred + [label for label in CANONICAL_L_BACKBONE_SEEDS if label not in preferred]

    def add_seed(label: str, phi_target: float, psi_target: float, suffix: str = "") -> None:
        conf = Chem.Conformer(template)
        applied = 0
        # Some canonical residues (especially Pro) place a target torsion on a
        # bond that RDKit treats as ring-constrained/non-rotatable. A single
        # unavailable dihedral must not discard the entire seed. Apply every
        # backbone torsion that is geometrically settable, then let the normal
        # constrained relaxation + measured phi/psi classifier decide whether
        # the resulting conformer actually belongs to the requested family.
        for i, r in enumerate(residues):
            if i > 0 and all(x is not None for x in (residues[i-1].get("C"), r.get("N"), r.get("CA"), r.get("C"))):
                try:
                    rdMolTransforms.SetDihedralDeg(conf, residues[i-1]["C"], r["N"], r["CA"], r["C"], float(phi_target))
                    applied += 1
                except Exception:
                    pass
            if i < len(residues)-1 and all(x is not None for x in (r.get("N"), r.get("CA"), r.get("C"), residues[i+1].get("N"))):
                try:
                    rdMolTransforms.SetDihedralDeg(conf, r["N"], r["CA"], r["C"], residues[i+1]["N"], float(psi_target))
                    applied += 1
                except Exception:
                    pass
        if applied <= 0:
            return
        try:
            cid = int(mol.AddConformer(conf, assignId=True))
            out[cid] = f"{label}{suffix}"
        except Exception:
            return

    for label in ordered_labels:
        phi_target, psi_target = CANONICAL_L_BACKBONE_SEEDS[label]
        add_seed(label, phi_target, psi_target)
        if label in preferred:
            for variant in range(max(0, int(variants_per_preferred))):
                # Deterministic search jitter around an existing curated basin;
                # this is not a literature-derived new torsion assignment.
                delta = 7.5 * (variant + 1)
                sign = -1.0 if variant % 2 else 1.0
                add_seed(label, phi_target + sign * delta, psi_target - sign * delta, f"_guided_variant{variant + 1}")
    return out
