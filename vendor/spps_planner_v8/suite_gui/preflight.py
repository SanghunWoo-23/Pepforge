"""Pre-experiment validation for SPPS Planner V6.

Preflight is deliberately read-only.  It validates whether the current planned
chemistry is internally resolvable before a Run is frozen; it never edits the
Plan or turns a warning into an automatic chemistry change.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping
import math
import re

from suite_gui.calculation_context import canonical, material_lookup

HARD = "BLOCK"
REVIEW = "REVIEW"
PASS = "PASS"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _num(value: Any) -> float | None:
    try:
        number = float(str(value).replace(",", "").strip())
        return number if math.isfinite(number) else None
    except Exception:
        return None


def _check(code: str, status: str, label: str, detail: str = "") -> dict[str, str]:
    return {"code": code, "status": status, "label": label, "detail": detail}


def _names_from_plan(rows: Iterable[Mapping[str, Any]]) -> list[tuple[str, str, float | None, float | None]]:
    fields = {
        "Unit name": ("MW", "Density(g/mL)"),
        "Reagent 1": ("R1 MW", "R1 Density"),
        "Reagent 2 / catalyst": ("R2 MW", "R2 Density"),
        "Base": ("Base MW", "Base Density"),
        "Coupling solvent": ("", ""),
    }
    out: list[tuple[str, str, float | None, float | None]] = []
    for row in rows:
        for field, (mw_field, density_field) in fields.items():
            name = _text(row.get(field))
            if name:
                out.append((field, name, _num(row.get(mw_field)) if mw_field else None, _num(row.get(density_field)) if density_field else None))
    return out


def check_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a planner snapshot and return a compact auditable report."""
    snap = dict(snapshot or {})
    checks: list[dict[str, str]] = []
    sequence = _text(snap.get("sequence"))
    resin = _text(snap.get("resin"))
    scale = _num(snap.get("scale_mmol"))
    loading = _num(snap.get("loading_target_mmol_g"))
    plan = [dict(row) for row in (snap.get("selected_plan_rows") or []) if isinstance(row, Mapping)]

    checks.append(_check("SEQUENCE", PASS if sequence else HARD, "Sequence", sequence or "Sequence is empty."))
    checks.append(_check("RESIN", PASS if resin else HARD, "Resin", resin or "Resin is not selected."))
    checks.append(_check("SCALE", PASS if scale and scale > 0 else HARD, "Scale", f"{scale:g} mmol" if scale and scale > 0 else "Scale must be > 0 mmol."))
    checks.append(_check("LOADING", PASS if loading and loading > 0 else HARD, "Resin loading", f"{loading:g} mmol/g" if loading and loading > 0 else "Resin loading must be > 0 mmol/g."))
    checks.append(_check("PLAN", PASS if plan else HARD, "Generated Plan", f"{len(plan)} row(s)" if plan else "Generate the Plan before starting the experiment."))

    polluted: list[str] = []
    unresolved: list[str] = []
    for field, original, row_mw, row_density in _names_from_plan(plan):
        canon = canonical(original)
        low = original.lower()
        if re.search(r"\bfor\s+n[- ]terminal\b", low) or re.search(r"\b(?:coupling|route)\s*/", low):
            polluted.append(f"{field}: {original}")
        lookup_mw, lookup_density = material_lookup(canon)
        mw = row_mw or lookup_mw
        density = row_density or lookup_density
        # Generated rows may already carry resolved bottle MW/density even when
        # the generic fallback catalog does not know an amino-acid synonym.
        if field == "Coupling solvent":
            if not mw and not density:
                unresolved.append(f"{field}: {canon}")
        elif not mw and canon.lower() not in {"resin", "manual"}:
            unresolved.append(f"{field}: {canon}")

    checks.append(_check(
        "CANONICAL_NAMES", HARD if polluted else PASS, "Canonical reagent names",
        "; ".join(polluted) if polluted else "No purpose/route suffix is present in Plan reagent identities.",
    ))
    checks.append(_check(
        "MATERIAL_LOOKUP", REVIEW if unresolved else PASS, "Material lookup",
        "; ".join(unresolved[:12]) + (f"; +{len(unresolved)-12} more" if len(unresolved) > 12 else "") if unresolved
        else "All named Plan materials resolve to known MW/density information where required.",
    ))

    blocks = [row for row in checks if row["status"] == HARD]
    reviews = [row for row in checks if row["status"] == REVIEW]
    return {
        "schema_version": "6.0.0",
        "ready": not blocks,
        "requires_review": bool(reviews),
        "block_count": len(blocks),
        "review_count": len(reviews),
        "checks": checks,
    }


def format_report(report: Mapping[str, Any]) -> str:
    rows = []
    for row in report.get("checks") or []:
        icon = {PASS: "✓", REVIEW: "!", HARD: "✕"}.get(str(row.get("status")), "•")
        detail = _text(row.get("detail"))
        rows.append(f"{icon} {row.get('label','Check')}: {detail}" if detail else f"{icon} {row.get('label','Check')}")
    rows.append("")
    if report.get("ready"):
        rows.append("READY" + (" — review item(s) remain." if report.get("requires_review") else ""))
    else:
        rows.append(f"NOT READY — {report.get('block_count', 0)} blocking item(s).")
    return "\n".join(rows)


__all__ = ["HARD", "REVIEW", "PASS", "check_snapshot", "format_report"]
