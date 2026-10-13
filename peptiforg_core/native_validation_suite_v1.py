from __future__ import annotations

"""Aggregate external/reference validation evidence for Pepforge Native Core.

The module intentionally distinguishes:
- software/numerical self-consistency, and
- external structural benchmark evidence.
No threshold in this module is presented as an experimental validation standard.
"""

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable
import json
import numpy as np
import pandas as pd

NATIVE_VALIDATION_SUITE_VERSION="0.1.0"

@dataclass(frozen=True)
class NativePromotionPolicy:
    min_docking_targets:int=20
    min_targets_with_ranked_poses:int=10
    min_top5_acceptable_rate:float=0.50
    require_mechanics_numerical_pass:bool=True
    note:str="Pepforge project promotion policy; configurable engineering criterion, not a CAPRI or experimental standard."


def _acceptable(dockq: Any) -> bool:
    try: return float(dockq) >= 0.23
    except Exception: return False


def aggregate_validation_evidence(benchmark_jsons: Iterable[str|Path], output_dir: str|Path, *, mechanics_validation_json: str|Path|None=None, policy: NativePromotionPolicy|None=None) -> dict[str,Any]:
    pol=policy or NativePromotionPolicy(); out=Path(output_dir).expanduser().resolve(); out.mkdir(parents=True,exist_ok=True)
    rows=[]; errors=[]
    for path in benchmark_jsons:
        p=Path(path)
        try:
            d=json.loads(p.read_text(encoding="utf-8"))
            rows.append({
                "target":p.parent.name,
                "source":str(p.resolve()),
                "models_evaluated":d.get("models_evaluated"),
                "best_dockq":d.get("best_dockq_compatible"),
                "top1_dockq":d.get("top1_by_internal_score_dockq"),
                "top5_best_dockq":d.get("best_top5_by_internal_score_dockq"),
                "score_dockq_spearman":d.get("score_dockq_spearman"),
            })
        except Exception as exc: errors.append({"source":str(p),"error":str(exc)})
    df=pd.DataFrame(rows)
    csv_path=out/"native_validation_targets.csv"; df.to_csv(csv_path,index=False,encoding="utf-8-sig")
    n=int(len(df)); ranked=int(df["top1_dockq"].notna().sum()) if not df.empty and "top1_dockq" in df else 0
    top1_rate=float(df["top1_dockq"].dropna().map(_acceptable).mean()) if ranked else None
    top5_series=df["top5_best_dockq"].dropna() if not df.empty and "top5_best_dockq" in df else pd.Series(dtype=float)
    top5_rate=float(top5_series.map(_acceptable).mean()) if len(top5_series) else None
    median_best=float(df["best_dockq"].dropna().median()) if not df.empty and df["best_dockq"].notna().any() else None
    corr=float(df["score_dockq_spearman"].dropna().median()) if not df.empty and "score_dockq_spearman" in df and df["score_dockq_spearman"].notna().any() else None

    mech=None; mech_pass=False
    if mechanics_validation_json:
        try:
            mech=json.loads(Path(mechanics_validation_json).read_text(encoding="utf-8")); mech_pass=mech.get("status")=="PASS"
        except Exception as exc: errors.append({"source":str(mechanics_validation_json),"error":str(exc)})

    data_sufficient=n>=pol.min_docking_targets and ranked>=pol.min_targets_with_ranked_poses
    docking_policy_pass=bool(data_sufficient and top5_rate is not None and top5_rate>=pol.min_top5_acceptable_rate)
    mechanics_policy_pass=bool(mech_pass or not pol.require_mechanics_numerical_pass)
    if n==0:
        status="VALIDATION_HARNESS_READY_EXTERNAL_DATA_PENDING"
    elif not data_sufficient:
        status="EXTERNAL_BENCHMARK_INCOMPLETE"
    elif docking_policy_pass and mechanics_policy_pass:
        status="PROJECT_PROMOTION_GATE_PASS_RESEARCH_VALIDATION_ONLY"
    else:
        status="PROJECT_PROMOTION_GATE_NOT_MET"
    payload={
        "version":NATIVE_VALIDATION_SUITE_VERSION,"status":status,"policy":asdict(pol),
        "docking":{"targets":n,"targets_with_ranked_poses":ranked,"top1_acceptable_or_better_rate":top1_rate,"top5_acceptable_or_better_rate":top5_rate,"median_best_dockq":median_best,"median_score_dockq_spearman":corr,"policy_pass":docking_policy_pass},
        "mechanics":{"validation_provided":mech is not None,"numerical_validation_pass":mech_pass,"policy_pass":mechanics_policy_pass},
        "errors":errors,"targets_csv":str(csv_path.resolve()),
        "claim_guard":"This is an engineering promotion gate over reference-structure benchmarks. Passing it does not establish experimental affinity accuracy, physical MD validity, or broad biological generalization.",
    }
    j=out/"native_validation_suite.json"; j.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    lines=["# Pepforge Native Validation Suite","",f"Status: **{status}**","",f"Docking targets: {n}",f"Targets with ranked poses: {ranked}",f"Top-1 acceptable-or-better rate: {top1_rate}",f"Top-5 acceptable-or-better rate: {top5_rate}",f"Median best DockQ-compatible score: {median_best}",f"Mechanics numerical validation: {'PASS' if mech_pass else 'NOT PASS / NOT PROVIDED'}","","## Boundary",payload["claim_guard"],""]
    (out/"NATIVE_VALIDATION_SUITE.md").write_text("\n".join(lines),encoding="utf-8")
    return payload


def discover_benchmark_summaries(root: str|Path) -> list[str]:
    return [str(p) for p in sorted(Path(root).rglob("native_docking_reference_benchmark.json"))]

__all__=["NATIVE_VALIDATION_SUITE_VERSION","NativePromotionPolicy","aggregate_validation_evidence","discover_benchmark_summaries"]
