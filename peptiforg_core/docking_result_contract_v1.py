from __future__ import annotations

"""Shared docking-result normalization for Pepforge PSB and Docking Workbench.

The contract deliberately separates *engine-native* output from the user-facing
comparison tables.  A docking engine may expose its own score and artifacts, but
all engines are normalized into the same provenance/pose/evidence structure.
No normalized field is allowed to imply measured affinity, DeltaG, or Kd.
"""

from pathlib import Path
from typing import Any, Iterable
import json
import re
import pandas as pd

DOCKING_RESULT_CONTRACT_VERSION = "1.0.0"

POSE_COLUMNS = [
    "pose_rank", "pose_id", "engine", "engine_version", "evidence_grade",
    "engine_score", "score_name", "score_direction", "quality_status",
    "contact_count", "clash_count", "min_distance_A", "pose_pdb",
    "interaction_evidence_csv", "claim_guard",
]

EVIDENCE_COLUMNS = [
    "pose_rank", "pose_id", "interaction", "target_residue", "peptide_residue",
    "target_atoms", "peptide_atoms", "distance_A", "angle_deg", "plane_angle_deg",
    "offset_A", "vdw_overlap_A", "geometry_status", "evidence_level", "note",
]


def _safe_number(value: Any, default: float | int | None = None):
    try:
        return float(value)
    except Exception:
        return default


def _read_evidence(path: str | Path | None, *, rank: int, pose_id: str) -> pd.DataFrame:
    if not path:
        return pd.DataFrame(columns=EVIDENCE_COLUMNS)
    p = Path(path)
    if not p.exists():
        return pd.DataFrame(columns=EVIDENCE_COLUMNS)
    try:
        frame = pd.read_csv(p)
    except Exception:
        return pd.DataFrame(columns=EVIDENCE_COLUMNS)
    frame = frame.copy()
    frame.insert(0, "pose_id", pose_id)
    frame.insert(0, "pose_rank", int(rank))
    for col in EVIDENCE_COLUMNS:
        if col not in frame.columns:
            frame[col] = ""
    return frame[EVIDENCE_COLUMNS]


