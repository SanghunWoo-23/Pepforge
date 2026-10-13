from __future__ import annotations

"""Pepforge Native Mechanics v2 with explicit parameter provenance and validation.

Still not production MD.  This module advances the native engine by separating
parameter provenance, a soft-core LJ-like nonbonded term, electrostatic proxy,
1-4 geometry preservation, deterministic damped velocity-Verlet integration,
restart, and validation diagnostics.
"""

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
import json
import numpy as np
import pandas as pd

from .native_topology_v1 import build_native_topology, export_native_topology
from .native_forcefield_v2 import NativeParameterSet, evaluate_native_forcefield
from .native_quality_gate_v1 import audit_peptide_geometry, assess_native_mechanics
from .native_trajectory_analysis_v1 import analyze_native_frames
from .native_mechanics_v1 import _write_pdb

NATIVE_MECHANICS_V2_VERSION="0.5.0"

@dataclass(frozen=True)
class NativeMechanicsV2Config:
    steps:int=750
    dt_reduced:float=0.0006
    damping:float=0.035
    velocity_noise:float=0.0
    max_displacement_A:float=0.08
    save_every:int=50
    seed:int=20260929
    freeze_receptor:bool=False
    peptide_chain:str="P"
    reject_if_score_explodes:bool=True
    explosion_factor:float=25.0


def _integrator_diagnostics(trace:list[dict[str,float]])->dict[str,Any]:
    if not trace:
        return {"status":"FAIL","reason":"empty trace"}
    vals=np.asarray([float(x["total_reduced_score"]) for x in trace],dtype=float)
    finite=bool(np.isfinite(vals).all())
    initial=float(vals[0]); final=float(vals[-1]); vmax=float(np.max(np.abs(vals)))
    denom=max(1.0,abs(initial))
    ratio=float(vmax/denom)
    return {
        "status":"PASS" if finite and ratio<25.0 else "WARN" if finite else "FAIL",
        "finite":finite,"initial_reduced_score":initial,"final_reduced_score":final,
        "max_abs_score_ratio_to_initial":ratio,
        "score_improved_or_equal":bool(final<=initial+1e-9),
        "note":"Diagnostic of numerical boundedness only; not physical energy conservation or MD validation.",
    }


