from __future__ import annotations

"""Literature-scoped SPPS aggregation evidence for the public V5 workflow.

The 2026 AFPS study by Tamas et al. is used as *qualitative evidence only*.
Its trained model and private/internal data are not reproduced here.  Pepforge
therefore reports composition/context flags, not an aggregation probability.
"""

from collections import Counter
from typing import Any

AGGREGATION_EVIDENCE_VERSION = "1.1.0"
AFPS_PRIMARY_ASSOCIATED = {"S", "V", "I", "T"}
AFPS_SECONDARY_ASSOCIATED = {"Q", "L"}
AFPS_LOWER_CONTRIBUTION_CONTEXT = {"F", "D", "Y", "R", "C", "H", "P"}
PSEUDOPROLINE_ELIGIBLE = {"S", "T"}


def _core_tokens(sequence: str) -> tuple[list[str], list[str]]:
    warnings=[]
    try:
        # Import through the package path first so this evidence module also
        # works when it is called directly (candidate summaries, CLI/tests),
        # before the desktop GUI has added ``apps/spps_planner_app`` to
        # ``sys.path``.  Keep the short import as a frozen/legacy fallback.
        try:
            from apps.spps_planner_app.spps_planner.parser import parse_sequence
        except ImportError:
            from spps_planner.parser import parse_sequence
        parsed=parse_sequence(str(sequence or ""))
        tokens=[str(x) for x in (parsed.core_tokens or [])]
        warnings.extend(list(getattr(parsed, "warnings", []) or []))
        return tokens, warnings
    except Exception as exc:
        return [], [str(exc)]


def literature_aggregation_evidence(sequence: str) -> dict[str, Any]:
    tokens, warnings = _core_tokens(sequence)
    canonical=[]
    for token in tokens:
        t=str(token).strip()
        # The 2026 AFPS model explicitly filtered non-canonical residues.  D-amino
        # acids therefore remain out-of-domain here rather than being silently
        # collapsed onto the corresponding L residue.
        if len(t) == 2 and t[0].lower() == "d":
            canonical.append("")
            continue
        aa=t.upper()
        canonical.append(aa if len(aa)==1 and aa in "ARNDCQEGHILKMFPSTWYV" else "")
    canonical_count = sum(bool(x) for x in canonical)
    out_of_domain_count = sum(not bool(x) for x in canonical)
    total_core_count = len(canonical)
    counts=Counter(x for x in canonical if x)
    associated_positions=[]; pseudoproline_positions=[]; aggregation_window_positions=[]
    # Resin-side position 1 is the C-terminal residue in an Fmoc synthesis.
    for nterm_pos, aa in enumerate(canonical, start=1):
        if not aa: continue
        resin_pos=len(canonical)-nterm_pos+1
        if aa in AFPS_PRIMARY_ASSOCIATED:
            associated_positions.append({"sequence_position":nterm_pos,"resin_side_position":resin_pos,"residue":aa,"evidence_tier":"primary_reported_contributor"})
        if 5 <= resin_pos <= 15:
            aggregation_window_positions.append({"sequence_position":nterm_pos,"resin_side_position":resin_pos,"residue":aa})
        if aa in PSEUDOPROLINE_ELIGIBLE and 2 <= resin_pos <= 12:
            pseudoproline_positions.append({"sequence_position":nterm_pos,"resin_side_position":resin_pos,"residue":aa,"status":"literature_mitigation_candidate_only"})
    fraction = (
        sum(counts[x] for x in AFPS_PRIMARY_ASSOCIATED) / canonical_count
        if canonical_count else None
    )
    secondary_positions=[]
    lower_context_positions=[]
    for nterm_pos, aa in enumerate(canonical, start=1):
        if not aa:
            continue
        resin_pos=len(canonical)-nterm_pos+1
        if aa in AFPS_SECONDARY_ASSOCIATED:
            secondary_positions.append({"sequence_position":nterm_pos,"resin_side_position":resin_pos,"residue":aa,"evidence_tier":"secondary_reported_contributor"})
        if aa in AFPS_LOWER_CONTRIBUTION_CONTEXT:
            lower_context_positions.append({"sequence_position":nterm_pos,"resin_side_position":resin_pos,"residue":aa,"evidence_tier":"reported_lower_model_contribution_context"})
    if not tokens:
        status = "unavailable"
        applicability = "not_available"
        domain_interpretation = "No core residues were resolved, so the AFPS canonical-L literature context was not applied."
    elif canonical_count == 0:
        status = "out_of_domain"
        applicability = "outside_AFPS_canonical_L_domain"
        domain_interpretation = "All resolved core positions are D-amino-acid, non-natural, modified, or otherwise outside the canonical-L AFPS evidence domain."
    elif out_of_domain_count:
        status = "partial_out_of_domain"
        applicability = "partial_AFPS_canonical_L_subset_only"
        domain_interpretation = "Only the canonical-L subset is evaluated; D-amino-acid, non-natural, modified, or unresolved positions are excluded rather than canonicalized."
    else:
        status = "available"
        applicability = "limited_AFPS_canonical_L_sequence_only"
        domain_interpretation = "All core positions are canonical-L residues, but this remains sequence-only qualitative literature context rather than a synthesis-failure model."

    return {
        "version": AGGREGATION_EVIDENCE_VERSION,
        "status": status,
        "canonical_residue_count": canonical_count,
        "out_of_domain_core_count": out_of_domain_count,
        "modified_or_unresolved_core_count": out_of_domain_count,
        "core_residue_count": total_core_count,
        "canonical_subset_fraction_of_core": round(canonical_count / total_core_count, 4) if total_core_count else None,
        "composition_fraction_S_V_I_T": round(fraction, 4) if fraction is not None else None,
        "composition_counts": {aa:int(counts.get(aa,0)) for aa in sorted(AFPS_PRIMARY_ASSOCIATED)},
        "AFPS_primary_associated_positions": associated_positions,
        "AFPS_secondary_associated_positions": secondary_positions,
        "AFPS_reported_lower_contribution_context_positions": lower_context_positions,
        "literature_resin_side_5_to_15_window": aggregation_window_positions,
        "literature_resin_side_5_to_15_window_count": len(aggregation_window_positions),
        "resin_side_2_to_12_pseudoproline_candidate_positions": pseudoproline_positions,
        "interpretation": (
            "Composition/context evidence from an AFPS canonical-L peptide study. Ser(tBu), Ile, Val and Thr(tBu) were the strongest positive model contributors; "
            "Gln(Trt) and Leu were also reported as major contributors, while several other protected residues showed lower model contribution. Literature notes aggregation commonly appears 5-15 residues from the resin anchoring point; "
            "the study's pseudoproline mitigation analysis examined S/T contributions in resin-side positions 2-12. Sequence-only Pepforge review cannot verify the exact protection/synthesis context. "
            "These are review signals, not a Pepforge failure probability or a universal batch-SPPS rule."
        ),
        "applicability": applicability,
        "domain_interpretation": domain_interpretation,
        "automatic_plan_change_allowed": False,
        "warnings": warnings,
        "literature": ["DOI:10.1038/s41557-026-02090-0"],
        "claim_guard": (
            "No aggregation probability is calculated. No pseudoproline substitution is automatically applied. Non-canonical and D-amino-acid positions are outside this literature model domain and are not silently converted to L residues. "
            "Actual resin, loading, chemistry, temperature, protecting groups and local experimental history remain independent evidence."
        ),
    }


__all__ = ["AGGREGATION_EVIDENCE_VERSION", "literature_aggregation_evidence"]
