from __future__ import annotations

"""Native-core readiness aggregation for Pepforge V5.

External scientific engines are optional comparison/validation backends here.
Readiness is separated into software execution readiness and scientific
validation maturity so independent execution is never confused with validated
production MD/docking accuracy.
"""

from pathlib import Path
from typing import Any
import json, tempfile

from .native_peptide_builder_v1 import export_native_backbone
from .native_end_to_end_v1 import NativeE2EConfig, run_native_end_to_end
from .native_mechanics_validation_v1 import validate_native_mechanics, MechanicsValidationConfig

NATIVE_CORE_READINESS_VERSION="0.1.0"


def assess_native_core_readiness(output_dir:str|Path, *, run_self_smoke:bool=True)->dict[str,Any]:
    out=Path(output_dir).expanduser().resolve(); out.mkdir(parents=True,exist_ok=True)
    components={}
    imports=[
        ("native_peptide_builder","peptiforg_core.native_peptide_builder_v1"),
        ("native_topology","peptiforg_core.native_topology_v1"),
        ("native_forcefield","peptiforg_core.native_forcefield_v2"),
        ("native_mechanics","peptiforg_core.native_mechanics_v2"),
        ("native_docking","peptiforg_core.native_docking_v1"),
        ("native_trajectory","peptiforg_core.native_trajectory_analysis_v1"),
        ("quality_gate","peptiforg_core.native_quality_gate_v1"),
        ("quality_arbitration","peptiforg_core.quality_arbitration_v1"),
        ("native_docking_benchmark","peptiforg_core.native_docking_benchmark_v1"),
        ("native_mechanics_validation","peptiforg_core.native_mechanics_validation_v1"),
        ("native_validation_suite","peptiforg_core.native_validation_suite_v1"),
    ]
    import importlib
    for name,mod in imports:
        try:
            importlib.import_module(mod); components[name]="READY"
        except Exception as exc:
            components[name]=f"FAILED: {exc}"

    smoke={"status":"NOT_RUN"}
    if run_self_smoke and all(v=="READY" for v in components.values()):
        try:
            work=out/"self_smoke"; rec=export_native_backbone("AAAAAAAAAA",work/"receptor",chain="A")["pdb"]
            cfg=NativeE2EConfig(enable_rdkit_quality_layer=False,docking_poses=2,docking_anchors=3,docking_rotations=4,docking_candidates=20,mechanics_steps=4,mechanics_save_every=2)
            run=run_native_end_to_end("EEMQRR",rec,work/"run",config=cfg)
            mech_input=(run.get("native_mechanics") or {}).get("final_pdb") or rec
            mech_validation=validate_native_mechanics(mech_input,work/"mechanics_validation",config=MechanicsValidationConfig(integration_steps=6,max_coordinates=18))
            workflow_ok=run.get("status") in {"COMPLETED","COMPLETED_NO_USABLE_DOCKING_POSE"}
            smoke={
                "status":"PASS" if workflow_ok and mech_validation.get("status")=="PASS" else "FAIL",
                "workflow_status":run.get("status"),
                "docking_status":(run.get("native_docking") or {}).get("status"),
                "mechanics_status":(run.get("native_mechanics") or {}).get("status"),
                "mechanics_numerical_validation":mech_validation.get("status"),
                "network_policy":run.get("network_policy"),
            }
        except Exception as exc:
            smoke={"status":"FAIL","reason":str(exc)}

    software_ready=all(v=="READY" for v in components.values()) and smoke.get("status") in {"PASS","NOT_RUN"}
    overall="NATIVE_CORE_SOFTWARE_READY_RESEARCH_VALIDATION_PENDING" if software_ready else "NATIVE_CORE_NOT_READY"
    blockers=[]
    if not software_ready:
        blockers.append("native component import/self-smoke failure")
    blockers += [
        "Native mechanics numerical self-consistency is checked, but parameterization/timestep mapping is not externally benchmark-validated as production molecular dynamics.",
        "Native docking search/scoring requires external benchmark sets before accuracy claims.",
        "Modified/noncanonical chemistry requires validated parameter/topology provenance before native mechanics promotion.",
        "AI ranker requires explicitly labelled external validation before production promotion.",
    ]
    payload={
        "version":NATIVE_CORE_READINESS_VERSION,"overall_status":overall,"components":components,"self_smoke":smoke,
        "external_engine_policy":"HADDOCK3/OpenMM/RDKit/MDTraj/AF3/ESMFold are optional comparison, quality-enhancement, or validation resources; the native core software path does not require them.",
        "remaining_scientific_validation":blockers,
        "claim_guard":"Software-independent execution is not equivalent to validated scientific accuracy. Native docking remains experimental and native mechanics is not production MD until benchmark validation supports promotion.",
    }
    (out/"NATIVE_CORE_READINESS.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    lines=["# Pepforge V5 Native Core Readiness","",f"Overall: **{overall}**","","## Components"]
    lines += [f"- {k}: {v}" for k,v in components.items()]
    lines += ["",f"Self-smoke: **{smoke.get('status')}**","","## Remaining scientific validation"]
    lines += [f"- {x}" for x in blockers]
    lines += ["","## Claim boundary",payload["claim_guard"],""]
    (out/"NATIVE_CORE_READINESS.md").write_text("\n".join(lines),encoding="utf-8")
    return payload

__all__=["NATIVE_CORE_READINESS_VERSION","assess_native_core_readiness"]
