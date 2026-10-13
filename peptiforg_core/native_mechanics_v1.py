from __future__ import annotations

"""Pepforge-native experimental molecular mechanics foundation.

The engine evaluates explicit bonded and nonbonded terms over a Pepforge-native
PDB topology.  Parameters are transparent generic/proxy values and therefore the
engine is NOT a validated force field and its trajectories are NOT production MD.
It exists to remove scientific-engine lock-in while preserving strict claim guards.
"""

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
import json
import math
import numpy as np
import pandas as pd

from .native_topology_v1 import NativeTopology, build_native_topology, export_native_topology
from .native_quality_gate_v1 import audit_peptide_geometry, assess_native_mechanics
from .native_trajectory_analysis_v1 import analyze_native_frames

NATIVE_MECHANICS_VERSION="0.3.0"
_VDW={"H":1.20,"C":1.70,"N":1.55,"O":1.52,"S":1.80,"P":1.80,"F":1.47,"CL":1.75,"BR":1.85,"I":1.98}

@dataclass(frozen=True)
class NativeMechanicsConfig:
    steps: int = 500
    dt_reduced: float = 0.0008
    bond_k: float = 45.0
    angle_k: float = 6.0
    repulsion_k: float = 3.0
    attraction_k: float = 0.025
    electrostatic_k: float = 0.35
    dielectric: float = 20.0
    damping: float = 0.06
    velocity_noise: float = 0.0
    max_displacement_A: float = 0.12
    save_every: int = 50
    seed: int = 20260929
    freeze_receptor: bool = False
    peptide_chain: str = "P"


def _rad(el:str)->float: return float(_VDW.get(str(el).upper(),1.70))

def _angle_force(xyz,i,j,k,theta0,k_angle):
    a=xyz[i]-xyz[j]; b=xyz[k]-xyz[j]
    ra=float(np.linalg.norm(a)); rb=float(np.linalg.norm(b))
    if ra<1e-9 or rb<1e-9: return None,0.0
    ua=a/ra; ub=b/rb; c=float(np.clip(np.dot(ua,ub),-0.999999,0.999999)); th=float(math.acos(c)); s=max(1e-6,math.sqrt(1-c*c))
    d=th-theta0; pref=-float(k_angle)*d/s
    fi=pref*(ub-c*ua)/ra; fk=pref*(ua-c*ub)/rb; fj=-(fi+fk)
    return (fi,fj,fk),0.5*float(k_angle)*d*d


def evaluate_native_mechanics(top:NativeTopology, xyz:np.ndarray, cfg:NativeMechanicsConfig)->tuple[np.ndarray,dict[str,float]]:
    xyz=np.asarray(xyz,dtype=float); f=np.zeros_like(xyz)
    eb=ea=erep=eatt=eelec=0.0
    for i,j,r0,_ in top.bonds:
        v=xyz[j]-xyz[i]; d=float(np.linalg.norm(v))
        if d<1e-9: continue
        delta=d-r0; ff=float(cfg.bond_k)*delta*(v/d); f[i]+=ff; f[j]-=ff; eb+=0.5*float(cfg.bond_k)*delta*delta
    for i,j,k,th0 in top.angles:
        ff,e=_angle_force(xyz,i,j,k,th0,cfg.angle_k); ea+=e
        if ff is not None:
            f[i]+=ff[0]; f[j]+=ff[1]; f[k]+=ff[2]
    n=len(top.atoms)
    for i in range(n):
        ei=str(top.atoms.iloc[i].element).upper()
        for j in range(i+1,n):
            pair=(i,j)
            if pair in top.exclusions_12 or pair in top.exclusions_13: continue
            ej=str(top.atoms.iloc[j].element).upper(); v=xyz[j]-xyz[i]; d=float(np.linalg.norm(v))
            if d<1e-6: d=1e-6
            u=v/d; contact=_rad(ei)+_rad(ej); overlap=contact-d
            if overlap>0:
                mag=float(cfg.repulsion_k)*overlap; ff=mag*u; f[i]-=ff; f[j]+=ff; erep+=0.5*float(cfg.repulsion_k)*overlap*overlap
            elif d<contact+2.0 and cfg.attraction_k>0:
                gap=d-contact; mag=float(cfg.attraction_k)*gap; ff=mag*u; f[i]+=ff; f[j]-=ff; eatt+=0.5*float(cfg.attraction_k)*gap*gap
            qi=float(top.formal_charge_proxy_e[i]); qj=float(top.formal_charge_proxy_e[j])
            if qi and qj and d<12.0:
                # Reduced electrostatic proxy. Sign follows Coulomb interaction,
                # but the coefficient is deliberately not presented as physical energy.
                e=float(cfg.electrostatic_k)*qi*qj/(max(1e-6,float(cfg.dielectric))*d)
                eelec+=e
                # E=A/d -> F on i along +u for like charges? Force_i=-dE/dri = -A*u/d^2.
                mag=float(cfg.electrostatic_k)*qi*qj/(max(1e-6,float(cfg.dielectric))*d*d)
                f[i]-=mag*u; f[j]+=mag*u
    terms={"bond":eb,"angle":ea,"steric_repulsion":erep,"weak_contact":eatt,"electrostatic_proxy":eelec}
    terms["total_reduced_score"]=sum(terms.values())
    return f,{k:float(v) for k,v in terms.items()}


