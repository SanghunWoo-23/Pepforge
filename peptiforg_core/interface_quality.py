from __future__ import annotations

"""Coordinate-derived interface quality evidence for Pepforge V4.0.0.

This module deliberately reports separate geometric descriptors.  It does not
collapse them into an affinity/confidence score.  The SASA implementation is a
transparent, deterministic Shrake-Rupley-style approximation intended for
screening and comparison inside one Pepforge workflow, not publication-grade
surface analysis.
"""

from pathlib import Path
from typing import Any
import math
import numpy as np
import pandas as pd

from peptiforg_core.interaction_evidence import analyze_interaction_evidence, VDW_RADII

INTERFACE_QUALITY_VERSION = "1.0.0"
POLAR_ELEMENTS = {"N", "O", "S"}


def _norm(df: pd.DataFrame) -> pd.DataFrame:
    out=(df.copy() if df is not None else pd.DataFrame())
    for c in ["atom","resn","chain","resi","element"]:
        if c not in out: out[c]=""
        out[c]=out[c].astype(str)
    for c in ["x","y","z"]:
        out[c]=pd.to_numeric(out.get(c), errors="coerce")
    out=out.dropna(subset=["x","y","z"]).reset_index(drop=True)
    out["atom"]=out["atom"].str.upper(); out["resn"]=out["resn"].str.upper(); out["element"]=out["element"].str.upper()
    return out


def _radius(element: str) -> float:
    return float(VDW_RADII.get(str(element or "").upper(), 1.70))


def _sphere_points(n: int = 96) -> np.ndarray:
    # Fibonacci sphere; deterministic and dependency-free.
    i=np.arange(n, dtype=float)
    phi=(1.0 + 5.0**0.5)/2.0
    theta=2.0*math.pi*i/phi
    z=1.0-(2.0*i+1.0)/n
    r=np.sqrt(np.maximum(0.0, 1.0-z*z))
    return np.column_stack((r*np.cos(theta), r*np.sin(theta), z))


def _interface_mask(a: pd.DataFrame, b: pd.DataFrame, cutoff: float = 6.0) -> np.ndarray:
    if a.empty or b.empty: return np.zeros(len(a), dtype=bool)
    ax=a[["x","y","z"]].to_numpy(float); bx=b[["x","y","z"]].to_numpy(float)
    mask=np.zeros(len(a), dtype=bool)
    # Chunk to avoid a huge all-pairs matrix on large receptors.
    for start in range(0, len(a), 500):
        block=ax[start:start+500]
        d2=((block[:,None,:]-bx[None,:,:])**2).sum(axis=2)
        mask[start:start+len(block)] = (d2 <= cutoff*cutoff).any(axis=1)
    return mask


def _atom_sasa(frame: pd.DataFrame, *, probe_A: float = 1.4, points: int = 96,
               atom_indices: np.ndarray | None = None) -> dict[int,float]:
    f=_norm(frame)
    if f.empty: return {}
    xyz=f[["x","y","z"]].to_numpy(float)
    radii=np.asarray([_radius(x)+probe_A for x in f["element"]], dtype=float)
    samples=_sphere_points(points)
    if atom_indices is None: atom_indices=np.arange(len(f), dtype=int)
    result={}
    max_r=float(radii.max()) if len(radii) else 3.4
    try:
        from scipy.spatial import cKDTree
        tree=cKDTree(xyz)
        neighbor_lists=[tree.query_ball_point(xyz[int(i)], radii[int(i)]+max_r) for i in atom_indices]
    except Exception:
        neighbor_lists=[list(range(len(f))) for _ in atom_indices]
    for pos, idxv in enumerate(atom_indices):
        idx=int(idxv); rad=radii[idx]
        pts=xyz[idx][None,:] + samples*rad
        exposed=np.ones(points, dtype=bool)
        for j in neighbor_lists[pos]:
            if int(j)==idx: continue
            rr=radii[int(j)]
            inside=((pts-xyz[int(j)][None,:])**2).sum(axis=1) < rr*rr
            exposed &= ~inside
            if not exposed.any(): break
        result[idx]=float(exposed.mean() * 4.0*math.pi*rad*rad)
    return result


