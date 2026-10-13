from __future__ import annotations

"""Quantitative, claim-guarded comparison utilities for Pepforge native results.

This module compares already-generated computational poses/trajectory summaries.
It does not estimate affinity, ΔG/Kd, or experimental correctness.
"""

from pathlib import Path
from typing import Any
import csv
import json
import math
import numpy as np

COMPARE_VERSION = "0.1.0"


def _records(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if hasattr(value, "to_dict"):
        try:
            return list(value.to_dict(orient="records"))
        except Exception:
            return []
    if isinstance(value, list):
        return [dict(x) for x in value if isinstance(x, dict)]
    return []


def _parse_pdb(path: str | Path) -> dict[tuple[str, str, str, str], np.ndarray]:
    out: dict[tuple[str, str, str, str], np.ndarray] = {}
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith(("ATOM  ", "HETATM")) or len(line) < 54:
            continue
        try:
            atom = line[12:16].strip(); alt = line[16:17].strip(); res = line[17:20].strip()
            chain = line[21:22].strip() or "_"; resi = line[22:27].strip()
            x, y, z = float(line[30:38]), float(line[38:46]), float(line[46:54])
        except Exception:
            continue
        if alt not in ("", "A"):
            continue
        out[(chain, resi, res, atom)] = np.asarray([x, y, z], dtype=float)
    return out


def _kabsch(mobile: np.ndarray, target: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    cm = mobile.mean(axis=0); ct = target.mean(axis=0)
    x = mobile - cm; y = target - ct
    u, _s, vt = np.linalg.svd(x.T @ y)
    r = u @ vt
    if np.linalg.det(r) < 0:
        u[:, -1] *= -1
        r = u @ vt
    t = ct - cm @ r
    return r, t


def pose_geometry_comparison(path_a: str | Path, path_b: str | Path, *, peptide_chain: str = "P") -> dict[str, Any]:
    a = _parse_pdb(path_a); b = _parse_pdb(path_b)
    common = sorted(set(a) & set(b))
    rec = [k for k in common if k[0] != peptide_chain and k[3] in {"N", "CA", "C", "O"}]
    lig = [k for k in common if k[0] == peptide_chain and not k[3].startswith("H")]
    if len(rec) >= 3:
        ma = np.vstack([a[k] for k in rec]); mb = np.vstack([b[k] for k in rec])
        r, t = _kabsch(mb, ma)
    else:
        r = np.eye(3); t = np.zeros(3)
    result: dict[str, Any] = {"common_receptor_backbone_atoms": len(rec), "common_peptide_heavy_atoms": len(lig)}
    if lig:
        la = np.vstack([a[k] for k in lig]); lb = np.vstack([b[k] for k in lig]) @ r + t
        d = la - lb
        result["ligand_rmsd_A"] = float(np.sqrt(np.mean(np.sum(d*d, axis=1))))
        result["peptide_centroid_shift_A"] = float(np.linalg.norm(la.mean(axis=0) - lb.mean(axis=0)))
    else:
        result["ligand_rmsd_A"] = None; result["peptide_centroid_shift_A"] = None
    result["claim_guard"] = "Geometry comparison after receptor-backbone superposition; not a native-pose or affinity validation metric unless a suitable experimental reference is explicitly supplied."
    return result


def interaction_gain_loss(normalized: dict[str, Any], pose_a: str, pose_b: str) -> dict[str, Any]:
    rows = _records(normalized.get("evidence"))
    def keys(pid: str) -> set[tuple[str, str, str]]:
        return {
            (str(r.get("interaction") or ""), str(r.get("target_residue") or ""), str(r.get("peptide_residue") or ""))
            for r in rows if str(r.get("pose_id") or "") == pid
        }
    aa, bb = keys(pose_a), keys(pose_b)
    inter = aa & bb; union = aa | bb
    gained = sorted(bb - aa); lost = sorted(aa - bb)
    return {
        "pose_a": pose_a, "pose_b": pose_b,
        "interaction_count_a": len(aa), "interaction_count_b": len(bb),
        "shared_interactions": len(inter), "contact_jaccard": float(len(inter)/len(union)) if union else 1.0,
        "gained_in_b": [{"interaction":x[0],"target_residue":x[1],"peptide_residue":x[2]} for x in gained],
        "lost_from_a": [{"interaction":x[0],"target_residue":x[1],"peptide_residue":x[2]} for x in lost],
        "claim_guard": "Interaction gain/loss is a categorical comparison of computational contact annotations, not an energetic or affinity decomposition."
    }


def compare_poses(normalized: dict[str, Any], pose_a: str, pose_b: str, *, peptide_chain: str = "P") -> dict[str, Any]:
    poses = _records(normalized.get("poses")); lookup = {str(p.get("pose_id") or ""): p for p in poses}
    if pose_a not in lookup or pose_b not in lookup:
        raise ValueError("Both pose IDs must exist in the normalized result.")
    pa, pb = lookup[pose_a], lookup[pose_b]
    ppa, ppb = Path(str(pa.get("pose_pdb") or "")), Path(str(pb.get("pose_pdb") or ""))
    if not ppa.exists() or not ppb.exists():
        raise FileNotFoundError("One or both pose PDB files are missing.")
    geo = pose_geometry_comparison(ppa, ppb, peptide_chain=peptide_chain)
    contacts = interaction_gain_loss(normalized, pose_a, pose_b)
    return {
        "version": COMPARE_VERSION, "pose_a": pose_a, "pose_b": pose_b,
        "score_a": pa.get("engine_score"), "score_b": pb.get("engine_score"),
        "quality_a": pa.get("quality_status"), "quality_b": pb.get("quality_status"),
        "geometry": geo, "interactions": contacts,
        "claim_guard": "A/B comparison is descriptive computational evidence only. Score differences, RMSD, and contact overlap are not ΔG, Kd, affinity, or experimental validation."
    }


def trajectory_cluster_summary(followup: dict[str, Any]) -> list[dict[str, Any]]:
    payload = followup.get("payload") if isinstance(followup.get("payload"), dict) else followup
    mechanics = payload.get("native_mechanics") or {}
    traj = mechanics.get("native_trajectory_analysis") or payload.get("native_trajectory_analysis") or {}
    metrics = Path(str(traj.get("frame_metrics_csv") or ""))
    if not metrics.exists():
        return []
    rows: list[dict[str, Any]] = []
    with metrics.open("r", encoding="utf-8-sig", newline="") as fh:
        raw = list(csv.DictReader(fh))
    groups: dict[str, list[dict[str, str]]] = {}
    for r in raw:
        groups.setdefault(str(r.get("cluster") or ""), []).append(r)
    medoids = {str(x.get("cluster") or x.get("cluster_id") or ""): x.get("medoid_frame") for x in (traj.get("clusters") or []) if isinstance(x, dict)}
    for cluster, items in sorted(groups.items(), key=lambda x: x[0]):
        def nums(key: str):
            vals=[]
            for i in items:
                try: vals.append(float(i.get(key, "")))
                except Exception: pass
            return vals
        rmsd=nums("rmsd_A"); rg=nums("rg_A")
        rows.append({
            "cluster": cluster, "frame_count": len(items),
            "fraction": len(items)/len(raw) if raw else 0.0,
            "mean_rmsd_A": float(np.mean(rmsd)) if rmsd else None,
            "min_rmsd_A": min(rmsd) if rmsd else None, "max_rmsd_A": max(rmsd) if rmsd else None,
            "mean_rg_A": float(np.mean(rg)) if rg else None,
            "medoid_frame": medoids.get(cluster),
        })
    return rows


def export_review_report(normalized: dict[str, Any], followups: list[dict[str, Any]], output_dir: str | Path, *, pose_a: str = "", pose_b: str = "") -> dict[str, str]:
    out = Path(output_dir).expanduser().resolve(); out.mkdir(parents=True, exist_ok=True)
    poses = _records(normalized.get("poses")); evidence = _records(normalized.get("evidence"))
    report: dict[str, Any] = {
        "version": COMPARE_VERSION, "engine": normalized.get("engine"), "evidence_grade": normalized.get("evidence_grade"),
        "pose_count": len(poses), "interaction_rows": len(evidence), "followup_count": len(followups),
        "claim_guard": "Review report summarizes computational evidence and does not report measured affinity or experimental validation."
    }
    if pose_a and pose_b and pose_a != pose_b:
        report["pose_comparison"] = compare_poses(normalized, pose_a, pose_b)
    clusters=[]
    for idx, f in enumerate(followups,1):
        for row in trajectory_cluster_summary(f):
            clusters.append({"followup":idx, **row})
    report["trajectory_clusters"] = clusters
    j = out / "native_review_report.json"; j.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    csv_path = out / "native_review_cluster_summary.csv"
    if clusters:
        with csv_path.open("w", encoding="utf-8-sig", newline="") as fh:
            w=csv.DictWriter(fh, fieldnames=list(clusters[0])); w.writeheader(); w.writerows(clusters)
    else: csv_path.write_text("\n", encoding="utf-8")
    md = out / "native_review_report.md"
    lines=["# Pepforge Native Review Report", "", f"- Engine: {report.get('engine','')}", f"- Poses: {len(poses)}", f"- Interaction rows: {len(evidence)}", f"- Follow-up records: {len(followups)}", "", "> Computational evidence only; not measured affinity or experimental validation."]
    if "pose_comparison" in report:
        c=report["pose_comparison"]; g=c["geometry"]; i=c["interactions"]
        lines += ["", "## Pose A/B comparison", f"- A: {pose_a}", f"- B: {pose_b}", f"- Ligand RMSD after receptor alignment (Å): {g.get('ligand_rmsd_A')}", f"- Contact Jaccard: {i.get('contact_jaccard')}", f"- Gained in B: {len(i.get('gained_in_b',[]))}", f"- Lost from A: {len(i.get('lost_from_a',[]))}"]
    if clusters:
        lines += ["", "## Trajectory cluster summary", "", "| Follow-up | Cluster | Frames | Fraction | Mean RMSD Å | Mean Rg Å | Medoid |", "|---:|---:|---:|---:|---:|---:|---:|"]
        for r in clusters:
            lines.append(f"| {r['followup']} | {r['cluster']} | {r['frame_count']} | {r['fraction']:.3f} | {r['mean_rmsd_A']} | {r['mean_rg_A']} | {r['medoid_frame']} |")
    md.write_text("\n".join(lines)+"\n", encoding="utf-8")
    return {"json": str(j), "markdown": str(md), "cluster_csv": str(csv_path)}


__all__ = ["COMPARE_VERSION", "pose_geometry_comparison", "interaction_gain_loss", "compare_poses", "trajectory_cluster_summary", "export_review_report", "multi_pose_comparison_matrix", "export_multi_pose_matrix", "trajectory_cluster_rmsd_matrix", "export_trajectory_cluster_rmsd_matrix"]


def multi_pose_comparison_matrix(normalized: dict[str, Any], *, peptide_chain: str = "P") -> dict[str, Any]:
    """Build pairwise descriptive geometry/contact matrices for every usable pose."""
    poses = _records(normalized.get("poses"))
    ids = [str(p.get("pose_id") or "") for p in poses if str(p.get("pose_id") or "")]
    n = len(ids)
    rmsd = [[0.0 if i == j else None for j in range(n)] for i in range(n)]
    jaccard = [[1.0 if i == j else None for j in range(n)] for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            c = compare_poses(normalized, ids[i], ids[j], peptide_chain=peptide_chain)
            rv = c.get("geometry", {}).get("ligand_rmsd_A")
            jv = c.get("interactions", {}).get("contact_jaccard")
            rmsd[i][j] = rmsd[j][i] = rv
            jaccard[i][j] = jaccard[j][i] = jv
    ranking=[]
    for p in poses:
        ranking.append({
            "pose_id": str(p.get("pose_id") or ""),
            "pose_rank": p.get("pose_rank"),
            "engine_score": p.get("engine_score"),
            "quality_status": p.get("quality_status"),
            "contact_count": p.get("contact_count"),
            "clash_count": p.get("clash_count"),
        })
    return {
        "version": COMPARE_VERSION,
        "pose_ids": ids,
        "ranking": ranking,
        "ligand_rmsd_A_matrix": rmsd,
        "contact_jaccard_matrix": jaccard,
        "claim_guard": "Pairwise matrices compare computational pose geometry/contact annotations only; they are not affinity, ΔG/Kd, or native-pose probabilities.",
    }


def export_multi_pose_matrix(normalized: dict[str, Any], output_dir: str | Path, *, peptide_chain: str = "P") -> dict[str, str]:
    out=Path(output_dir).expanduser().resolve(); out.mkdir(parents=True, exist_ok=True)
    data=multi_pose_comparison_matrix(normalized, peptide_chain=peptide_chain)
    js=out/"multi_pose_compare_matrix.json"; js.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    ids=data["pose_ids"]
    def write_matrix(path: Path, matrix: list[list[Any]]):
        with path.open("w",encoding="utf-8-sig",newline="") as fh:
            w=csv.writer(fh); w.writerow(["pose_id",*ids])
            for pid,row in zip(ids,matrix): w.writerow([pid,*row])
    r=out/"multi_pose_ligand_rmsd_A.csv"; write_matrix(r,data["ligand_rmsd_A_matrix"])
    j=out/"multi_pose_contact_jaccard.csv"; write_matrix(j,data["contact_jaccard_matrix"])
    rank=out/"multi_pose_ranking.csv"
    rows=data["ranking"]
    if rows:
        with rank.open("w",encoding="utf-8-sig",newline="") as fh:
            w=csv.DictWriter(fh,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    else: rank.write_text("\n",encoding="utf-8")
    return {"json":str(js),"rmsd_csv":str(r),"contact_csv":str(j),"ranking_csv":str(rank)}


def trajectory_cluster_rmsd_matrix(followup: dict[str, Any]) -> dict[str, Any]:
    """Pairwise RMSD matrix among trajectory cluster medoids using common heavy atoms."""
    payload = followup.get("payload") if isinstance(followup.get("payload"), dict) else followup
    mechanics = payload.get("native_mechanics") or {}
    traj = mechanics.get("native_trajectory_analysis") or payload.get("native_trajectory_analysis") or {}
    metric_csv=Path(str(traj.get("frame_metrics_csv") or ""))
    if not metric_csv.exists(): return {"clusters":[],"matrix":[],"claim_guard":"No trajectory metrics available."}
    raw=list(csv.DictReader(metric_csv.open("r",encoding="utf-8-sig",newline="")))
    by_frame={str(r.get("frame")):r for r in raw}
    medoids=[]
    for idx,c in enumerate([dict(x) for x in (traj.get("clusters") or []) if isinstance(x,dict)],1):
        cid=str(c.get("cluster") or c.get("cluster_id") or idx); fr="" if c.get("medoid_frame") is None else str(c.get("medoid_frame"))
        row=by_frame.get(fr)
        if row and row.get("source_pdb") and Path(row["source_pdb"]).exists(): medoids.append((cid,Path(row["source_pdb"])))
    ids=[x[0] for x in medoids]; n=len(ids); mat=[[0.0 if i==j else None for j in range(n)] for i in range(n)]
    for i in range(n):
        ai=_parse_pdb(medoids[i][1])
        for j in range(i+1,n):
            bj=_parse_pdb(medoids[j][1]); common=sorted(set(ai)&set(bj))
            keys=[k for k in common if not k[3].startswith("H")]
            if len(keys)>=3:
                a=np.vstack([ai[k] for k in keys]); b=np.vstack([bj[k] for k in keys]); rr,tt=_kabsch(b,a); d=a-(b@rr+tt)
                v=float(np.sqrt(np.mean(np.sum(d*d,axis=1))))
            else: v=None
            mat[i][j]=mat[j][i]=v
    return {"clusters":ids,"matrix":mat,"claim_guard":"Cluster-medoid RMSD describes sampled native-mechanics geometry only; it is not equilibrium population or free-energy separation."}


def export_trajectory_cluster_rmsd_matrix(followup: dict[str, Any], output_dir: str | Path) -> dict[str,str]:
    out=Path(output_dir).expanduser().resolve(); out.mkdir(parents=True,exist_ok=True)
    data=trajectory_cluster_rmsd_matrix(followup); js=out/"trajectory_cluster_rmsd_matrix.json"; js.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    csvp=out/"trajectory_cluster_rmsd_A.csv"; ids=data["clusters"]
    with csvp.open("w",encoding="utf-8-sig",newline="") as fh:
        w=csv.writer(fh); w.writerow(["cluster",*ids]);
        for cid,row in zip(ids,data["matrix"]): w.writerow([cid,*row])
    return {"json":str(js),"csv":str(csvp)}
