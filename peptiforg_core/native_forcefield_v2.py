from __future__ import annotations

"""Pepforge-native transparent mechanics parameter layer.

This is an independently implemented, deliberately conservative parameter layer
for Pepforge's native mechanics path.  It provides explicit provenance and
keeps every quantity in documented reduced/mechanical units.  It is NOT a
validated biomolecular force field and must not be presented as one.
"""

from dataclasses import dataclass, asdict
from typing import Any
import math
import numpy as np

from .native_topology_v1 import NativeTopology

NATIVE_FORCEFIELD_VERSION = "0.2.0"

# Element-level generic Lennard-Jones-like radii/depths.  They are transparent
# screening/mechanics proxies, not AMBER/CHARMM/OPLS parameters.
_ELEMENT_SIGMA_A = {"H":2.40,"C":3.40,"N":3.10,"O":3.00,"S":3.60,"P":3.60,"F":2.90,"CL":3.50,"BR":3.70,"I":3.95}
_ELEMENT_EPS_REDUCED = {"H":0.015,"C":0.070,"N":0.060,"O":0.080,"S":0.100,"P":0.090,"F":0.050,"CL":0.090,"BR":0.110,"I":0.130}

@dataclass(frozen=True)
class NativeParameterSet:
    name: str = "PEPFORGE_NATIVE_TRANSPARENT_V2"
    bond_k: float = 55.0
    angle_k: float = 8.0
    torsion_14_k: float = 0.50
    lj_scale: float = 1.0
    coulomb_scale: float = 0.30
    dielectric: float = 20.0
    cutoff_A: float = 12.0
    scale_14_nonbonded: float = 0.50
    provenance: str = "Pepforge independent transparent generic element/topology proxy parameters; not copied from a third-party biomolecular force field."
    units: str = "coordinates=A; masses=Da; energies/forces=reduced Pepforge mechanics units; no physical time mapping"

    def metadata(self) -> dict[str, Any]:
        d = asdict(self)
        d["version"] = NATIVE_FORCEFIELD_VERSION
        d["claim_guard"] = "Not a validated force field; no physical free-energy, thermodynamic, or timescale claim is permitted."
        return d


def _sigma(el: str) -> float:
    return float(_ELEMENT_SIGMA_A.get(str(el).upper(), 3.40))


def _eps(el: str) -> float:
    return float(_ELEMENT_EPS_REDUCED.get(str(el).upper(), 0.07))


def _pair14(top: NativeTopology) -> set[tuple[int,int]]:
    out:set[tuple[int,int]] = set()
    for i,_,_,l,_ in top.dihedrals:
        out.add((min(i,l), max(i,l)))
    return out


def _angle_force(xyz: np.ndarray, i:int, j:int, k:int, theta0:float, k_angle:float):
    a=xyz[i]-xyz[j]; b=xyz[k]-xyz[j]
    ra=float(np.linalg.norm(a)); rb=float(np.linalg.norm(b))
    if ra<1e-10 or rb<1e-10:
        return None, 0.0
    ua=a/ra; ub=b/rb
    c=float(np.clip(np.dot(ua,ub),-0.999999,0.999999)); th=float(math.acos(c))
    s=max(1e-8,math.sqrt(1-c*c)); d=th-theta0
    pref=-float(k_angle)*d/s
    fi=pref*(ub-c*ua)/ra; fk=pref*(ua-c*ub)/rb; fj=-(fi+fk)
    return (fi,fj,fk), 0.5*float(k_angle)*d*d


def evaluate_native_forcefield(top: NativeTopology, xyz: np.ndarray, params: NativeParameterSet|None=None) -> tuple[np.ndarray, dict[str,float]]:
    p=params or NativeParameterSet(); xyz=np.asarray(xyz,dtype=float)
    if xyz.shape != top.coordinates_A.shape:
        raise ValueError("Coordinate shape does not match topology")
    f=np.zeros_like(xyz)
    eb=ea=et14=elj=ecoul=0.0

    for i,j,r0,_ in top.bonds:
        v=xyz[j]-xyz[i]; d=float(np.linalg.norm(v))
        if d<1e-10: continue
        delta=d-r0; ff=float(p.bond_k)*delta*(v/d)
        f[i]+=ff; f[j]-=ff; eb += 0.5*float(p.bond_k)*delta*delta

    for i,j,k,th0 in top.angles:
        ff,e=_angle_force(xyz,i,j,k,th0,p.angle_k); ea+=e
        if ff is not None:
            f[i]+=ff[0]; f[j]+=ff[1]; f[k]+=ff[2]

    # Preserve local torsional geometry without pretending to use a validated
    # torsional potential: restrain the 1-4 distance implied by each input torsion.
    # This gives an explicit differentiable geometry term and provenance remains clear.
    seen14=set()
    for i,_,_,l,_ in top.dihedrals:
        key=(min(i,l),max(i,l))
        if key in seen14: continue
        seen14.add(key)
        r0=float(np.linalg.norm(top.coordinates_A[l]-top.coordinates_A[i]))
        v=xyz[l]-xyz[i]; d=float(np.linalg.norm(v))
        if d<1e-10: continue
        delta=d-r0; ff=float(p.torsion_14_k)*delta*(v/d)
        f[i]+=ff; f[l]-=ff; et14 += 0.5*float(p.torsion_14_k)*delta*delta

    pair14=_pair14(top); n=len(top.atoms); cutoff=float(p.cutoff_A)
    for i in range(n):
        ei=str(top.atoms.iloc[i].element).upper()
        for j in range(i+1,n):
            pair=(i,j)
            if pair in top.exclusions_12 or pair in top.exclusions_13:
                continue
            v=xyz[j]-xyz[i]; d=float(np.linalg.norm(v))
            if d<1e-8: d=1e-8
            if d>cutoff: continue
            u=v/d
            scale14=float(p.scale_14_nonbonded) if pair in pair14 else 1.0
            sigma=0.5*(_sigma(ei)+_sigma(str(top.atoms.iloc[j].element).upper()))
            eps=math.sqrt(_eps(ei)*_eps(str(top.atoms.iloc[j].element).upper()))*float(p.lj_scale)*scale14
            # Smooth soft-core radius avoids a non-differentiable hard cap and
            # keeps the reported score mathematically consistent with its force.
            # rr = sqrt(d^2 + alpha^2); drr/dd = d/rr.
            alpha=0.35*sigma
            rr=math.sqrt(d*d + alpha*alpha)
            sr6=(sigma/rr)**6; sr12=sr6*sr6
            e_lj=4.0*eps*(sr12-sr6); elj+=e_lj
            dE_drr=24.0*eps*(-2.0*sr12+sr6)/rr
            dE_dd=dE_drr*(d/rr)
            ff=dE_dd*u
            f[i]+=ff; f[j]-=ff

            qi=float(top.formal_charge_proxy_e[i]); qj=float(top.formal_charge_proxy_e[j])
            if qi and qj:
                A=float(p.coulomb_scale)*qi*qj/max(1e-8,float(p.dielectric))*scale14
                e=A/d; ecoul+=e
                dEdr=-A/(d*d); ff=dEdr*u
                f[i]+=ff; f[j]-=ff

    terms={"bond":eb,"angle":ea,"torsion_14_proxy":et14,"lj_proxy":elj,"electrostatic_proxy":ecoul}
    terms["total_reduced_score"]=sum(terms.values())
    return f,{k:float(v) for k,v in terms.items()}


__all__=["NATIVE_FORCEFIELD_VERSION","NativeParameterSet","evaluate_native_forcefield"]
