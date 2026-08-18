"""Reviewed, versionable ML observations built from real Work Item history."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
from typing import Any, Callable, Iterable, Mapping
from uuid import uuid4

import pandas as pd

from spps_v4_gui import synthesis_execution


SCHEMA_VERSION = 1
REVIEW_KEY = "ml_review"
TARGETS = (
    "actual_yield_percent",
    "actual_purity_percent",
    "failure_flag",
    "doubling_required",
)
TARGET_TASKS = {
    "actual_yield_percent": "regression",
    "actual_purity_percent": "regression",
    "failure_flag": "classification",
    "doubling_required": "classification",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id() -> str:
    return uuid4().hex


def _float(value: Any, *, name: str, percent: bool = False) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        number = float(str(value).replace(",", "").strip())
    except ValueError as exc:
        raise ValueError(f"{name} must be numeric.") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite.")
    if percent and not 0 <= number <= 100:
        raise ValueError(f"{name} must be between 0 and 100.")
    return number


def _bool(value: Any, *, name: str) -> bool | None:
    if value is None or str(value).strip().lower() in {"", "unknown", "auto", "none"}:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "failed", "required"}:
        return True
    if text in {"0", "false", "no", "n", "passed", "not required"}:
        return False
    raise ValueError(f"{name} must be Yes, No, or Unknown.")


def normalize_review(value: Any) -> dict[str, Any]:
    source = value if isinstance(value, Mapping) else {}
    current = dict(source.get("current", {})) if isinstance(source.get("current"), Mapping) else {}
    versions = [
        dict(version)
        for version in source.get("versions", [])
        if isinstance(version, Mapping)
    ]
    revision = max(
        [int(source.get("revision", 0) or 0)]
        + [int(version.get("revision", 0) or 0) for version in versions]
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "revision": revision,
        "current": current,
        "versions": versions,
    }


def ensure_review(item: dict[str, Any]) -> dict[str, Any]:
    synthesis_execution.ensure_work_item_id(item)
    review = normalize_review(item.get(REVIEW_KEY))
    item[REVIEW_KEY] = review
    return review


def effective_doubling(item: Mapping[str, Any]) -> bool:
    history = synthesis_execution.events(item)
    compensated = synthesis_execution.compensated_event_ids(history)
    return any(
        event.get("event_type") == "doubling"
        and str(event.get("event_id", "")) not in compensated
        and str(event.get("after", "")) != "1"
        for event in history
    )


def review_item(
    item: dict[str, Any],
    *,
    actual_yield_percent: Any = None,
    actual_purity_percent: Any = None,
    failure_flag: Any = None,
    doubling_required: Any = None,
    included: bool = True,
    exclusion_reason: str = "",
    review_reason: str,
    operator_note: str = "",
    clock: Callable[[], str] = _utc_now,
    id_factory: Callable[[], str] = _new_id,
) -> dict[str, Any]:
    """Save one reviewed outcome revision without deleting earlier revisions."""
    reason = str(review_reason).strip()
    if not reason:
        raise ValueError("A review reason is required.")
    exclusion_reason = str(exclusion_reason).strip()
    if not bool(included) and not exclusion_reason:
        raise ValueError("An exclusion reason is required when data is excluded.")
    doubling = _bool(doubling_required, name="Doubling required")
    doubling_source = "reviewed"
    if doubling is None:
        doubling = effective_doubling(item)
        doubling_source = "inferred_from_execution"
    after = {
        "reviewed": True,
        "included": bool(included),
        "exclusion_reason": exclusion_reason if not included else "",
        "actual_yield_percent": _float(
            actual_yield_percent, name="Actual yield %", percent=True,
        ),
        "actual_purity_percent": _float(
            actual_purity_percent, name="Actual purity %", percent=True,
        ),
        "failure_flag": _bool(failure_flag, name="Failure flag"),
        "doubling_required": doubling,
        "doubling_source": doubling_source,
        "operator_note": str(operator_note or ""),
        "reviewed_at": clock(),
        "source_event_count": len(synthesis_execution.events(item)),
    }
    review = ensure_review(item)
    revision = int(review["revision"]) + 1
    version = {
        "version_id": id_factory(),
        "revision": revision,
        "timestamp": after["reviewed_at"],
        "work_item_id": item["work_item_id"],
        "before": deepcopy(review.get("current", {})),
        "after": deepcopy(after),
        "reason": reason,
    }
    review["revision"] = revision
    review["current"] = after
    review["versions"].append(version)
    return deepcopy(version)


def review_versions(item: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [deepcopy(row) for row in normalize_review(item.get(REVIEW_KEY))["versions"]]


def _num(value: Any, default: float = 0.0) -> float:
    try:
        number = float(str(value).replace(",", "").strip())
        return number if math.isfinite(number) else default
    except Exception:
        return default


def _sequence_features(sequence: str) -> dict[str, Any]:
    try:
        from spps_planner.parser import NATURAL_AA_LETTERS, parse_sequence

        parsed = parse_sequence(sequence)
        tokens = list(parsed.core_tokens or []) + list(parsed.branch_tokens or [])
        normalized = [str(token).replace("d", "", 1).upper() for token in tokens]
        natural = set(NATURAL_AA_LETTERS)
        return {
            "sequence_length": len(tokens),
            "branch_count": len(parsed.branch_sites or []),
            "nterm_modified": bool(parsed.nterm),
            "d_residue_count": sum(str(token).startswith("d") for token in tokens),
            "non_natural_count": sum(token not in natural for token in normalized),
            "cys_count": normalized.count("C"),
            "pro_count": normalized.count("P"),
            "gly_count": normalized.count("G"),
            "hydrophobic_count": sum(token in set("AILMFWVY") for token in normalized),
            "charged_count": sum(token in set("DEKR") for token in normalized),
        }
    except Exception:
        compact = "".join(ch for ch in str(sequence) if ch.isalpha())
        return {
            "sequence_length": len(compact), "branch_count": 0,
            "nterm_modified": False, "d_residue_count": 0,
            "non_natural_count": 0, "cys_count": compact.upper().count("C"),
            "pro_count": compact.upper().count("P"),
            "gly_count": compact.upper().count("G"),
            "hydrophobic_count": 0, "charged_count": 0,
        }


def observation(item: Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(item, dict):
        synthesis_execution.ensure_work_item_id(item)
    history = synthesis_execution.events(item)
    compensated = synthesis_execution.compensated_event_ids(history)
    active_events = [
        event for event in history
        if event.get("event_type") != "revert"
        and str(event.get("event_id", "")) not in compensated
    ]
    values = synthesis_execution.current_values(item)
    plan = [
        dict(row) for row in item.get("selected_plan_rows", [])
        if isinstance(row, Mapping)
    ]
    repeats = [_num(row.get("Repeat"), 1.0) for row in plan]
    unit_eqs = [_num(row.get("Unit eq"), 0.0) for row in plan]
    statuses = [
        value for (step, field), value in values.items() if field == "step_status"
    ]
    actuals = [
        value for (step, field), value in values.items()
        if field.startswith("actual_material::") and isinstance(value, Mapping)
    ]
    amount_by_unit = {"mmol": 0.0, "mg": 0.0, "g": 0.0, "µL": 0.0, "mL": 0.0}
    for actual in actuals:
        unit = str(actual.get("unit", ""))
        if unit in amount_by_unit:
            amount_by_unit[unit] += _num(actual.get("amount"), 0.0)
    review = normalize_review(item.get(REVIEW_KEY))
    current = review.get("current", {})
    sequence = str(item.get("sequence", ""))
    row = {
        "feature_schema_version": SCHEMA_VERSION,
        "work_item_id": str(item.get("work_item_id", "")),
        "project": item.get("project", ""),
        "peptide": item.get("peptide", ""),
        "sequence": sequence,
        "scale_mmol": _num(item.get("scale"), 0.0),
        "resin": item.get("resin", ""),
        "loading_mmol_g": _num(item.get("loading"), 0.0),
        "chemistry": item.get("chemistry", ""),
        "copies": _num(item.get("copies"), 1.0),
        "plan_step_count": len(plan),
        "mean_unit_eq": sum(unit_eqs) / len(unit_eqs) if unit_eqs else 0.0,
        "max_unit_eq": max(unit_eqs, default=0.0),
        "mean_repeat": sum(repeats) / len(repeats) if repeats else 0.0,
        "max_repeat": max(repeats, default=0.0),
        "plan_doubling_step_count": sum(repeat >= 2 for repeat in repeats),
        "execution_event_count": len(history),
        "active_execution_event_count": len(active_events),
        "correction_count": sum(event.get("event_type") == "plan_correction" for event in active_events),
        "doubling_event_count": sum(event.get("event_type") == "doubling" for event in active_events),
        "revert_count": sum(event.get("event_type") == "revert" for event in history),
        "actual_material_record_count": len(actuals),
        "actual_material_unique_count": len({str(value.get("material", "")) for value in actuals}),
        "completed_step_count": statuses.count("Completed"),
        "failed_step_count": statuses.count("Failed"),
        "hold_step_count": statuses.count("Hold"),
        "actual_total_mmol": amount_by_unit["mmol"],
        "actual_total_mg": amount_by_unit["mg"],
        "actual_total_g": amount_by_unit["g"],
        "actual_total_uL": amount_by_unit["µL"],
        "actual_total_mL": amount_by_unit["mL"],
        "review_status": "reviewed" if current.get("reviewed") else "unreviewed",
        "review_revision": review.get("revision", 0),
        "included": bool(current.get("included", False)),
        "exclusion_reason": current.get("exclusion_reason", ""),
        "reviewed_at": current.get("reviewed_at", ""),
        "actual_yield_percent": current.get("actual_yield_percent"),
        "actual_purity_percent": current.get("actual_purity_percent"),
        "failure_flag": current.get("failure_flag"),
        "doubling_required": current.get("doubling_required"),
    }
    row.update(_sequence_features(sequence))
    return row


def dataset_frame(items: Iterable[Any]) -> pd.DataFrame:
    rows = [observation(item) for item in items if isinstance(item, Mapping)]
    return pd.DataFrame(rows)


def dataset_fingerprint(frame: pd.DataFrame) -> str:
    records = frame.where(pd.notna(frame), None).to_dict("records")
    payload = json.dumps(
        {"schema_version": SCHEMA_VERSION, "records": records},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


__all__ = [
    "REVIEW_KEY", "SCHEMA_VERSION", "TARGETS", "TARGET_TASKS",
    "dataset_fingerprint", "dataset_frame", "effective_doubling",
    "ensure_review", "normalize_review", "observation", "review_item",
    "review_versions",
]
