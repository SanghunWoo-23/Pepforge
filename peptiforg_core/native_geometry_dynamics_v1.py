from __future__ import annotations

"""Pepforge-native geometry relaxation / conformational exploration foundation.

This is NOT production molecular dynamics. It is an independently implemented,
dimensionless geometry-dynamics engine used to relax severe overlaps while
approximately preserving starting covalent geometry. It provides a real force
calculation loop, deterministic/stochastic coordinate updates, trajectory output,
and restart state without depending on OpenMM or another scientific engine.

A future Pepforge-native MD engine may build on these interfaces only after
validated force-field parameters, units, integrator validation and benchmarks are
added. Until then, outputs are labelled EXPERIMENTAL_GEOMETRY_DYNAMICS.
"""

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
import json
import math
import numpy as np
import pandas as pd

from .interface_quality import parse_pdb_atoms

NATIVE_GEOMETRY_DYNAMICS_VERSION = "0.1.0"

_COVALENT = {"H":0.31,"C":0.76,"N":0.71,"O":0.66,"S":1.05,"P":1.07,"F":0.57,"CL":1.02,"BR":1.20,"I":1.39}
_VDW = {"H":1.20,"C":1.70,"N":1.55,"O":1.52,"S":1.80,"P":1.80,"F":1.47,"CL":1.75,"BR":1.85,"I":1.98}


@dataclass(frozen=True)
class NativeGeometryDynamicsConfig:
    steps: int = 250
    step_size: float = 0.003
    bond_k: float = 30.0
    repulsion_k: float = 2.0
    weak_attraction_k: float = 0.02
    noise_scale: float = 0.0
    save_every: int = 25
    seed: int = 20260929
    freeze_receptor: bool = True
    peptide_chain: str = "P"


def _radius(el: str, table: dict[str,float], default: float) -> float:
    return table.get(str(el or "").strip().upper(), default)


def _infer_bonds(atoms: pd.DataFrame, xyz: np.ndarray) -> list[tuple[int,int,float]]:
    bonds=[]
    n=len(atoms)
    for i in range(n):
        ei=str(atoms.iloc[i].element).upper()
        for j in range(i+1,n):
            # limit inference mostly within residue or sequential residues/chains;
            # prevents spurious interface covalent bonds.
            ai=atoms.iloc[i]; aj=atoms.iloc[j]
            if str(ai.chain)!=str(aj.chain):
                continue
            try:
                ri=int(''.join(c for c in str(ai.resi) if c.isdigit() or c=='-') or '0')
                rj=int(''.join(c for c in str(aj.resi) if c.isdigit() or c=='-') or '0')
                if abs(ri-rj)>1: continue
            except Exception:
                if str(ai.resi)!=str(aj.resi): continue
            ej=str(aj.element).upper()
            d=float(np.linalg.norm(xyz[i]-xyz[j]))
            cutoff=_radius(ei,_COVALENT,0.77)+_radius(ej,_COVALENT,0.77)+0.45
            if 0.55 <= d <= cutoff:
                bonds.append((i,j,d))
    return bonds


def _forces(atoms: pd.DataFrame, xyz: np.ndarray, bonds: list[tuple[int,int,float]], cfg: NativeGeometryDynamicsConfig) -> tuple[np.ndarray,dict[str,float]]:
    f=np.zeros_like(xyz)
    bond_term=0.0; rep_term=0.0; attr_term=0.0
    bonded=set()
    for i,j,r0 in bonds:
        bonded.add((i,j)); bonded.add((j,i))
        v=xyz[j]-xyz[i]; d=float(np.linalg.norm(v))
        if d<1e-12: continue
        delta=d-r0
        mag=float(cfg.bond_k)*delta
        unit=v/d
        force=mag*unit
        f[i]+=force; f[j]-=force
        bond_term+=0.5*float(cfg.bond_k)*delta*delta
    n=len(atoms)
    for i in range(n):
        ei=str(atoms.iloc[i].element).upper()
        for j in range(i+1,n):
            if (i,j) in bonded: continue
            ej=str(atoms.iloc[j].element).upper()
            v=xyz[j]-xyz[i]; d=float(np.linalg.norm(v))
            if d<1e-8: d=1e-8
            unit=v/d
            contact=_radius(ei,_VDW,1.7)+_radius(ej,_VDW,1.7)
            # Soft overlap penalty. This is a geometry term, not a force-field LJ energy.
            overlap=contact-d
            if overlap>0:
                mag=float(cfg.repulsion_k)*overlap
                force=mag*unit
                f[i]-=force; f[j]+=force
                rep_term+=0.5*float(cfg.repulsion_k)*overlap*overlap
            elif d < contact+2.0 and cfg.weak_attraction_k>0:
                # small bounded attraction only to prevent interface evaporation;
                # deliberately weak and dimensionless.
                gap=d-contact
                mag=float(cfg.weak_attraction_k)*gap
                force=mag*unit
                f[i]+=force; f[j]-=force
                attr_term+=0.5*float(cfg.weak_attraction_k)*gap*gap
    return f,{"bond_geometry":bond_term,"steric_overlap":rep_term,"weak_contact":attr_term,"total_geometry_score":bond_term+rep_term+attr_term}


