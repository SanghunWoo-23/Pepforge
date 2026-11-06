"""Evidence-first loading and cleavage advisors for SPPS Planner V6.0.0."""
from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from suite_gui import experimental_data


def _num(value: Any) -> float | None:
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except Exception:
        return None


def _confidence(count: int, exact_count: int, spread: float | None = None, parsed_fraction: float = 0.0) -> str:
    score = min(1.0, count / 12.0) * 0.45 + min(1.0, exact_count / 6.0) * 0.4 + (0.15 if spread is not None and spread < 0.2 else 0.0)
    score *= max(0.55, 1.0 - 0.35 * parsed_fraction)
    return "HIGH" if score >= 0.72 else "MEDIUM" if score >= 0.40 else "LOW"


def _eligible_loading(db_path: str | Path | None, include_parsed: bool) -> pd.DataFrame:
    statuses = ["verified"] + (["parsed"] if include_parsed else [])
    frame = pd.DataFrame(experimental_data.list_records("loading", db_path, statuses=statuses))
    if frame.empty:
        return frame
    frame = frame[frame["outlier_flag"].fillna(0).astype(int) == 0].copy()
    frame["resin_type"] = frame["resin_type"].fillna("").map(experimental_data.normalize_resin)
    frame["amino_acid_normalized"] = frame["amino_acid_normalized"].fillna("").map(experimental_data.normalize_amino_acid)
    frame["loading_rate_mmol_g"] = pd.to_numeric(frame["loading_rate_mmol_g"], errors="coerce")
    return frame.dropna(subset=["loading_rate_mmol_g"])


def _verified_loading_ml_prediction(
    frame: pd.DataFrame,
    *,
    resin: str,
    amino_acid: str,
    aa_eq: float | None,
    base_eq: float | None,
    loading_time_h: float | None,
) -> tuple[float | None, int]:
    """Train a deterministic small-data regressor only on operator-Verified rows.

    This prediction is advisory evidence only.  It is never used as the source of an
    Apply action; Apply remains tied to one real Verified exact-match experiment.
    """
    verified = frame[frame.get("status", pd.Series(index=frame.index, dtype=object)).eq("verified")].copy()
    if len(verified) < 12 or verified["loading_rate_mmol_g"].nunique(dropna=True) < 3:
        return None, len(verified)
    try:
        from sklearn.compose import ColumnTransformer
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.impute import SimpleImputer
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import OneHotEncoder
    except ImportError:
        return None, len(verified)

    categorical = ["resin_type", "amino_acid_normalized"]
    numeric = ["aa_eq", "base_eq", "loading_time_h"]
    for column in numeric:
        verified[column] = pd.to_numeric(verified[column], errors="coerce")
    X = verified[categorical + numeric]
    y = verified["loading_rate_mmol_g"].astype(float)
    preprocess = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore"), categorical),
        ("num", SimpleImputer(strategy="median"), numeric),
    ])
    model = Pipeline([
        ("preprocess", preprocess),
        ("model", RandomForestRegressor(
            n_estimators=240, max_depth=8, min_samples_leaf=2,
            random_state=41, n_jobs=1,
        )),
    ])
    model.fit(X, y)
    query = pd.DataFrame([{
        "resin_type": resin,
        "amino_acid_normalized": amino_acid,
        "aa_eq": aa_eq,
        "base_eq": base_eq,
        "loading_time_h": loading_time_h,
    }])
    pred = float(model.predict(query)[0])
    if not math.isfinite(pred):
        return None, len(verified)
    # Loading cannot be negative; clipping here is a physical-domain guard, not a
    # fabricated target.  The unclipped training data remain untouched.
    return max(0.0, pred), len(verified)


