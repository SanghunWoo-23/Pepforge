from __future__ import annotations

"""Pepforge-native canonical peptide backbone coordinate builder.

Builds N/CA/C/O and an approximate CB (except Gly) from one-letter canonical
sequence and user/proposed phi/psi torsions using an independent internal-coordinate
implementation.  No RDKit/OpenMM/PyMOL is required.

Scope is intentionally narrow: side-chain heavy atoms beyond CB, protonation,
chemical modifications, disulfides and force-field relaxation are not yet built.
Therefore this module emits EXPERIMENTAL_BACKBONE_ONLY evidence.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence, Any
import csv
import json
import math
import numpy as np

NATIVE_PEPTIDE_BUILDER_VERSION="0.2.0"
AA3={
"A":"ALA","C":"CYS","D":"ASP","E":"GLU","F":"PHE","G":"GLY","H":"HIS","I":"ILE","K":"LYS","L":"LEU","M":"MET","N":"ASN","P":"PRO","Q":"GLN","R":"ARG","S":"SER","T":"THR","V":"VAL","W":"TRP","Y":"TYR"}

# Transparent canonical peptide geometry constants (Angstrom/degrees). These are
# generic construction values, not a force field.
L_N_CA=1.458; L_CA_C=1.525; L_C_N=1.329; L_C_O=1.231; L_CA_CB=1.530
A_N_CA_C=111.2; A_CA_C_N=116.2; A_C_N_CA=121.7; A_CA_C_O=120.8


def _unit(v):
    n=float(np.linalg.norm(v))
    if n<1e-12: raise ValueError("Degenerate coordinate frame")
    return v/n


def place_atom(a:np.ndarray,b:np.ndarray,c:np.ndarray,length_A:float,angle_deg:float,dihedral_deg:float)->np.ndarray:
    """Place D from A-B-C and internal coordinates C-D, angle B-C-D, dihedral A-B-C-D."""
    bc=_unit(c-b)
    ba=b-a
    normal=np.cross(ba,bc)
    if np.linalg.norm(normal)<1e-10:
        trial=np.array([1.0,0.0,0.0]) if abs(bc[0])<0.8 else np.array([0.0,1.0,0.0])
        normal=np.cross(trial,bc)
    n=_unit(normal)
    m=np.cross(n,bc)
    th=math.radians(float(angle_deg)); ph=math.radians(float(dihedral_deg))
    # Direction from C.  -bc gives the reference direction for bond angle.
    direction=(-math.cos(th))*bc + math.sin(th)*(math.cos(ph)*m + math.sin(ph)*n)
    return c + float(length_A)*direction


def _initial_backbone():
    n=np.array([0.0,0.0,0.0],dtype=float)
    ca=np.array([L_N_CA,0.0,0.0],dtype=float)
    th=math.radians(180.0-A_N_CA_C)
    c=ca+np.array([L_CA_C*math.cos(th),L_CA_C*math.sin(th),0.0])
    return n,ca,c


def _cb_position(n,ca,c):
    # Approximate L-amino-acid tetrahedral CB direction from local backbone frame.
    u=_unit(n-ca); v=_unit(c-ca); bis=_unit(u+v); normal=_unit(np.cross(u,v))
    # coefficients chosen to create a stable tetrahedral-like direction; geometry
    # is a coordinate seed and will require later native refinement.
    direction=_unit(-0.60*bis + 0.80*normal)
    return ca + L_CA_CB*direction


def _carbonyl_o(n,ca,c,next_n=None):
    if next_n is not None:
        # Peptide plane: O points approximately opposite next N around carbonyl C.
        u=_unit(ca-c); v=_unit(next_n-c)
        direction=_unit(-(u+v))
        return c+L_C_O*direction
    # Terminal fallback in the N-CA-C plane.
    u=_unit(ca-c); normal=np.cross(n-ca,c-ca)
    if np.linalg.norm(normal)<1e-10: normal=np.array([0.0,0.0,1.0])
    perp=_unit(np.cross(_unit(normal),u))
    th=math.radians(A_CA_C_O)
    direction=math.cos(th)*u+math.sin(th)*perp
    return c+L_C_O*direction


def normalize_torsions(sequence:str, phi_deg:Sequence[float]|None=None, psi_deg:Sequence[float]|None=None, omega_deg:Sequence[float]|None=None):
    seq=str(sequence or "").strip().upper()
    if not seq or any(x not in AA3 for x in seq): raise ValueError("Native peptide builder v1 accepts non-empty canonical one-letter sequences only.")
    n=len(seq)
    phi=list(phi_deg) if phi_deg is not None else [-60.0]*n
    psi=list(psi_deg) if psi_deg is not None else [-45.0]*n
    omg=list(omega_deg) if omega_deg is not None else [180.0]*max(0,n-1)
    if len(phi)!=n or len(psi)!=n or len(omg)!=max(0,n-1): raise ValueError("phi/psi must match sequence length and omega must have length n-1")
    return seq,[float(x) for x in phi],[float(x) for x in psi],[float(x) for x in omg]


def build_native_backbone(sequence:str, *, phi_deg:Sequence[float]|None=None, psi_deg:Sequence[float]|None=None, omega_deg:Sequence[float]|None=None, chain:str="P") -> dict[str,Any]:
    seq,phi,psi,omega=normalize_torsions(sequence,phi_deg,psi_deg,omega_deg)
    n0,ca0,c0=_initial_backbone(); back=[(n0,ca0,c0)]
    for i in range(len(seq)-1):
        ni,cai,ci=back[-1]
        nnext=place_atom(ni,cai,ci,L_C_N,A_CA_C_N,psi[i])
        canext=place_atom(cai,ci,nnext,L_N_CA,A_C_N_CA,omega[i])
        cnext=place_atom(ci,nnext,canext,L_CA_C,A_N_CA_C,phi[i+1])
        back.append((nnext,canext,cnext))
    atoms=[]
    serial=1
    for i,(aa,(nn,ca,cc)) in enumerate(zip(seq,back),1):
        next_n=back[i][0] if i<len(back) else None
        oo=_carbonyl_o(nn,ca,cc,next_n)
        for atom,el,xyz in (("N","N",nn),("CA","C",ca),("C","C",cc),("O","O",oo)):
            atoms.append({"serial":serial,"atom":atom,"resn":AA3[aa],"chain":chain[:1] or "P","resi":i,"element":el,"x":float(xyz[0]),"y":float(xyz[1]),"z":float(xyz[2])}); serial+=1
        if aa!="G":
            cb=_cb_position(nn,ca,cc); atoms.append({"serial":serial,"atom":"CB","resn":AA3[aa],"chain":chain[:1] or "P","resi":i,"element":"C","x":float(cb[0]),"y":float(cb[1]),"z":float(cb[2])}); serial+=1
    return {
        "version":NATIVE_PEPTIDE_BUILDER_VERSION,"status":"COMPLETED","engine":"Pepforge Native Peptide Builder v1",
        "evidence_grade":"EXPERIMENTAL_BACKBONE_ONLY","sequence":seq,"phi_deg":phi,"psi_deg":psi,"omega_deg":omega,"atoms":atoms,
        "claim_guard":"Backbone/CB coordinate seed only. Side-chain chemistry, modifications, protonation, force-field energetics and native-state probability are not represented.",
    }


def write_native_backbone_pdb(result:dict[str,Any],path:str|Path)->str:
    p=Path(path); p.parent.mkdir(parents=True,exist_ok=True)
    lines=["REMARK 950 PEPFORGE EXPERIMENTAL_BACKBONE_ONLY",f"REMARK 951 VERSION {NATIVE_PEPTIDE_BUILDER_VERSION}",f"REMARK 952 SEQUENCE {result['sequence']}"]
    for r in result["atoms"]:
        lines.append(f"ATOM  {int(r['serial']):5d} {str(r['atom'])[:4]:>4s} {str(r['resn'])[:3]:>3s} {str(r['chain'])[:1]}{int(r['resi']):4d}    {float(r['x']):8.3f}{float(r['y']):8.3f}{float(r['z']):8.3f}  1.00  0.00          {str(r['element'])[:2]:>2s}")
    lines.append("END"); p.write_text("\n".join(lines)+"\n",encoding="utf-8"); return str(p.resolve())


def export_native_backbone(sequence:str,output_dir:str|Path,**kwargs)->dict[str,Any]:
    out=Path(output_dir).expanduser().resolve(); out.mkdir(parents=True,exist_ok=True)
    result=build_native_backbone(sequence,**kwargs); pdb=write_native_backbone_pdb(result,out/'native_backbone.pdb')
    from .native_quality_gate_v1 import audit_peptide_geometry
    quality=audit_peptide_geometry(pdb, optional_rdkit=True)
    tors=out/'native_backbone_torsions.csv'
    with tors.open('w',newline='',encoding='utf-8-sig') as fh:
        w=csv.writer(fh); w.writerow(['resi','aa','phi_deg','psi_deg','omega_to_next_deg'])
        for i,aa in enumerate(result['sequence']): w.writerow([i+1,aa,result['phi_deg'][i],result['psi_deg'][i],result['omega_deg'][i] if i<len(result['omega_deg']) else ''])
    summary={k:v for k,v in result.items() if k!='atoms'}; summary.update({'pdb':pdb,'torsion_csv':str(tors.resolve()),'atom_count':len(result['atoms']),'quality_gate':quality})
    (out/'native_backbone_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return summary

__all__=["NATIVE_PEPTIDE_BUILDER_VERSION","place_atom","build_native_backbone","write_native_backbone_pdb","export_native_backbone"]