def _write_pdb_frame(atoms: pd.DataFrame, xyz: np.ndarray, path: Path) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    lines=["REMARK 950 PEPFORGE EXPERIMENTAL_GEOMETRY_DYNAMICS",f"REMARK 951 VERSION {NATIVE_GEOMETRY_DYNAMICS_VERSION}"]
    for serial,(_,row) in enumerate(atoms.iterrows(),1):
        atom=str(row.atom)[:4]; resn=str(row.resn)[:3]; chain=(str(row.chain)[:1] or 'A')
        raw=''.join(c for c in str(row.resi) if c.isdigit() or c=='-')
        try: resi=int(raw or '1')
        except Exception: resi=1
        el=str(row.element).upper()[:2]
        x,y,z=xyz[serial-1]
        rec='ATOM  ' if resn in {"ALA","ARG","ASN","ASP","CYS","GLN","GLU","GLY","HIS","ILE","LEU","LYS","MET","PHE","PRO","SER","THR","TRP","TYR","VAL"} else 'HETATM'
        lines.append(f"{rec}{serial:5d} {atom:>4s} {resn:>3s} {chain}{resi:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00          {el:>2s}")
    lines += ["END"]
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')


def run_native_geometry_dynamics(pdb_path: str|Path, output_dir: str|Path, *, config: NativeGeometryDynamicsConfig|None=None, restart_state: str|Path|None=None) -> dict[str,Any]:
    cfg=config or NativeGeometryDynamicsConfig()
    src=Path(pdb_path).expanduser().resolve()
    atoms=parse_pdb_atoms(src)
    if atoms.empty: raise ValueError('No readable atoms in input PDB.')
    xyz=atoms[["x","y","z"]].to_numpy(dtype=float)
    out=Path(output_dir).expanduser().resolve(); out.mkdir(parents=True,exist_ok=True)
    start_step=0
    if restart_state:
        state=json.loads(Path(restart_state).read_text(encoding='utf-8'))
        arr=np.asarray(state.get('coordinates_A'),dtype=float)
        if arr.shape!=xyz.shape: raise ValueError('Restart coordinates do not match input atom count.')
        xyz=arr; start_step=int(state.get('step',0))
    bonds=_infer_bonds(atoms,xyz)
    rng=np.random.default_rng(int(cfg.seed)+start_step)
    movable=np.ones(len(atoms),dtype=bool)
    if cfg.freeze_receptor:
        movable=atoms['chain'].astype(str).eq(str(cfg.peptide_chain)).to_numpy(dtype=bool)
        if not movable.any():
            # peptide chain labels vary; if P is absent, allow all atoms rather than silently doing nothing.
            movable[:]=True
    rows=[]; frame_paths=[]
    for local_step in range(max(0,int(cfg.steps))+1):
        step=start_step+local_step
        force,terms=_forces(atoms,xyz,bonds,cfg)
        max_force=float(np.linalg.norm(force,axis=1).max()) if len(force) else 0.0
        rows.append({"step":step,**{k:float(v) for k,v in terms.items()},"max_force":max_force})
        if local_step % max(1,int(cfg.save_every)) == 0 or local_step == int(cfg.steps):
            fp=out/'frames'/f'frame_{step:06d}.pdb'; _write_pdb_frame(atoms,xyz,fp); frame_paths.append(str(fp.resolve()))
        if local_step == int(cfg.steps): break
        update=float(cfg.step_size)*force
        if float(cfg.noise_scale)>0:
            update += rng.normal(0.0,float(cfg.noise_scale),size=xyz.shape)
        update[~movable]=0.0
        # protect against numerical explosions in malformed input.
        norms=np.linalg.norm(update,axis=1)
        mask=norms>0.25
        if mask.any(): update[mask]*=(0.25/norms[mask])[:,None]
        xyz=xyz+update
    traj_csv=out/'native_geometry_dynamics_trace.csv'; pd.DataFrame(rows).to_csv(traj_csv,index=False,encoding='utf-8-sig')
    final_pdb=out/'final_relaxed_geometry.pdb'; _write_pdb_frame(atoms,xyz,final_pdb)
    state_path=out/'restart_state.json'
    state={"version":NATIVE_GEOMETRY_DYNAMICS_VERSION,"step":start_step+int(cfg.steps),"coordinates_A":xyz.tolist(),"config":asdict(cfg),"source_pdb":str(src)}
    state_path.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    payload={
        "version":NATIVE_GEOMETRY_DYNAMICS_VERSION,"status":"COMPLETED",
        "engine":"Pepforge Native Geometry Dynamics v1","evidence_grade":"EXPERIMENTAL_GEOMETRY_DYNAMICS",
        "source_pdb":str(src),"config":asdict(cfg),"inferred_bond_count":len(bonds),
        "initial_geometry_score":rows[0]['total_geometry_score'],"final_geometry_score":rows[-1]['total_geometry_score'],
        "final_pdb":str(final_pdb.resolve()),"trace_csv":str(traj_csv.resolve()),"restart_state":str(state_path.resolve()),"frames":frame_paths,
        "claim_guard":"This is not production molecular dynamics, physical time evolution, free-energy simulation, or validated force-field dynamics. It is a Pepforge-native dimensionless geometry relaxation/exploration foundation.",
    }
    (out/'native_geometry_dynamics_summary.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return payload

__all__=["NATIVE_GEOMETRY_DYNAMICS_VERSION","NativeGeometryDynamicsConfig","run_native_geometry_dynamics"]
