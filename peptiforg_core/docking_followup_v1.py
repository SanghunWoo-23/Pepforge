from __future__ import annotations

"""Native post-docking follow-up for Pepforge Docking Workbench and PSB.

This module consumes the shared docking-result contract, selects a usable pose
without inventing affinity claims, and runs Pepforge Native Mechanics v2 plus
Pepforge Native Trajectory Analysis.  It is intentionally offline-capable and
keeps the mechanics result evidence grade separate from production MD.
"""

from dataclasses import asdict
from pathlib import Path
from typing import Any
import json
import pandas as pd

from .native_mechanics_v2 import NativeMechanicsV2Config, run_native_mechanics_v2

DOCKING_FOLLOWUP_VERSION = "0.1.0"


def _pose_table(normalized: dict[str, Any]) -> pd.DataFrame:
    poses = normalized.get("poses") if isinstance(normalized, dict) else None
    if not isinstance(poses, pd.DataFrame):
        return pd.DataFrame()
    return poses.copy()


def select_followup_pose(normalized: dict[str, Any], *, allow_warn: bool = True, pose_id: str | None = None) -> dict[str, Any]:
    """Select the highest-ranked usable pose from the shared docking contract.

    PASS is preferred over WARN. FAIL is never selected. Within a quality tier,
    the lower pose_rank wins.  The engine score is retained as provenance only.
    """
    poses = _pose_table(normalized)
    if poses.empty:
        raise ValueError("Shared docking result contains no poses for native follow-up.")

    allowed = {"PASS"}
    if allow_warn:
        allowed.add("WARN")
    work = poses.copy()
    work["quality_status"] = work["quality_status"].astype(str).str.upper()
    if pose_id:
        requested = str(pose_id)
        work = work[work["pose_id"].astype(str) == requested].copy()
        if work.empty:
            raise ValueError(f"Requested pose_id is not present in the shared docking result: {requested}")
    work = work[work["quality_status"].isin(allowed)].copy()
    if work.empty:
        raise ValueError("No PASS/WARN docking pose is available for native follow-up.")
    quality_order = {"PASS": 0, "WARN": 1}
    work["_quality_order"] = work["quality_status"].map(quality_order).fillna(9)
    work["_rank"] = pd.to_numeric(work.get("pose_rank"), errors="coerce").fillna(10**9)
    work = work.sort_values(["_quality_order", "_rank"], kind="stable")
    row = work.iloc[0].to_dict()
    pose_pdb = Path(str(row.get("pose_pdb") or "")).expanduser()
    if not pose_pdb.exists():
        raise FileNotFoundError(f"Selected docking pose PDB is missing: {pose_pdb}")
    row.pop("_quality_order", None)
    row.pop("_rank", None)
    row["pose_pdb"] = str(pose_pdb.resolve())
    return row


def _trajectory_rows(payload: dict[str, Any]) -> pd.DataFrame:
    traj = dict(payload.get("native_trajectory_analysis") or {})
    frame_csv = str(traj.get("frame_metrics_csv") or "")
    if frame_csv and Path(frame_csv).exists():
        try:
            df = pd.read_csv(frame_csv)
            if "frame" in df.columns:
                df["time_ps"] = ""
            df["interpretation"] = "Descriptive native-mechanics geometry frame; no physical-time or equilibrium claim."
            return df
        except Exception:
            pass
    return pd.DataFrame(columns=["frame", "rmsd_A", "rg_A", "cluster", "interpretation"])


