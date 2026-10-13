"""Lightweight V5 empirical cleavage fallback.

Priority is deliberately conservative:
1) operator-defined Cys override: 100 TFA eq per Cys, independent of mer count,
2) optional operator-approved exact sequence anchor (Private data only),
3) exact historical condition handled by the canonical history advisor,
4) sequence-similar historical residual correction,
5) generic monotonic length baseline + TFA/water/TIS chemistry fallback.

This module never fabricates a historical record. Estimated values are explicitly
labelled empirical/model fallback and are separate from observed evidence.
"""
from __future__ import annotations

from collections import Counter
import csv
import math
from pathlib import Path
from typing import Any, Iterable

from suite_gui import experimental_data

# Public-safe generic operational curve.  It is intentionally conservative and
# monotonic.  <=5mer stays <=20 eq unless sequence-specific chemistry/history says
# otherwise.  >=15/22mer preserves the established V4 80/100 eq classes.
_LENGTH_ANCHORS: tuple[tuple[int, float], ...] = (
    (1, 8.0), (2, 10.0), (3, 15.0), (4, 18.0), (5, 20.0),
    (6, 30.0), (8, 35.0), (10, 45.0), (12, 50.0), (14, 60.0),
    (15, 80.0), (18, 88.0), (21, 95.0), (22, 100.0),
)
_SENSITIVE = {"C", "M", "W", "Y"}
_NATURAL = set("ARNDCQEGHILKMFPSTWYV")


def _num(value: Any) -> float | None:
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except Exception:
        return None


def _round_eq(value: float) -> float:
    # Bench records are generally integer eq. Keep special short values (e.g. 18)
    # possible while avoiding false decimal precision.
    return float(int(round(float(value))))


def generic_length_eq(length: int) -> float:
    n = max(1, int(length or 1))
    if n <= _LENGTH_ANCHORS[0][0]:
        return _LENGTH_ANCHORS[0][1]
    if n >= _LENGTH_ANCHORS[-1][0]:
        return _LENGTH_ANCHORS[-1][1]
    for (x0, y0), (x1, y1) in zip(_LENGTH_ANCHORS, _LENGTH_ANCHORS[1:]):
        if x0 <= n <= x1:
            if x1 == x0:
                return y1
            frac = (n - x0) / (x1 - x0)
            return _round_eq(y0 + frac * (y1 - y0))
    return 30.0


def _parse(sequence: str) -> dict[str, Any] | None:
    try:
        from spps_planner.parser import parse_sequence
        parsed = parse_sequence(str(sequence or ""))
        raw_tokens = list(parsed.core_tokens or []) + list(getattr(parsed, "branch_tokens", []) or [])
        if not raw_tokens:
            return None
        tokens: list[str] = []
        for token in raw_tokens:
            text = str(token).strip()
            if len(text) == 2 and text[0].lower() == "d" and text[1].upper() in _NATURAL:
                tokens.append(text[1].upper())
            elif len(text) == 1 and text.upper() in _NATURAL:
                tokens.append(text.upper())
            else:
                # Preserve modified/non-natural tokens as their own symbols so they
                # affect edit similarity without pretending they are a natural AA.
                tokens.append(text.upper())
        return {
            "tokens": tuple(tokens),
            "length": len(tokens),
            "nterm": str(getattr(parsed, "nterm", "") or "").strip().upper(),
            "cterm": str(getattr(parsed, "cterm_text", "") or "").strip().upper(),
            "sensitive": tuple(sorted(x for x in tokens if x in _SENSITIVE)),
            "cys_count": sum(1 for x in tokens if x == "C"),
        }
    except Exception:
        return None


