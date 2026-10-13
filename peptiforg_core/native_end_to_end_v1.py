from __future__ import annotations

"""Pepforge native-first end-to-end offline workflow.

Sequence -> quality-preserving local structure -> Pepforge native docking ->
quality arbitration -> Pepforge native mechanics v2 -> native trajectory analysis.
No network request is made by this module.  Optional RDKit is local-only and may
be disabled; it is used only to improve/validate canonical peptide geometry.
"""

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Sequence
import json

from .quality_preserving_peptide_builder_v1 import build_quality_preserving_peptide
from .native_docking_v1 import NativeDockingConfig, run_native_docking
from .native_mechanics_v2 import NativeMechanicsV2Config, run_native_mechanics_v2
from .native_forcefield_v2 import NativeParameterSet

NATIVE_E2E_VERSION="0.1.0"

@dataclass(frozen=True)
class NativeE2EConfig:
    enable_rdkit_quality_layer: bool = True
    docking_mode: str = "blind"
    docking_poses: int = 5
    docking_anchors: int = 10
    docking_rotations: int = 14
    docking_candidates: int = 300
    mechanics_steps: int = 300
    mechanics_save_every: int = 50
    mechanics_dt_reduced: float = 0.0004
    run_mechanics_on_top_pose: bool = True
    peptide_chain: str = "P"


def _usable_pose(poses:list[dict[str,Any]])->dict[str,Any]|None:
    for row in poses:
        status=str((row.get("quality_gate") or {}).get("status") or "").upper()
        if status=="PASS": return row
    for row in poses:
        status=str((row.get("quality_gate") or {}).get("status") or "").upper()
        if status=="WARN": return row
    return None


def run_native_end_to_end(sequence:str, receptor_pdb:str|Path, output_dir:str|Path, *, config:NativeE2EConfig|None=None,
                          binding_residues:Sequence[str]|None=None)->dict[str,Any]:
    cfg=config or NativeE2EConfig(); out=Path(output_dir).expanduser().resolve(); out.mkdir(parents=True,exist_ok=True)
    seq=str(sequence or "").strip().upper()
    if not seq: raise ValueError("sequence is required")
    receptor=Path(receptor_pdb).expanduser().resolve()
    if not receptor.exists(): raise FileNotFoundError(receptor)

    builder=build_quality_preserving_peptide(seq,out/"01_peptide",chain=cfg.peptide_chain,enable_rdkit=bool(cfg.enable_rdkit_quality_layer))
    preferred=Path(builder["preferred_structure"]["pdb"])

    dock_cfg=NativeDockingConfig(mode=cfg.docking_mode,poses=int(cfg.docking_poses),anchor_count=int(cfg.docking_anchors),
                                 rotations_per_anchor=int(cfg.docking_rotations),max_candidates=int(cfg.docking_candidates))
    docking=run_native_docking(receptor,preferred,out/"02_docking",config=dock_cfg,binding_residues=binding_residues)
    chosen=_usable_pose(list(docking.get("poses") or [])) if docking.get("status")=="COMPLETED" else None
    mechanics={"status":"SKIPPED","reason":"no PASS/WARN docking pose or mechanics disabled"}
    if chosen is not None and cfg.run_mechanics_on_top_pose:
        mech_cfg=NativeMechanicsV2Config(steps=int(cfg.mechanics_steps),save_every=int(cfg.mechanics_save_every),
                                         dt_reduced=float(cfg.mechanics_dt_reduced),freeze_receptor=True,peptide_chain=cfg.peptide_chain)
        mechanics=run_native_mechanics_v2(chosen["pose_pdb"],out/"03_mechanics",config=mech_cfg,parameters=NativeParameterSet())

    status="COMPLETED" if chosen is not None else "COMPLETED_NO_USABLE_DOCKING_POSE"
    payload={
        "version":NATIVE_E2E_VERSION,"status":status,"sequence":seq,"receptor_pdb":str(receptor),"config":asdict(cfg),
        "network_policy":"NO_NETWORK_CALLS_IN_NATIVE_E2E_MODULE","peptide_builder":builder,"native_docking":docking,
        "selected_docking_pose":chosen,"native_mechanics":mechanics,
        "evidence_grade":"EXPERIMENTAL_NATIVE_END_TO_END",
        "claim_guard":"This workflow is offline/native-first research computation. Docking scores are not affinities; native mechanics is not validated production MD; trajectory descriptors do not prove equilibrium or function.",
    }
    (out/"native_end_to_end_summary.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return payload

__all__=["NATIVE_E2E_VERSION","NativeE2EConfig","run_native_end_to_end"]
