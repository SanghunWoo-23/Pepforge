from __future__ import annotations

"""Deterministic interpretation layer for Pepforge native result contracts.

This module summarizes what a docking/follow-up result supports and what it does
not support. It never upgrades native scores to affinity/DeltaG/Kd claims.
"""

from pathlib import Path
from typing import Any
import json

NATIVE_RESULT_INTERPRETATION_VERSION = "0.1.0"


def _records(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if hasattr(value, "to_dict"):
        try:
            return [dict(x) for x in value.to_dict(orient="records")]
        except Exception:
            return []
    if isinstance(value, list):
        return [dict(x) for x in value if isinstance(x, dict)]
    return []


def interpret_native_result(normalized: dict[str, Any] | None, followups: list[dict[str, Any]] | None = None, *, selected_pose_id: str = "") -> dict[str, Any]:
    normalized = dict(normalized or {})
    followups = [dict(x) for x in (followups or []) if isinstance(x, dict)]
    poses = _records(normalized.get("poses"))
    evidence = _records(normalized.get("evidence"))
    selected = None
    if selected_pose_id:
        selected = next((p for p in poses if str(p.get("pose_id") or "") == selected_pose_id), None)
    if selected is None and poses:
        selected = min(poses, key=lambda p: int(p.get("pose_rank") or 999999))
    pid = str((selected or {}).get("pose_id") or selected_pose_id or "")
    ev = [e for e in evidence if not pid or str(e.get("pose_id") or "") == pid]

    interaction_counts: dict[str, int] = {}
    for row in ev:
        key = str(row.get("interaction") or "unknown")
        interaction_counts[key] = interaction_counts.get(key, 0) + 1

    warnings: list[str] = []
    strengths: list[str] = []
    next_actions: list[str] = []
    quality = str((selected or {}).get("quality_status") or "UNKNOWN").upper()
    clashes = int((selected or {}).get("clash_count") or 0)
    contacts = int((selected or {}).get("contact_count") or len(ev) or 0)

    if quality == "PASS":
        strengths.append("Selected pose passed the docking quality gate.")
    elif quality == "WARN":
        warnings.append("Selected pose is WARN; inspect clashes, contact geometry, and alternative poses before follow-up.")
    elif quality == "FAIL":
        warnings.append("Selected pose failed the docking quality gate and should not be promoted as verified downstream evidence.")
        next_actions.append("Select or regenerate a PASS/WARN pose before native mechanics follow-up.")
    else:
        warnings.append("Selected pose quality status is unavailable or undeclared.")

    if clashes > 0:
        warnings.append(f"Selected pose reports {clashes} clash(es); inspect geometry before interpretation.")
    if contacts == 0:
        warnings.append("No interaction/contact evidence is recorded for the selected pose.")
    elif contacts >= 3:
        strengths.append(f"Selected pose has {contacts} recorded contact/evidence rows for structural review.")

    follow = None
    for item in followups:
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else item
        sp = payload.get("selected_pose") or item.get("selected_pose") or {}
        fpid = str(sp.get("pose_id") or "")
        model = item.get("model_rank")
        if model and fpid and not fpid.startswith(f"m{int(model):02d}_"):
            fpid = f"m{int(model):02d}_{fpid}"
        if not pid or fpid == pid:
            follow = item
            break
    if follow:
        payload = follow.get("payload") if isinstance(follow.get("payload"), dict) else follow
        mech = payload.get("native_mechanics") or {}
        traj = mech.get("native_trajectory_analysis") or payload.get("native_trajectory_analysis") or {}
        mq = str(((mech.get("quality_gate") or {}).get("status") or "UNKNOWN")).upper()
        tq = str(((traj.get("quality_gate") or {}).get("status") or "UNKNOWN")).upper()
        if mq == "PASS": strengths.append("Native mechanics numerical/geometry quality gate passed for this follow-up record.")
        if mq in {"WARN", "FAIL"}: warnings.append(f"Native mechanics quality gate is {mq}; do not over-interpret trajectory behavior.")
        if tq in {"WARN", "FAIL"}: warnings.append(f"Trajectory analysis quality gate is {tq}; inspect drift/clustering diagnostics.")
        if traj.get("frame_count"):
            strengths.append(f"Trajectory analysis contains {traj.get('frame_count')} saved frame(s).")
    else:
        next_actions.append("Run Native Mechanics/Trajectory follow-up if conformational follow-up is needed.")

    if len(poses) > 1:
        next_actions.append("Compare top poses with ligand RMSD/contact Jaccard before choosing one pose for follow-up.")
    if quality != "FAIL" and not warnings:
        next_actions.append("Use external/reference benchmark or experiment for claims beyond structural-search evidence.")

    support = [
        "Relative structural-search evidence among generated poses.",
        "Geometry-based interaction review for recorded contacts.",
    ]
    if follow:
        support.append("Descriptive native-mechanics/trajectory behavior within Pepforge's experimental reduced model.")

    not_supported = [
        "Measured binding affinity, DeltaG, or Kd.",
        "Functional or biological validation.",
        "Production molecular-dynamics validity or thermodynamic ensemble claims.",
        "Experimental structure equivalence unless independently benchmarked.",
    ]

    return {
        "version": NATIVE_RESULT_INTERPRETATION_VERSION,
        "pose_id": pid,
        "pose_rank": (selected or {}).get("pose_rank"),
        "engine_score": (selected or {}).get("engine_score"),
        "quality_status": quality,
        "contact_count": contacts,
        "clash_count": clashes,
        "interaction_counts": interaction_counts,
        "strengths": strengths,
        "warnings": warnings,
        "next_actions": next_actions,
        "supported_interpretation": support,
        "not_supported": not_supported,
        "claim_guard": normalized.get("claim_guard") or "Native docking/trajectory output is research structural evidence, not measured affinity or production MD.",
    }


def export_native_result_interpretation(normalized: dict[str, Any] | None, followups: list[dict[str, Any]] | None, output_dir: str | Path, *, selected_pose_id: str = "") -> dict[str, str]:
    out = Path(output_dir).expanduser().resolve(); out.mkdir(parents=True, exist_ok=True)
    data = interpret_native_result(normalized, followups, selected_pose_id=selected_pose_id)
    jp = out / "native_result_interpretation.json"
    mp = out / "NATIVE_RESULT_INTERPRETATION.md"
    jp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# Pepforge Native Result Interpretation", "", f"Selected pose: **{data['pose_id'] or '-'}**", f"Quality: **{data['quality_status']}**", "", "## Supported interpretation"]
    lines += [f"- {x}" for x in data["supported_interpretation"]]
    lines += ["", "## Strengths"] + ([f"- {x}" for x in data["strengths"]] or ["- None recorded."])
    lines += ["", "## Warnings"] + ([f"- {x}" for x in data["warnings"]] or ["- None recorded."])
    lines += ["", "## Recommended next actions"] + ([f"- {x}" for x in data["next_actions"]] or ["- No additional action generated."])
    lines += ["", "## Not supported by this result"] + [f"- {x}" for x in data["not_supported"]]
    lines += ["", "## Claim guard", str(data["claim_guard"]), ""]
    mp.write_text("\n".join(lines), encoding="utf-8")
    return {"json": str(jp), "markdown": str(mp)}


__all__ = ["NATIVE_RESULT_INTERPRETATION_VERSION", "interpret_native_result", "export_native_result_interpretation"]
