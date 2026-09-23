from __future__ import annotations

"""Evidence provenance/dependency helpers used to reduce double counting."""

from typing import Any, Iterable

EVIDENCE_PROVENANCE_VERSION = "1.0.0"
VALID_ROLES = {"selection_driving", "independent", "contradictory", "missing", "contextual"}
VALID_KINDS = {"measured", "calculated", "literature_derived", "heuristic", "operator_recorded", "unavailable"}


def evidence_record(*, name: str, role: str, kind: str, source_id: str, status: str,
                    detail: Any = None, depends_on: Iterable[str] = (), limitations: str = "") -> dict[str, Any]:
    r = role if role in VALID_ROLES else "contextual"
    k = kind if kind in VALID_KINDS else "heuristic"
    deps=[str(x) for x in depends_on if str(x)]
    return {
        "name": str(name), "role": r, "kind": k, "source_id": str(source_id),
        "status": str(status), "detail": detail, "depends_on": deps,
        "independent_of_selection": r == "independent" and not deps,
        "limitations": str(limitations or ""),
    }


def dependency_audit(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows=[dict(x) for x in records]
    source_counts={}
    roles_by_source: dict[str, set[str]] = {}
    for row in rows:
        sid=str(row.get("source_id") or "unspecified")
        source_counts[sid]=source_counts.get(sid,0)+1
        roles_by_source.setdefault(sid, set()).add(str(row.get("role") or "contextual"))
    shared=sorted(k for k,v in source_counts.items() if v>1 and k!="unspecified")
    selection_sources={sid for sid,roles in roles_by_source.items() if "selection_driving" in roles}
    independent_role_sources={sid for sid,roles in roles_by_source.items() if "independent" in roles}
    eligible_independent_sources={
        str(row.get("source_id") or "unspecified")
        for row in rows
        if str(row.get("role") or "") == "independent" and bool(row.get("independent_of_selection"))
    }
    same_source_independent=sorted((selection_sources & independent_role_sources) - {"unspecified"})
    dependency_limited_independent=sorted((independent_role_sources - eligible_independent_sources) - {"unspecified"})
    external_independent=sorted(eligible_independent_sources - selection_sources - {"unspecified"})
    return {
        "version": EVIDENCE_PROVENANCE_VERSION,
        "record_count": len(rows),
        "shared_source_ids": shared,
        "selection_source_ids": sorted(selection_sources - {"unspecified"}),
        "independent_role_source_ids": sorted(independent_role_sources - {"unspecified"}),
        "independent_eligible_source_ids": sorted(eligible_independent_sources - {"unspecified"}),
        "dependency_limited_independent_source_ids": dependency_limited_independent,
        "same_source_selection_and_independent_ids": same_source_independent,
        "orthogonal_independent_source_ids": external_independent,
        "orthogonal_independent_source_count": len(external_independent),
        "policy": (
            "Evidence derived from the same source is not counted as independent validation merely because it appears in multiple metrics; specifically, it is not counted as orthogonal independent validation. "
            "Intent-independent sampling within the same backend remains useful challenge evidence but is reported separately from external orthogonal evidence."
        ),
    }


__all__ = ["EVIDENCE_PROVENANCE_VERSION", "evidence_record", "dependency_audit"]
