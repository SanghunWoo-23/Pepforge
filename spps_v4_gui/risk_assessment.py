"""Versioned risk assessments and acknowledgement audit records."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Callable, Mapping
from uuid import uuid4

from spps_v4_gui import risk_engine


RISK_KEY = "risk_review"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _id() -> str:
    return uuid4().hex


def ensure_review(container: dict[str, Any]) -> dict[str, Any]:
    review = container.get(RISK_KEY)
    if not isinstance(review, Mapping):
        review = {}
    normalized = {
        "schema_version": 1, "revision": int(review.get("revision", 0) or 0),
        "current": deepcopy(review.get("current", {})) if isinstance(review.get("current"), Mapping) else {},
        "versions": [deepcopy(row) for row in review.get("versions", []) if isinstance(row, Mapping)],
        "acknowledgements": [deepcopy(row) for row in review.get("acknowledgements", []) if isinstance(row, Mapping)],
    }
    container[RISK_KEY] = normalized
    return normalized


def save_assessment(container: dict[str, Any], assessment: Mapping[str, Any], *,
                    clock: Callable[[], str] = _now, id_factory: Callable[[], str] = _id) -> dict[str, Any]:
    review = ensure_review(container)
    payload = deepcopy(dict(assessment))
    for key in ("assessment_id", "revision", "assessed_at", "fingerprint"):
        payload.pop(key, None)
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    fingerprint = sha256(canonical.encode("utf-8")).hexdigest()
    if review["current"].get("fingerprint") == fingerprint:
        return deepcopy(review["current"])
    revision = review["revision"] + 1
    saved = {**payload, "assessment_id": id_factory(), "revision": revision,
             "assessed_at": clock(), "fingerprint": fingerprint}
    review["revision"] = revision
    review["current"] = deepcopy(saved)
    review["versions"].append(deepcopy(saved))
    return saved


def acknowledge(container: dict[str, Any], finding_id: str, reason: str, *,
                clock: Callable[[], str] = _now, id_factory: Callable[[], str] = _id) -> dict[str, Any]:
    if not str(reason).strip():
        raise ValueError("An acknowledgement reason is required.")
    review = ensure_review(container)
    current = review.get("current", {})
    if not any(str(row.get("finding_id")) == str(finding_id) for row in current.get("findings", [])):
        raise ValueError("Risk finding was not found in the current assessment.")
    event = {"acknowledgement_id": id_factory(), "finding_id": str(finding_id),
             "assessment_id": current.get("assessment_id", ""), "timestamp": clock(),
             "reason": str(reason).strip()}
    review["acknowledgements"].append(event)
    return deepcopy(event)


def assess(container: dict[str, Any]) -> dict[str, Any]:
    return risk_engine.evaluate_rules(container)


__all__ = ["RISK_KEY", "acknowledge", "assess", "ensure_review", "save_assessment"]
