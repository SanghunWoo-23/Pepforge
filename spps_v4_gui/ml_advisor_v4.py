"""Evidence-first loading and cleavage advisors for SPPS Planner V4.0.0."""
from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from spps_v4_gui import experimental_data


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
    frame = frame[frame["outlier_flag"].fillna(0).astype(int) == 0]
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
    frame = _eligible_loading(db_path, include_parsed)
    if frame.empty:
        return {"method": "no-data", "prediction": None, "confidence": "LOW", "evidence": [], "recommended_condition": None, "message": "No eligible loading records."}

    q_aa = _num(aa_eq); q_base = _num(base_eq); q_time = _num(loading_time_h)
    q_target = _num(target_loading_mmol_g)
    frame = frame.copy()
    frame["resin_match"] = (frame["resin_type"].fillna("") == resin_n).astype(float)
    frame["aa_match"] = (frame["amino_acid_normalized"].fillna("") == aa_n).astype(float)
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

    evidence_cols = ["record_id", "date", "resin_type", "amino_acid_normalized", "aa_eq", "base_eq", "loading_time_h", "loading_solvent", "loading_rate_mmol_g", "status", "raw_note"]
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
        "recommended_condition": recommended,
        "warnings": warnings, "evidence": evidence,
    }


def _normalize_product_key(value: Any) -> str:
    """Normalize cosmetic/date variants without merging distinct peptide numbers."""
    text = str(value or "").strip().lower().replace("–", "-").replace("—", "-")
    # Historical report names commonly append production dates in parentheses.
    text = re.sub(r"\((?:\d{6,8}|\d{2}[.]\d{2}[.]\d{2})\)\s*$", "", text)
    text = re.sub(r"\s*-\s*", "-", text)
    text = re.sub(r"\s+", " ", text).strip(" :")
    return text




def _sequence_match_key(sequence: Any) -> str:
    text = str(sequence or "").strip()
    if not text:
        return ""
    try:
        from spps_planner.parser import parse_sequence
        parsed = parse_sequence(text)
        tokens = []
        for token in list(parsed.core_tokens or []) + list(getattr(parsed, "branch_tokens", []) or []):
            raw = str(token).strip()
            if raw.lower().startswith("d") and len(raw) > 1:
                tokens.append("d" + raw[1:].upper())
            else:
                tokens.append(raw.upper())
        nterm = str(getattr(parsed, "nterm", "") or "").strip().upper()
        cterm = str(getattr(parsed, "cterm_text", "") or "").strip().upper()
        return "|".join([nterm, *tokens, cterm])
    except Exception:
        return re.sub(r"\s+", "", text).upper()


def _bundled_product_sequence_map() -> dict[str, str]:
    root = Path(__file__).resolve().parents[1] / "apps" / "spps_planner_app" / "data" / "experimental_seed"
    path = root / "cleavage_sequence_map_seed.csv"
    if not path.is_file():
        return {}
    try:
        frame = pd.read_csv(path)
    except Exception:
        return {}
    out: dict[str, str] = {}
    for _, row in frame.iterrows():
        product_key = _normalize_product_key(row.get("product_key"))
        seq_key = _sequence_match_key(row.get("sequence"))
        if product_key and seq_key:
            out[product_key] = seq_key
    return out


def _product_sequence_supported(product: Any, sequence: Any, exact_rows: pd.DataFrame) -> tuple[bool, str]:
    current_key = _sequence_match_key(sequence)
    if not current_key:
        return False, "current sequence is empty/unparseable"
    row_keys = set()
    if not exact_rows.empty and "sequence" in exact_rows:
        for value in exact_rows["sequence"].dropna().tolist():
            key = _sequence_match_key(value)
            if key:
                row_keys.add(key)
    if current_key in row_keys:
        return True, "sequence stored in exact experimental record"
    product_key = _normalize_product_key(product)
    mapped = _bundled_product_sequence_map().get(product_key)
    if mapped:
        return (mapped == current_key, "local product↔sequence mapping" if mapped == current_key else "product name exists but mapped sequence does not match current Planner sequence")
    return False, "no verified product↔sequence mapping is available for this historical product"

def _json_components(value: Any) -> dict[str, float]:
    try:
        import json
        raw = json.loads(str(value or "{}"))
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, float] = {}
    for key, value in raw.items():
        number = _num(value)
        if number is not None and number > 0:
            out[str(key)] = number
    return out


