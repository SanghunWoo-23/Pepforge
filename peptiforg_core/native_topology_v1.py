from __future__ import annotations

"""Pepforge-native molecular topology foundation.

Independent implementation for offline Pepforge scientific workflows.  It builds
an explicit atom/bond/angle/dihedral graph from a PDB without RDKit/OpenMM.
The inferred graph is intended for canonical peptide/protein geometry work and
must not be treated as a validated chemical perception engine for arbitrary
ligands or modified residues.
"""

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
import json
import math
import numpy as np
import pandas as pd

from .interface_quality import parse_pdb_atoms

NATIVE_TOPOLOGY_VERSION = "0.1.0"

COVALENT_RADII_A = {
    "H": 0.31, "C": 0.76, "N": 0.71, "O": 0.66, "S": 1.05, "P": 1.07,
    "F": 0.57, "CL": 1.02, "BR": 1.20, "I": 1.39,
}
ATOMIC_MASS_DA = {
    "H": 1.008, "C": 12.011, "N": 14.007, "O": 15.999, "S": 32.06,
    "P": 30.974, "F": 18.998, "CL": 35.45, "BR": 79.904, "I": 126.90,
}
CANONICAL = {"ALA","ARG","ASN","ASP","CYS","GLN","GLU","GLY","HIS","ILE","LEU","LYS","MET","PHE","PRO","SER","THR","TRP","TYR","VAL"}


def _element(x: Any) -> str:
    return str(x or "").strip().upper()


def _res_index(x: Any) -> int | None:
    raw="".join(c for c in str(x) if c.isdigit() or c=="-")
    try: return int(raw)
    except Exception: return None


def _cov(el: str) -> float:
    return float(COVALENT_RADII_A.get(_element(el), 0.77))


def _mass(el: str) -> float:
    return float(ATOMIC_MASS_DA.get(_element(el), 12.0))


def _is_backbone_peptide_pair(a: pd.Series, b: pd.Series) -> bool:
    if str(a.chain) != str(b.chain): return False
    ra, rb = _res_index(a.resi), _res_index(b.resi)
    if ra is None or rb is None or abs(ra-rb) != 1: return False
    if str(a.resn).upper() not in CANONICAL or str(b.resn).upper() not in CANONICAL: return False
    # peptide C(i)-N(i+1), accepting either row order
    if ra + 1 == rb and str(a.atom).upper()=="C" and str(b.atom).upper()=="N": return True
    if rb + 1 == ra and str(b.atom).upper()=="C" and str(a.atom).upper()=="N": return True
    return False


def infer_bonds(atoms: pd.DataFrame, xyz: np.ndarray, tolerance_A: float = 0.42) -> list[tuple[int,int,float,str]]:
    bonds=[]
    n=len(atoms)
    for i in range(n):
        ai=atoms.iloc[i]; ei=_element(ai.element)
        for j in range(i+1,n):
            aj=atoms.iloc[j]; ej=_element(aj.element)
            if str(ai.chain) != str(aj.chain): continue
            ri,rj=_res_index(ai.resi),_res_index(aj.resi)
            same_res = str(ai.resi)==str(aj.resi)
            sequential = ri is not None and rj is not None and abs(ri-rj)==1
            if not (same_res or sequential): continue
            d=float(np.linalg.norm(xyz[i]-xyz[j]))
            if _is_backbone_peptide_pair(ai,aj):
                if 1.05 <= d <= 1.75:
                    bonds.append((i,j,d,"peptide_backbone"))
                continue
            # General distance inference is restricted to the same residue.
            if not same_res: continue
            cutoff=_cov(ei)+_cov(ej)+float(tolerance_A)
            if 0.55 <= d <= cutoff:
                bonds.append((i,j,d,"distance_within_residue"))
    return bonds