def loading_advice(
    resin: str,
    amino_acid: str,
    aa_eq: Any = None,
    base_eq: Any = None,
    loading_time_h: Any = None,
    target_loading_mmol_g: Any = None,
    db_path: str | Path | None = None,
    *,
    include_parsed: bool = True,
    allow_parsed_apply: bool = False,
) -> dict[str, Any]:
    """Return evidence plus a conservative, auditable loading recommendation.

    Parsed rows may be shown as supporting evidence, but an actionable recommendation
    is created only from an exact resin + amino-acid match. Verified rows are preferred.
    If a target loading is supplied, the selected historical condition is the exact-match
    record whose measured loading is closest to that target. Without a target, no
    condition is auto-selected because there is no meaningful optimization objective.
    """
    resin_n = experimental_data.normalize_resin(resin)
    aa_n = experimental_data.normalize_amino_acid(amino_acid)
    resin_key = experimental_data.canonical_resin_key(resin_n)
    aa_key = experimental_data.canonical_amino_acid_key(aa_n)
    frame = _eligible_loading(db_path, include_parsed)
    if frame.empty:
        return {"method": "no-data", "prediction": None, "confidence": "LOW", "evidence": [], "recommended_condition": None, "message": "No eligible loading records."}

    q_aa = _num(aa_eq); q_base = _num(base_eq); q_time = _num(loading_time_h)
    q_target = _num(target_loading_mmol_g)
    frame = frame.copy()
    frame_resin_keys = frame.get("resin_key", frame["resin_type"].fillna("").map(experimental_data.canonical_resin_key)).fillna("")
    frame_aa_keys = frame.get("amino_acid_key", frame["amino_acid_normalized"].fillna("").map(experimental_data.canonical_amino_acid_key)).fillna("")
    frame["resin_match"] = frame_resin_keys.eq(resin_key).astype(float)
    frame["aa_match"] = frame_aa_keys.eq(aa_key).astype(float)
    frame["distance"] = 3.0 - 1.2 * frame["resin_match"] - 1.5 * frame["aa_match"]
    for column, query, weight in (("aa_eq", q_aa, 0.7), ("base_eq", q_base, 0.35), ("loading_time_h", q_time, 0.2)):
        values = pd.to_numeric(frame[column], errors="coerce")
        if query is not None:
            frame["distance"] += (values - query).abs().fillna(1.5) * weight
    frame = frame.sort_values(["distance", "date"]).head(12)
    exact = frame[(frame["resin_match"] == 1) & (frame["aa_match"] == 1)].copy()

    weights = 1.0 / (1.0 + frame["distance"].clip(lower=0))
    similarity_prediction = float((frame["loading_rate_mmol_g"] * weights).sum() / weights.sum())
    ml_prediction, ml_training_count = _verified_loading_ml_prediction(
        _eligible_loading(db_path, include_parsed=False),
        resin=resin_n, amino_acid=aa_n, aa_eq=q_aa, base_eq=q_base, loading_time_h=q_time,
    )
    prediction = ml_prediction if ml_prediction is not None else similarity_prediction
    method = "random-forest + similarity" if ml_prediction is not None else "similarity"
    spread = float(frame["loading_rate_mmol_g"].std()) if len(frame) > 1 else None
    parsed_fraction = float((frame["status"] == "parsed").mean()) if "status" in frame else 0.0
    confidence = _confidence(len(frame), len(exact), spread, parsed_fraction)

    evidence_cols = ["record_id", "date", "resin_type", "amino_acid_normalized", "aa_eq", "base_eq", "loading_time_h", "loading_solvent", "loading_rate_mmol_g", "capping_performed", "capping_method", "status", "source_locator", "raw_note"]
    evidence_frame = frame[evidence_cols].copy()
    evidence = evidence_frame.astype(object).where(pd.notna(evidence_frame), None).to_dict("records")

    warnings: list[str] = []
    if parsed_fraction:
        warnings.append("Parsed records are shown as evidence but are not silently treated as verified training truth.")
    if exact.empty:
        warnings.append("No exact resin + amino-acid record exists. Broader similarity is evidence only; Apply is disabled.")
    if q_target is None:
        warnings.append("Target loading is required for an actionable loading recommendation. Apply is disabled until a target is supplied.")

    recommended = None
    # Actionable recommendations must come from exact matches. Prefer operator-verified
    # records. Parsed exact matches are used only when there are no verified exact rows,
    # and remain explicitly marked as parsed for operator confirmation.
    if q_target is not None and not exact.empty:
        verified_exact = exact[exact["status"] == "verified"] if "status" in exact else exact.iloc[0:0]
        if not verified_exact.empty:
            pool = verified_exact.copy()
        elif allow_parsed_apply:
            pool = exact[exact["status"] == "parsed"].copy() if "status" in exact else exact.copy()
            warnings.append("No Verified exact loading row exists; Apply uses one exact user-imported Parsed row and requires operator confirmation.")
        else:
            pool = exact.iloc[0:0]
            warnings.append("Exact loading records exist, but none are Verified. Parsed records remain evidence only; Apply is disabled.")
        if not pool.empty:
            pool["target_gap"] = (pool["loading_rate_mmol_g"] - q_target).abs()
            chosen = pool.sort_values(["target_gap", "distance"]).iloc[0]
            chosen_aa = _num(chosen.get("aa_eq"))
            chosen_base = _num(chosen.get("base_eq"))
            chosen_time = _num(chosen.get("loading_time_h"))
            time_source = "source record"
            if chosen_time is None:
                times = pd.to_numeric(exact.get("loading_time_h"), errors="coerce").dropna()
                times = times[times > 0]
                if not times.empty:
                    chosen_time = round(float(times.median()) * 2.0) / 2.0
                    time_source = f"median of {len(times)} exact resin+AA time records"
            chosen_solvent = str(chosen.get("loading_solvent") or "").strip()
            actionable = any(value is not None for value in (chosen_aa, chosen_base, chosen_time)) or bool(chosen_solvent)
            if not actionable:
                warnings.append("The closest exact record has no actionable AA/base/time condition. Apply is disabled.")
            recommended = {
                "record_id": chosen.get("record_id"),
                "aa_eq": chosen_aa,
                "base_eq": chosen_base,
                "loading_time_h": chosen_time,
                "loading_time_source": time_source,
                "loading_solvent": chosen_solvent,
                "observed_loading_mmol_g": _num(chosen.get("loading_rate_mmol_g")),
                "source_status": chosen.get("status"),
                "source_date": chosen.get("date"),
                "target_loading_mmol_g": q_target,
                "apply_allowed": actionable,
            }

    return {
        "method": method,
        "prediction": prediction,
        "similarity_prediction": similarity_prediction,
        "ml_training_count": ml_training_count,
        "observed_min": float(frame["loading_rate_mmol_g"].min()),
        "observed_max": float(frame["loading_rate_mmol_g"].max()),
        "confidence": confidence,
        "evidence_count": len(frame), "exact_count": len(exact), "spread": spread,
        "evidence_summary": {
            "source_kind": "HISTORICAL EXACT" if len(exact) else "SIMILARITY EVIDENCE",
            "total_records": int(len(frame)), "exact_records": int(len(exact)),
            "verified_exact_records": int((exact["status"] == "verified").sum()) if not exact.empty and "status" in exact else 0,
            "parsed_exact_records": int((exact["status"] == "parsed").sum()) if not exact.empty and "status" in exact else 0,
            "apply_allowed": bool((recommended or {}).get("apply_allowed", False)),
        },
        "recommended_condition": recommended,
        "warnings": warnings, "evidence": evidence,
    }


def _normalize_product_key(value: Any) -> str:
    return experimental_data.canonical_product_key(value)


def _sequence_signature(sequence: Any) -> tuple[str, tuple[str, ...], str] | None:
    return experimental_data.sequence_signature(sequence)


def _sequence_match_key(sequence: Any) -> str:
    return experimental_data.canonical_sequence_key(sequence)


def _sequence_observation_matches(observed: Any, current: Any) -> bool:
    """Match a page-local STD observation without inventing omitted termini.

    Core residues and explicit N-terminal modification must agree.  A blank C-term
    marker in a Check table is treated as unrecorded, not as evidence against an
    explicitly entered current -NH2/-COOH marker.  Explicit conflicting C-terms fail.
    """
    observed_sig = _sequence_signature(observed)
    current_sig = _sequence_signature(current)
    if not observed_sig or not current_sig:
        return _sequence_match_key(observed) == _sequence_match_key(current)
    onterm, otokens, octerm = observed_sig
    cnterm, ctokens, ccterm = current_sig
    if onterm != cnterm or otokens != ctokens:
        return False
    if octerm and ccterm and octerm != ccterm:
        return False
    return True


def _product_sequence_observations(db_path: str | Path | None = None) -> dict[str, set[str]]:
    """Return all observed page-local sequences per product; never force 1:1 mapping."""
    root = Path(__file__).resolve().parents[2] / "apps" / "spps_planner_app" / "data" / "experimental_seed"
    out: dict[str, set[str]] = {}
    for filename in ("cleavage_sequence_map_seed.csv", "synthesis_sequence_history_seed.csv"):
        path = root / filename
        if not path.is_file():
            continue
        try:
            frame = pd.read_csv(path)
        except Exception:
            continue
        product_column = "product_key" if "product_key" in frame.columns else "product" if "product" in frame.columns else ""
        if not product_column or "sequence" not in frame.columns:
            continue
        for _, row in frame.iterrows():
            product_key = _normalize_product_key(row.get(product_column))
            sequence = str(row.get("sequence") or "").strip()
            if product_key and sequence:
                out.setdefault(product_key, set()).add(sequence)
    try:
        rows = experimental_data.list_records("sequence", db_path, statuses=["verified", "parsed"])
    except Exception:
        rows = []
    for row in rows:
        product_key = _normalize_product_key(row.get("product"))
        sequence = str(row.get("sequence") or "").strip()
        if product_key and sequence:
            out.setdefault(product_key, set()).add(sequence)
    return out


