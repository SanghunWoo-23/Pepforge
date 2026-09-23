from __future__ import annotations

"""Convert selected sequence-hotspot rows into an auditable PDE chemistry profile."""

from pathlib import Path
from typing import Any, Iterable
import csv
import json

HOTSPOT_TRANSFER_VERSION="1.2.0"
AA=set("ACDEFGHIKLMNPQRSTVWY")
GROUPS={
    "acidic":set("DE"),"basic":set("KR"),"hydrophobic":set("AILMFWVY"),"aromatic":set("FWY"),"polar_hbond_capable":set("NQSTHDEKR")
}


def _clean(seq: str) -> str: return "".join(x for x in str(seq or "").upper() if x in AA)


def build_hotspot_chemistry_profile(rows: Iterable[dict[str,Any]]) -> dict[str,Any]:
    source=[]; residues=[]
    for row in rows:
        seq=_clean(row.get("sequence", ""))
        if not seq: continue
        try: weight=max(0.0,float(row.get("hotspot_score") or 1.0))
        except Exception: weight=1.0
        if weight==0: weight=1.0
        source.append({"sequence":seq,"weight":weight,"rank":row.get("rank",""),"region_start":row.get("region_start",""),"region_end":row.get("region_end","")})
        residues.extend([(aa,weight) for aa in seq])
    denom=sum(w for _,w in residues) or 1.0
    fractions={name:round(sum(w for aa,w in residues if aa in members)/denom,6) for name,members in GROUPS.items()}
    beta_edge=[]
    for row in rows:
        raw=str(row.get("beta_edge_candidate","")).strip().lower()
        if raw in {"true","1","yes","y"}:
            beta_edge.append({
                "record_name":row.get("record_name",""),"position":row.get("region_start",row.get("position","")),
                "secondary_structure":row.get("secondary_structure",""),"evidence":row.get("beta_edge_evidence",""),
                "backbone_pairing_atoms":row.get("beta_edge_backbone_pairing_atoms",""),
                "local_strand_axis_xyz":row.get("beta_edge_local_strand_axis_xyz",""),
                "register_status":row.get("beta_edge_register_status","not_inferred"),
            })
    return {
        "version":HOTSPOT_TRANSFER_VERSION,"status":"available" if residues else "unavailable","source_hotspots":source,
        "chemistry_fractions":fractions,"weighted_residue_count":round(denom,6) if residues else 0.0,
        "structure_opportunities":{
            "beta_edge_candidate_count":len(beta_edge),"beta_edge_candidates":beta_edge,
            "selection_active":False,
            "claim_guard":"Report-only V4 evidence. A beta-edge candidate is a structure-derived review opportunity, not a binding-site prediction; local strand-axis/backbone metadata do not infer a peptide register, beta-pairing event, or affinity."
        },
        "claim_guard":"Sequence-hotspot chemistry profile plus optional report-only structure opportunity metadata. It is not a 3D contact map or docking pose, binding energy, or affinity prediction.",
    }


def export_hotspot_chemistry_profile(rows: Iterable[dict[str,Any]], output_dir: str | Path) -> dict[str,str]:
    out=Path(output_dir); out.mkdir(parents=True,exist_ok=True); payload=build_hotspot_chemistry_profile(rows)
    j=out/"hotspot_chemistry_profile_for_PDE.json"; c=out/"hotspot_chemistry_profile_for_PDE.csv"
    j.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    with c.open("w",encoding="utf-8-sig",newline="") as h:
        fields=["dimension","fraction","interpretation"]; w=csv.DictWriter(h,fieldnames=fields); w.writeheader()
        for name,val in payload["chemistry_fractions"].items(): w.writerow({"dimension":name,"fraction":val,"interpretation":"weighted selected-hotspot sequence composition"})
        beta_count=(payload.get("structure_opportunities") or {}).get("beta_edge_candidate_count",0)
        w.writerow({"dimension":"beta_edge_candidate_count","fraction":beta_count,"interpretation":"report-only structure-derived beta-edge opportunity count; not a selection score"})
    return {"profile_json":str(j),"profile_csv":str(c)}


__all__=["HOTSPOT_TRANSFER_VERSION","build_hotspot_chemistry_profile","export_hotspot_chemistry_profile"]