def normalize_native_docking_result(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize Pepforge Native Docking output into the shared contract."""
    rows: list[dict[str, Any]] = []
    evidence_frames: list[pd.DataFrame] = []
    engine = str(payload.get("engine") or "Pepforge Native Docking")
    version = str(payload.get("version") or "")
    grade = str(payload.get("evidence_grade") or "EXPERIMENTAL_NATIVE")
    guard = str(payload.get("claim_guard") or "Docking search output is not measured affinity.")
    for raw in payload.get("poses") or []:
        rank = int(raw.get("rank") or len(rows) + 1)
        pose_id = f"native_pose_{rank:02d}"
        q = dict(raw.get("quality_gate") or {})
        rows.append({
            "pose_rank": rank,
            "pose_id": pose_id,
            "engine": engine,
            "engine_version": version,
            "evidence_grade": grade,
            "engine_score": _safe_number(raw.get("pepforge_native_score")),
            "score_name": "Pepforge Native Docking Score",
            "score_direction": "lower_is_better_within_same_run",
            "quality_status": str(q.get("status") or "WARN"),
            "contact_count": int(raw.get("contact_count") or 0),
            "clash_count": int(raw.get("clash_count") or 0),
            "min_distance_A": _safe_number(raw.get("min_distance_A")),
            "pose_pdb": str(raw.get("pose_pdb") or ""),
            "interaction_evidence_csv": str(raw.get("interaction_evidence_csv") or ""),
            "claim_guard": guard,
        })
        evidence_frames.append(_read_evidence(raw.get("interaction_evidence_csv"), rank=rank, pose_id=pose_id))
    poses = pd.DataFrame(rows, columns=POSE_COLUMNS)
    nonempty_evidence = [df for df in evidence_frames if isinstance(df, pd.DataFrame) and not df.empty]
    evidence = pd.concat(nonempty_evidence, ignore_index=True) if nonempty_evidence else pd.DataFrame(columns=EVIDENCE_COLUMNS)
    return {
        "contract_version": DOCKING_RESULT_CONTRACT_VERSION,
        "status": str(payload.get("status") or "UNKNOWN"),
        "engine": engine,
        "engine_version": version,
        "evidence_grade": grade,
        "poses": poses,
        "evidence": evidence,
        "claim_guard": guard,
        "raw": payload,
    }


def evidence_to_workbench_contacts(evidence: pd.DataFrame) -> pd.DataFrame:
    """Map geometry-aware interaction evidence onto Workbench contact columns.

    This adapter is intentionally lossy only in the display direction.  The full
    evidence table remains exported separately and retains angles/offsets/levels.
    """
    columns = [
        "protein_residue", "peptide_residue", "distance_A", "interaction",
        "protein_window", "peptide_window", "orientation", "pose_id",
        "target_residue", "pep_pos", "pep_aa", "target_chain", "target_resi", "target_aa",
        "cutoff_A", "note",
    ]
    if evidence is None or evidence.empty:
        return pd.DataFrame(columns=columns)

    def split_label(label: Any) -> tuple[str, str, str]:
        text = str(label or "")
        m = re.match(r"(?:(?P<chain>[^:]+):)?(?P<resi>-?\d+[A-Za-z]?)(?P<resn>[A-Za-z0-9]+)$", text)
        if not m:
            return "", "", ""
        return m.group("chain") or "", m.group("resi") or "", m.group("resn") or ""

    rows: list[dict[str, Any]] = []
    cutoff_map = {
        "hydrogen_bond": 3.5, "hydrophobic": 5.0, "salt_bridge": 4.0,
        "pi_pi": 5.0, "cation_pi": 5.0, "van_der_Waals": "vdW",
        "weak_C_H_O_N": 3.5,
    }
    for _, r in evidence.iterrows():
        target = str(r.get("target_residue") or "")
        pep = str(r.get("peptide_residue") or "")
        tc, tr, tresn = split_label(target)
        _, pr, presn = split_label(pep)
        rows.append({
            "protein_residue": target,
            "peptide_residue": pep,
            "distance_A": r.get("distance_A", ""),
            "interaction": str(r.get("interaction") or "contact"),
            "protein_window": "",
            "peptide_window": "",
            "orientation": "native_rigid_body",
            "pose_id": str(r.get("pose_id") or ""),
            "target_residue": target,
            "pep_pos": pr,
            "pep_aa": presn,
            "target_chain": tc,
            "target_resi": tr,
            "target_aa": tresn,
            "cutoff_A": cutoff_map.get(str(r.get("interaction") or ""), ""),
            "note": f"{r.get('geometry_status','')}; evidence={r.get('evidence_level','')}; {r.get('note','')}",
        })
    return pd.DataFrame(rows, columns=columns)


def normalized_to_workbench_poses(normalized: dict[str, Any]) -> pd.DataFrame:
    """Convert shared contract poses to the legacy Workbench comparison schema."""
    columns = [
        "pose_rank", "pose_id", "conformation", "orientation", "contact_count",
        "centroid_overlap_warnings", "hydrophobic_proximities", "opposite_charge_proximities",
        "aromatic_proximities", "polar_residue_proximities", "min_centroid_distance_A",
        "rotation_z_deg", "translation_x_A", "translation_y_A", "translation_z_A",
        "center_x_A", "center_y_A", "center_z_A",
        "engine", "engine_score", "quality_status", "note",
    ]
    poses = normalized.get("poses")
    ev = normalized.get("evidence")
    if not isinstance(poses, pd.DataFrame) or poses.empty:
        return pd.DataFrame(columns=columns)
    ev = ev if isinstance(ev, pd.DataFrame) else pd.DataFrame()
    rows=[]
    for _, p in poses.iterrows():
        pid = str(p.get("pose_id") or "")
        e = ev[ev["pose_id"].astype(str).eq(pid)] if not ev.empty and "pose_id" in ev.columns else pd.DataFrame()
        inter = e.get("interaction", pd.Series(dtype=str)).astype(str) if not e.empty else pd.Series(dtype=str)
        rows.append({
            "pose_rank": int(p.get("pose_rank") or len(rows)+1),
            "pose_id": pid,
            "conformation": "pepforge_native_docking",
            "orientation": "native_rigid_body",
            "contact_count": int(p.get("contact_count") or len(e)),
            "centroid_overlap_warnings": int(p.get("clash_count") or 0),
            "hydrophobic_proximities": int((inter == "hydrophobic").sum()),
            "opposite_charge_proximities": int((inter == "salt_bridge").sum()),
            "aromatic_proximities": int(inter.isin(["pi_pi", "cation_pi"]).sum()),
            "polar_residue_proximities": int((inter == "hydrogen_bond").sum()),
            "min_centroid_distance_A": p.get("min_distance_A", ""),
            "rotation_z_deg": "",
            "translation_x_A": "", "translation_y_A": "", "translation_z_A": "",
            "center_x_A": "", "center_y_A": "", "center_z_A": "",
            "engine": p.get("engine", ""),
            "engine_score": p.get("engine_score", ""),
            "quality_status": p.get("quality_status", ""),
            "note": f"{p.get('engine','')} score={p.get('engine_score','')}; quality={p.get('quality_status','')}; score is not affinity.",
        })
    return pd.DataFrame(rows, columns=columns)


def write_atoms_as_pdb(atoms: pd.DataFrame, path: str | Path, *, default_chain: str = "A") -> str:
    """Write a normalized atom frame to PDB without using an external chemistry engine."""
    out = Path(path); out.parent.mkdir(parents=True, exist_ok=True)
    if atoms is None or atoms.empty:
        raise ValueError("Cannot write an empty atom frame as PDB.")
    lines = ["REMARK 949 PEPFORGE NORMALIZED COORDINATE INPUT"]
    serial = 1
    for _, r in atoms.iterrows():
        record = str(r.get("record") or "ATOM").upper()
        if record not in {"ATOM", "HETATM"}: record = "ATOM"
        atom = str(r.get("atom") or "X")[:4]
        resn = str(r.get("resn") or "UNK")[:3].upper()
        chain = (str(r.get("chain") or default_chain).strip() or default_chain)[:1]
        try: resi = int(float(r.get("resi") or 1))
        except Exception: resi = 1
        x, y, z = (float(r.get(c) or 0.0) for c in ("x","y","z"))
        elem = str(r.get("element") or atom[:1] or "C").strip().upper()[:2]
        lines.append(f"{record:<6}{serial:5d} {atom:>4s} {resn:>3s} {chain}{resi:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00          {elem:>2s}")
        serial += 1
    lines += ["TER", "END"]
    out.write_text("\n".join(lines)+"\n", encoding="utf-8")
    return str(out.resolve())


def export_normalized_result(normalized: dict[str, Any], output_dir: str | Path) -> dict[str, str]:
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    poses = normalized.get("poses") if isinstance(normalized.get("poses"), pd.DataFrame) else pd.DataFrame(columns=POSE_COLUMNS)
    evidence = normalized.get("evidence") if isinstance(normalized.get("evidence"), pd.DataFrame) else pd.DataFrame(columns=EVIDENCE_COLUMNS)
    poses_path = out / "docking_result_poses.csv"
    ev_path = out / "docking_result_evidence.csv"
    meta_path = out / "docking_result_contract.json"
    poses.to_csv(poses_path, index=False, encoding="utf-8-sig")
    evidence.to_csv(ev_path, index=False, encoding="utf-8-sig")
    meta = {
        "contract_version": normalized.get("contract_version", DOCKING_RESULT_CONTRACT_VERSION),
        "status": normalized.get("status"), "engine": normalized.get("engine"),
        "engine_version": normalized.get("engine_version"), "evidence_grade": normalized.get("evidence_grade"),
        "pose_count": int(len(poses)), "evidence_row_count": int(len(evidence)),
        "claim_guard": normalized.get("claim_guard"),
        "poses_csv": str(poses_path.resolve()), "evidence_csv": str(ev_path.resolve()),
    }
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    return {"poses_csv": str(poses_path.resolve()), "evidence_csv": str(ev_path.resolve()), "contract_json": str(meta_path.resolve())}


def combine_normalized_results(items: Iterable[tuple[int, dict[str, Any]]]) -> dict[str, Any]:
    """Combine per-model normalized docking results for shared PSB/Workbench viewing.

    Pose identifiers are prefixed with the PSB model rank so repeated per-model
    identifiers remain unique.  Scores are preserved exactly as engine-native
    values and are never pooled into an affinity-like quantity.
    """
    pose_frames: list[pd.DataFrame] = []
    evidence_frames: list[pd.DataFrame] = []
    engines: list[str] = []
    grades: list[str] = []
    guards: list[str] = []
    statuses: list[str] = []
    version = DOCKING_RESULT_CONTRACT_VERSION
    for model_rank, normalized in items:
        if not isinstance(normalized, dict):
            continue
        version = str(normalized.get("contract_version") or version)
        statuses.append(str(normalized.get("status") or "UNKNOWN"))
        engines.append(str(normalized.get("engine") or ""))
        grades.append(str(normalized.get("evidence_grade") or ""))
        guards.append(str(normalized.get("claim_guard") or ""))
        poses = normalized.get("poses")
        if isinstance(poses, pd.DataFrame) and not poses.empty:
            frame = poses.copy()
            frame.insert(0, "model_rank", int(model_rank))
            frame["pose_id"] = frame["pose_id"].astype(str).map(lambda x: f"m{int(model_rank):02d}_{x}")
            pose_frames.append(frame)
        evidence = normalized.get("evidence")
        if isinstance(evidence, pd.DataFrame) and not evidence.empty:
            frame = evidence.copy()
            frame.insert(0, "model_rank", int(model_rank))
            frame["pose_id"] = frame["pose_id"].astype(str).map(lambda x: f"m{int(model_rank):02d}_{x}")
            evidence_frames.append(frame)
    poses = pd.concat(pose_frames, ignore_index=True) if pose_frames else pd.DataFrame(columns=["model_rank", *POSE_COLUMNS])
    evidence = pd.concat(evidence_frames, ignore_index=True) if evidence_frames else pd.DataFrame(columns=["model_rank", *EVIDENCE_COLUMNS])
    unique_engines = [x for x in dict.fromkeys(engines) if x]
    unique_grades = [x for x in dict.fromkeys(grades) if x]
    unique_guards = [x for x in dict.fromkeys(guards) if x]
    return {
        "contract_version": version,
        "status": "COMBINED" if statuses else "EMPTY",
        "engine": "; ".join(unique_engines),
        "engine_version": "",
        "evidence_grade": "; ".join(unique_grades),
        "poses": poses,
        "evidence": evidence,
        "claim_guard": " | ".join(unique_guards),
        "model_count": len({int(x[0]) for x in items}) if hasattr(items, "__len__") else len(pose_frames),
    }


__all__ = [
    "DOCKING_RESULT_CONTRACT_VERSION", "POSE_COLUMNS", "EVIDENCE_COLUMNS",
    "normalize_native_docking_result", "evidence_to_workbench_contacts",
    "normalized_to_workbench_poses", "write_atoms_as_pdb", "export_normalized_result",
    "combine_normalized_results",
]
