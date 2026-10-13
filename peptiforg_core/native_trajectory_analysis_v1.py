from __future__ import annotations

"""Pepforge-native descriptive trajectory analysis.

Consumes an ordered sequence of PDB frames and computes geometry descriptors
with NumPy only.  This is intentionally independent of MDTraj/MDAnalysis and is
usable for Pepforge-native mechanics output when no optional trajectory package
is installed.

The analysis is descriptive.  RMSD stability, cluster occupancy, medoids and
frame counts are never promoted to equilibrium, folding probability, affinity,
or functional validation claims.
"""

from pathlib import Path
from typing import Any, Sequence
import csv, json, math
import numpy as np

from .interface_quality import parse_pdb_atoms

NATIVE_TRAJECTORY_ANALYSIS_VERSION = "0.1.0"


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("\n", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for k in row:
            if k not in fields:
                fields.append(k)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader(); w.writerows(rows)


def _atom_key(row: Any) -> tuple[str, str, str, str, str]:
    return (str(row.chain), str(row.resi), str(row.resn), str(row.atom), str(row.element))


def _load_common_frames(frame_paths: Sequence[str | Path]) -> tuple[list[Path], list[tuple[str,str,str,str,str]], np.ndarray]:
    paths=[Path(p).expanduser().resolve() for p in frame_paths]
    if not paths:
        raise ValueError("No trajectory frames were supplied.")
    tables=[]
    for p in paths:
        if not p.exists():
            raise FileNotFoundError(p)
        df=parse_pdb_atoms(p).reset_index(drop=True)
        if df.empty:
            raise ValueError(f"Frame contains no readable atoms: {p}")
        tables.append(df)
    common=set(_atom_key(r) for _,r in tables[0].iterrows())
    for df in tables[1:]:
        common &= set(_atom_key(r) for _,r in df.iterrows())
    if not common:
        raise ValueError("Trajectory frames have no common atom identity set.")
    # Preserve first-frame atom order and prefer heavy atoms; CA if >=2.
    first=tables[0]
    ca=[_atom_key(r) for _,r in first.iterrows() if _atom_key(r) in common and str(r.atom).upper()=="CA"]
    if len(ca)>=2:
        keys=ca
    else:
        keys=[_atom_key(r) for _,r in first.iterrows() if _atom_key(r) in common and str(r.element).upper()!="H"]
    if not keys:
        keys=[_atom_key(r) for _,r in first.iterrows() if _atom_key(r) in common]
    coords=[]
    for df in tables:
        lookup={_atom_key(r): np.array([float(r.x),float(r.y),float(r.z)],dtype=float) for _,r in df.iterrows()}
        arr=np.vstack([lookup[k] for k in keys])
        if not np.isfinite(arr).all():
            raise ValueError("Non-finite coordinates in trajectory frame.")
        coords.append(arr)
    return paths, keys, np.stack(coords,axis=0)


def _kabsch_align(mobile: np.ndarray, reference: np.ndarray) -> np.ndarray:
    m=np.asarray(mobile,dtype=float); r=np.asarray(reference,dtype=float)
    mc=m.mean(axis=0); rc=r.mean(axis=0)
    x=m-mc; y=r-rc
    cov=x.T@y
    u,_,vt=np.linalg.svd(cov)
    rot=u@vt
    if np.linalg.det(rot)<0:
        u[:,-1]*=-1.0; rot=u@vt
    return x@rot + rc


def _pairwise_rmsd(aligned: np.ndarray) -> np.ndarray:
    n=len(aligned); out=np.zeros((n,n),dtype=float)
    for i in range(n):
        for j in range(i+1,n):
            d=aligned[i]-aligned[j]
            v=float(np.sqrt(np.mean(np.sum(d*d,axis=1))))
            out[i,j]=out[j,i]=v
    return out


def _farthest_medoids(dist: np.ndarray, k: int) -> list[int]:
    n=len(dist); k=max(1,min(int(k),n))
    if n==1: return [0]
    first=int(np.argmin(np.mean(dist,axis=1)))
    med=[first]
    mind=dist[first].copy()
    while len(med)<k:
        idx=int(np.argmax(mind))
        if idx in med: break
        med.append(idx); mind=np.minimum(mind,dist[idx])
    return med


def _cluster_by_medoids(dist: np.ndarray, medoids: list[int]) -> tuple[np.ndarray,list[int]]:
    m=list(medoids)
    labels=np.argmin(dist[:,m],axis=1)
    # one PAM-like medoid update for deterministic refinement
    for ci in range(len(m)):
        members=np.where(labels==ci)[0]
        if len(members):
            sub=dist[np.ix_(members,members)]
            m[ci]=int(members[int(np.argmin(np.sum(sub,axis=1)))])
    labels=np.argmin(dist[:,m],axis=1)
    return labels,m


def analyze_native_frames(frame_paths: Sequence[str | Path], output_dir: str | Path, *, clusters: int=5) -> dict[str,Any]:
    out=Path(output_dir).expanduser().resolve(); out.mkdir(parents=True,exist_ok=True)
    paths,keys,raw=_load_common_frames(frame_paths)
    ref=raw[0]
    aligned=np.stack([_kabsch_align(x,ref) for x in raw],axis=0)
    rmsd=np.sqrt(np.mean(np.sum((aligned-ref[None,:,:])**2,axis=2),axis=1))
    centers=raw.mean(axis=1,keepdims=True)
    rg=np.sqrt(np.mean(np.sum((raw-centers)**2,axis=2),axis=1))
    mean_struct=aligned.mean(axis=0)
    rmsf=np.sqrt(np.mean(np.sum((aligned-mean_struct[None,:,:])**2,axis=2),axis=0))
    n=len(paths); half=max(1,n//2)
    drift=float(np.mean(rmsd[half:])-np.mean(rmsd[:half])) if n>=2 else 0.0
    dist=_pairwise_rmsd(aligned)
    med0=_farthest_medoids(dist,min(int(clusters),n)); labels,medoids=_cluster_by_medoids(dist,med0)
    frame_rows=[]
    for i,p in enumerate(paths):
        frame_rows.append({"frame":i,"source_pdb":str(p),"rmsd_A":float(rmsd[i]),"rg_A":float(rg[i]),"cluster":int(labels[i])+1})
    _write_csv(out/'native_trajectory_frame_metrics.csv',frame_rows)
    atom_rows=[]
    for i,(k,v) in enumerate(zip(keys,rmsf)):
        atom_rows.append({"atom_index":i,"chain":k[0],"resi":k[1],"resn":k[2],"atom":k[3],"element":k[4],"rmsf_A":float(v)})
    _write_csv(out/'native_trajectory_rmsf.csv',atom_rows)
    cluster_rows=[]
    for ci,mi in enumerate(medoids):
        members=np.where(labels==ci)[0]
        cluster_rows.append({"cluster":ci+1,"frame_count":int(len(members)),"fraction_of_sampled_frames":float(len(members)/n),"medoid_frame":int(mi),"medoid_pdb":str(paths[mi])})
    _write_csv(out/'native_trajectory_clusters.csv',cluster_rows)
    fail=warn=0; issues=[]; warnings=[]
    if n<3:
        warn+=1; warnings.append("Very few frames; distribution and clustering descriptors are weak.")
    if not np.isfinite(rmsd).all() or not np.isfinite(rg).all() or not np.isfinite(rmsf).all():
        fail+=1; issues.append("Non-finite native trajectory metrics detected.")
    if float(np.max(rmsd))>25.0:
        warn+=1; warnings.append("Large aligned RMSD excursion detected; inspect trajectory geometry.")
    status="FAIL" if fail else ("WARN" if warn else "PASS")
    payload={
        "version":NATIVE_TRAJECTORY_ANALYSIS_VERSION,"status":"COMPLETED","engine":"Pepforge Native Trajectory Analysis v1",
        "evidence_grade":"DESCRIPTIVE_NATIVE_TRAJECTORY_ANALYSIS","frame_count":n,"analysis_atom_count":len(keys),
        "mean_rmsd_A":float(np.mean(rmsd)),"max_rmsd_A":float(np.max(rmsd)),"mean_rg_A":float(np.mean(rg)),
        "first_half_vs_second_half_rmsd_drift_A":drift,"cluster_count":len(medoids),"clusters":cluster_rows,
        "quality_gate":{"status":status,"fail_count":fail,"warn_count":warn,"issues":issues,"warnings":warnings},
        "frame_metrics_csv":str((out/'native_trajectory_frame_metrics.csv').resolve()),"rmsf_csv":str((out/'native_trajectory_rmsf.csv').resolve()),
        "clusters_csv":str((out/'native_trajectory_clusters.csv').resolve()),
        "claim_guard":"RMSD/Rg/RMSF, sampled-frame cluster fractions and medoids are descriptive geometry evidence only; they do not prove equilibrium, folding probability, affinity, function, or convergence.",
    }
    (out/'native_trajectory_analysis_summary.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return payload

__all__=["NATIVE_TRAJECTORY_ANALYSIS_VERSION","analyze_native_frames"]
