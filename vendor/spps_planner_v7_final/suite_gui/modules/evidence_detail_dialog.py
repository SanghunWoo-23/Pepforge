"""Compact, read-only provenance detail dialog for V6 recommendations."""
from __future__ import annotations

import json
import tkinter as tk
from tkinter import ttk
from typing import Any, Iterable

from suite_gui.recommendation.provenance import detail_lines


def _compact_record(row: dict[str, Any]) -> str:
    preferred = (
        "date", "product", "sequence", "resin", "resin_type", "amino_acid_normalized",
        "aa_eq", "base_eq", "loading_time_h", "loading_rate_mmol_g", "cleavage_eq",
        "cleavage_time_h", "yield_percent", "purity_percent", "status", "record_state",
    )
    parts = [f"{key}={row.get(key)}" for key in preferred if row.get(key) not in (None, "")]
    if parts:
        return " | ".join(parts)
    return json.dumps(row, ensure_ascii=False, default=str, sort_keys=True)


def format_sections(sections: Iterable[tuple[str, dict[str, Any] | None]]) -> str:
    out: list[str] = []
    for title, result in sections:
        result = dict(result or {})
        out += [title, "-" * max(8, len(title))]
        out += detail_lines(result)
        rec = result.get("target_recommendation") or result.get("recommended_condition") or {}
        identity = result.get("amino_acid_identity") or {}
        if identity:
            out += [
                f"Loaded-AA identity: {identity.get('normalized') or identity.get('input') or '—'}",
                f"Identity class: {identity.get('category') or 'unknown'} | stereochemistry={identity.get('stereochemistry') or '—'} | exact-history n={identity.get('exact_history_count',0)}",
                f"Identity recognition: {identity.get('identity_origin') or 'literal identity'}; recognition alone is not experimental support",
            ]
        if rec:
            basis = rec.get("basis") or rec.get("recommendation_kind") or rec.get("condition_source")
            if basis:
                out.append(f"Recommendation basis: {basis}")
        profile = result.get("exact_evidence_profile") or {}
        if profile and int(profile.get("exact_record_count") or 0):
            out += [
                "",
                "Exact resin + loaded-AA coverage:",
                f"• records={profile.get('exact_record_count',0)} | verified={profile.get('verified_record_count',0)} | parsed={profile.get('parsed_record_count',0)}",
                f"• distinct conditions={profile.get('distinct_condition_count',0)} | repeated conditions={profile.get('repeated_condition_count',0)}",
                f"• dates={profile.get('date_min') or '—'} → {profile.get('date_max') or '—'}",
                f"• loading range={profile.get('observed_loading_min')}–{profile.get('observed_loading_max')} mmol/g | median={profile.get('observed_loading_median')}",
            ]
            support = rec.get("condition_support") if isinstance(rec, dict) else None
            if support:
                out += [
                    "Selected-condition support:",
                    f"• n={support.get('evidence_count',0)} | verified={support.get('verified_count',0)} | parsed={support.get('parsed_count',0)}",
                    f"• median={support.get('loading_median_mmol_g')} | range={support.get('loading_min_mmol_g')}–{support.get('loading_max_mmol_g')} mmol/g",
                    f"• dates={support.get('date_min') or '—'} → {support.get('date_max') or '—'}",
                ]
            nearest = (rec.get("nearest_observed_conditions") if isinstance(rec, dict) else None) or profile.get("nearest_conditions") or []
            if nearest:
                out.append("Nearest observed conditions:")
                for item in nearest[:5]:
                    out.append(
                        f"• AA={item.get('aa_eq')} eq | base={item.get('base_eq')} eq | time={item.get('loading_time_h')} h | "
                        f"median={item.get('loading_median_mmol_g')} [{item.get('loading_min_mmol_g')}–{item.get('loading_max_mmol_g')}] | n={item.get('evidence_count',0)}"
                    )
        warnings = [str(value) for value in (result.get("warnings") or []) if str(value).strip()]
        if warnings:
            out += ["", "Warnings / limits:"] + [f"• {value}" for value in warnings]
        evidence = [row for row in (result.get("evidence") or []) if isinstance(row, dict)]
        if evidence:
            out += ["", f"Evidence records ({len(evidence)}):"]
            out += [f"• {_compact_record(row)}" for row in evidence[:25]]
            if len(evidence) > 25:
                out.append(f"• … {len(evidence) - 25} more record(s)")
        out.append("")
    return "\n".join(out).strip() or "No recommendation evidence is available yet."


def show(parent: tk.Misc, title: str, sections: Iterable[tuple[str, dict[str, Any] | None]]) -> tk.Toplevel:
    window = tk.Toplevel(parent)
    window.title(title)
    window.geometry("900x620")
    window.minsize(720, 480)
    outer = ttk.Frame(window, padding=10)
    outer.pack(fill="both", expand=True)
    text = tk.Text(outer, wrap="word", font=("Consolas", 9))
    ybar = ttk.Scrollbar(outer, orient="vertical", command=text.yview)
    text.configure(yscrollcommand=ybar.set)
    text.pack(side="left", fill="both", expand=True)
    ybar.pack(side="right", fill="y")
    text.insert("1.0", format_sections(sections))
    text.configure(state="disabled")
    ttk.Button(window, text="Close", command=window.destroy).pack(pady=(0, 10))
    try:
        window.transient(parent)
    except tk.TclError:
        pass
    return window


__all__ = ["format_sections", "show"]