def _bundled_product_sequence_map() -> dict[str, set[str]]:
    """Backward-compatible name: now returns all page-local observations per product."""
    return _product_sequence_observations(None)


def _product_sequence_supported(
    product: Any,
    sequence: Any,
    exact_rows: pd.DataFrame,
    db_path: str | Path | None = None,
) -> tuple[bool, str]:
    current = str(sequence or "").strip()
    if not current or not _sequence_match_key(current):
        return False, "current sequence is empty/unparseable"
    if not exact_rows.empty and "sequence" in exact_rows:
        for value in exact_rows["sequence"].dropna().tolist():
            if _sequence_observation_matches(value, current):
                return True, "sequence stored in exact experimental record"
    product_key = _normalize_product_key(product)
    observed = _product_sequence_observations(db_path).get(product_key, set())
    if observed:
        if any(_sequence_observation_matches(value, current) for value in observed):
            return True, "page-local Check table product↔sequence observation"
        return False, "mapped sequence does not match current Planner sequence; product exists in sequence history but no page-local STD observation matches"
    return False, "no recorded product↔sequence observation is available for this historical product"

def _json_component_state(value: Any) -> tuple[dict[str, float], list[str]]:
    """Return explicitly numeric extra components plus any unresolved entries.

    A non-empty extra component is never silently discarded.  Numeric values are
    preserved as recorded; text/unknown values make the cocktail incomplete for
    automatic reproduction until the operator verifies the amount.
    """
    text = str(value or "{}").strip()
    try:
        import json
        raw = json.loads(text or "{}")
    except Exception:
        return {}, ([text] if text not in {"", "{}"} else [])
    if not isinstance(raw, dict):
        return {}, ([text] if raw not in ({}, None, "") else [])
    out: dict[str, float] = {}
    unresolved: list[str] = []
    for key, raw_value in raw.items():
        if str(raw_value).strip() in {"", "None", "0", "0.0"}:
            continue
        number = _num(raw_value)
        if number is not None and number > 0:
            out[str(key)] = number
        else:
            unresolved.append(str(key))
    return out, unresolved


def _json_components(value: Any) -> dict[str, float]:
    # Backward-compatible helper for callers that need only verified numeric values.
    return _json_component_state(value)[0]


def _recorded_cocktail(row: Mapping[str, Any]) -> dict[str, Any] | None:
    """Recover one complete recorded cocktail without manufacturing components.

    Other scavengers are preserved as recorded numeric volumes.  A blank standard
    component is accepted as zero only when all explicitly recorded volumes already
    account for the full scale×eq cocktail volume within 2%.
    """
    scale = _num(row.get("scale_mmol"))
    eq = _num(row.get("cleavage_eq"))
    standard: dict[str, float | None] = {
        "TFA": _num(row.get("tfa_ml")),
        "TIS": _num(row.get("tis_ml")),
        "Water": _num(row.get("water_ml")),
    }
    other, unresolved_other = _json_component_state(row.get("other_scavengers_json"))
    if unresolved_other:
        return None
    known: dict[str, float | None] = dict(standard)
    for name, value in other.items():
        if name not in known:
            known[name] = value
    present_total = sum(float(value) for value in known.values() if value is not None and value >= 0)
    expected_total = (scale * eq) if scale and scale > 0 and eq and eq > 0 else None
    if expected_total is not None and expected_total > 0:
        relative_error = abs(present_total - expected_total) / expected_total
        blanks = [name for name, value in standard.items() if value is None]
        if blanks and relative_error <= 0.02:
            for name in blanks:
                known[name] = 0.0
    if any(known.get(name) is None for name in standard):
        return None
    total = sum(float(value or 0.0) for value in known.values())
    if total <= 0:
        return None
    pct = {
        name: float(value or 0.0) / total * 100.0
        for name, value in known.items()
        if float(value or 0.0) > 0
    }
    return {
        "composition_pct": pct,
        "source_total_ml": total,
        "source_ml_per_mmol": (total / scale if scale and scale > 0 else None),
    }


def _historical_condition_compatible(rule_preset: str, composition: Mapping[str, float]) -> bool:
    """Validate a recorded TFA cocktail without letting a generic preset veto it.

    The generic chemistry preset is a fallback/reference.  It must never reject a
    real historical TFA cocktail merely because that record did not contain EDT,
    phenol, thioanisole, DTT, or another reagent suggested by the fallback rule.
    """
    names = {str(name).strip().lower() for name, value in composition.items() if _num(value) and float(value) > 0}
    return bool(names) and "tfa" in names

def _same_eq_time(frame: pd.DataFrame, recommended_eq: float | None) -> tuple[float | None, str]:
    """Recommend time from the closest relevant historical cleavage class."""
    if frame.empty or recommended_eq is None:
        return None, "no relevant cleavage-time evidence"
    eq_values = pd.to_numeric(frame.get("cleavage_eq"), errors="coerce")
    times = pd.to_numeric(frame.get("cleavage_time_h"), errors="coerce")
    relevant = times[(eq_values - float(recommended_eq)).abs() <= 1e-9]
    relevant = relevant[relevant > 0].dropna()
    if len(relevant):
        # Mode first: it preserves the user's actually repeated bench duration.
        modes = relevant.mode()
        chosen = float(modes.iloc[0]) if len(modes) else float(relevant.median())
        return chosen, f"mode of {len(relevant)} historical records at {float(recommended_eq):g} eq"
    positive = times[times > 0].dropna()
    if len(positive):
        modes = positive.mode()
        chosen = float(modes.iloc[0]) if len(modes) else float(positive.median())
        return chosen, f"fallback mode of {len(positive)} historical cleavage-time records"
    return None, "no historical cleavage-time evidence"