def _summary_rows(selected: dict[str, Any], mechanics: dict[str, Any]) -> pd.DataFrame:
    traj = dict(mechanics.get("native_trajectory_analysis") or {})
    q = dict(mechanics.get("quality_gate") or {})
    tq = dict(traj.get("quality_gate") or {})
    rows = [
        {"metric": "selected_pose", "value": selected.get("pose_id", ""), "unit": "-", "interpretation": "Highest-ranked PASS pose, otherwise WARN if allowed; FAIL poses are not used."},
        {"metric": "docking_quality", "value": selected.get("quality_status", ""), "unit": "-", "interpretation": "Docking quality gate status from the shared docking result contract."},
        {"metric": "native_mechanics_status", "value": mechanics.get("status", ""), "unit": "-", "interpretation": "Pepforge Native Mechanics v2; not production MD."},
        {"metric": "mechanics_quality", "value": q.get("status", ""), "unit": "-", "interpretation": "Geometry/mechanics quality gate only."},
        {"metric": "initial_reduced_score", "value": mechanics.get("initial_reduced_score", ""), "unit": "reduced", "interpretation": "Internal reduced score; not physical energy or affinity."},
        {"metric": "final_reduced_score", "value": mechanics.get("final_reduced_score", ""), "unit": "reduced", "interpretation": "Internal reduced score; not physical energy or affinity."},
        {"metric": "trajectory_quality", "value": tq.get("status", ""), "unit": "-", "interpretation": "Descriptive trajectory-analysis quality gate."},
        {"metric": "sampled_frames", "value": traj.get("frame_count", 0), "unit": "frames", "interpretation": "Saved native-mechanics coordinate frames."},
        {"metric": "mean_rmsd", "value": traj.get("mean_rmsd_A", ""), "unit": "A", "interpretation": "Alignment-based descriptive RMSD; not convergence proof."},
        {"metric": "max_rmsd", "value": traj.get("max_rmsd_A", ""), "unit": "A", "interpretation": "Maximum sampled-frame RMSD; inspect large excursions."},
        {"metric": "mean_rg", "value": traj.get("mean_rg_A", ""), "unit": "A", "interpretation": "Radius-of-gyration descriptor."},
        {"metric": "rmsd_half_drift", "value": traj.get("first_half_vs_second_half_rmsd_drift_A", ""), "unit": "A", "interpretation": "Descriptive first-half vs second-half drift; not convergence grade."},
    ]
    return pd.DataFrame(rows)



def load_normalized_result_export(path: str | Path) -> dict[str, Any]:
    """Load a previously exported shared docking-result contract."""
    src = Path(path).expanduser().resolve()
    meta_path = src / "docking_result_contract.json" if src.is_dir() else src
    if not meta_path.exists():
        raise FileNotFoundError(meta_path)
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    base = meta_path.parent
    poses_path = Path(str(meta.get("poses_csv") or base / "docking_result_poses.csv"))
    evidence_path = Path(str(meta.get("evidence_csv") or base / "docking_result_evidence.csv"))
    if not poses_path.is_absolute():
        poses_path = (base / poses_path).resolve()
    if not evidence_path.is_absolute():
        evidence_path = (base / evidence_path).resolve()
    poses = pd.read_csv(poses_path) if poses_path.exists() else pd.DataFrame()
    evidence = pd.read_csv(evidence_path) if evidence_path.exists() else pd.DataFrame()
    return {
        "contract_version": meta.get("contract_version", ""),
        "status": meta.get("status", "UNKNOWN"),
        "engine": meta.get("engine", ""),
        "engine_version": meta.get("engine_version", ""),
        "evidence_grade": meta.get("evidence_grade", ""),
        "claim_guard": meta.get("claim_guard", ""),
        "poses": poses,
        "evidence": evidence,
    }


def run_native_docking_followup(
    normalized: dict[str, Any],
    output_dir: str | Path,
    *,
    mechanics_config: NativeMechanicsV2Config | None = None,
    allow_warn_pose: bool = True,
    pose_id: str | None = None,
) -> dict[str, Any]:
    out = Path(output_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    selected = select_followup_pose(normalized, allow_warn=allow_warn_pose, pose_id=pose_id)
    cfg = mechanics_config or NativeMechanicsV2Config(steps=400, save_every=40, freeze_receptor=True, peptide_chain="P")
    mechanics = run_native_mechanics_v2(selected["pose_pdb"], out / "mechanics", config=cfg)
    summary_df = _summary_rows(selected, mechanics)
    frames_df = _trajectory_rows(mechanics)
    summary_csv = out / "native_followup_summary.csv"
    frames_csv = out / "native_followup_frames.csv"
    summary_df.to_csv(summary_csv, index=False, encoding="utf-8-sig")
    frames_df.to_csv(frames_csv, index=False, encoding="utf-8-sig")
    payload = {
        "version": DOCKING_FOLLOWUP_VERSION,
        "status": "COMPLETED" if mechanics.get("status") in {"COMPLETED", "TERMINATED_GUARD"} else str(mechanics.get("status") or "UNKNOWN"),
        "engine": "Pepforge Native Docking Follow-up v1",
        "selected_pose": selected,
        "mechanics_config": asdict(cfg),
        "native_mechanics": mechanics,
        "summary_csv": str(summary_csv.resolve()),
        "frames_csv": str(frames_csv.resolve()),
        "claim_guard": "Native follow-up combines docking, experimental native mechanics and descriptive trajectory analysis. It is not production MD and does not imply equilibrium, physical time, DeltaG, Kd, affinity, or functional validation.",
    }
    (out / "native_followup_contract.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


__all__ = [
    "DOCKING_FOLLOWUP_VERSION",
    "select_followup_pose",
    "run_native_docking_followup",
    "load_normalized_result_export",
]