def _write_pdb(atoms:pd.DataFrame,xyz:np.ndarray,path:Path):
    canonical={"ALA","ARG","ASN","ASP","CYS","GLN","GLU","GLY","HIS","ILE","LEU","LYS","MET","PHE","PRO","SER","THR","TRP","TYR","VAL"}
    lines=["REMARK 950 PEPFORGE EXPERIMENTAL_NATIVE_MECHANICS",f"REMARK 951 VERSION {NATIVE_MECHANICS_VERSION}"]
    for serial,(_,r) in enumerate(atoms.iterrows(),1):
        raw=''.join(c for c in str(r.resi) if c.isdigit() or c=='-')
        try: resi=int(raw or '1')
        except Exception: resi=1
        rec='ATOM  ' if str(r.resn).upper() in canonical else 'HETATM'
        x,y,z=xyz[serial-1]
        lines.append(f"{rec}{serial:5d} {str(r.atom)[:4]:>4s} {str(r.resn)[:3]:>3s} {(str(r.chain)[:1] or 'A')}{resi:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00          {str(r.element).upper()[:2]:>2s}")
    lines.append("END"); path.parent.mkdir(parents=True,exist_ok=True); path.write_text('\n'.join(lines)+'\n',encoding='utf-8')


def run_native_mechanics(pdb_path:str|Path,output_dir:str|Path,*,config:NativeMechanicsConfig|None=None,restart_state:str|Path|None=None)->dict[str,Any]:
    cfg=config or NativeMechanicsConfig(); top=build_native_topology(pdb_path); out=Path(output_dir).expanduser().resolve(); out.mkdir(parents=True,exist_ok=True)
    xyz=top.coordinates_A.copy(); vel=np.zeros_like(xyz); start=0
    if restart_state:
        state=json.loads(Path(restart_state).read_text(encoding='utf-8')); arr=np.asarray(state.get('coordinates_A'),dtype=float); vv=np.asarray(state.get('velocities_reduced'),dtype=float)
        if arr.shape!=xyz.shape or vv.shape!=xyz.shape: raise ValueError('Restart state shape does not match topology.')
        xyz=arr; vel=vv; start=int(state.get('step',0))
    rng=np.random.default_rng(int(cfg.seed)+start); masses=np.maximum(top.masses_Da,1.0)[:,None]
    movable=np.ones(len(xyz),dtype=bool)
    if cfg.freeze_receptor:
        movable=top.atoms['chain'].astype(str).eq(str(cfg.peptide_chain)).to_numpy(dtype=bool)
        if not movable.any(): raise ValueError(f"freeze_receptor requested but peptide chain {cfg.peptide_chain!r} was not found.")
    trace=[]; frames=[]
    force,terms=evaluate_native_mechanics(top,xyz,cfg)
    for local in range(max(0,int(cfg.steps))+1):
        step=start+local
        maxf=float(np.linalg.norm(force,axis=1).max()) if len(force) else 0.0
        trace.append({"step":step,**terms,"max_force_reduced":maxf,"rms_speed_reduced":float(np.sqrt(np.mean(vel*vel)))})
        if local%max(1,int(cfg.save_every))==0 or local==int(cfg.steps):
            fp=out/'frames'/f'frame_{step:06d}.pdb'; _write_pdb(top.atoms,xyz,fp); frames.append(str(fp.resolve()))
        if local==int(cfg.steps): break
        dt=float(cfg.dt_reduced)
        acc=force/masses; vel += 0.5*dt*acc
        vel *= max(0.0,1.0-float(cfg.damping))
        if cfg.velocity_noise>0: vel += rng.normal(0.0,float(cfg.velocity_noise),size=vel.shape)
        disp=dt*vel; disp[~movable]=0.0; vel[~movable]=0.0
        norms=np.linalg.norm(disp,axis=1); mask=norms>float(cfg.max_displacement_A)
        if mask.any(): disp[mask]*=(float(cfg.max_displacement_A)/norms[mask])[:,None]
        xyz += disp
        new_force,terms=evaluate_native_mechanics(top,xyz,cfg); vel += 0.5*dt*(new_force/masses); force=new_force
    trace_path=out/'native_mechanics_trace.csv'; pd.DataFrame(trace).to_csv(trace_path,index=False,encoding='utf-8-sig')
    final=out/'final_native_mechanics.pdb'; _write_pdb(top.atoms,xyz,final); topo_path=export_native_topology(top,out/'native_topology.json')
    final_geometry=audit_peptide_geometry(final, optional_rdkit=True)
    quality=assess_native_mechanics(initial_score=float(trace[0]['total_reduced_score']),final_score=float(trace[-1]['total_reduced_score']),final_geometry=final_geometry)
    state={"version":NATIVE_MECHANICS_VERSION,"step":start+int(cfg.steps),"coordinates_A":xyz.tolist(),"velocities_reduced":vel.tolist(),"config":asdict(cfg),"source_pdb":str(Path(pdb_path).resolve())}
    state_path=out/'native_mechanics_restart.json'; state_path.write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    native_trajectory=analyze_native_frames(frames,out/'native_trajectory_analysis',clusters=min(5,max(1,len(frames)))) if frames else {"status":"NO_FRAMES"}
    payload={
        "version":NATIVE_MECHANICS_VERSION,"status":"COMPLETED","engine":"Pepforge Native Mechanics v1",
        "evidence_grade":"EXPERIMENTAL_NATIVE_MECHANICS_NOT_MD","config":asdict(cfg),"topology":top.summary(),
        "initial_reduced_score":float(trace[0]['total_reduced_score']),"final_reduced_score":float(trace[-1]['total_reduced_score']),
        "final_pdb":str(final.resolve()),"trace_csv":str(trace_path.resolve()),"restart_state":str(state_path.resolve()),"topology_json":topo_path,"frames":frames,
        "quality_gate":quality,"final_geometry_quality":final_geometry,"native_trajectory_analysis":native_trajectory,
        "claim_guard":"Not production molecular dynamics: generic reduced parameters, coarse charge proxies, and unvalidated time/temperature mapping are used. No ΔG, Kd, physical trajectory time, or equilibrium claim is permitted.",
    }
    (out/'native_mechanics_summary.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return payload

__all__=["NATIVE_MECHANICS_VERSION","NativeMechanicsConfig","evaluate_native_mechanics","run_native_mechanics"]