def _recorded_cocktail(row: Mapping[str, Any]) -> dict[str, Any] | None:
    """Recover one recorded cocktail without turning an unexplained blank into zero.

    A blank TIS cell can be accepted as a recorded zero only when the other recorded
    liquid volumes already account for the full reported cocktail volume implied by
    scale x cleavage_eq.  This supports complete TFA/water records while still preventing arbitrary
    blank-as-zero interpretation.
    """
    scale = _num(row.get("scale_mmol"))
    eq = _num(row.get("cleavage_eq"))
    known = {
        "TFA": _num(row.get("tfa_ml")),
        "TIS": _num(row.get("tis_ml")),
        "Water": _num(row.get("water_ml")),
    }
    other = _json_components(row.get("other_scavengers_json"))
    if other:
        return None
    present_total = sum(v for v in known.values() if v is not None and v >= 0)
    expected_total = (scale * eq) if scale and scale > 0 and eq and eq > 0 else None
    if expected_total is not None and expected_total > 0:
        relative_error = abs(present_total - expected_total) / expected_total
        blanks = [name for name, value in known.items() if value is None]
        if blanks and relative_error <= 0.02:
            # The explicitly recorded components already sum to the full reported
            # total, so the blank standard component is supported as not used.
            for name in blanks:
                known[name] = 0.0
    if any(value is None for value in known.values()):
        return None
    total = sum(float(value or 0.0) for value in known.values())
    if total <= 0:
        return None
    pct = {name: float(value or 0.0) / total * 100.0 for name, value in known.items() if float(value or 0.0) > 0}
    return {"composition_pct": pct, "source_total_ml": total, "source_ml_per_mmol": (total / scale if scale and scale > 0 else None)}