def run_native_mechanics_v2(pdb_path:str|Path, output_dir:str|Path, *, config:NativeMechanicsV2Config|None=None,
                            parameters:NativeParameterSet|None=None, restart_state:str|Path|None=None)->dict[str,Any]:
    cfg=config or NativeMechanicsV2Config(); prm=parameters or NativeParameterSet()
    top=build_native_topology(pdb_path); out=Path(output_dir).expanduser().resolve(); out.mkdir(parents=True,exist_ok=True)
    xyz=top.coordinates_A.copy(); vel=np.zeros_like(xyz); start=0
    if restart_state:
        state=json.loads(Path(restart_state).read_text(encoding="utf-8"))
        arr=np.asarray(state.get("coordinates_A"),dtype=float); vv=np.asarray(state.get("velocities_reduced"),dtype=float)
        if arr.shape!=xyz.shape or vv.shape!=xyz.shape: raise ValueError("Restart state shape does not match topology")
        xyz=arr; vel=vv; start=int(state.get("step",0))
    rng=np.random.default_rng(int(cfg.seed)+start); masses=np.maximum(top.masses_Da,1.0)[:,None]
    movable=np.ones(len(xyz),dtype=bool)
    if cfg.freeze_receptor:
        movable=top.atoms["chain"].astype(str).eq(str(cfg.peptide_chain)).to_numpy(dtype=bool)
        if not movable.any(): raise ValueError(f"freeze_receptor requested but peptide chain {cfg.peptide_chain!r} was not found")
    trace=[]; frames=[]
    force,terms=evaluate_native_forcefield(top,xyz,prm)
    initial_abs=max(1.0,abs(float(terms["total_reduced_score"])))
    terminated_reason=None
    for local in range(max(0,int(cfg.steps))+1):
        step=start+local
        maxf=float(np.linalg.norm(force,axis=1).max()) if len(force) else 0.0
        row={"step":step,**terms,"max_force_reduced":maxf,"rms_speed_reduced":float(np.sqrt(np.mean(vel*vel)))}; trace.append(row)
        if local%max(1,int(cfg.save_every))==0 or local==int(cfg.steps):
            fp=out/"frames"/f"frame_{step:06d}.pdb"; _write_pdb(top.atoms,xyz,fp); frames.append(str(fp.resolve()))
        if local==int(cfg.steps): break
        if cfg.reject_if_score_explodes and (not np.isfinite(float(terms["total_reduced_score"])) or abs(float(terms["total_reduced_score"]))>float(cfg.explosion_factor)*initial_abs):
            terminated_reason="NUMERICAL_SCORE_EXPLOSION_GUARD"; break
        dt=float(cfg.dt_reduced)
        acc=force/masses; vel += 0.5*dt*acc
        vel *= max(0.0,1.0-float(cfg.damping))
        if cfg.velocity_noise>0: vel += rng.normal(0.0,float(cfg.velocity_noise),size=vel.shape)
        disp=dt*vel; disp[~movable]=0.0; vel[~movable]=0.0
        norms=np.linalg.norm(disp,axis=1); mask=norms>float(cfg.max_displacement_A)
        if mask.any(): disp[mask]*=(float(cfg.max_displacement_A)/norms[mask])[:,None]
        xyz += disp
        new_force,terms=evaluate_native_forcefield(top,xyz,prm); vel += 0.5*dt*(new_force/masses); force=new_force

    trace_path=out/"native_mechanics_v2_trace.csv"; pd.DataFrame(trace).to_csv(trace_path,index=False,encoding="utf-8-sig")
    final=out/"final_native_mechanics_v2.pdb"; _write_pdb(top.atoms,xyz,final)
    topology_json=export_native_topology(top,out/"native_topology.json")
    final_geometry=audit_peptide_geometry(final,optional_rdkit=True)
    quality=assess_native_mechanics(initial_score=float(trace[0]["total_reduced_score"]),final_score=float(trace[-1]["total_reduced_score"]),final_geometry=final_geometry)
    integ=_integrator_diagnostics(trace)
    state={"version":NATIVE_MECHANICS_V2_VERSION,"step":int(trace[-1]["step"]),"coordinates_A":xyz.tolist(),"velocities_reduced":vel.tolist(),"config":asdict(cfg),"parameters":prm.metadata(),"source_pdb":str(Path(pdb_path).resolve())}
    restart=out/"native_mechanics_v2_restart.json"; restart.write_text(json.dumps(state,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    traj=analyze_native_frames(frames,out/"native_trajectory_analysis",clusters=min(5,max(1,len(frames)))) if frames else {"status":"NO_FRAMES"}
    payload={
        "version":NATIVE_MECHANICS_V2_VERSION,"status":"COMPLETED" if terminated_reason is None else "TERMINATED_GUARD",
        "engine":"Pepforge Native Mechanics v2","evidence_grade":"EXPERIMENTAL_NATIVE_MECHANICS_NOT_PRODUCTION_MD",
        "config":asdict(cfg),"parameter_set":prm.metadata(),"topology":top.summary(),"termination_reason":terminated_reason,
        "initial_reduced_score":float(trace[0]["total_reduced_score"]),"final_reduced_score":float(trace[-1]["total_reduced_score"]),
        "integrator_diagnostics":integ,"quality_gate":quality,"final_geometry_quality":final_geometry,
        "final_pdb":str(final.resolve()),"trace_csv":str(trace_path.resolve()),"restart_state":str(restart.resolve()),"topology_json":topology_json,"frames":frames,
        "native_trajectory_analysis":traj,
        "claim_guard":"Not production MD: parameter set and reduced time mapping are not validated against a biomolecular force field. Results are mechanics/geometry evidence only; no physical time, equilibrium, ΔG, Kd, or affinity claim is permitted.",
    }
    (out/"native_mechanics_v2_summary.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return payload

__all__=["NATIVE_MECHANICS_V2_VERSION","NativeMechanicsV2Config","run_native_mechanics_v2"]
