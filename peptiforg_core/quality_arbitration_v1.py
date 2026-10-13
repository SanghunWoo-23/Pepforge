from __future__ import annotations

"""Cross-engine quality arbitration without erasing provenance.

Pepforge may have a native candidate and one or more optional enhancement or
reference candidates.  Arbitration never treats engine identity as evidence of
truth; it uses explicit quality status, artifact richness and caller-provided
scope preference, while keeping every candidate in the result bundle.
"""
from typing import Any, Sequence

QUALITY_ARBITRATION_VERSION="0.1.0"
_STATUS={"PASS":3,"WARN":2,"UNKNOWN":1,"SKIPPED":1,"FAIL":0}


def arbitrate_candidates(candidates: Sequence[dict[str,Any]], *, prefer_native_on_tie: bool=True) -> dict[str,Any]:
    rows=[]
    for idx,c in enumerate(candidates):
        name=str(c.get("name") or c.get("source") or f"candidate_{idx+1}")
        q=str((c.get("quality_gate") or {}).get("status",c.get("quality_status","UNKNOWN"))).upper()
        richness=float(c.get("richness",c.get("atom_count",0)) or 0)
        native=bool(c.get("native",False))
        usable=bool(c.get("usable",True)) and q!="FAIL"
        score=(_STATUS.get(q,1), richness, 1 if (native and prefer_native_on_tie) else 0)
        rows.append({"name":name,"quality_status":q,"richness":richness,"native":native,"usable":usable,"score_tuple":score,"candidate":c})
    usable=[r for r in rows if r["usable"]]
    selected=max(usable,key=lambda r:r["score_tuple"]) if usable else None
    return {
        "version":QUALITY_ARBITRATION_VERSION,"status":"SELECTED" if selected else "NO_USABLE_CANDIDATE",
        "selected":None if selected is None else {k:v for k,v in selected.items() if k not in {"candidate","score_tuple"}},
        "selected_candidate":None if selected is None else selected["candidate"],
        "candidates":[{k:v for k,v in r.items() if k not in {"candidate","score_tuple"}} for r in rows],
        "claim_guard":"Arbitration selects a downstream initialization artifact under explicit quality rules; selection is not experimental validation or proof of native structure/pose/dynamics.",
    }

__all__=["QUALITY_ARBITRATION_VERSION","arbitrate_candidates"]
