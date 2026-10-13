from __future__ import annotations

"""Numerical validation harness for Pepforge Native Mechanics.

The checks here test implementation consistency and numerical boundedness.  They
are deliberately separated from physical force-field validation.
"""

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
import json
import numpy as np

from .native_topology_v1 import build_native_topology
from .native_forcefield_v2 import NativeParameterSet, evaluate_native_forcefield
from .native_mechanics_v2 import NativeMechanicsV2Config, run_native_mechanics_v2

NATIVE_MECHANICS_VALIDATION_VERSION = "0.1.0"


@dataclass(frozen=True)
class MechanicsValidationConfig:
    finite_difference_h_A: float = 1e-5
    max_coordinates: int = 48
    force_abs_tolerance: float = 2e-4
    force_rel_tolerance: float = 2e-4
    integration_steps: int = 40
    integration_dt_reduced: float = 0.0003
    max_score_ratio: float = 25.0


def finite_difference_force_check(pdb_path: str|Path, *, parameters: NativeParameterSet|None=None, config: MechanicsValidationConfig|None=None) -> dict[str, Any]:
    cfg=config or MechanicsValidationConfig(); prm=parameters or NativeParameterSet(); top=build_native_topology(pdb_path)
    xyz=top.coordinates_A.copy(); force,terms=evaluate_native_forcefield(top,xyz,prm)
    h=float(cfg.finite_difference_h_A); checks=[]
    flat=[(i,k) for i in range(len(xyz)) for k in range(3)][:max(1,int(cfg.max_coordinates))]
    for i,k in flat:
        xp=xyz.copy(); xm=xyz.copy(); xp[i,k]+=h; xm[i,k]-=h
        ep=evaluate_native_forcefield(top,xp,prm)[1]["total_reduced_score"]
        em=evaluate_native_forcefield(top,xm,prm)[1]["total_reduced_score"]
        numerical=-(float(ep)-float(em))/(2*h); analytic=float(force[i,k])
        abs_err=abs(analytic-numerical); scale=max(1.0,abs(analytic),abs(numerical)); rel_err=abs_err/scale
        checks.append((abs_err,rel_err,analytic,numerical,i,k))
    max_abs=max(x[0] for x in checks) if checks else float("inf")
    max_rel=max(x[1] for x in checks) if checks else float("inf")
    passed=bool(max_abs<=cfg.force_abs_tolerance or max_rel<=cfg.force_rel_tolerance)
    return {
        "status":"PASS" if passed else "FAIL",
        "coordinates_checked":len(checks),
        "max_abs_force_error":float(max_abs),
        "max_rel_force_error":float(max_rel),
        "tolerances":{"absolute":cfg.force_abs_tolerance,"relative":cfg.force_rel_tolerance},
        "initial_terms":terms,
        "note":"Checks force == negative numerical gradient of the Pepforge reduced score. It is an implementation-consistency test, not physical force-field validation.",
    }


def parameter_sensitivity_check(pdb_path: str|Path, *, parameters: NativeParameterSet|None=None) -> dict[str, Any]:
    prm=parameters or NativeParameterSet(); top=build_native_topology(pdb_path); x=top.coordinates_A.copy()
    base=evaluate_native_forcefield(top,x,prm)[1]
    variants={
        "bond_k_x0.8": NativeParameterSet(**{**asdict(prm),"bond_k":prm.bond_k*0.8}),
        "angle_k_x1.2": NativeParameterSet(**{**asdict(prm),"angle_k":prm.angle_k*1.2}),
        "lj_scale_x0.8": NativeParameterSet(**{**asdict(prm),"lj_scale":prm.lj_scale*0.8}),
        "dielectric_x1.2": NativeParameterSet(**{**asdict(prm),"dielectric":prm.dielectric*1.2}),
    }
    vals={}
    for name,p in variants.items(): vals[name]=evaluate_native_forcefield(top,x,p)[1]["total_reduced_score"]
    finite=all(np.isfinite(v) for v in vals.values())
    return {"status":"PASS" if finite else "FAIL","base_total_reduced_score":float(base["total_reduced_score"]),"variants":{k:float(v) for k,v in vals.items()},"note":"Sensitivity audit only; no parameter set is promoted as physically calibrated by this test."}


def validate_native_mechanics(pdb_path: str|Path, output_dir: str|Path, *, parameters: NativeParameterSet|None=None, config: MechanicsValidationConfig|None=None) -> dict[str, Any]:
    cfg=config or MechanicsValidationConfig(); prm=parameters or NativeParameterSet(); out=Path(output_dir).expanduser().resolve(); out.mkdir(parents=True,exist_ok=True)
    fd=finite_difference_force_check(pdb_path,parameters=prm,config=cfg)
    sens=parameter_sensitivity_check(pdb_path,parameters=prm)
    run=run_native_mechanics_v2(pdb_path,out/"integration_smoke",config=NativeMechanicsV2Config(steps=cfg.integration_steps,dt_reduced=cfg.integration_dt_reduced,damping=0.02,save_every=max(1,cfg.integration_steps//4)),parameters=prm)
    integ=run.get("integrator_diagnostics",{})
    bounded=bool(integ.get("finite")) and float(integ.get("max_abs_score_ratio_to_initial",float("inf"))) <= float(cfg.max_score_ratio)
    status="PASS" if fd["status"]=="PASS" and sens["status"]=="PASS" and bounded and run.get("status")=="COMPLETED" else "FAIL"
    payload={
        "version":NATIVE_MECHANICS_VALIDATION_VERSION,"status":status,"config":asdict(cfg),"parameter_set":prm.metadata(),
        "finite_difference_force_check":fd,"parameter_sensitivity":sens,"integration_smoke":{
            "status":run.get("status"),"integrator_diagnostics":integ,"quality_gate":run.get("quality_gate"),"termination_reason":run.get("termination_reason")},
        "validation_scope":"SOFTWARE_NUMERICAL_CONSISTENCY_ONLY",
        "remaining_for_production_md":"Independent biomolecular parameter calibration/validation, physical unit and timestep mapping, ensemble/thermostat validation, and benchmark comparison against experimental/reference simulations.",
        "claim_guard":"PASS means Pepforge's implemented reduced-score forces and integrator are numerically self-consistent under this test; it does not make the engine production molecular dynamics.",
    }
    (out/"native_mechanics_validation.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return payload


__all__=["NATIVE_MECHANICS_VALIDATION_VERSION","MechanicsValidationConfig","finite_difference_force_check","parameter_sensitivity_check","validate_native_mechanics"]