def _sequence_cleavage_condition(
    sequence: str,
    resin: str,
    scale_mmol: float | None,
    frame: pd.DataFrame,
    product: str = "",
    db_path: str | Path | None = None,
) -> dict[str, Any] | None:
    """Build a sequence-first condition, then refine it with one compatible lab record.

    Sequence chemistry decides whether a historical cocktail is chemically eligible.
    If a compatible exact-product record exists, one real record supplies cocktail,
    volume/scale, equivalent and time together.  Otherwise the planner's sequence
    chemistry rule is used and historical time is restricted to the same eq class.
    No cross-record cocktail averaging is performed.
    """
    seq = str(sequence or "").strip()
    if not seq:
        return None
    try:
        from spps_planner.engine import (
            PlanInput,
            cleavage_eq_suggestion,
            generate_cleavage_cocktail,
            recommend_cleavage_preset,
        )
        from spps_planner.parser import parse_sequence
        parsed = parse_sequence(seq)
        tokens = list(parsed.core_tokens or []) + list(getattr(parsed, "branch_tokens", []) or [])
        if not tokens:
            return None
        scale = float(scale_mmol) if scale_mmol is not None and scale_mmol > 0 else 1.0
        base = PlanInput(sequence=seq, resin=str(resin or "Amide"), scale_mmol=scale)
        eq_info = cleavage_eq_suggestion(base)
        preset_info = recommend_cleavage_preset(base)
        rule_preset = str(preset_info.get("preset") or "DEFAULT_TFA_TIS_WATER")
        rule_eq = _num(eq_info.get("cleavage_eq"))

        # Historical evidence is sequence-first.  A current product label may be
        # stale or unrelated, so a real row can qualify by (a) its stored sequence,
        # or (b) a page-local Check table product↔sequence observation.  Exact current
        # product rows are included only when that product is itself sequence-supported.
        product_key = _normalize_product_key(product)
        product_keys = frame.get("product_key", frame.get("product", pd.Series(index=frame.index, dtype=object)).fillna("").map(_normalize_product_key)).fillna("")
        row_sequences = frame.get("sequence", pd.Series(index=frame.index, dtype=object)).fillna("")
        row_sequence_match = row_sequences.map(lambda observed: _sequence_observation_matches(observed, seq) if str(observed).strip() else False)
        observations = _product_sequence_observations(db_path)
        mapped_product_keys = {
            key for key, values in observations.items()
            if any(_sequence_observation_matches(observed, seq) for observed in values)
        }
        exact = frame[row_sequence_match | product_keys.isin(mapped_product_keys)].copy()
        current_product_rows = frame[product_keys.eq(product_key)].copy() if product_key else frame.iloc[0:0]
        product_sequence_ok, product_sequence_basis = _product_sequence_supported(product, seq, current_product_rows, db_path=db_path)
        if product_sequence_ok and not current_product_rows.empty:
            exact = pd.concat([exact, current_product_rows], ignore_index=False).drop_duplicates(subset=["record_id"])
        elif not exact.empty:
            product_sequence_basis = "sequence stored in a historical record or page-local Check table product↔sequence observation"
        historical_candidates: list[dict[str, Any]] = []
        for _, row in exact.iterrows():
            recovered = _recorded_cocktail(row)
            if not recovered:
                continue
            if not _historical_condition_compatible(rule_preset, recovered["composition_pct"]):
                continue
            source_scale = _num(row.get("scale_mmol"))
            source_eq = _num(row.get("cleavage_eq"))
            source_time = _num(row.get("cleavage_time_h"))
            distance = abs((source_scale or scale) - scale) / max(scale, 1.0)
            historical_candidates.append({
                **recovered,
                "record_id": row.get("record_id"),
                "source_status": row.get("status"),
                "source_product": row.get("product"),
                "source_scale_mmol": source_scale,
                "cleavage_eq": source_eq,
                "cleavage_time_h": source_time,
                "distance": distance,
            })
        if historical_candidates:
            chosen = min(historical_candidates, key=lambda row: row["distance"])
            source_per = _num(chosen.get("source_ml_per_mmol"))
            scaled_total = source_per * scale if source_per is not None else None
            source_time = _num(chosen.get("cleavage_time_h"))
            if source_time is None:
                exact_times = pd.to_numeric(exact.get("cleavage_time_h"), errors="coerce").dropna()
                exact_times = exact_times[exact_times > 0]
                source_time = float(exact_times.mode().iloc[0]) if len(exact_times) else None
            return {
                "sequence": seq,
                "sequence_length": len(tokens),
                "cleavage_eq": _num(chosen.get("cleavage_eq")) or rule_eq,
                "cleavage_time_h": source_time,
                "preset": "",
                "composition_pct": chosen["composition_pct"],
                "scaled_total_ml": scaled_total,
                "volume_apply_allowed": bool(scaled_total is not None and scaled_total > 0),
                "apply_allowed": bool((_num(chosen.get("cleavage_eq")) or rule_eq) is not None and source_time is not None),
                "basis": f"{product_sequence_basis}; exact lab record {chosen.get('record_id')} ({chosen.get('source_product')}) preserved as recorded; chemistry reference={rule_preset}",
                "time_basis": "same exact-product laboratory record" if _num(chosen.get("cleavage_time_h")) is not None else "mode of exact-product laboratory records",
                "eq_basis": "same exact-product laboratory record" if _num(chosen.get("cleavage_eq")) is not None else str(eq_info.get("source") or "planner sequence rule"),
                "condition_source": "exact_lab_record",
                "source_record_id": chosen.get("record_id"),
                "source_product": chosen.get("source_product"),
                "source_status": chosen.get("source_status"),
                "rule_preset": rule_preset,
            }

        if not exact.empty:
            # The sequence/product mapping is valid, but none of the matched rows
            # contains a complete reproducible cocktail.  Recognize the user's
            # history explicitly instead of making it look as if no data existed.
            return {
                "sequence": seq,
                "sequence_length": len(tokens),
                "cleavage_eq": None,
                "cleavage_time_h": None,
                "preset": "",
                "composition_pct": {},
                "scaled_total_ml": None,
                "volume_apply_allowed": False,
                "apply_allowed": False,
                "basis": f"{len(exact)} sequence-matched historical record(s) recognized, but none contains a complete reproducible cocktail; chemistry reference={rule_preset}",
                "time_basis": "historical match incomplete",
                "eq_basis": "historical match incomplete",
                "condition_source": "historical_match_incomplete",
                "source_record_id": None,
                "source_product": product or None,
                "source_status": None,
                "rule_preset": rule_preset,
                "matched_history_count": int(len(exact)),
            }

        recommended_time, time_basis = _same_eq_time(frame, rule_eq)
        timed = PlanInput(
            sequence=seq,
            resin=str(resin or "Amide"),
            scale_mmol=scale,
            cleavage_preset=rule_preset,
            cleavage_time_h=float(recommended_time or 0.0),
        )
        cocktail = generate_cleavage_cocktail(timed)
        total_row = cocktail[cocktail["component"].astype(str).eq("Total cocktail")]
        total_ml = None if total_row.empty else _num(total_row.iloc[0].get("volume_mL"))
        components: dict[str, float] = {}
        for _, row in cocktail.iterrows():
            if str(row.get("include", "")) != "YES" or str(row.get("component", "")) == "Total cocktail":
                continue
            pct = _num(row.get("percent"))
            if pct is not None:
                components[str(row.get("component"))] = pct
        return {
            "sequence": seq,
            "sequence_length": len(tokens),
            "cleavage_eq": rule_eq,
            "cleavage_time_h": recommended_time,
            "preset": rule_preset,
            "composition_pct": components,
            "scaled_total_ml": total_ml,
            "volume_apply_allowed": bool(total_ml is not None and total_ml > 0),
            "apply_allowed": bool(rule_eq is not None and rule_preset and recommended_time is not None),
            "basis": f"sequence chemistry rule: {preset_info.get('reason','')}; time: {time_basis}; exact-product refinement not used ({product_sequence_basis})",
            "time_basis": time_basis,
            "eq_basis": str(eq_info.get("source") or "planner sequence rule"),
            "condition_source": "sequence_rule_fallback",
            "rule_preset": rule_preset,
        }
    except Exception:
        return None

