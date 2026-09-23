from __future__ import annotations

"""Traceable candidate -> PSB conformer -> docking-pose lineage metadata.

Pepforge V4.0.0 does not claim an internal publication-grade docking execution
backend.  This module prepares lineage and PyMOL review artifacts so future V5
external/internal docking poses can be attached without losing provenance.
"""

from pathlib import Path
from typing import Any, Iterable
import csv
import json
import re

DOCKING_LINEAGE_VERSION="1.0.0"


def _safe(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+","_",str(value or "unknown")).strip("_") or "unknown"


def psb_structure_id(candidate_id: str, conformer_rank: int) -> str:
    return f"{_safe(candidate_id)}/PSB-R{int(conformer_rank):02d}"


def docking_pose_id(candidate_id: str, conformer_rank: int, pose_rank: int) -> str:
    return f"{psb_structure_id(candidate_id,conformer_rank)}/DOCK-P{int(pose_rank):02d}"


def lineage_record(candidate_id: str, sequence: str, *, conformer_rank: int, pose_rank: int | None = None, structure_path: str | Path | None = None, pose_path: str | Path | None = None, docking_engine: str = "not_run", docking_status: str = "prepared_only", notes: str = "") -> dict[str, Any]:
    row={
        "candidate_id":str(candidate_id or ""),"sequence":str(sequence or ""),
        "psb_structure_id":psb_structure_id(candidate_id,conformer_rank),"psb_conformer_rank":int(conformer_rank),
        "pose_id":"" if pose_rank is None else docking_pose_id(candidate_id,conformer_rank,pose_rank),
        "pose_rank":"" if pose_rank is None else int(pose_rank),"docking_engine":str(docking_engine),"docking_status":str(docking_status),
        "structure_path":str(structure_path or ""),"pose_path":str(pose_path or ""),"notes":str(notes or ""),
    }
    return row


def _pml(records: list[dict[str,Any]], target_path: str | Path | None) -> str:
    lines=["# Pepforge V4 docking-lineage PyMOL review template", "# No docking is claimed by this file; it only loads supplied coordinates."]
    if target_path:
        lines += [f'load "{Path(target_path).as_posix()}", target', "color gray70, target"]
    for i,row in enumerate(records,1):
        path=str(row.get("pose_path") or row.get("structure_path") or "").strip()
        if not path: continue
        obj=f"pep_{i:02d}_{_safe(str(row.get('candidate_id','')))}"
        lines += [f'load "{Path(path).as_posix()}", {obj}', f"show sticks, {obj}", f"color cyan, {obj}"]
    lines += ["hide everything, hydro", "show cartoon, target", "zoom", "# Future V5 docking poses can be loaded with the same candidate/PSB/pose IDs."]
    return "\n".join(lines)+"\n"


def export_lineage(records: Iterable[dict[str,Any]], output_dir: str | Path, *, target_path: str | Path | None = None) -> dict[str,str]:
    out=Path(output_dir); out.mkdir(parents=True,exist_ok=True); rows=[dict(r) for r in records]
    payload={"version":DOCKING_LINEAGE_VERSION,"records":rows,"target_path":str(target_path or ""),"claim_guard":"Lineage/visualization preparation only in V4.0.0. A pose is a docking result only when an actual docking engine output is imported or executed and recorded."}
    j=out/"docking_lineage.json"; c=out/"docking_lineage.csv"; p=out/"pymol_docking_review_template.pml"
    j.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    fields=list(rows[0]) if rows else ["candidate_id","sequence","psb_structure_id","psb_conformer_rank","pose_id","pose_rank","docking_engine","docking_status","structure_path","pose_path","notes"]
    with c.open("w",encoding="utf-8-sig",newline="") as h:
        w=csv.DictWriter(h,fieldnames=fields,extrasaction="ignore"); w.writeheader(); w.writerows(rows)
    p.write_text(_pml(rows,target_path),encoding="utf-8")
    return {"lineage_json":str(j),"lineage_csv":str(c),"pymol_review_pml":str(p)}


__all__=["DOCKING_LINEAGE_VERSION","psb_structure_id","docking_pose_id","lineage_record","export_lineage"]
