from __future__ import annotations

"""Offline review-artifact builder for Pepforge native docking/follow-up results.

This module does not require PyMOL.  It writes PDB/PML/CSV review artifacts that
can be opened by PyMOL when available, while keeping all review metadata usable
without it.  Generated scripts visualize computational models only.
"""

from pathlib import Path
from typing import Any, Iterable
import csv
import json
from .native_result_compare_v1 import compare_poses
import re

REVIEW_ARTIFACT_VERSION = "0.2.0"


def _safe(text: Any) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(text or "item")).strip("_") or "item"


def _records(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if hasattr(value, "to_dict"):
        try:
            return list(value.to_dict(orient="records"))
        except Exception:
            return []
    return [dict(x) for x in value if isinstance(x, dict)] if isinstance(value, list) else []


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("\n", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)


def build_pose_review(
    normalized: dict[str, Any],
    output_dir: str | Path,
    *,
    pose_id: str,
    visible_interactions: Iterable[str] | None = None,
) -> dict[str, str]:
    out = Path(output_dir).expanduser().resolve(); out.mkdir(parents=True, exist_ok=True)
    poses = _records(normalized.get("poses")); evidence = _records(normalized.get("evidence"))
    pose = next((p for p in poses if str(p.get("pose_id") or "") == str(pose_id)), None)
    if not pose:
        raise ValueError(f"Pose not found in normalized result: {pose_id}")
    pdb = Path(str(pose.get("pose_pdb") or "")).expanduser()
    if not pdb.exists():
        raise FileNotFoundError(pdb)
    allowed = {str(x) for x in visible_interactions} if visible_interactions else None
    rows = [e for e in evidence if str(e.get("pose_id") or "") == str(pose_id)]
    if allowed is not None:
        rows = [e for e in rows if str(e.get("interaction") or "") in allowed]
    ev_csv = out / f"{_safe(pose_id)}_review_interactions.csv"
    _write_csv(ev_csv, rows)
    obj = _safe(pose_id)
    pml = out / f"{obj}_review.pml"
    lines = [
        "# Pepforge Native Result Review",
        "# Computational structure visualization only; not experimental validation.",
        "reinitialize",
        "bg_color white",
        f'load "{pdb.as_posix()}", {obj}',
        f"hide everything, {obj}",
        f"show cartoon, {obj}",
        f"show sticks, {obj} and polymer and not name C+N+O+CA",
        f"color gray70, {obj}",
        f"select pepforge_receptor, {obj} and not chain P",
        f"select pepforge_peptide, {obj} and chain P",
        "color slate, pepforge_receptor",
        "color orange, pepforge_peptide",
        "show sticks, pepforge_peptide",
    ]
    # Add conservative residue-level selections for visible evidence.
    for idx, e in enumerate(rows, 1):
        tr = str(e.get("target_residue") or "")
        pr = str(e.get("peptide_residue") or "")
        inter = _safe(e.get("interaction") or "contact")
        # Labels vary by source; keep review script robust by comments when parsing is ambiguous.
        lines.append(f"# {idx}: {inter} target={tr} peptide={pr} distance_A={e.get('distance_A','')}")
    lines += ["orient", "zoom all"]
    pml.write_text("\n".join(lines) + "\n", encoding="utf-8")
    manifest = out / f"{obj}_review_manifest.json"
    manifest.write_text(json.dumps({
        "version": REVIEW_ARTIFACT_VERSION,
        "pose_id": pose_id,
        "pose_pdb": str(pdb.resolve()),
        "interaction_filter": sorted(allowed) if allowed is not None else "ALL",
        "interaction_count": len(rows),
        "pml": str(pml.resolve()),
        "evidence_csv": str(ev_csv.resolve()),
        "claim_guard": "Review artifacts visualize computational models only and do not imply affinity, native-pose proof, or experimental validation.",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"pml": str(pml), "evidence_csv": str(ev_csv), "manifest": str(manifest), "pose_pdb": str(pdb.resolve())}


def build_pose_comparison(normalized: dict[str, Any], output_dir: str | Path, *, pose_a: str, pose_b: str) -> dict[str, str]:
    out = Path(output_dir).expanduser().resolve(); out.mkdir(parents=True, exist_ok=True)
    poses = _records(normalized.get("poses"))
    lookup = {str(p.get("pose_id") or ""): p for p in poses}
    if pose_a not in lookup or pose_b not in lookup:
        raise ValueError("Both comparison pose IDs must exist in the normalized result.")
    pa = Path(str(lookup[pose_a].get("pose_pdb") or "")).expanduser(); pb = Path(str(lookup[pose_b].get("pose_pdb") or "")).expanduser()
    if not pa.exists() or not pb.exists():
        raise FileNotFoundError("One or both pose PDB files are missing.")
    pml = out / f"compare_{_safe(pose_a)}__{_safe(pose_b)}.pml"
    lines = [
        "# Pepforge pose comparison; computational models only.", "reinitialize", "bg_color white",
        f'load "{pa.as_posix()}", pose_A', f'load "{pb.as_posix()}", pose_B',
        "hide everything, pose_A or pose_B", "show cartoon, pose_A or pose_B",
        "show sticks, (pose_A or pose_B) and chain P", "color cyan, pose_A", "color magenta, pose_B",
        "set cartoon_transparency, 0.35, pose_B", "orient", "zoom all",
    ]
    pml.write_text("\n".join(lines) + "\n", encoding="utf-8")
    manifest = out / f"compare_{_safe(pose_a)}__{_safe(pose_b)}.json"
    metrics = compare_poses(normalized, pose_a, pose_b)
    metrics_json = out / f"compare_{_safe(pose_a)}__{_safe(pose_b)}_metrics.json"
    metrics_json.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest.write_text(json.dumps({
        "version": REVIEW_ARTIFACT_VERSION, "pose_a": pose_a, "pose_b": pose_b,
        "pose_a_pdb": str(pa.resolve()), "pose_b_pdb": str(pb.resolve()), "pml": str(pml.resolve()),
        "metrics_json": str(metrics_json.resolve()),
        "claim_guard": "Visual and quantitative computational comparison only; no pose-accuracy ranking or affinity is implied by this artifact.",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"pml": str(pml), "manifest": str(manifest), "metrics_json": str(metrics_json)}


def build_trajectory_review(followup: dict[str, Any], output_dir: str | Path, *, frame: int | None = None) -> dict[str, str]:
    out = Path(output_dir).expanduser().resolve(); out.mkdir(parents=True, exist_ok=True)
    payload = followup.get("payload") if isinstance(followup.get("payload"), dict) else followup
    mechanics = payload.get("native_mechanics") or {}
    traj = mechanics.get("native_trajectory_analysis") or payload.get("native_trajectory_analysis") or {}
    metric_csv = Path(str(traj.get("frame_metrics_csv") or "")).expanduser()
    if not metric_csv.exists():
        raise FileNotFoundError("Native trajectory frame metrics are unavailable.")
    import pandas as pd
    df = pd.read_csv(metric_csv)
    if df.empty or "source_pdb" not in df.columns:
        raise ValueError("Trajectory metrics do not contain source_pdb frame paths.")
    if frame is None:
        clusters = traj.get("clusters") or []
        frame = int(clusters[0].get("medoid_frame", 0)) if clusters else 0
    hit = df[pd.to_numeric(df.get("frame"), errors="coerce") == int(frame)]
    if hit.empty:
        raise ValueError(f"Trajectory frame not found: {frame}")
    pdb = Path(str(hit.iloc[0]["source_pdb"])).expanduser()
    if not pdb.exists():
        raise FileNotFoundError(pdb)
    pml = out / f"trajectory_frame_{int(frame):04d}.pml"
    pml.write_text("\n".join([
        "# Pepforge native trajectory frame review; descriptive geometry only.", "reinitialize", "bg_color white",
        f'load "{pdb.as_posix()}", native_frame', "show cartoon, native_frame", "show sticks, native_frame and chain P",
        "color slate, native_frame and not chain P", "color orange, native_frame and chain P", "orient", "zoom all",
    ]) + "\n", encoding="utf-8")
    return {"pml": str(pml), "frame_pdb": str(pdb.resolve()), "frame": str(int(frame))}


def build_cluster_medoid_comparison(followup: dict[str, Any], output_dir: str | Path) -> dict[str, str]:
    out = Path(output_dir).expanduser().resolve(); out.mkdir(parents=True, exist_ok=True)
    payload = followup.get("payload") if isinstance(followup.get("payload"), dict) else followup
    mechanics = payload.get("native_mechanics") or {}
    traj = mechanics.get("native_trajectory_analysis") or payload.get("native_trajectory_analysis") or {}
    metric_csv = Path(str(traj.get("frame_metrics_csv") or "")).expanduser()
    if not metric_csv.exists():
        raise FileNotFoundError("Native trajectory frame metrics are unavailable.")
    import pandas as pd
    df = pd.read_csv(metric_csv)
    if df.empty or "source_pdb" not in df.columns or "frame" not in df.columns:
        raise ValueError("Trajectory metrics do not contain frame/source_pdb paths.")
    clusters = [dict(x) for x in (traj.get("clusters") or []) if isinstance(x, dict)]
    if not clusters and "cluster" in df.columns:
        for c in sorted(set(df["cluster"].dropna().tolist())):
            sub=df[df["cluster"]==c]
            if not sub.empty:
                clusters.append({"cluster":c,"medoid_frame":int(sub.iloc[0]["frame"])})
    medoids=[]
    for idx,c in enumerate(clusters,1):
        frame=c.get("medoid_frame")
        if frame is None: continue
        hit=df[pd.to_numeric(df["frame"],errors="coerce")==int(frame)]
        if hit.empty: continue
        pdb=Path(str(hit.iloc[0]["source_pdb"])).expanduser()
        if pdb.exists(): medoids.append((str(c.get("cluster") or c.get("cluster_id") or idx),int(frame),pdb.resolve()))
    if not medoids:
        raise ValueError("No usable cluster medoid frames were found.")
    pml=out/"trajectory_cluster_medoids.pml"
    colors=["cyan","magenta","orange","green","yellow","violet","salmon","teal"]
    lines=["# Pepforge trajectory cluster-medoid comparison; descriptive computational geometry only.","reinitialize","bg_color white"]
    for idx,(cluster,frame,pdb) in enumerate(medoids):
        obj=f"cluster_{str(cluster).replace('-','_')}_medoid"
        lines += [f'load "{pdb.as_posix()}", {obj}',f"show cartoon, {obj}",f"show sticks, {obj} and chain P",f"color {colors[idx%len(colors)]}, {obj}",f"# cluster={cluster} medoid_frame={frame}"]
    lines += ["orient","zoom all"]
    pml.write_text("\n".join(lines)+"\n",encoding="utf-8")
    manifest=out/"trajectory_cluster_medoids.json"
    manifest.write_text(json.dumps({"version":REVIEW_ARTIFACT_VERSION,"medoids":[{"cluster":c,"frame":f,"pdb":str(p)} for c,f,p in medoids],"pml":str(pml.resolve()),"claim_guard":"Cluster medoids summarize sampled native-mechanics frames only; occupancy is not folding probability or equilibrium population."},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return {"pml":str(pml),"manifest":str(manifest)}


__all__ = ["REVIEW_ARTIFACT_VERSION", "build_pose_review", "build_pose_comparison", "build_trajectory_review", "build_cluster_medoid_comparison", "build_gain_loss_review", "build_cluster_medoid_montage"]


def build_gain_loss_review(normalized: dict[str, Any], output_dir: str | Path, *, pose_a: str, pose_b: str) -> dict[str,str]:
    """Create a pose-B review with gained/lost interaction residues highlighted when labels are parseable."""
    import re
    from .native_result_compare_v1 import interaction_gain_loss
    out=Path(output_dir).expanduser().resolve(); out.mkdir(parents=True,exist_ok=True)
    poses=_records(normalized.get("poses")); lookup={str(p.get("pose_id") or ""):p for p in poses}
    if pose_a not in lookup or pose_b not in lookup: raise ValueError("Both pose IDs must exist.")
    pdb=Path(str(lookup[pose_b].get("pose_pdb") or ""));
    if not pdb.exists(): raise FileNotFoundError(pdb)
    delta=interaction_gain_loss(normalized,pose_a,pose_b)
    def parse_res(text:str):
        # Accept examples A:95, A95, chainA:95, 95; ambiguous labels remain report-only.
        m=re.search(r"(?:chain\s*)?([A-Za-z0-9])?\s*[:/_-]?\s*(-?\d+)$",str(text).strip(),re.I)
        if not m: return None
        return (m.group(1) or "",m.group(2))
    pml=out/f"gain_loss_{_safe(pose_a)}__{_safe(pose_b)}.pml"
    lines=["# Pepforge interaction gain/loss review; categorical computational annotations only.","reinitialize","bg_color white",f'load "{pdb.as_posix()}", pose_B',"show cartoon, pose_B","color gray70, pose_B","show sticks, pose_B and chain P","color orange, pose_B and chain P"]
    selections=[]
    for label,rows,color in (("gained",delta.get("gained_in_b",[]),"green"),("lost",delta.get("lost_from_a",[]),"red")):
        terms=[]
        for r in rows:
            for field in ("target_residue","peptide_residue"):
                pr=parse_res(r.get(field,""))
                if pr:
                    ch,resi=pr; terms.append(f"(chain {ch} and resi {resi})" if ch else f"(resi {resi})")
        if terms:
            sel=f"pepforge_{label}"; lines += [f"select {sel}, pose_B and ({' or '.join(sorted(set(terms)))})",f"show sticks, {sel}",f"color {color}, {sel}"]
            selections.append(sel)
    lines += ["orient","zoom all"]
    pml.write_text("\n".join(lines)+"\n",encoding="utf-8")
    js=out/f"gain_loss_{_safe(pose_a)}__{_safe(pose_b)}.json"; js.write_text(json.dumps({"pose_a":pose_a,"pose_b":pose_b,"delta":delta,"colored_selections":selections,"pml":str(pml.resolve()),"claim_guard":"Green/red marks categorical gained/lost contact annotations where residue labels were parseable; colors do not encode energetic gain/loss."},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return {"pml":str(pml),"json":str(js)}


def build_cluster_medoid_montage(followup: dict[str, Any], output_dir: str | Path, *, spacing_A: float = 35.0) -> dict[str,str]:
    """Create a spatially separated PyMOL montage of cluster medoids for quick visual comparison."""
    out=Path(output_dir).expanduser().resolve(); out.mkdir(parents=True,exist_ok=True)
    base=build_cluster_medoid_comparison(followup,out)
    data=json.loads(Path(base["manifest"]).read_text(encoding="utf-8")); medoids=data.get("medoids",[])
    pml=out/"trajectory_cluster_medoids_montage.pml"; colors=["cyan","magenta","orange","green","yellow","violet","salmon","teal"]
    lines=["# Pepforge cluster-medoid montage; translated copies for visual comparison only.","reinitialize","bg_color white"]
    for idx,m in enumerate(medoids):
        obj=f"cluster_{_safe(m.get('cluster',idx))}_medoid"; x=float(idx)*float(spacing_A)
        lines += [f'load "{Path(m["pdb"]).as_posix()}", {obj}',f"show cartoon, {obj}",f"show sticks, {obj} and chain P",f"color {colors[idx%len(colors)]}, {obj}",f"translate [{x:.3f},0,0], {obj}"]
    lines += ["orient","zoom all"]
    pml.write_text("\n".join(lines)+"\n",encoding="utf-8")
    return {"pml":str(pml),"source_manifest":base["manifest"]}