def cleavage_advice(
    *,
    product: str = "",
    sequence: str = "",
    resin: str = "",
    scale_mmol: Any = None,
    cleavage_eq: Any = None,
    cleavage_time_h: Any = None,
    db_path: str | Path | None = None,
    include_parsed: bool = True,
) -> dict[str, Any]:
    """Sequence-first cleavage advisor with historical evidence.

    The current Planner sequence, not the product-name field, drives the actionable
    cleavage eq/cocktail recommendation. Historical records provide time evidence
    and contextual comparison. Exact-product rows remain visible as evidence only.
    """
    statuses = ["verified"] + (["parsed"] if include_parsed else [])
    all_frame = pd.DataFrame(experimental_data.list_records("cleavage", db_path, statuses=statuses))
    if all_frame.empty:
        return {"method": "no-data", "confidence": "LOW", "evidence": [], "recommended_condition": None, "message": "No eligible cleavage records."}

    q_scale = _num(scale_mmol); q_eq = _num(cleavage_eq); q_time = _num(cleavage_time_h)
    product_low = _normalize_product_key(product)
    frame = all_frame.copy()
    frame["distance"] = 2.0
    if product_low:
        product_keys = frame.get("product_key", frame["product"].fillna("").map(_normalize_product_key)).fillna("")
        frame["product_match"] = product_keys.eq(product_low).astype(float)
        frame["distance"] -= frame["product_match"] * 1.0
    else:
        frame["product_match"] = 0.0
    for column, query, scale in (("scale_mmol", q_scale, 0.004), ("cleavage_eq", q_eq, 0.03), ("cleavage_time_h", q_time, 0.20)):
        values = pd.to_numeric(frame[column], errors="coerce")
        if query is not None:
            frame["distance"] += (values - query).abs().fillna(10.0) * scale
    frame = frame.sort_values("distance").head(10)
    exact = frame[frame["product_match"] == 1].copy()
    parsed_fraction = float((frame["status"] == "parsed").mean())
    confidence = _confidence(len(frame), len(exact), None, parsed_fraction)

    seq_text = str(sequence or "").strip()
    recommended = _sequence_cleavage_condition(seq_text, str(resin or ""), q_scale, all_frame, product=str(product or ""), db_path=db_path) if seq_text else None
    # Generic chemistry output is reference-only.  It can explain a safe baseline,
    # but it is not historical/ML evidence and must never become Apply-enabled.
    if recommended and recommended.get("condition_source") == "sequence_rule_fallback":
        recommended = dict(recommended)
        recommended.update({
            "apply_allowed": False,
            "volume_apply_allowed": False,
            "condition_source": "chemistry_rule_reference",
            "recommendation_kind": "CHEMISTRY RULE",
        })
    warnings: list[str] = []
    if recommended and recommended.get("condition_source") == "historical_match_incomplete":
        warnings.append(
            f"{recommended.get('matched_history_count', 0)} sequence-matched historical record(s) were recognized, but the recorded cocktail is incomplete/inconsistent, so no missing component is guessed and Apply remains disabled."
        )
    if not seq_text:
        # Backward-compatible evidence mode for callers that have only a product name.
        # This branch never substitutes product matching for the new sequence-first UI.
        if product_low and not exact.empty:
            verified_exact = exact[exact["status"] == "verified"] if "status" in exact else exact.iloc[0:0]
            if verified_exact.empty:
                warnings.append("Exact-product records exist, but none are Verified. Parsed records remain evidence only; Apply is disabled.")
            else:
                chosen = verified_exact.sort_values("distance").iloc[0]
                vals = [_num(chosen.get(k)) for k in ("tfa_ml", "tis_ml", "water_ml")]
                try:
                    import json as _json
                    other = _json.loads(str(chosen.get("other_scavengers_json") or "{}"))
                except Exception:
                    other = {"unparsed": chosen.get("other_scavengers_json")}
                other = {str(k): v for k, v in (other or {}).items() if str(v).strip() not in {"", "None", "0", "0.0"}}
                complete = all(v is not None for v in vals) and sum(float(v) for v in vals) > 0
                pct = None
                if complete and not other:
                    total = sum(float(v) for v in vals)
                    pct = {"TFA": float(vals[0]) / total * 100.0, "TIS": float(vals[1]) / total * 100.0, "Water": float(vals[2]) / total * 100.0}
                if other:
                    warnings.append("The verified exact-product record contains additional/unknown components. Its cocktail is evidence only and will not be auto-applied.")
                if not complete:
                    warnings.append("The verified exact-product record does not contain a complete TFA/TIS/H2O composition. Apply is disabled to avoid interpreting blanks as zero.")
                chosen_eq = _num(chosen.get("cleavage_eq"))
                chosen_time = _num(chosen.get("cleavage_time_h"))
                apply_allowed = bool(complete and not other and (chosen_eq is not None or chosen_time is not None))
                source_scale = _num(chosen.get("scale_mmol"))
                source_total_ml = sum(float(v) for v in vals) if complete else None
                ml_per_mmol = (source_total_ml / source_scale) if source_total_ml is not None and source_scale and source_scale > 0 else None
                scaled_total_ml = (ml_per_mmol * q_scale) if ml_per_mmol is not None and q_scale is not None and q_scale > 0 else None
                recommended = {
                    "record_id": chosen.get("record_id"), "product": chosen.get("product"), "scale_mmol": source_scale,
                    "cleavage_eq": chosen_eq, "cleavage_time_h": chosen_time, "tfa_ml": vals[0], "tis_ml": vals[1], "water_ml": vals[2],
                    "composition_pct": pct, "source_total_ml": source_total_ml, "source_ml_per_mmol": ml_per_mmol, "scaled_total_ml": scaled_total_ml,
                    "other_components": other, "source_status": chosen.get("status"), "apply_allowed": apply_allowed,
                    "volume_apply_allowed": bool(apply_allowed and scaled_total_ml is not None and scaled_total_ml > 0),
                }
                if not apply_allowed:
                    warnings.append("The verified exact-product record is not a complete, safely reproducible cleavage condition; Apply is disabled.")
        else:
            warnings.append("Planner sequence is empty; sequence-based Apply is disabled.")
    elif recommended is None:
        warnings.append("The current sequence could not be parsed into a safe cleavage recommendation.")
    if parsed_fraction:
        warnings.append("Parsed historical rows are used as time/context evidence and are not treated as verified causal proof.")

    def rate(column: str) -> float | None:
        values = pd.to_numeric(frame[column], errors="coerce").dropna()
        return float(values.mean()) if len(values) else None

    recommendations: list[str] = []
    concentrate_rate = rate("concentration_recommended")
    separation_rate = rate("separation_problem")
    if concentrate_rate is not None and concentrate_rate >= 0.45:
        recommendations.append("Historical notes frequently recommend concentration before ether precipitation.")
    if separation_rate is not None and separation_rate >= 0.45:
        recommendations.append("Comparable records show recurring supernatant/separation difficulty.")

    evidence_cols = ["record_id", "product", "sequence", "scale_mmol", "tfa_ml", "tis_ml", "water_ml", "cleavage_eq", "cleavage_time_h", "ether_ratio", "filter_speed", "status", "raw_observation"]
    evidence_cols = [c for c in evidence_cols if c in frame.columns]
    evidence_frame = frame[evidence_cols].copy()
    return {
        "method": "current sequence + compatible single-record lab evidence",
        "confidence": confidence,
        "evidence_count": len(frame),
        "exact_count": len(exact),
        "evidence_summary": {
            "source_kind": (recommended or {}).get("recommendation_kind") or ("HISTORICAL PRODUCT EVIDENCE" if len(exact) else "CONTEXT EVIDENCE"),
            "total_records": int(len(frame)), "exact_product_records": int(len(exact)),
            "sequence_key": experimental_data.canonical_sequence_key(seq_text),
            "product_key": product_low,
            "apply_allowed": bool((recommended or {}).get("apply_allowed", False)),
        },
        "recommendations": recommendations,
        "recommended_condition": recommended,
        "warnings": warnings,
        "evidence": evidence_frame.astype(object).where(pd.notna(evidence_frame), None).to_dict("records"),
    }


