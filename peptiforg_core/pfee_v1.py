"""Pepforge Peptide Ensemble Engine (PFEE) v1 search planning and selection.

PFEE v1 is deliberately conservative.  It orchestrates transparent search
metadata, candidate-pool accounting and geometry-diversity selection around the
existing PSB/RDKit engine.  It does not claim thermodynamic populations, native
structures, free energies or binding affinities.
"""
from __future__ import annotations

from math import inf
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


_CANONICAL_SIDECHAIN_PKA = {
    "D": 3.9,
    "E": 4.3,
    "H": 6.0,
    "C": 8.3,
    "Y": 10.1,
    "K": 10.5,
    "R": 12.5,
}


def _as_float(value: Any, default: float, *, name: str) -> float:
    if value in (None, ""):
        return float(default)
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc


def normalize_pfee_environment(environment_conditions: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Normalize PFEE environment metadata with conservative validation."""
    src = dict(environment_conditions or {})
    ph = _as_float(src.get("pH"), 7.0, name="pH")
    ionic = _as_float(src.get("ionic_strength_mM"), 150.0, name="ionic_strength_mM")
    temp_c = _as_float(src.get("temperature_C"), 25.0, name="temperature_C")
    if not 0.0 <= ph <= 14.0:
        raise ValueError("pH must be between 0 and 14")
    if ionic < 0.0:
        raise ValueError("ionic_strength_mM must be >= 0")
    if not -20.0 <= temp_c <= 120.0:
        raise ValueError("temperature_C must be between -20 and 120 for PFEE v1 context recording")
    solvent = str(src.get("environment") or src.get("solvent") or "aqueous_unspecified").strip() or "aqueous_unspecified"
    return {
        "pH": ph,
        "ionic_strength_mM": ionic,
        "temperature_C": temp_c,
        "environment": solvent,
        "source": "user_or_default_context",
        "used_as_explicit_coordinate_energy_model": False,
    }


def canonical_charge_proxy(sequence: str, pH: float, *, n_term_free: bool = True, c_term_free: bool = True) -> Dict[str, Any]:
    """Approximate canonical-peptide net-charge proxy via Henderson-Hasselbalch."""
    seq = str(sequence or "").upper()
    if any(aa not in "ACDEFGHIKLMNPQRSTVWY" for aa in seq):
        raise ValueError("canonical_charge_proxy accepts canonical one-letter amino-acid sequences only")

    positive = 0.0
    negative = 0.0
    for aa in seq:
        if aa in {"K", "R", "H"}:
            pka = _CANONICAL_SIDECHAIN_PKA[aa]
            positive += 1.0 / (1.0 + 10.0 ** (pH - pka))
        elif aa in {"D", "E", "C", "Y"}:
            pka = _CANONICAL_SIDECHAIN_PKA[aa]
            negative += 1.0 / (1.0 + 10.0 ** (pka - pH))
    if n_term_free:
        positive += 1.0 / (1.0 + 10.0 ** (pH - 8.0))
    if c_term_free:
        negative += 1.0 / (1.0 + 10.0 ** (3.1 - pH))
    net = positive - negative
    return {
        "method": "Henderson-Hasselbalch canonical-residue charge proxy",
        "pH": float(pH),
        "positive_charge_proxy": round(positive, 4),
        "negative_charge_proxy": round(negative, 4),
        "net_charge_proxy": round(net, 4),
        "absolute_charge_density_proxy": round(abs(net) / max(1, len(seq)), 4),
        "claim_guard": "Approximate canonical-residue screening descriptor; not a protonation microstate, pKa prediction, or free-energy calculation.",
    }


def pfee_search_plan(
    sequence_evidence: Dict[str, Any],
    base_family_plan: Dict[str, Any],
    environment_conditions: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Return PFEE v1 environment-aware search and representative-selection plan."""
    env = normalize_pfee_environment(environment_conditions)
    evidence = dict(sequence_evidence or {})
    base = dict(base_family_plan or {})
    budget = dict(base.get("budget") or {})
    sequence = str(evidence.get("canonical_L_sequence") or "")
    coverage = float(evidence.get("canonical_L_coverage_fraction") or 0.0)

    charge = None
    adjustments = []
    if sequence and coverage == 1.0:
        charge = canonical_charge_proxy(sequence, env["pH"])
        if abs(float(charge["net_charge_proxy"])) >= 3.0 and env["ionic_strength_mM"] < 50.0:
            old = max(1, int(budget.get("etkdg_multiplier", 1) or 1))
            new = min(4, old + 1)
            if new != old:
                budget["etkdg_multiplier"] = new
                adjustments.append({
                    "type": "sampling_expansion",
                    "reason": "high canonical charge proxy under low ionic-strength context",
                    "old_etkdg_multiplier": old,
                    "new_etkdg_multiplier": new,
                })
    else:
        adjustments.append({
            "type": "no_charge_proxy",
            "reason": "modified/non-canonical chemistry is not canonicalized for PFEE charge estimation",
        })

    threshold = max(0.0, float(budget.get("rmsd_threshold_A", 1.0) or 1.0))
    return {
        "engine": "PFEE_v1",
        "environment": env,
        "canonical_charge_proxy": charge,
        "family_priority": list(base.get("family_priority") or []),
        "family_priority_changed_by_environment": False,
        "budget": budget,
        "adjustments": adjustments,
        "candidate_pool_policy": {
            "reject_severe_steric_clashes": True,
            "retain_requested_structure_priority": True,
            "modified_chemistry_canonicalization": False,
        },
        "representative_selection": {
            "method": "quality-ranked greedy RMSD separation with explicit fallback",
            "minimum_pairwise_rmsd_A": threshold,
            "force_family_diversity": False,
            "fallback_if_pool_too_compact": True,
        },
        "claim_guard": (
            "PFEE v1 uses environment metadata only for transparent search-context handling and optional sampling expansion. "
            "Representative selection uses coordinate diversity as a search-quality criterion, not as a population, free-energy, or affinity estimate."
        ),
    }


def build_candidate_pool(conformation_analysis: Mapping[str, Any]) -> Dict[str, Any]:
    """Summarize the physically usable PFEE candidate pool without inventing scores."""
    rows = [dict(r) for r in (conformation_analysis or {}).get("conformers", [])]
    clean = []
    rejected = []
    for row in rows:
        severe = row.get("severe_steric_clashes")
        severe_n = int(severe) if isinstance(severe, (int, float)) else 0
        if severe_n > 0:
            rejected.append({"conf_id": int(row.get("conf_id", -1)), "reason": "severe_steric_clash", "count": severe_n})
        else:
            clean.append(row)
    families: Dict[str, int] = {}
    sources: Dict[str, int] = {}
    for row in clean:
        family = str(row.get("family") or "unclassified")
        source = str(row.get("source") or row.get("conformer_source") or "unspecified")
        families[family] = families.get(family, 0) + 1
        sources[source] = sources.get(source, 0) + 1
    return {
        "total_candidates": len(rows),
        "usable_candidates": len(clean),
        "rejected_candidates": len(rejected),
        "usable_conf_ids": [int(r.get("conf_id", -1)) for r in clean],
        "family_counts": families,
        "source_counts": sources,
        "rejections": rejected,
        "claim_guard": "Candidate-pool accounting describes generated coordinates and steric screening only; it is not a conformational population estimate.",
    }


def _distance(pairwise_rmsd: Mapping[Tuple[int, int], float], left: int, right: int) -> Optional[float]:
    value = pairwise_rmsd.get(tuple(sorted((int(left), int(right)))))
    return float(value) if isinstance(value, (int, float)) else None


def diversify_ranked_representatives(
    ranked_rows: Sequence[Mapping[str, Any]],
    pairwise_rmsd: Mapping[Tuple[int, int], float] | None,
    *,
    limit: int = 5,
    minimum_rmsd_A: float = 1.0,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Greedily retain quality order while preferring geometrically separated rows.

    The input order remains the quality order established by PSB.  PFEE does not
    re-score energy or force one member per structural family.  It first accepts
    rows separated by ``minimum_rmsd_A`` from already selected representatives;
    if that would return fewer than ``limit`` rows, it fills from the original
    quality order and labels those entries as diversity fallbacks.
    """
    ranked = [dict(r) for r in ranked_rows]
    target = max(1, int(limit))
    threshold = max(0.0, float(minimum_rmsd_A))
    matrix = pairwise_rmsd or {}
    if not ranked:
        return [], {
            "method": "quality-ranked greedy RMSD separation with explicit fallback",
            "requested_count": target,
            "selected_count": 0,
            "minimum_rmsd_A": threshold,
            "fallback_count": 0,
            "status": "empty_candidate_list",
        }

    selected: List[Dict[str, Any]] = []
    used: set[int] = set()
    skipped_compact: List[int] = []

    for row in ranked:
        if len(selected) >= target:
            break
        cid = int(row.get("conf_id", -1))
        if cid in used:
            continue
        distances = [_distance(matrix, cid, int(other.get("conf_id", -1))) for other in selected]
        known = [d for d in distances if d is not None]
        separated = not selected or (len(known) == len(selected) and all(d >= threshold for d in known))
        # Missing RMSD evidence must not be treated as proof of diversity.  It is
        # accepted later only through the explicit quality-order fallback.
        if separated:
            item = dict(row)
            item["pfee_diversity_fallback"] = False
            item["pfee_min_distance_to_previous_A"] = round(min(known), 4) if known else None
            selected.append(item)
            used.add(cid)
        else:
            skipped_compact.append(cid)

    fallback_count = 0
    if len(selected) < target:
        for row in ranked:
            if len(selected) >= target:
                break
            cid = int(row.get("conf_id", -1))
            if cid in used:
                continue
            distances = [_distance(matrix, cid, int(other.get("conf_id", -1))) for other in selected]
            known = [d for d in distances if d is not None]
            item = dict(row)
            item["pfee_diversity_fallback"] = True
            item["pfee_min_distance_to_previous_A"] = round(min(known), 4) if known else None
            selected.append(item)
            used.add(cid)
            fallback_count += 1

    for rank, row in enumerate(selected, 1):
        row["rank"] = rank

    selected_ids = [int(r.get("conf_id", -1)) for r in selected]
    selected_distances: List[float] = []
    for pos, left in enumerate(selected_ids):
        for right in selected_ids[pos + 1:]:
            value = _distance(matrix, left, right)
            if value is not None:
                selected_distances.append(value)
    minimum_observed = min(selected_distances) if selected_distances else None
    status = "threshold_met" if fallback_count == 0 and len(selected) >= min(target, len(ranked)) else "fallback_required"
    audit = {
        "method": "quality-ranked greedy RMSD separation with explicit fallback",
        "requested_count": target,
        "selected_count": len(selected),
        "minimum_rmsd_A": threshold,
        "minimum_observed_pairwise_rmsd_A": round(minimum_observed, 4) if minimum_observed is not None else None,
        "fallback_count": fallback_count,
        "skipped_as_too_similar_conf_ids": skipped_compact,
        "force_family_diversity": False,
        "status": status,
        "claim_guard": "Geometry-diverse representatives are search outputs, not conformational populations, native-state probabilities, or thermodynamic states.",
    }
    return selected, audit


def adaptive_sampling_request(
    selection_audit: Mapping[str, Any],
    candidate_pool: Mapping[str, Any],
    *,
    requested_representatives: int = 5,
    round_index: int = 0,
    max_rounds: int = 2,
    per_round_cap: int = 20,
) -> Dict[str, Any]:
    """Plan an additional *real* conformer sampling round when diversity is insufficient.

    This planner never fabricates candidates or claims improved physical accuracy.
    It only requests more coordinate proposals when the current geometry pool
    required diversity fallback or cannot fill the requested representative count.
    """
    audit = dict(selection_audit or {})
    pool = dict(candidate_pool or {})
    target = max(1, int(requested_representatives))
    current_round = max(0, int(round_index))
    usable = max(0, int(pool.get("usable_candidates", 0) or 0))
    selected = max(0, int(audit.get("selected_count", 0) or 0))
    fallback = max(0, int(audit.get("fallback_count", 0) or 0))
    status = str(audit.get("status") or "unknown")

    needs_more = selected < target or fallback > 0 or status == "fallback_required"
    if not needs_more:
        reason = "representative diversity target met"
        count = 0
    elif current_round >= max(0, int(max_rounds)):
        reason = "adaptive sampling round limit reached"
        count = 0
    else:
        deficit = max(0, target - selected)
        # Ask for a modest oversampled batch because ETKDG embedding, optimization
        # and steric screening can reject or collapse candidates. The count is a
        # search budget, not a scientific confidence score.
        count = min(max(1, int(per_round_cap)), max(target * 2, deficit * 4, min(12, usable // 2 + target)))
        reason = "current pool required diversity fallback or did not fill requested representatives"

    return {
        "request_additional_sampling": bool(count > 0),
        "requested_additional_conformers": int(count),
        "round_index": current_round,
        "max_rounds": max(0, int(max_rounds)),
        "reason": reason,
        "observed_selection_status": status,
        "observed_fallback_count": fallback,
        "observed_usable_candidates": usable,
        "claim_guard": "Adaptive resampling expands coordinate search only; it is not evidence of thermodynamic convergence, population, or native-state probability.",
    }