def enumerate_angles(n_atoms: int, bonds: list[tuple[int,int,float,str]], xyz: np.ndarray) -> list[tuple[int,int,int,float]]:
    neigh=[set() for _ in range(n_atoms)]
    for i,j,_,_ in bonds: neigh[i].add(j); neigh[j].add(i)
    out=[]
    for j in range(n_atoms):
        ns=sorted(neigh[j])
        for a in range(len(ns)):
            for b in range(a+1,len(ns)):
                i,k=ns[a],ns[b]
                v1=xyz[i]-xyz[j]; v2=xyz[k]-xyz[j]
                den=float(np.linalg.norm(v1)*np.linalg.norm(v2))
                if den < 1e-12: continue
                c=float(np.clip(np.dot(v1,v2)/den,-1.0,1.0))
                out.append((i,j,k,float(math.acos(c))))
    return out


def _dihedral(p0,p1,p2,p3) -> float:
    b0=-(p1-p0); b1=p2-p1; b2=p3-p2
    n=float(np.linalg.norm(b1))
    if n<1e-12: return 0.0
    b1=b1/n
    v=b0-np.dot(b0,b1)*b1
    w=b2-np.dot(b2,b1)*b1
    x=float(np.dot(v,w)); y=float(np.dot(np.cross(b1,v),w))
    return float(math.atan2(y,x))


def enumerate_dihedrals(n_atoms: int, bonds: list[tuple[int,int,float,str]], xyz: np.ndarray) -> list[tuple[int,int,int,int,float]]:
    neigh=[set() for _ in range(n_atoms)]
    for i,j,_,_ in bonds: neigh[i].add(j); neigh[j].add(i)
    seen=set(); out=[]
    for j in range(n_atoms):
        for k in neigh[j]:
            if j>=k: continue
            for i in neigh[j]-{k}:
                for l in neigh[k]-{j}:
                    key=min((i,j,k,l),(l,k,j,i))
                    if key in seen: continue
                    seen.add(key)
                    out.append((i,j,k,l,_dihedral(xyz[i],xyz[j],xyz[k],xyz[l])))
    return out


def exclusion_pairs(bonds, angles) -> tuple[set[tuple[int,int]],set[tuple[int,int]]]:
    ex12=set(); ex13=set()
    for i,j,_,_ in bonds: ex12.add((min(i,j),max(i,j)))
    for i,j,k,_ in angles: ex13.add((min(i,k),max(i,k)))
    return ex12,ex13


def heuristic_formal_charges(atoms: pd.DataFrame) -> tuple[np.ndarray,list[str]]:
    """Conservative integer/fractional charge centers for experimental mechanics.

    This is not an atomistic partial-charge model.  It only encodes obvious
    ionized side-chain groups and canonical free termini when identifiable.
    """
    q=np.zeros(len(atoms),dtype=float); notes=[]
    for idx,row in atoms.iterrows():
        resn=str(row.resn).upper(); atom=str(row.atom).upper()
        if resn=="LYS" and atom=="NZ": q[idx]=1.0
        elif resn=="ARG" and atom in {"NH1","NH2"}: q[idx]=0.5
        elif resn=="ASP" and atom in {"OD1","OD2"}: q[idx]=-0.5
        elif resn=="GLU" and atom in {"OE1","OE2"}: q[idx]=-0.5
    # Termini: only canonical chains, and only when explicit backbone atoms exist.
    for chain,g in atoms.groupby(atoms["chain"].astype(str),sort=False):
        canon=g[g["resn"].astype(str).str.upper().isin(CANONICAL)]
        if canon.empty: continue
        ris=[_res_index(x) for x in canon.resi]
        vals=[x for x in ris if x is not None]
        if not vals: continue
        rmin,rmax=min(vals),max(vals)
        nmask=(atoms["chain"].astype(str)==str(chain)) & (atoms["resi"].map(_res_index)==rmin) & atoms["atom"].astype(str).str.upper().eq("N")
        cmask=(atoms["chain"].astype(str)==str(chain)) & (atoms["resi"].map(_res_index)==rmax) & atoms["atom"].astype(str).str.upper().isin(["OXT"])
        if nmask.any(): q[np.where(nmask.to_numpy())[0][0]] += 1.0
        if cmask.any(): q[np.where(cmask.to_numpy())[0][0]] -= 1.0
    notes.append("Charges are coarse formal-group centers, not validated force-field partial charges.")
    notes.append("His protonation and chemical modifications are intentionally not guessed.")
    return q,notes