def loading_recommendation(
    resin: str,
    amino_acid: str,
    *,
    target_loading_mmol_g: Any = None,
    db_path: str | Path | None = None,
    include_parsed: bool = True,
) -> dict[str, Any]:
    """Recommend a *recorded* loading condition for the requested target.

    No interpolated AA/base/time values are generated. Exact resin + amino-acid
    records are grouped by the condition actually used at the bench, and the
    least-reagent observed condition whose group median reached the target is
    selected. Parsed rows can support a provisional recommendation, but their
    status is exposed and confidence is reduced.
    """
    resin_n = experimental_data.normalize_resin(resin)
    aa_n = experimental_data.normalize_amino_acid(amino_acid)
    target = _num(target_loading_mmol_g)
    frame = _eligible_loading(db_path, include_parsed)
    if frame.empty:
        return {"method": "no-data", "confidence": "LOW", "recommended_condition": None, "warnings": ["No eligible loading records."], "evidence": []}
    exact = frame[
        frame["resin_type"].fillna("").eq(resin_n)
        & frame["amino_acid_normalized"].fillna("").eq(aa_n)
    ].copy()
    if exact.empty:
        return {
            "method": "exact-condition observed recommendation",
            "confidence": "LOW",
            "recommended_condition": None,
            "warnings": ["No exact resin + amino-acid loading history exists; no condition is recommended."],
            "evidence": [],
        }

    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for row in exact.astype(object).where(pd.notna(exact), None).to_dict("records"):
        aa_eq = _num(row.get("aa_eq")); base_eq = _num(row.get("base_eq")); time_h = _num(row.get("loading_time_h"))
        loading = _num(row.get("loading_rate_mmol_g"))
        if aa_eq is None or base_eq is None or loading is None:
            continue
        key = (aa_eq, base_eq, time_h, str(row.get("loading_solvent") or "").strip())
        groups.setdefault(key, []).append(row)
    if not groups:
        return {
            "method": "exact-condition observed recommendation",
            "confidence": "LOW",
            "recommended_condition": None,
            "warnings": ["Exact loading records exist, but no complete AA eq + base eq + measured-loading condition is available."],
            "evidence": exact.astype(object).where(pd.notna(exact), None).to_dict("records"),
        }

    candidates: list[dict[str, Any]] = []
    for key, rows in groups.items():
        loadings = sorted(_num(r.get("loading_rate_mmol_g")) for r in rows if _num(r.get("loading_rate_mmol_g")) is not None)
        if not loadings:
            continue
        mid = len(loadings) // 2
        median_loading = loadings[mid] if len(loadings) % 2 else (loadings[mid - 1] + loadings[mid]) / 2.0
        verified_count = sum(str(r.get("status") or "") == "verified" for r in rows)
        representative = next((r for r in rows if str(r.get("status") or "") == "verified"), rows[0])
        candidates.append({
            "aa_eq": key[0], "base_eq": key[1], "loading_time_h": key[2], "loading_solvent": key[3],
            "median_loading_mmol_g": median_loading,
            "observed_min": min(loadings), "observed_max": max(loadings),
            "evidence_count": len(rows), "verified_count": verified_count,
            "representative": representative,
            "meets_target": bool(target is not None and median_loading >= target),
        })
    if not candidates:
        return {"method": "exact-condition observed recommendation", "confidence": "LOW", "recommended_condition": None, "warnings": ["No complete candidate loading condition is available."], "evidence": []}

    warnings: list[str] = []
    if target is not None:
        meeting = [c for c in candidates if c["meets_target"]]
        if meeting:
            chosen = min(
                meeting,
                key=lambda c: (
                    c["aa_eq"], c["base_eq"], c["loading_time_h"] if c["loading_time_h"] is not None else float("inf"),
                    c["median_loading_mmol_g"] - target, -c["verified_count"], -c["evidence_count"],
                ),
            )
            demonstrated = True
        else:
            chosen = max(candidates, key=lambda c: (c["median_loading_mmol_g"], c["verified_count"], c["evidence_count"]))
            demonstrated = False
            warnings.append("No recorded exact condition demonstrated the requested target loading; the best observed condition is shown but Apply is disabled.")
    else:
        chosen = max(candidates, key=lambda c: (c["evidence_count"], c["verified_count"], -c["aa_eq"], -c["base_eq"]))
        demonstrated = False
        warnings.append("Target loading is blank. The most repeated exact condition is shown as context; Apply is disabled until a target is supplied.")

    rep = chosen["representative"]
    status = str(rep.get("status") or "parsed")
    if chosen["verified_count"] >= 2 and chosen["evidence_count"] >= 3:
        confidence = "HIGH"
    elif chosen["verified_count"] >= 1 or chosen["evidence_count"] >= 2:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"
    if chosen["verified_count"] == 0:
        warnings.append("Recommendation is provisional because all supporting exact records are Parsed, not Verified.")

    recommended = {
        "aa_eq": chosen["aa_eq"], "base_eq": chosen["base_eq"],
        "loading_time_h": chosen["loading_time_h"], "loading_solvent": chosen["loading_solvent"],
        "target_loading_mmol_g": target,
        "expected_loading_mmol_g": chosen["median_loading_mmol_g"],
        "observed_min": chosen["observed_min"], "observed_max": chosen["observed_max"],
        "condition_evidence_count": chosen["evidence_count"], "condition_verified_count": chosen["verified_count"],
        "source_record_id": rep.get("record_id"), "source_status": status, "source_date": rep.get("date"),
        "apply_allowed": bool(demonstrated),
        "basis": "minimum recorded exact condition whose observed group median reached target" if demonstrated else "best/most repeated recorded exact condition; target not demonstrated",
        "recommendation_kind": "observed_exact_condition",
    }
    evidence = sorted(candidates, key=lambda c: (c["aa_eq"], c["base_eq"], c["loading_time_h"] if c["loading_time_h"] is not None else 9999.0))
    clean_evidence = [{k: v for k, v in row.items() if k != "representative"} for row in evidence]
    return {
        "method": "target-constrained exact-condition recommendation",
        "confidence": confidence,
        "recommended_condition": recommended,
        "warnings": warnings,
        "evidence": clean_evidence,
    }


