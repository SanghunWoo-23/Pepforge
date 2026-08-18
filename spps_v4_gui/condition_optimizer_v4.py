"""Auditable SPPS condition recommendations for V4.0.0.

Recommendations are evidence-first. Repeated successful historical conditions are
preferred over model output. The module does not synthesize reagent identities or
mix parts of unrelated experiments into a new chemistry condition.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import math
import re
from typing import Any, Iterable, Mapping

from spps_v4_gui import ml_dataset


def _num(value: Any) -> float | None:
    try:
        number = float(str(value).replace(",", "").strip())
        return number if math.isfinite(number) else None
    except Exception:
        return None


def _resin_family(value: Any) -> str:
    text = str(value or "").lower()
    return "CTC/Trityl" if any(k in text for k in ("ctc", "trityl", "chlorotrityl")) else "Amide/Rink"


def _sequence_features(sequence: Any) -> dict[str, float]:
    text = str(sequence or "")
    try:
        from spps_planner.parser import parse_sequence
        parsed = parse_sequence(text)
        tokens = [str(t) for t in (list(parsed.core_tokens or []) + list(getattr(parsed, "branch_tokens", []) or []))]
        aa = [re.sub(r"^d", "", t, flags=re.I).upper() for t in tokens]
    except Exception:
        aa = list("".join(ch for ch in text.upper() if ch in "ACDEFGHIKLMNPQRSTVWY"))
    n = max(1, len(aa))
    return {
        "length": float(len(aa)),
        "hydrophobic_fraction": sum(x in set("AILMFWVY") for x in aa) / n,
        "charged_fraction": sum(x in set("DEKR") for x in aa) / n,
        "pro_fraction": aa.count("P") / n,
        "gly_fraction": aa.count("G") / n,
        "cys_fraction": aa.count("C") / n,
    }


def _feature_distance(a: Mapping[str, float], b: Mapping[str, float]) -> float:
    return (
        abs(a["length"] - b["length"]) * 0.08
        + abs(a["hydrophobic_fraction"] - b["hydrophobic_fraction"]) * 4.0
        + abs(a["charged_fraction"] - b["charged_fraction"]) * 2.5
        + abs(a["pro_fraction"] - b["pro_fraction"]) * 2.0
        + abs(a["gly_fraction"] - b["gly_fraction"]) * 1.5
        + abs(a["cys_fraction"] - b["cys_fraction"]) * 1.5
    )


def _review(item: Mapping[str, Any]) -> dict[str, Any]:
    return ml_dataset.normalize_review(item.get(ml_dataset.REVIEW_KEY)).get("current", {})


def _outcome_score(review: Mapping[str, Any]) -> tuple[float | None, list[str]]:
    purity = _num(review.get("actual_purity_percent"))
    yield_pct = _num(review.get("actual_yield_percent"))
    failed = review.get("failure_flag")
    if purity is None and yield_pct is None and failed is None:
        return None, []
    score = 0.0
    notes: list[str] = []
    weight = 0.0
    if purity is not None:
        score += max(0.0, min(100.0, purity)) / 100.0 * 0.55
        weight += 0.55
        notes.append(f"purity {purity:.1f}%")
    if yield_pct is not None:
        score += max(0.0, min(100.0, yield_pct)) / 100.0 * 0.30
        weight += 0.30
        notes.append(f"yield {yield_pct:.1f}%")
    if failed is False:
        score += 0.15
        weight += 0.15
        notes.append("failure=No")
    elif failed is True:
        score -= 0.45
        weight += 0.15
        notes.append("failure=Yes")
    if weight <= 0:
        return None, notes
    return score / weight, notes


def _compound_key(value: Any) -> str:
    text = str(value or "").strip()
    try:
        from spps_v4_gui import catalogs
        text = catalogs.canonical_unit_name(text)
    except Exception as exc:
        _canonicalization_error = exc
    return re.sub(r"\s+", "", text).lower()


def _compound_category(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return "unknown"
    if any(k in text for k in ("his6", "his8", "his10", "flag", "myc", "strep", "avitag", "spytag", "alfatag", "ha tag", "v5 tag")):
        return "tag"
    if any(k in text for k in ("aeea", "ahx", "peg", "beta-ala", "β-ala", "bala", "linker")):
        return "linker"
    if any(k in text for k in ("fam", "fitc", "tamra", "cy3", "cy5", "dabcyl", "edans", "dota", "nota", "dfo", "biotin", "palmit", "gallic", "chol", "acetyl", "chemical", "label")):
        return "chemical/label"
    if "fmoc-" in text or re.fullmatch(r"d?[acdefghiklmnpqrstvwy]", text):
        return "amino acid"
    return "chemical/label"


def _rounded(value: Any, digits: int = 4) -> float | None:
    number = _num(value)
    return None if number is None else round(number, digits)


def _row_condition(row: Mapping[str, Any], item: Mapping[str, Any]) -> dict[str, Any]:
    scale = _num(item.get("scale"))
    unit_mmol = _num(row.get("Unit mmol"))
    unit_eq = _num(row.get("Unit eq"))
    if unit_eq is None and scale and scale > 0 and unit_mmol is not None:
        unit_eq = unit_mmol / scale

    def eq_from_mmol(field: str, fallback: str) -> float | None:
        mmol = _num(row.get(field))
        if scale and scale > 0 and mmol is not None:
            return mmol / scale
        return _num(item.get(fallback))

    solvent_ml = _num(row.get("Solvent mL"))
    ml_per_mmol = solvent_ml / scale if scale and scale > 0 and solvent_ml is not None else None
    return {
        "coupling_eq": _rounded(unit_eq if unit_eq is not None else item.get("coupling_eq")),
        "coupling_repeats": int(round(_num(row.get("Repeat")) or _num(item.get("coupling_repeats")) or 1)),
        "coupling_time_h": _rounded(item.get("coupling_time_h"), 3),
        "default_reagent": str(row.get("Reagent 1") or item.get("default_reagent") or "").strip(),
        "default_reagent_eq": _rounded(eq_from_mmol("R1 mmol", "default_reagent_eq")),
        "default_catalyst": str(row.get("Reagent 2 / catalyst") or item.get("default_catalyst") or "").strip(),
        "default_catalyst_eq": _rounded(eq_from_mmol("R2 mmol", "default_catalyst_eq")),
        "default_base": str(row.get("Base") or item.get("default_base") or "").strip(),
        "default_base_eq": _rounded(eq_from_mmol("Base mmol", "default_base_eq")),
        "default_coupling_solution_solvent": str(row.get("Coupling solvent") or item.get("default_coupling_solution_solvent") or "").strip(),
        "coupling_solvent_ml_per_mmol": _rounded(ml_per_mmol, 4),
        "solvent_volume_mode": item.get("solvent_volume_mode"),
        "solvent_molarity_m": _rounded(item.get("solvent_molarity_m"), 4),
        "amide_ml_per_mmol": _rounded(item.get("amide_ml_per_mmol"), 4),
        "ctc_ml_per_mmol": _rounded(item.get("ctc_ml_per_mmol"), 4),
    }


def _condition_signature(condition: Mapping[str, Any]) -> tuple[Any, ...]:
    fields = (
        "coupling_eq", "coupling_repeats", "coupling_time_h", "default_reagent", "default_reagent_eq",
        "default_catalyst", "default_catalyst_eq", "default_base", "default_base_eq",
        "default_coupling_solution_solvent", "coupling_solvent_ml_per_mmol",
    )
    values: list[Any] = []
    for field in fields:
        value = condition.get(field)
        values.append(str(value).strip().lower() if isinstance(value, str) else value)
    return tuple(values)


def _current_units(item: Mapping[str, Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in item.get("selected_plan_rows", []) or []:
        if not isinstance(row, Mapping):
            continue
        name = str(row.get("Unit name") or "").strip()
        key = _compound_key(name)
        if not key or key in seen:
            continue
        low_note = str(row.get("Note") or "").lower()
        if any(term in low_note for term in ("deprotection", "wash", "loading")):
            continue
        seen.add(key)
        out.append({"compound": name, "compound_key": key, "category": _compound_category(name)})
    return out


def coupling_advice(items: Iterable[Any], current_item: Mapping[str, Any]) -> dict[str, Any]:
    """Recommend coupling conditions with repeated successful history first.

    Exact bottle-level compound consensus requires at least two successful reviewed
    occurrences with the same full condition. Category consensus is allowed only
    when no exact consensus exists and the same full condition repeats at least two
    times within the same building-block category.
    """
    current_features = _sequence_features(current_item.get("sequence", ""))
    current_family = _resin_family(current_item.get("resin", ""))
    historical_rows: list[dict[str, Any]] = []
    item_evidence: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, Mapping) or item is current_item:
            continue
        review = _review(item)
        if not review.get("reviewed") or not review.get("included"):
            continue
        outcome, outcome_notes = _outcome_score(review)
        if outcome is None:
            continue
        failed = review.get("failure_flag") is True
        distance = _feature_distance(current_features, _sequence_features(item.get("sequence", "")))
        if _resin_family(item.get("resin", "")) != current_family:
            distance += 2.5
        item_evidence.append({
            "work_item_id": item.get("work_item_id", ""), "project": item.get("project", ""),
            "peptide": item.get("peptide", ""), "sequence": item.get("sequence", ""), "resin": item.get("resin", ""),
            "distance": distance, "outcome_score": outcome, "outcome_notes": ", ".join(outcome_notes), "failed": failed,
        })
        if failed:
            continue
        for row in item.get("selected_plan_rows", []) or []:
            if not isinstance(row, Mapping):
                continue
            compound = str(row.get("Unit name") or "").strip()
            key = _compound_key(compound)
            if not key:
                continue
            historical_rows.append({
                "compound": compound, "compound_key": key, "category": _compound_category(compound),
                "resin_family": _resin_family(item.get("resin", "")),
                "condition": _row_condition(row, item), "work_item_id": item.get("work_item_id", ""),
                "project": item.get("project", ""), "peptide": item.get("peptide", ""), "sequence": item.get("sequence", ""),
                "resin": item.get("resin", ""), "distance": distance, "outcome_score": outcome,
                "outcome_notes": ", ".join(outcome_notes),
            })

    units = _current_units(current_item)
    unit_recommendations: list[dict[str, Any]] = []
    warnings: list[str] = []
    for unit in units:
        exact = [r for r in historical_rows if r["compound_key"] == unit["compound_key"] and r["resin_family"] == current_family]
        exact_counter = Counter(_condition_signature(r["condition"]) for r in exact)
        exact_sig, exact_n = (exact_counter.most_common(1)[0] if exact_counter else (None, 0))
        source_rows: list[dict[str, Any]] = []
        kind = ""
        if exact_sig is not None and exact_n >= 2:
            source_rows = [r for r in exact if _condition_signature(r["condition"]) == exact_sig]
            kind = "HISTORICAL CONSENSUS"
        else:
            category = [r for r in historical_rows if r["category"] == unit["category"] and r["resin_family"] == current_family]
            cat_counter = Counter(_condition_signature(r["condition"]) for r in category)
            cat_sig, cat_n = (cat_counter.most_common(1)[0] if cat_counter else (None, 0))
            if cat_sig is not None and cat_n >= 2:
                source_rows = [r for r in category if _condition_signature(r["condition"]) == cat_sig]
                kind = "CATEGORY CONSENSUS"
        if not source_rows:
            unit_recommendations.append({**unit, "recommendation_kind": "INSUFFICIENT EVIDENCE", "apply_allowed": False, "evidence_count": len(exact)})
            continue
        representative = min(source_rows, key=lambda r: (r["distance"], -r["outcome_score"]))
        unit_recommendations.append({
            **unit, "recommendation_kind": kind, "apply_allowed": True,
            "evidence_count": len(source_rows), "condition": dict(representative["condition"]),
            "source_projects": sorted({str(r["project"]) for r in source_rows if r.get("project")}),
            "source_outcomes": sorted({str(r["outcome_notes"]) for r in source_rows if r.get("outcome_notes")}),
        })

    actionable = [r for r in unit_recommendations if r.get("apply_allowed")]
    signatures = Counter(_condition_signature(r["condition"]) for r in actionable if r.get("condition"))
    global_rec = None
    if signatures:
        sig, count = signatures.most_common(1)[0]
        matching = [r for r in actionable if _condition_signature(r["condition"]) == sig]
        # A global Planner change is safe only when every actionable current unit agrees.
        if matching and count == len(actionable) and len(actionable) == len(unit_recommendations):
            condition = dict(matching[0]["condition"])
            global_rec = {
                **condition,
                "recommendation_kind": matching[0]["recommendation_kind"],
                "condition_evidence_count": sum(int(r.get("evidence_count", 0)) for r in matching),
                "covered_units": [r["compound"] for r in matching],
                "apply_allowed": True,
                "source_project": ", ".join(sorted({p for r in matching for p in r.get("source_projects", [])})),
                "source_peptide": "multiple reviewed experiments",
                "source_outcome": "repeated successful condition",
                "distance": 0.0,
            }
        elif actionable:
            warnings.append("Current building blocks have different supported coupling conditions. Review per-unit recommendations; global Apply is disabled to avoid overwriting distinct conditions.")
    if not historical_rows:
        warnings.append("No successful operator-reviewed coupling rows are available yet. Use Record Coupling after experiments to build evidence.")
    elif not actionable:
        warnings.append("No coupling condition repeats enough to support an automatic recommendation for the current building blocks.")

    confidence = "LOW"
    if actionable and all(int(r.get("evidence_count", 0)) >= 4 for r in actionable):
        confidence = "HIGH"
    elif actionable:
        confidence = "MEDIUM"
    item_evidence.sort(key=lambda r: (r["distance"], -r["outcome_score"]))
    return {
        "method": "historical consensus by bottle-level compound, then repeated category condition",
        "confidence": confidence,
        "evidence_count": len(historical_rows),
        "recommended_condition": global_rec,
        "unit_recommendations": unit_recommendations,
        "warnings": warnings,
        "evidence": item_evidence[:12],
    }


def parse_ether_ratio(value: Any) -> float | None:
    text = str(value or "").strip().replace(" ", "")
    match = re.fullmatch(r"(?:1[:：])?(\d+(?:\.\d+)?)", text)
    if not match:
        return None
    number = float(match.group(1))
    return number if number > 0 else None


__all__ = ["coupling_advice", "parse_ether_ratio"]
