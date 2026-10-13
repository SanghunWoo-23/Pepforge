from __future__ import annotations
from suite_gui.decision_support import attach_evidence_trace, evidence_trace

def detail_lines(result):
    trace = evidence_trace(result or {})
    lines = [
        f"Source: {trace.get('source','Unknown')}",
        f"Confidence: {trace.get('confidence','LOW')}",
        f"Evidence count: {trace.get('evidence_count',0)}",
        f"Verified evidence: {trace.get('verified_evidence_count',0)}",
    ]
    observed = trace.get('observed_range')
    if observed:
        lines.append(f"Observed range: {observed[0]} – {observed[1]}")
    lines.append(f"Apply allowed: {'YES' if trace.get('apply_allowed') else 'NO'}")
    if trace.get('basis'):
        lines.append(f"Basis: {trace['basis']}")
    if trace.get('blocked_reason'):
        lines.append(f"Blocked reason: {trace['blocked_reason']}")
    if trace.get('provisional'):
        lines.append("Evidence is provisional.")
    return lines

__all__ = ["attach_evidence_trace", "evidence_trace", "detail_lines"]