def _cleavage_outcome_score(row: Mapping[str, Any]) -> tuple[float, int]:
    score = 0.0; count = 0
    precip = row.get("precipitation_good")
    if precip is not None:
        count += 1; score += 1.0 if int(precip) == 1 else -1.0
    separation = row.get("separation_problem")
    if separation is not None:
        count += 1; score += -0.8 if int(separation) == 1 else 0.2
    concentrate = row.get("concentration_recommended")
    if concentrate is not None:
        count += 1; score += -0.35 if int(concentrate) == 1 else 0.1
    speed = str(row.get("filter_speed") or "").strip().lower()
    if speed:
        count += 1
        if "느" in speed or "slow" in speed:
            score -= 0.25
        elif "빠" in speed or "fast" in speed:
            score += 0.2
    return score, count


def cleavage_recommendation(
    *,
    product: str = "",
    sequence: str = "",
    resin: str = "",
    scale_mmol: Any = None,
    db_path: str | Path | None = None,
    include_parsed: bool = True,
) -> dict[str, Any]:
    """Recommend one coherent cleavage condition without cross-record mixing.

    Sequence identity is primary. When matching historical records exist, only
    whole recorded conditions that are compatible with the sequence chemistry
    rule compete. Repeated/positive records are preferred; no synthetic cocktail,
    eq or time is created. If sequence-matched history is absent, the existing
    chemistry-rule advisor is returned explicitly as a rule-based fallback.
    """
    seq = str(sequence or "").strip()
    if not seq:
        return {"method": "sequence-first recommendation", "confidence": "LOW", "recommended_condition": None, "warnings": ["Current Planner sequence is empty."], "evidence": []}
    statuses = ["verified"] + (["parsed"] if include_parsed else [])
    frame = pd.DataFrame(experimental_data.list_records("cleavage", db_path, statuses=statuses))
    if frame.empty:
        fallback = _sequence_cleavage_condition(seq, str(resin or ""), _num(scale_mmol), frame, product="", db_path=db_path)
        if fallback:
            fallback = dict(fallback)
            fallback.update({"apply_allowed": False, "condition_source": "chemistry_rule_reference", "recommendation_kind": "CHEMISTRY RULE"})
        return {"method": "sequence chemistry fallback", "confidence": "LOW", "recommended_condition": fallback, "warnings": ["No cleavage history is available. Chemistry rule is shown as a non-applicable reference, not as ML/historical evidence."], "evidence": []}

    observations = _product_sequence_observations(db_path)
    mapped_products = {
        product_key for product_key, sequences in observations.items()
        if any(_sequence_observation_matches(observed, seq) for observed in sequences)
    }
    row_sequences = frame.get("sequence", pd.Series(index=frame.index, dtype=object)).fillna("")
    row_sequence_match = row_sequences.map(lambda observed: _sequence_observation_matches(observed, seq) if str(observed).strip() else False)
    product_keys = frame.get("product", pd.Series(index=frame.index, dtype=object)).fillna("").map(_normalize_product_key)
    matched = frame[row_sequence_match | product_keys.isin(mapped_products)].copy()

    # If the current product name is supported by any page-local STD observation,
    # include its historical rows. Multiple page observations are retained; there is
    # no forced product→single-sequence canonicalization.
    product_key = _normalize_product_key(product)
    if product_key and any(_sequence_observation_matches(observed, seq) for observed in observations.get(product_key, set())):
        matched = pd.concat([matched, frame[product_keys.eq(product_key)]], ignore_index=False).drop_duplicates(subset=["record_id"])

    # Chemistry-rule class remains reference metadata only; it does not veto history.
    rule_only = _sequence_cleavage_condition(seq, str(resin or ""), _num(scale_mmol), frame.iloc[0:0], product="", db_path=db_path)
    rule_preset = str((rule_only or {}).get("rule_preset") or (rule_only or {}).get("preset") or "")
    candidates: list[dict[str, Any]] = []
    for row in matched.astype(object).where(pd.notna(matched), None).to_dict("records"):
        cocktail = _recorded_cocktail(row)
        if not cocktail or not _historical_condition_compatible(rule_preset, cocktail["composition_pct"]):
            continue
        eq = _num(row.get("cleavage_eq")); time_h = _num(row.get("cleavage_time_h"))
        if eq is None or time_h is None:
            continue
        outcome_score, outcome_count = _cleavage_outcome_score(row)
        candidates.append({
            "row": row,
            "cocktail": cocktail,
            "cleavage_eq": eq,
            "cleavage_time_h": time_h,
            "outcome_score": outcome_score,
            "outcome_count": outcome_count,
            "verified": str(row.get("status") or "") == "verified",
        })

    if not candidates:
        if not matched.empty:
            evidence_cols = [
                "record_id", "product", "sequence", "scale_mmol", "tfa_ml", "tis_ml",
                "water_ml", "other_scavengers_json", "cleavage_eq", "cleavage_time_h",
                "ether_ratio", "filter_speed", "status", "raw_observation",
            ]
            evidence_cols = [column for column in evidence_cols if column in matched.columns]
            evidence_frame = matched[evidence_cols].copy()
            return {
                "method": "sequence-matched history recognized but incomplete",
                "confidence": "LOW",
                "recommended_condition": None,
                "matched_history_count": int(len(matched)),
                "warnings": [
                    f"{len(matched)} sequence-matched historical record(s) were recognized, but none contains a complete reproducible cocktail (recorded components + eq + time). No chemistry fallback is substituted as if it were historical data."
                ],
                "evidence": evidence_frame.astype(object).where(pd.notna(evidence_frame), None).to_dict("records"),
            }
        fallback = _sequence_cleavage_condition(seq, str(resin or ""), _num(scale_mmol), frame, product="", db_path=db_path)
        if fallback:
            fallback = dict(fallback)
            fallback.update({"apply_allowed": False, "condition_source": "chemistry_rule_reference", "recommendation_kind": "CHEMISTRY RULE"})
        warnings = ["No sequence-matched cleavage history is available. Chemistry rule is shown only as a non-applicable reference; no historical cocktail is invented."]
        return {"method": "sequence chemistry fallback", "confidence": "LOW", "recommended_condition": fallback, "matched_history_count": 0, "warnings": warnings, "evidence": []}

    # Group identical recorded conditions. Composition is atomic; components from
    # different experiments are never averaged or spliced together.
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for candidate in candidates:
        composition = tuple(sorted((str(k), round(float(v), 6)) for k, v in candidate["cocktail"]["composition_pct"].items()))
        key = (candidate["cleavage_eq"], candidate["cleavage_time_h"], composition, str(candidate["row"].get("ether_ratio") or "").strip())
        groups.setdefault(key, []).append(candidate)

    ranked: list[dict[str, Any]] = []
    for key, rows in groups.items():
        outcome_rows = [r for r in rows if r["outcome_count"] > 0]
        quality = sum(r["outcome_score"] for r in outcome_rows) / len(outcome_rows) if outcome_rows else 0.0
        verified_count = sum(r["verified"] for r in rows)
        ranked.append({
            "key": key, "rows": rows, "quality": quality, "outcome_count": len(outcome_rows),
            "evidence_count": len(rows), "verified_count": verified_count,
        })
    any_outcome = any(g["outcome_count"] > 0 for g in ranked)
    if any_outcome:
        chosen_group = max(ranked, key=lambda g: (g["quality"], g["evidence_count"], g["verified_count"], -float(g["key"][0])))
        basis = "best repeated sequence-matched recorded condition using available precipitation/separation/filter outcomes"
    else:
        chosen_group = max(ranked, key=lambda g: (g["evidence_count"], g["verified_count"], -float(g["key"][0])))
        basis = "most repeated sequence-matched recorded condition; no outcome labels available to prove superiority"

    chosen = next((r for r in chosen_group["rows"] if r["verified"]), chosen_group["rows"][0])
    row = chosen["row"]; cocktail = chosen["cocktail"]
    source_per = _num(cocktail.get("source_ml_per_mmol")); scale = _num(scale_mmol)
    scaled_total = source_per * scale if source_per is not None and scale is not None and scale > 0 else None
    confidence = "HIGH" if chosen_group["verified_count"] >= 2 and chosen_group["evidence_count"] >= 3 else "MEDIUM" if chosen_group["verified_count"] >= 1 or chosen_group["evidence_count"] >= 2 else "LOW"
    warnings: list[str] = []
    if chosen_group["verified_count"] == 0:
        warnings.append("Recommendation is provisional because the supporting sequence-matched condition is Parsed, not Verified.")
    if not any_outcome:
        warnings.append("No outcome labels distinguish better from worse sequence-matched conditions; frequency is used, not claimed optimality.")

    recommended = {
        "sequence": seq,
        "cleavage_eq": chosen["cleavage_eq"], "cleavage_time_h": chosen["cleavage_time_h"],
        "preset": "", "composition_pct": cocktail["composition_pct"],
        "scaled_total_ml": scaled_total,
        "volume_apply_allowed": bool(scaled_total is not None and scaled_total > 0),
        "ether_ratio": row.get("ether_ratio"),
        "filter_speed": row.get("filter_speed"),
        "source_record_id": row.get("record_id"), "source_product": row.get("product"), "source_status": row.get("status"),
        "condition_evidence_count": chosen_group["evidence_count"], "condition_verified_count": chosen_group["verified_count"],
        "outcome_evidence_count": chosen_group["outcome_count"],
        "basis": basis,
        "condition_source": "recommended_exact_sequence_record",
        "apply_allowed": True,
        "recommendation_kind": "observed_sequence_condition",
    }
    evidence = []
    for group in ranked:
        evidence.append({
            "cleavage_eq": group["key"][0], "cleavage_time_h": group["key"][1],
            "composition": dict(group["key"][2]), "ether_ratio": group["key"][3],
            "evidence_count": group["evidence_count"], "verified_count": group["verified_count"],
            "outcome_evidence_count": group["outcome_count"], "outcome_score": group["quality"],
        })
    return {
        "method": "sequence-matched observed-condition recommendation", "confidence": confidence,
        "evidence_summary": {
            "source_kind": "HISTORICAL CONSENSUS",
            "matched_records": int(len(matched)),
            "condition_records": int(chosen_group["evidence_count"]),
            "verified_condition_records": int(chosen_group["verified_count"]),
            "outcome_records": int(chosen_group["outcome_count"]),
            "apply_allowed": True,
        },
        "recommended_condition": recommended, "warnings": warnings, "evidence": evidence,
    }


__all__ = ["loading_advice", "cleavage_advice", "loading_recommendation", "cleavage_recommendation"]
