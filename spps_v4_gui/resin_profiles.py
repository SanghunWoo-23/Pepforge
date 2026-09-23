"""Authoritative resin identity and direct-loading rules for the desktop UI."""
from __future__ import annotations

from dataclasses import replace
import csv
import re
from pathlib import Path


REMOVED_CTC_ALIASES = {
    "CTC(합성용)",
    "CTC 합성용",
    "CTC-synthesis",
    "CTC synthesis",
}


ROOT = Path(__file__).resolve().parents[1]
SETTINGS_DB_PATH = ROOT / "apps" / "spps_planner_app" / "data" / "settings_db.csv"


def _resin_key(value):
    text = str(value or "").strip().lower()
    text = text.replace(" resin", "")
    return re.sub(r"[^0-9a-z가-힣]+", "", text)


def _settings_loading_catalog():
    """Read the original SPPS settings database as the loading source of truth."""
    out = {}
    try:
        with SETTINGS_DB_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                resin = str(row.get("Resin", "") or "").strip()
                raw = str(row.get("Default loading (mmol/g)", "") or "").strip()
                if not resin or not raw:
                    continue
                try:
                    value = float(raw)
                except Exception:
                    continue
                out[_resin_key(resin)] = value
    except Exception:
        return {}
    return out


def default_loading_for_resin(value):
    """Return the original planner's default resin loading, or None if unknown.

    Only aliases that are explicitly equivalent to a settings_db resin are
    migrated.  Resin types without an original database value keep the user's
    current loading rather than receiving an invented number.
    """
    key = _resin_key(normalize_resin(value))
    aliases = {
        _resin_key("Amide"): _resin_key("Rink Amide AM resin"),
        _resin_key("Rink Amide"): _resin_key("Rink Amide AM resin"),
        _resin_key("Rink Amide AM"): _resin_key("Rink Amide AM resin"),
        _resin_key("Rink Amide MBHA"): _resin_key("Rink Amide MBHA resin"),
        _resin_key("Sieber Amide"): _resin_key("Sieber Amide resin"),
        _resin_key("Wang"): _resin_key("Wang resin"),
        _resin_key("CTC/Trityl"): _resin_key("2-CTC"),
        _resin_key("CTC(합성기)"): _resin_key("2-CTC"),
    }
    key = aliases.get(key, key)
    return _settings_loading_catalog().get(key)


def apply_default_loading_to_editor(gui, resin=None):
    """Apply the original resin default to the visible editor when available."""
    selected = resin if resin is not None else _get_var(gui, "pm_resin", "")
    value = default_loading_for_resin(selected)
    if value is None:
        return None
    variable = getattr(gui, "pm_loading", None)
    if hasattr(variable, "set"):
        variable.set(f"{value:g}")
    legacy = getattr(gui, "loading", None)
    if hasattr(legacy, "set"):
        try:
            legacy.set(value)
        except Exception:
            pass
    return value


def bind_resin_loading_autofill(gui):
    """Bind resin selection -> original default loading exactly once."""
    if getattr(gui, "_pepforge_resin_loading_trace", None):
        return
    variable = getattr(gui, "pm_resin", None)
    if variable is None or not hasattr(variable, "trace_add"):
        return
    def _sync(*_args):
        if getattr(gui, "_restoring_state", False):
            return
        try:
            apply_default_loading_to_editor(gui)
        except Exception:
            pass
    try:
        gui._pepforge_resin_loading_trace = variable.trace_add("write", _sync)
    except Exception:
        gui._pepforge_resin_loading_trace = None


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
    return bool(item.get("apply_loading_calc", True)) and is_direct_resin(
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
    loading_enabled = bool(row.get("_apply_loading_calc", True))
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
    "default_loading_for_resin",
    "apply_default_loading_to_editor",
    "bind_resin_loading_autofill",
]
