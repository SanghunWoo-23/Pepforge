"""Authoritative resin identity and direct-loading rules for the desktop UI."""
from __future__ import annotations

from dataclasses import replace


REMOVED_CTC_ALIASES = {
    "CTC(합성용)",
    "CTC 합성용",
    "CTC-synthesis",
    "CTC synthesis",
}


def normalize_resin(value):
    """Migrate removed saved aliases without collapsing active resin choices."""
    text = str(value or "").strip()
    if text in REMOVED_CTC_ALIASES:
        return "CTC(합성기)"
    if text.lower() in {"ctc/trityl", "ctc_trityl"}:
        return "2-CTC"
    return text or "Rink Amide AM"


def is_direct_resin(value):
    """Return whether the profile supports direct C-terminal loading."""
    resin = normalize_resin(value)
    try:
        from spps_planner.engine import resin_profile

        return resin_profile(resin) == "CTC_DIRECT"
    except Exception:
        return resin == "2-CTC"


def item_loading_enabled(item, resin=None):
    item = item or {}
    normalized = normalize_resin(
        resin if resin is not None else item.get("resin", "")
    )
    return bool(item.get("apply_loading_calc", False)) and is_direct_resin(
        normalized
    )


def _get_var(gui, name, default=""):
    value = getattr(gui, name, default)
    try:
        return value.get()
    except Exception:
        return value


def editor_loading_enabled(gui, resin=None):
    normalized = normalize_resin(
        resin if resin is not None else _get_var(gui, "pm_resin", "")
    )
    if not is_direct_resin(normalized):
        return False
    try:
        return bool(gui.apply_loading_calc.get())
    except Exception:
        return False


def apply_editor_profile(gui, base_plan):
    """Apply the final editor resin/loading state to an existing PlanInput."""
    resin = normalize_resin(
        _get_var(gui, "pm_resin", getattr(base_plan, "resin", ""))
    )
    return replace(
        base_plan,
        resin=resin,
        apply_resin_loading=editor_loading_enabled(gui, resin),
    )


def apply_batch_profile(row, base_plan):
    """Apply one saved peptide's final resin/loading state to a PlanInput."""
    resin = normalize_resin(row.get("Resin", getattr(base_plan, "resin", "")))
    loading_enabled = bool(row.get("_apply_loading_calc", False))
    loading_enabled = loading_enabled and is_direct_resin(resin)
    return replace(
        base_plan,
        resin=resin,
        apply_resin_loading=loading_enabled,
        loading_aa_eq=float(
            row.get(
                "_loading_aa_eq",
                getattr(base_plan, "loading_aa_eq", 2.0),
            )
            or 2.0
        ),
        loading_diea_eq=float(
            row.get(
                "_loading_diea_eq",
                getattr(base_plan, "loading_diea_eq", 4.0),
            )
            or 4.0
        ),
    )


__all__ = [
    "REMOVED_CTC_ALIASES",
    "apply_batch_profile",
    "apply_editor_profile",
    "editor_loading_enabled",
    "is_direct_resin",
    "item_loading_enabled",
    "normalize_resin",
]