def interface_quality_evidence(target_atoms: pd.DataFrame, peptide_atoms: pd.DataFrame,
                               *, interaction_profile: str = "CONSERVATIVE_MANUAL",
                               probe_A: float = 1.4, sphere_points: int = 96,
                               target_hotspot_residues: list[str] | tuple[str, ...] | set[str] | None = None) -> dict[str,Any]:
    t=_norm(target_atoms); p=_norm(peptide_atoms)
    if t.empty or p.empty:
        return {"version":INTERFACE_QUALITY_VERSION,"status":"not_available","reason":"missing target or peptide coordinates"}
    tmask=_interface_mask(t,p,6.0); pmask=_interface_mask(p,t,6.0)
    ti=np.where(tmask)[0]; pi=np.where(pmask)[0]
    combined=pd.concat([
        t.assign(_partner="target", _local_index=np.arange(len(t))),
        p.assign(_partner="peptide", _local_index=np.arange(len(p))),
    ], ignore_index=True)
    ci=np.concatenate([ti, len(t)+pi]).astype(int)
    sasa_t=_atom_sasa(t,probe_A=probe_A,points=sphere_points,atom_indices=ti)
    sasa_p=_atom_sasa(p,probe_A=probe_A,points=sphere_points,atom_indices=pi)
    sasa_c=_atom_sasa(combined,probe_A=probe_A,points=sphere_points,atom_indices=ci)
    loss_t={int(i):max(0.0,sasa_t.get(int(i),0.0)-sasa_c.get(int(i),0.0)) for i in ti}
    loss_p={int(i):max(0.0,sasa_p.get(int(i),0.0)-sasa_c.get(len(t)+int(i),0.0)) for i in pi}
    delta=float(sum(loss_t.values())+sum(loss_p.values()))

    interactions=analyze_interaction_evidence(t,p,profile_name=interaction_profile,representative_only=True)
    counts={}
    if not interactions.empty:
        for kind,n in interactions["interaction"].value_counts().items(): counts[str(kind)]=int(n)

    # Candidate buried polar atoms: meaningful solvent burial but no specific
    # H-bond/salt-bridge evidence involving the same residue.  This is not a
    # Rosetta unsatisfied-H-bond metric and is labelled accordingly.
    satisfied_residues=set()
    if not interactions.empty:
        for _,row in interactions[interactions["interaction"].isin(["hydrogen_bond","salt_bridge"])].iterrows():
            satisfied_residues.add(("target",str(row.get("target_residue"))))
            satisfied_residues.add(("peptide",str(row.get("peptide_residue"))))
    def label(row):
        chain=str(row.get("chain","")).strip(); resi=str(row.get("resi","")).strip(); resn=str(row.get("resn","")).strip()
        return f"{chain}:{resi}{resn}" if chain else f"{resi}{resn}"
    buried_candidates=[]
    for partner, frame, losses in (("target",t,loss_t),("peptide",p,loss_p)):
        for idx,loss in losses.items():
            row=frame.iloc[int(idx)]
            if str(row.element) not in POLAR_ELEMENTS or loss < 5.0: continue
            rlabel=label(row)
            if (partner,rlabel) in satisfied_residues: continue
            buried_candidates.append({"partner":partner,"residue":rlabel,"atom":str(row.atom),"sasa_loss_A2":round(loss,2),"status":"buried_unsatisfied_polar_candidate"})

    contact_atom_pairs=0; hydrophobic_pairs=0; polar_pairs=0
    tx=t[["x","y","z"]].to_numpy(float); px=p[["x","y","z"]].to_numpy(float)
    for start in range(0,len(t),400):
        block=tx[start:start+400]
        d2=((block[:,None,:]-px[None,:,:])**2).sum(axis=2)
        ii,jj=np.where(d2<=25.0)
        for i,j in zip(ii,jj):
            tr=t.iloc[start+int(i)]; pr=p.iloc[int(j)]; contact_atom_pairs+=1
            te=str(tr.element); pe=str(pr.element)
            if te in {"C","S"} and pe in {"C","S"}: hydrophobic_pairs+=1
            if te in POLAR_ELEMENTS and pe in POLAR_ELEMENTS: polar_pairs+=1

    target_interface_residues=sorted({label(t.iloc[int(i)]) for i in ti})
    peptide_interface_residues=sorted({label(p.iloc[int(i)]) for i in pi})
    hotspot_labels=sorted({str(x).strip() for x in (target_hotspot_residues or []) if str(x).strip()})
    hotspot_at_interface=sorted(set(hotspot_labels) & set(target_interface_residues))
    hotspot_coverage = {
        "status": "available" if hotspot_labels else "not_supplied",
        "input_hotspot_count": len(hotspot_labels),
        "interface_hotspot_count": len(hotspot_at_interface),
        "interface_hotspots": hotspot_at_interface,
        "coverage_fraction": (round(len(hotspot_at_interface) / len(hotspot_labels), 4) if hotspot_labels else None),
        "claim_guard": "Hotspot coverage is a geometric overlap descriptor only; it is not hotspot validation, affinity, or binding free energy.",
    }

    nonpolar_fraction=(hydrophobic_pairs/contact_atom_pairs if contact_atom_pairs else None)
    polar_fraction=(polar_pairs/contact_atom_pairs if contact_atom_pairs else None)

    return {
        "version":INTERFACE_QUALITY_VERSION,
        "status":"available",
        "interaction_profile":interaction_profile,
        "interface_target_atom_count":int(tmask.sum()),
        "interface_peptide_atom_count":int(pmask.sum()),
        "interface_target_residue_count":len(target_interface_residues),
        "interface_peptide_residue_count":len(peptide_interface_residues),
        "interface_target_residues":target_interface_residues,
        "interface_peptide_residues":peptide_interface_residues,
        "contact_atom_pairs_le_5A":contact_atom_pairs,
        "nonpolar_contact_atom_pairs_le_5A":hydrophobic_pairs,
        "polar_contact_atom_pairs_le_5A":polar_pairs,
        "nonpolar_contact_pair_fraction":round(nonpolar_fraction,4) if nonpolar_fraction is not None else None,
        "polar_contact_pair_fraction":round(polar_fraction,4) if polar_fraction is not None else None,
        "interaction_counts":counts,
        "hotspot_coverage": hotspot_coverage,
        "approx_delta_SASA_A2":round(delta,2),
        "approx_interface_area_half_delta_SASA_A2":round(delta/2.0,2),
        "sasa_method":f"Shrake-Rupley-style deterministic approximation; probe={probe_A} A; sphere_points={sphere_points}",
        "buried_unsatisfied_polar_candidates":buried_candidates,
        "buried_unsatisfied_polar_candidate_count":len(buried_candidates),
        "shape_complementarity":{"status":"not_computed","reason":"No validated shape-complementarity backend is bundled in V4.0.0; Pepforge does not substitute a home-made score and call it Rosetta-style Sc."},
        "claim_guard": (
            "Interface-quality descriptors are coordinate-derived screening evidence. Approximate SASA and candidate buried polar flags are not affinity, "
            "binding free energy, Rosetta shape complementarity, or experimental interface validation. Compare like-with-like using the same method settings."
        ),
        "literature_context":["DOI:10.1038/s41586-025-09429-6"],
    }


