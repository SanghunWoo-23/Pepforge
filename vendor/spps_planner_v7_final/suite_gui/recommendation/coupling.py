"""Canonical coupling recommendation implementation.

The validated V4 consensus engine remains the source of actionable coupling
conditions. This owner adds decision-support context and evidence-quality metadata without
inventing reagent identities, dosages, or cross-record synthetic cocktails.
"""
from __future__ import annotations
from typing import Any, Iterable, Mapping

from . import coupling_base as coupling_engine
from .decision_support import sequence_difficulty_map


def _quality(result: Mapping[str, Any]) -> dict[str, Any]:
    independent = int(result.get("independent_experiment_count") or 0)
    actionable = [row for row in (result.get("unit_recommendations") or []) if row.get("apply_allowed")]
    all_units = list(result.get("unit_recommendations") or [])
    consensus_support = min([int(row.get("independent_experiment_count") or 0) for row in actionable], default=0)
    conflicts = int(bool(actionable) and len(actionable) != len(all_units))
    level = "HIGH" if consensus_support >= 4 and not conflicts else "MEDIUM" if consensus_support >= 2 else "LOW"
    return {
        "level": level,
        "independent_reviewed_syntheses": independent,
        "actionable_units": len(actionable),
        "current_units": len(all_units),
        "minimum_consensus_support": consensus_support,
        "conflicting_or_unsupported_units": max(0, len(all_units) - len(actionable)),
        "kind": "evidence quality; not a biochemical success probability",
    }


def coupling_advice(items: Iterable[Any], current_item: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(coupling_engine.coupling_advice(items, current_item))
    result["engine_version"] = "6.0.0"
    result["evidence_quality"] = _quality(result)
    result["sequence_difficulty"] = sequence_difficulty_map(str(current_item.get("sequence") or ""))
    result["ranking_policy"] = (
        "Repeated successful bottle-level historical consensus first; sequence/resin similarity "
        "ranks observed source records only. No new categorical reagent condition is generated."
    )
    return result


def advise(items, active):
    return coupling_advice(items, active)

parse_ether_ratio = coupling_engine.parse_ether_ratio

__all__ = ["advise", "coupling_advice", "parse_ether_ratio"]
