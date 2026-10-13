"""Pure presentation helpers for Run lifecycle review dialogs."""
from __future__ import annotations

import json
from typing import Any, Mapping


def _display(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return "" if value is None else str(value)


def format_finish_review(review: Mapping[str, Any]) -> str:
    execution = dict(review.get("execution") or {})
    run = dict(review.get("run") or {})
    lines = [
        f"Run: {run.get('run_name') or run.get('run_id') or 'Active Run'}",
        f"Progress: {execution.get('completed_steps', 0)}/{execution.get('total_steps', 0)} ({execution.get('progress_percent', 0)}%)",
        f"Planner changes since Start: {review.get('planner_change_count', 0)}",
        f"Recorded execution deviations: {review.get('deviation_count', 0)}",
    ]
    warnings = list(review.get("warnings") or [])
    if warnings:
        lines += ["", "Review:"] + [f"• {value}" for value in warnings]
    changes = list(review.get("planner_changes") or [])[:6]
    if changes:
        lines += ["", "Planner changes (not automatically treated as actual execution):"]
        for row in changes:
            lines.append(f"• {row.get('field')}: {_display(row.get('frozen'))} → {_display(row.get('current'))}")
    deviations = list(review.get("execution_deviations") or [])[:6]
    if deviations:
        lines += ["", "Recorded execution deviations:"]
        for row in deviations:
            label = row.get("field") or row.get("unit") or row.get("event_type")
            lines.append(f"• {label}: {_display(row.get('before'))} → {_display(row.get('after'))}")
    lines += ["", "Confirm these actual-run records and finish the Run?"]
    return "\n".join(lines)


__all__ = ["format_finish_review"]
