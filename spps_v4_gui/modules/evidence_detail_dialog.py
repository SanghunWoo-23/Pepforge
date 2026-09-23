"""Compact, read-only provenance detail dialog for V6 recommendations."""
from __future__ import annotations

import json
import tkinter as tk
from tkinter import ttk
from typing import Any, Iterable

from spps_v4_gui.recommendation.provenance import detail_lines


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
        if rec:
            basis = rec.get("basis") or rec.get("recommendation_kind") or rec.get("condition_source")
            if basis:
                out.append(f"Recommendation basis: {basis}")
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