def parse_pdb_atoms(path: str | Path) -> pd.DataFrame:
    rows=[]
    aa3={"ALA":"A","ARG":"R","ASN":"N","ASP":"D","CYS":"C","GLN":"Q","GLU":"E","GLY":"G","HIS":"H","ILE":"I","LEU":"L","LYS":"K","MET":"M","PHE":"F","PRO":"P","SER":"S","THR":"T","TRP":"W","TYR":"Y","VAL":"V"}
    for line in Path(path).read_text(encoding="utf-8",errors="ignore").splitlines():
        if not line.startswith(("ATOM  ","HETATM")): continue
        try:
            atom=line[12:16].strip(); resn=line[17:20].strip().upper(); chain=line[21].strip(); resi=line[22:27].strip()
            x=float(line[30:38]); y=float(line[38:46]); z=float(line[46:54]); element=(line[76:78].strip() if len(line)>=78 else "") or "".join(ch for ch in atom if ch.isalpha())[:1]
        except Exception: continue
        rows.append({"atom":atom,"resn":resn,"chain":chain,"resi":resi,"x":x,"y":y,"z":z,"element":element.upper(),"aa":aa3.get(resn,"X")})
    return pd.DataFrame(rows)


__all__=["INTERFACE_QUALITY_VERSION","interface_quality_evidence","parse_pdb_atoms"]
