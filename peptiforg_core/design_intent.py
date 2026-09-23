from __future__ import annotations

"""Normalize PDE -> downstream design-intent metadata.

Pepforge exports PDE rows with ``pde_objective_mode`` while older internal
structure bridges historically consumed ``mode``.  This module provides one
small, dependency-free normalization boundary so PSB, workflow mode, reports,
and future downstream tools see the same intent without silently dropping the
structure objective.
"""

from typing import Any, Mapping

_ALLOWED_MODES = {
    "INTERACTION_ONLY",
    "INTERACTION_FIRST",
    "BALANCED",
    "STRUCTURE_GUIDED",
    "STRUCTURE_EXPLORATION",
}
_ALLOWED_STRATEGIES = {"PREORGANIZED", "ADAPTIVE", "FLEXIBLE"}
_ALLOWED_HOTSPOT_COMPLEMENTARITY_MODES = {"OFF", "REPORT_ONLY", "EVIDENCE_AND_SELECTION"}

_ALLOWED_STRUCTURES = {
    "NONE",
    "ALPHA_HELIX",
    "AMPHIPATHIC_ALPHA",
    "HELIX_310",
    "BETA_HAIRPIN",
    "BETA_STRAND",
    "PPII_EXTENDED",
    "TURN_RICH",
    "COILED_COIL",
}


def _upper(value: Any, default: str = "") -> str:
    text = str(value or "").strip().upper()
    return text or default


def normalize_design_intent(intent: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return canonical downstream PDE intent keys without inventing evidence.

    Accepted mode keys are ``mode`` and the PDE export key
    ``pde_objective_mode``. Unknown non-empty values are retained in the
    ``*_raw`` fields but canonical values fall back conservatively.
    Interaction Only always disables a downstream preferred fold.
    """
    src = dict(intent or {})
    raw_mode = _upper(src.get("mode") or src.get("pde_objective_mode"), "BALANCED")
    mode = raw_mode if raw_mode in _ALLOWED_MODES else "BALANCED"
    raw_structure = _upper(src.get("preferred_structure"), "NONE")
    preferred_structure = raw_structure if raw_structure in _ALLOWED_STRUCTURES else "NONE"
    if mode == "INTERACTION_ONLY":
        preferred_structure = "NONE"

    raw_strategy = _upper(src.get("conformational_strategy"), "PREORGANIZED")
    strategy = raw_strategy if raw_strategy in _ALLOWED_STRATEGIES else "PREORGANIZED"
    raw_hotspot_mode = _upper(src.get("hotspot_complementarity_mode"), "REPORT_ONLY")
    hotspot_mode = raw_hotspot_mode if raw_hotspot_mode in _ALLOWED_HOTSPOT_COMPLEMENTARITY_MODES else "REPORT_ONLY"

    out = dict(src)
    out.update({
        "mode": mode,
        "pde_objective_mode": mode,
        "preferred_structure": preferred_structure,
        "structure_bias": _upper(src.get("structure_bias"), ""),
        "environment": str(src.get("environment") or src.get("structure_environment") or "").strip(),
        "conformational_strategy": strategy,
        "hotspot_complementarity_mode": hotspot_mode,
        "structure_direction_active": src.get("structure_direction_active", ""),
    })
    if raw_mode != mode:
        out["mode_raw"] = raw_mode
    if raw_structure != preferred_structure and mode != "INTERACTION_ONLY":
        out["preferred_structure_raw"] = raw_structure
    if raw_strategy != strategy:
        out["conformational_strategy_raw"] = raw_strategy
    if raw_hotspot_mode != hotspot_mode:
        out["hotspot_complementarity_mode_raw"] = raw_hotspot_mode
    out["claim_guard"] = (
        "PDE design intent is transfer metadata. It directs supported downstream search/ranking; "
        "Conformational Strategy changes optimization pressure only and is not a binding-mechanism assignment, "
        "experimental structural evidence, or a native-state probability."
    )
    return out


__all__ = ["normalize_design_intent"]