def _edit_distance(a: tuple[str, ...], b: tuple[str, ...]) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(cur[-1] + 1, prev[j] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def _category_vector(tokens: tuple[str, ...]) -> tuple[float, ...]:
    n = max(1, len(tokens))
    groups = (
        set("RKH"), set("DE"), set("STNQ"), set("AVLIFPG"), set("FYW"), set("CM"),
    )
    return tuple(sum(1 for x in tokens if x in group) / n for group in groups)


def sequence_similarity(current: dict[str, Any], observed: dict[str, Any]) -> float:
    a = current["tokens"]; b = observed["tokens"]
    if not a or not b:
        return 0.0
    length_score = max(0.0, 1.0 - abs(len(a) - len(b)) / max(len(a), len(b), 4))
    edit_score = max(0.0, 1.0 - _edit_distance(a, b) / max(len(a), len(b)))
    va = _category_vector(a); vb = _category_vector(b)
    comp_score = max(0.0, 1.0 - sum(abs(x - y) for x, y in zip(va, vb)) / 2.0)
    sa = {x for x in a if x in _NATURAL}; sb = {x for x in b if x in _NATURAL}
    union = sa | sb
    set_score = (len(sa & sb) / len(union)) if union else 0.0
    nterm_score = 1.0 if current.get("nterm") == observed.get("nterm") else 0.0
    sensitive_score = 1.0 if Counter(current.get("sensitive", ())) == Counter(observed.get("sensitive", ())) else 0.0
    return max(0.0, min(1.0,
        0.34 * length_score + 0.24 * comp_score + 0.22 * edit_score +
        0.10 * set_score + 0.05 * nterm_score + 0.05 * sensitive_score
    ))


def _sequence_match(a: str, b: str) -> bool:
    sa = experimental_data.sequence_signature(a)
    sb = experimental_data.sequence_signature(b)
    if not sa or not sb:
        return experimental_data.canonical_sequence_key(a) == experimental_data.canonical_sequence_key(b)
    an, at, ac = sa; bn, bt, bc = sb
    if an != bn or at != bt:
        return False
    return not (ac and bc and ac != bc)


def _anchor_file() -> Path:
    return Path(__file__).resolve().parents[2] / "apps" / "spps_planner_app" / "data" / "experimental_seed" / "cleavage_empirical_anchors_seed.csv"


def cys_equivalent_override(sequence: str, scale_mmol: Any = None, *, resin: str = "") -> dict[str, Any] | None:
    """Operator-defined hard rule: 100 TFA equivalents per Cys residue.

    The Cys rule overrides peptide-length and similar-sequence eq estimation.
    It changes the cleavage amount/equivalents only; cocktail composition remains
    selected by the existing sensitive-residue fallback unless a future explicit
    operator rule specifies otherwise.
    """
    parsed = _parse(sequence)
    if not parsed:
        return None
    cys_count = int(parsed.get("cys_count") or 0)
    if cys_count <= 0:
        return None
    eq = float(100 * cys_count)
    n = int(parsed.get("length") or 0)
    composition = {"TFA": 95.0, "TIS": 2.5, "Water": 2.5}
    cocktail_basis = "Cys-sensitive default cocktail; Cys rule itself controls TFA equivalents only"
    scale = _num(scale_mmol)
    factor = 0.5 if "ctc" in str(resin or "").lower() or "trityl" in str(resin or "").lower() else 1.0
    total = scale * eq * factor if scale is not None and scale > 0 else None
    return {
        "sequence": sequence,
        "sequence_length": n,
        "cleavage_eq": eq,
        "cleavage_eq_range": [eq, eq],
        "cleavage_time_h": 3.0,
        "preset": "DEFAULT_TFA_TIS_WATER",
        "composition_pct": composition,
        "scaled_total_ml": total,
        "volume_apply_allowed": bool(total is not None and total > 0),
        "apply_allowed": True,
        "basis": f"operator Cys rule: {cys_count} Cys × 100 eq = {eq:g} eq; {cocktail_basis}",
        "eq_basis": "operator hard rule: 100 TFA eq per Cys; mer count and historical-neighbor adjustment do not change the eq",
        "time_basis": "general 3 h fallback; replace with explicit SOP/time evidence when available",
        "condition_source": "operator_cys_rule",
        "recommendation_kind": "OPERATOR CYS RULE",
        "empirical_estimate": {
            "kind": "operator_cys_rule", "confidence": "HIGH",
            "baseline_eq": generic_length_eq(max(1, n)),
            "neighbor_adjustment_eq": 0.0, "neighbor_count": 0,
            "neighbors": [], "cocktail_basis": cocktail_basis,
            "sensitive_residues": list(parsed.get("sensitive") or ()),
            "cys_count": cys_count, "cys_eq_each": 100.0,
        },
    }


def operator_anchor(sequence: str, scale_mmol: Any = None) -> dict[str, Any] | None:
    """Read an optional exact operator-approved anchor. Public builds have no file."""
    path = _anchor_file()
    if not path.is_file() or not str(sequence or "").strip():
        return None
    try:
        rows = list(csv.DictReader(path.open("r", encoding="utf-8-sig", newline="")))
    except Exception:
        return None
    for row in rows:
        observed = str(row.get("sequence") or "").strip()
        if not observed or not _sequence_match(observed, sequence):
            continue
        eq = _num(row.get("cleavage_eq")); time_h = _num(row.get("cleavage_time_h")) or 3.0
        if eq is None:
            continue
        composition: dict[str, float] = {}
        raw = str(row.get("composition") or "").strip()
        for part in raw.replace(",", ";").split(";"):
            if "=" not in part:
                continue
            name, value = part.split("=", 1)
            num = _num(str(value).replace("%", "").strip())
            if num is not None and num > 0:
                composition[name.strip()] = num
        if not composition:
            composition = {"TFA": 95.0, "Water": 5.0}
        scale = _num(scale_mmol)
        factor = 1.0
        total = scale * eq * factor if scale is not None and scale > 0 else None
        return {
            "sequence": sequence,
            "sequence_length": (_parse(sequence) or {}).get("length"),
            "cleavage_eq": eq,
            "cleavage_eq_range": [max(1.0, eq - 2.0), eq + 2.0],
            "cleavage_time_h": time_h,
            "preset": "",
            "composition_pct": composition,
            "scaled_total_ml": total,
            "volume_apply_allowed": bool(total is not None and total > 0),
            "apply_allowed": True,
            "basis": str(row.get("source_note") or "operator-approved exact sequence anchor"),
            "eq_basis": "operator-approved exact sequence anchor",
            "time_basis": "operator-approved exact sequence anchor",
            "condition_source": "operator_approved_anchor",
            "recommendation_kind": "OPERATOR ANCHOR",
            "empirical_estimate": {
                "kind": "operator_anchor", "confidence": "HIGH", "neighbor_count": 0,
                "baseline_eq": generic_length_eq((_parse(sequence) or {}).get("length", 1)),
            },
        }
    return None


def _product_sequences(db_path: str | Path | None) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    root = Path(__file__).resolve().parents[2] / "apps" / "spps_planner_app" / "data" / "experimental_seed"
    for filename in ("cleavage_sequence_map_seed.csv", "synthesis_sequence_history_seed.csv"):
        path = root / filename
        if not path.is_file():
            continue
        try:
            rows = csv.DictReader(path.open("r", encoding="utf-8-sig", newline=""))
            for row in rows:
                product = row.get("product_key") or row.get("product") or ""
                key = experimental_data.canonical_product_key(product)
                seq = str(row.get("sequence") or "").strip()
                if key and seq:
                    out.setdefault(key, set()).add(seq)
        except Exception:
            pass
    try:
        for row in experimental_data.list_records("sequence", db_path, statuses=["verified", "parsed"]):
            key = experimental_data.canonical_product_key(row.get("product"))
            seq = str(row.get("sequence") or "").strip()
            if key and seq:
                out.setdefault(key, set()).add(seq)
    except Exception:
        pass
    return out


def _historical_neighbors(sequence: str, db_path: str | Path | None, limit: int = 6) -> list[dict[str, Any]]:
    current = _parse(sequence)
    if not current:
        return []
    mapping = _product_sequences(db_path)
    try:
        rows = experimental_data.list_records("cleavage", db_path, statuses=["verified", "parsed"])
    except Exception:
        rows = []
    best_by_key: dict[tuple[str, float, str], dict[str, Any]] = {}
    for row in rows:
        eq = _num(row.get("cleavage_eq"))
        if eq is None or eq <= 0:
            continue
        seqs: set[str] = set()
        stored = str(row.get("sequence") or "").strip()
        if stored:
            seqs.add(stored)
        pkey = experimental_data.canonical_product_key(row.get("product"))
        seqs.update(mapping.get(pkey, set()))
        for observed_seq in seqs:
            obs = _parse(observed_seq)
            if not obs:
                continue
            # Cys rules are a separate class; do not use Cys runs to pull a
            # non-Cys peptide upward or vice versa.
            if bool(current.get("cys_count")) != bool(obs.get("cys_count")):
                continue
            # Keep empirical residual correction local in chain length. A distant
            # long peptide may be compositionally similar but is not a valid volume/eq neighbor.
            if abs(int(current.get("length") or 0) - int(obs.get("length") or 0)) > 3:
                continue
            sim = sequence_similarity(current, obs)
            if sim < 0.55:
                continue
            residual = eq - generic_length_eq(obs["length"])
            tis = _num(row.get("tis_ml"))
            water = _num(row.get("water_ml"))
            tfa = _num(row.get("tfa_ml"))
            cocktail = None
            if tfa is not None and tfa > 0 and water is not None:
                total = (tfa or 0.0) + (water or 0.0) + (tis or 0.0)
                if total > 0:
                    cocktail = {"TFA": tfa / total * 100.0, "Water": water / total * 100.0}
                    if tis is not None and tis > 0:
                        cocktail["TIS"] = tis / total * 100.0
            item = {
                "record_id": row.get("record_id"), "product": row.get("product"), "sequence": observed_seq,
                "similarity": sim, "cleavage_eq": eq, "length": obs["length"], "residual_eq": residual,
                "status": row.get("status"), "cocktail": cocktail, "tis_present": bool(tis is not None and tis > 0),
            }
            key = (experimental_data.canonical_sequence_key(observed_seq), eq, str(cocktail))
            previous = best_by_key.get(key)
            if previous is None or (item["status"] == "verified", sim) > (previous["status"] == "verified", previous["similarity"]):
                best_by_key[key] = item
    neighbors = sorted(best_by_key.values(), key=lambda x: (x["similarity"], x["status"] == "verified"), reverse=True)
    return neighbors[:limit]


def _neighbor_adjustment(neighbors: Iterable[dict[str, Any]]) -> tuple[float, float]:
    vals = []
    total_w = 0.0
    weighted = 0.0
    for row in neighbors:
        sim = float(row.get("similarity") or 0.0)
        if sim < 0.58:
            continue
        weight = max(0.01, (sim - 0.50) ** 2) * (1.25 if row.get("status") == "verified" else 1.0)
        residual = float(row.get("residual_eq") or 0.0)
        weighted += residual * weight
        total_w += weight
        vals.append(residual)
    if not vals or total_w <= 0:
        return 0.0, 0.0
    adjustment = weighted / total_w
    # Sequence similarity may tune the length baseline, but cannot cause a large
    # extrapolation from a few unrelated historical records.
    adjustment = max(-10.0, min(20.0, adjustment))
    return adjustment, total_w


def _neighbor_cocktail(neighbors: list[dict[str, Any]], length: int, sensitive: tuple[str, ...]) -> tuple[dict[str, float], str]:
    high = [x for x in neighbors if float(x.get("similarity") or 0.0) >= 0.68 and x.get("cocktail")]
    if len(high) >= 2:
        no_tis = sum(not bool(x.get("tis_present")) for x in high)
        if no_tis / len(high) >= 0.75 and not sensitive:
            return {"TFA": 95.0, "Water": 5.0}, f"{no_tis}/{len(high)} high-similarity historical conditions used no TIS"
        with_tis = sum(bool(x.get("tis_present")) for x in high)
        if with_tis / len(high) >= 0.75:
            return {"TFA": 95.0, "TIS": 2.5, "Water": 2.5}, f"{with_tis}/{len(high)} high-similarity historical conditions used TIS"
    if length <= 5 and not sensitive:
        return {"TFA": 95.0, "Water": 5.0}, "short general peptide fallback (<=5mer): TFA/water 95/5, no TIS"
    return {"TFA": 95.0, "TIS": 2.5, "Water": 2.5}, "general Fmoc cleavage fallback; TIS retained for longer/sensitive sequence"


def empirical_fallback(sequence: str, scale_mmol: Any = None, db_path: str | Path | None = None, *, resin: str = "") -> dict[str, Any] | None:
    parsed = _parse(sequence)
    if not parsed:
        return None
    n = int(parsed["length"])
    cys_count = int(parsed.get("cys_count") or 0)
    if cys_count:
        return cys_equivalent_override(sequence, scale_mmol=scale_mmol, resin=resin)

    baseline = generic_length_eq(n)
    neighbors = _historical_neighbors(sequence, db_path)
    adjustment, support = _neighbor_adjustment(neighbors)
    eq = _round_eq(baseline + adjustment)
    if n <= 5 and not parsed.get("sensitive"):
        eq = min(eq, 20.0)
    eq = max(5.0, min(eq, 100.0))

    composition, cocktail_basis = _neighbor_cocktail(neighbors, n, parsed.get("sensitive") or ())
    scale = _num(scale_mmol)
    factor = 0.5 if "ctc" in str(resin or "").lower() or "trityl" in str(resin or "").lower() else 1.0
    total = scale * eq * factor if scale is not None and scale > 0 else None
    good_neighbors = [x for x in neighbors if float(x.get("similarity") or 0.0) >= 0.58]
    confidence = "MEDIUM" if len(good_neighbors) >= 3 and max((x["similarity"] for x in good_neighbors), default=0) >= 0.70 else "LOW"
    spread = 5.0 if confidence == "MEDIUM" else 8.0
    if n <= 5 and not parsed.get("sensitive"):
        lo = max(5.0, eq - min(spread, 4.0)); hi = min(20.0, eq + min(spread, 4.0))
    else:
        lo = max(5.0, eq - spread); hi = eq + spread
    neighbor_preview = [
        {k: row.get(k) for k in ("product", "sequence", "similarity", "cleavage_eq", "length", "status")}
        for row in good_neighbors[:5]
    ]
    return {
        "sequence": sequence,
        "sequence_length": n,
        "cleavage_eq": eq,
        "cleavage_eq_range": [round(lo, 1), round(hi, 1)],
        "cleavage_time_h": 3.0,
        "preset": "DEFAULT_TFA_WATER" if set(composition) <= {"TFA", "Water"} else "DEFAULT_TFA_TIS_WATER",
        "composition_pct": composition,
        "scaled_total_ml": total,
        "volume_apply_allowed": bool(total is not None and total > 0),
        # This is intentionally operator-confirmed Apply, not silent automatic use.
        "apply_allowed": True,
        "basis": f"empirical fallback: length baseline {baseline:g} eq; historical-neighbor adjustment {adjustment:+.1f} eq; {cocktail_basis}",
        "eq_basis": "monotonic length baseline + bounded similar-sequence historical residual",
        "time_basis": "general 3 h fallback; replace with exact historical/SOP time when available",
        "condition_source": "empirical_v5_fallback",
        "recommendation_kind": "EMPIRICAL ESTIMATE",
        "empirical_estimate": {
            "kind": "length_plus_similarity", "confidence": confidence, "baseline_eq": baseline,
            "neighbor_adjustment_eq": round(adjustment, 2), "neighbor_count": len(good_neighbors),
            "neighbors": neighbor_preview, "cocktail_basis": cocktail_basis,
            "sensitive_residues": list(parsed.get("sensitive") or ()), "cys_count": cys_count,
        },
    }


__all__ = ["generic_length_eq", "sequence_similarity", "cys_equivalent_override", "operator_anchor", "empirical_fallback"]