def _historical_condition_compatible(rule_preset: str, composition: Mapping[str, float]) -> bool:
    """Require sequence-sensitive scavengers while allowing simple lab 95/5 history."""
    names = {str(name).strip().lower() for name, value in composition.items() if _num(value) and float(value) > 0}
    if "tfa" not in names:
        return False
    preset = str(rule_preset or "").strip().upper()
    # Standard/non-sensitive sequences may use a complete recorded TFA/water
    # condition; TIS is not manufactured when the historical record omits it.
    if preset in {"DEFAULT_TFA_TIS_WATER", "DEFAULT_TFA_WATER", "TFA_TIS_WATER_96_2_2"}:
        return "water" in names
    requirements = {
        "REDUCING_TFA_TIS_WATER_EDT": {"edt", "water"},
        "CYS_EDT": {"edt", "water"},
        "REAGENT_B": {"phenol", "water"},
        "REAGENT_K": {"phenol", "water", "thioanisole", "edt"},
        "REAGENT_L": {"dtt", "water"},
        "REAGENT_R": {"thioanisole", "edt"},
        "REAGENT_H": {"phenol", "thioanisole", "edt"},
        "REAGENT_I": {"dmb"},
    }
    required = requirements.get(preset)
    return bool(required and required.issubset(names))


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

        # Exact-sequence evidence is the primary refinement source. Product-name
        # evidence is considered only when an explicit product↔sequence mapping
        # supports it. A label must never override the current Planner sequence.
        sequence_key = _sequence_match_key(seq)
        exact = frame.iloc[0:0]
        product_sequence_basis = "no exact sequence record"
        if sequence_key and "sequence" in frame:
            sequence_keys = frame["sequence"].fillna("").map(_sequence_match_key)
            exact = frame[sequence_keys.eq(sequence_key)].copy()
            if not exact.empty:
                product_sequence_basis = "exact sequence stored in experimental record"

        product_key = _normalize_product_key(product)
        if exact.empty and product_key and "product" in frame:
            keys = frame["product"].fillna("").map(_normalize_product_key)
            exact = frame[keys.eq(product_key)].copy()
            product_sequence_ok, product_sequence_basis = _product_sequence_supported(product, seq, exact)
            if not product_sequence_ok:
                exact = exact.iloc[0:0]
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
                "basis": f"{product_sequence_basis}; exact lab record {chosen.get('record_id')} ({chosen.get('source_product')}); sequence rule={rule_preset}",
                "time_basis": "same exact-product laboratory record" if _num(chosen.get("cleavage_time_h")) is not None else "mode of exact-product laboratory records",
                "eq_basis": "same exact-product laboratory record" if _num(chosen.get("cleavage_eq")) is not None else str(eq_info.get("source") or "planner sequence rule"),
                "condition_source": "exact_lab_record",
                "source_record_id": chosen.get("record_id"),
                "source_product": chosen.get("source_product"),
                "source_status": chosen.get("source_status"),
                "rule_preset": rule_preset,
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
    product_low = str(product or "").strip().lower()
    seq_text = str(sequence or "").strip()
    sequence_key = _sequence_match_key(seq_text)
    frame = all_frame.copy()
    frame["distance"] = 2.0
    if sequence_key:
        frame["sequence_match"] = frame["sequence"].fillna("").map(_sequence_match_key).eq(sequence_key).astype(float)
        frame["distance"] -= frame["sequence_match"] * 1.5
    else:
        frame["sequence_match"] = 0.0
    if product_low:
        frame["product_match"] = frame["product"].fillna("").str.strip().str.lower().eq(product_low).astype(float)
        frame["distance"] -= frame["product_match"] * 1.0
    else:
        frame["product_match"] = 0.0
    for column, query, scale in (("scale_mmol", q_scale, 0.004), ("cleavage_eq", q_eq, 0.03), ("cleavage_time_h", q_time, 0.20)):
        values = pd.to_numeric(frame[column], errors="coerce")
        if query is not None:
            frame["distance"] += (values - query).abs().fillna(10.0) * scale
    frame = frame.sort_values("distance").head(10)
    exact = frame[frame["sequence_match"] == 1].copy() if sequence_key else frame.iloc[0:0].copy()
    parsed_fraction = float((frame["status"] == "parsed").mean())
    confidence = _confidence(len(frame), len(exact), None, parsed_fraction)

    recommended = _sequence_cleavage_condition(seq_text, str(resin or ""), q_scale, all_frame, product=str(product or "")) if seq_text else None
    warnings: list[str] = []
    if not seq_text:
        recommended = None
        warnings.append("Planner sequence is empty; product-name matching is evidence only and Apply is disabled.")
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
        fallback = _sequence_cleavage_condition(seq, str(resin or ""), _num(scale_mmol), frame, product="")
        return {"method": "sequence chemistry fallback", "confidence": "LOW", "recommended_condition": fallback, "warnings": ["No cleavage history is available; recommendation is chemistry-rule only."], "evidence": []}

    current_key = _sequence_match_key(seq)
    mapped_products = {p for p, s in _bundled_product_sequence_map().items() if s == current_key}
    row_sequence_keys = frame.get("sequence", pd.Series(index=frame.index, dtype=object)).fillna("").map(_sequence_match_key)
    product_keys = frame.get("product", pd.Series(index=frame.index, dtype=object)).fillna("").map(_normalize_product_key)
    matched = frame[row_sequence_keys.eq(current_key) | product_keys.isin(mapped_products)].copy()

    # If the product field itself is correct and mapped to the current sequence, include it.
    product_key = _normalize_product_key(product)
    if product_key and _bundled_product_sequence_map().get(product_key) == current_key:
        matched = pd.concat([matched, frame[product_keys.eq(product_key)]], ignore_index=False).drop_duplicates(subset=["record_id"])

    # Get the chemistry-rule class solely as a compatibility gate.
    rule_only = _sequence_cleavage_condition(seq, str(resin or ""), _num(scale_mmol), frame.iloc[0:0], product="")
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
        fallback = _sequence_cleavage_condition(seq, str(resin or ""), _num(scale_mmol), frame, product="")
        warnings = ["No complete sequence-matched historical cocktail is available; chemistry-rule recommendation is used without inventing a lab cocktail."]
        return {"method": "sequence chemistry fallback", "confidence": "LOW", "recommended_condition": fallback, "warnings": warnings, "evidence": []}

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
    return {"method": "sequence-matched observed-condition recommendation", "confidence": confidence, "recommended_condition": recommended, "warnings": warnings, "evidence": evidence}


__all__ = ["loading_advice", "cleavage_advice", "loading_recommendation", "cleavage_recommendation"]