@dataclass
class NativeTopology:
    version: str
    atoms: pd.DataFrame
    coordinates_A: np.ndarray
    masses_Da: np.ndarray
    formal_charge_proxy_e: np.ndarray
    bonds: list[tuple[int,int,float,str]]
    angles: list[tuple[int,int,int,float]]
    dihedrals: list[tuple[int,int,int,int,float]]
    exclusions_12: set[tuple[int,int]]
    exclusions_13: set[tuple[int,int]]
    provenance: dict[str,Any]

    def summary(self) -> dict[str,Any]:
        return {
            "version":self.version,"atom_count":len(self.atoms),"bond_count":len(self.bonds),
            "angle_count":len(self.angles),"dihedral_count":len(self.dihedrals),
            "net_formal_charge_proxy_e":float(self.formal_charge_proxy_e.sum()),
            "provenance":self.provenance,
        }


def build_native_topology(pdb_path: str|Path) -> NativeTopology:
    path=Path(pdb_path).expanduser().resolve(); atoms=parse_pdb_atoms(path).reset_index(drop=True)
    if atoms.empty: raise ValueError("No readable atoms in input PDB.")
    xyz=atoms[["x","y","z"]].to_numpy(dtype=float)
    bonds=infer_bonds(atoms,xyz); angles=enumerate_angles(len(atoms),bonds,xyz); diheds=enumerate_dihedrals(len(atoms),bonds,xyz)
    ex12,ex13=exclusion_pairs(bonds,angles); q,notes=heuristic_formal_charges(atoms)
    masses=np.asarray([_mass(x) for x in atoms.element],dtype=float)
    unsupported=sorted(set(atoms.loc[~atoms["resn"].astype(str).str.upper().isin(CANONICAL),"resn"].astype(str)))
    provenance={
        "source_pdb":str(path),"bond_perception":"Pepforge distance-within-residue + explicit canonical peptide C-N rule",
        "reference_geometry":"input coordinates","charge_model":"coarse formal-group proxy",
        "unsupported_residue_names":unsupported,"notes":notes,
        "claim_guard":"Topology is inferred for Pepforge experimental native mechanics; it is not a validated arbitrary-chemistry parameterization.",
    }
    return NativeTopology(NATIVE_TOPOLOGY_VERSION,atoms,xyz,masses,q,bonds,angles,diheds,ex12,ex13,provenance)


def export_native_topology(top: NativeTopology, path: str|Path) -> str:
    p=Path(path); p.parent.mkdir(parents=True,exist_ok=True)
    payload=top.summary()
    payload["atoms"]=[{"index":int(i),"atom":str(r.atom),"resn":str(r.resn),"chain":str(r.chain),"resi":str(r.resi),"element":str(r.element),"mass_Da":float(top.masses_Da[i]),"formal_charge_proxy_e":float(top.formal_charge_proxy_e[i])} for i,r in top.atoms.iterrows()]
    payload["bonds"]=[{"i":i,"j":j,"r0_A":r0,"source":src} for i,j,r0,src in top.bonds]
    payload["angles"]=[{"i":i,"j":j,"k":k,"theta0_rad":th} for i,j,k,th in top.angles]
    payload["dihedrals"]=[{"i":i,"j":j,"k":k,"l":l,"phi0_rad":ph} for i,j,k,l,ph in top.dihedrals]
    p.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return str(p.resolve())

__all__=["NATIVE_TOPOLOGY_VERSION","NativeTopology","build_native_topology","export_native_topology","infer_bonds","enumerate_angles","enumerate_dihedrals"]
