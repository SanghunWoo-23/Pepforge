from __future__ import annotations

"""Pepforge-native rigid-body protein/peptide pose exploration.

This implementation is intentionally independent of HADDOCK/OpenMM/RDKit.
It performs deterministic rigid-body pose generation, steric filtering,
interaction-evidence scoring, local translation refinement, RMSD-like pose
clustering, and export using NumPy/Pandas plus Pepforge's own interaction rules.

Scientific scope: this is an experimental coordinate-search engine. Its score is
not binding free energy, affinity, Kd, or experimental validation.
"""

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable, Sequence
import json
import math
import numpy as np
import pandas as pd

from .interface_quality import parse_pdb_atoms
from .interaction_evidence import analyze_interaction_evidence, interaction_summary
from .native_quality_gate_v1 import assess_native_docking_pose

NATIVE_DOCKING_VERSION = "0.2.0"


@dataclass(frozen=True)
class NativeDockingConfig:
    mode: str = "blind"
    poses: int = 5
    anchor_count: int = 12
    rotations_per_anchor: int = 18
    shell_distance_A: float = 4.5
    local_refine_steps: int = 2
    local_step_A: float = 0.75
    cluster_centroid_A: float = 2.0
    max_candidates: int = 500
    seed: int = 20260929
    interaction_profile: str = "CONSERVATIVE_MANUAL"
    clash_penalty: float = 25.0
    smooth_contact_weight: float = 0.08
    contact_count_weight: float = 0.015
    interaction_score_scale: float = 1.0


@dataclass
class PoseCandidate:
    candidate_id: int
    anchor_index: int
    rotation_index: int
    score: float
    clash_count: int
    min_distance_A: float
    contact_count: int
    centroid: tuple[float, float, float]
    rotation_matrix: list[list[float]]
    translation: tuple[float, float, float]
    atoms: pd.DataFrame
    summary: dict[str, Any] | None = None


def _validate_atoms(df: pd.DataFrame, label: str) -> pd.DataFrame:
    if df is None or df.empty:
        raise ValueError(f"{label} structure contains no readable atoms.")
    req = {"atom", "resn", "chain", "resi", "x", "y", "z", "element"}
    missing = req.difference(df.columns)
    if missing:
        raise ValueError(f"{label} atom table missing columns: {sorted(missing)}")
    out = df.copy().reset_index(drop=True)
    for c in ["x", "y", "z"]:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    out = out.dropna(subset=["x", "y", "z"]).reset_index(drop=True)
    if out.empty:
        raise ValueError(f"{label} structure contains no finite coordinates.")
    return out


def _coords(df: pd.DataFrame) -> np.ndarray:
    return df[["x", "y", "z"]].to_numpy(dtype=float)


def _center(df: pd.DataFrame) -> np.ndarray:
    return _coords(df).mean(axis=0)


def _rotation_matrix_xyz(ax: float, ay: float, az: float) -> np.ndarray:
    cx, sx = math.cos(ax), math.sin(ax)
    cy, sy = math.cos(ay), math.sin(ay)
    cz, sz = math.cos(az), math.sin(az)
    rx = np.array([[1,0,0],[0,cx,-sx],[0,sx,cx]], dtype=float)
    ry = np.array([[cy,0,sy],[0,1,0],[-sy,0,cy]], dtype=float)
    rz = np.array([[cz,-sz,0],[sz,cz,0],[0,0,1]], dtype=float)
    return rz @ ry @ rx


def _rotation_set(n: int) -> list[np.ndarray]:
    """Deterministic low-discrepancy Euler rotations."""
    n = max(1, int(n))
    phi = (1 + 5 ** 0.5) / 2
    out = []
    for i in range(n):
        u = (i + 0.5) / n
        ax = 2 * math.pi * ((i / phi) % 1.0)
        ay = math.acos(max(-1.0, min(1.0, 1 - 2*u)))
        az = 2 * math.pi * ((i / (phi*phi)) % 1.0)
        out.append(_rotation_matrix_xyz(ax, ay, az))
    return out


def _farthest_point_indices(points: np.ndarray, count: int) -> list[int]:
    if len(points) == 0:
        return []
    count = min(max(1, int(count)), len(points))
    center = points.mean(axis=0)
    first = int(np.argmax(np.linalg.norm(points - center[None, :], axis=1)))
    selected = [first]
    min_d = np.linalg.norm(points - points[first][None, :], axis=1)
    while len(selected) < count:
        idx = int(np.argmax(min_d))
        if idx in selected:
            break
        selected.append(idx)
        min_d = np.minimum(min_d, np.linalg.norm(points - points[idx][None, :], axis=1))
    return selected


def _parse_residue_selector(value: str) -> tuple[str | None, str]:
    text = str(value or "").strip()
    if not text:
        raise ValueError("Empty residue selector")
    if ":" in text:
        chain, resi = text.split(":", 1)
        return chain.strip() or None, resi.strip()
    return None, text


def _anchor_points(receptor: pd.DataFrame, cfg: NativeDockingConfig, binding_residues: Sequence[str] | None) -> list[np.ndarray]:
    mode = str(cfg.mode or "blind").lower()
    xyz = _coords(receptor)
    if mode in {"manual", "hotspot"}:
        sels = list(binding_residues or [])
        if not sels:
            raise ValueError(f"{mode} mode requires binding_residues")
        subset_rows = []
        for token in sels:
            chain, resi = _parse_residue_selector(token)
            mask = receptor["resi"].astype(str).eq(str(resi))
            if chain is not None:
                mask &= receptor["chain"].astype(str).eq(str(chain))
            part = receptor[mask]
            if not part.empty:
                subset_rows.append(part)
        if not subset_rows:
            raise ValueError("No requested binding-site residues were found in receptor PDB.")
        sub = pd.concat(subset_rows, ignore_index=True)
        centers = []
        for _, g in sub.groupby(["chain", "resi"], dropna=False):
            centers.append(_coords(g).mean(axis=0))
        return centers[: max(1, int(cfg.anchor_count))]

    # Blind mode: use representative receptor heavy atoms selected by farthest-
    # point sampling. Prefer CA atoms because they spread anchors over the fold;
    # fall back to all heavy atoms for noncanonical/atom-only targets.
    ca = receptor[receptor["atom"].astype(str).str.upper().eq("CA")]
    base = _coords(ca if len(ca) >= 3 else receptor[~receptor["element"].astype(str).str.upper().eq("H")])
    idxs = _farthest_point_indices(base, cfg.anchor_count)
    return [base[i] for i in idxs]


def _place_peptide(peptide: pd.DataFrame, rotation: np.ndarray, target_center: np.ndarray) -> pd.DataFrame:
    out = peptide.copy()
    pxyz = _coords(peptide)
    pc = pxyz.mean(axis=0)
    moved = (pxyz - pc[None, :]) @ rotation.T + target_center[None, :]
    out.loc[:, ["x", "y", "z"]] = moved
    return out


def _quick_geometry_score(receptor: pd.DataFrame, peptide: pd.DataFrame, cfg: NativeDockingConfig) -> tuple[float, int, float, int]:
    """Fast deterministic geometry score; lower is better.

    The terms are intentionally dimensionless screening terms, not energies.
    Severe overlap dominates the penalty; close but non-overlapping interface
    contacts contribute favorable terms. Interaction classification is done
    separately with the full Pepforge evidence engine for retained candidates.
    """
    r = _coords(receptor[~receptor["element"].astype(str).str.upper().eq("H")])
    p = _coords(peptide[~peptide["element"].astype(str).str.upper().eq("H")])
    if not len(r) or not len(p):
        return 1e9, 0, float("inf"), 0
    # Chunk peptide atoms to avoid unbounded matrices on large receptors.
    min_d = float("inf")
    clash = 0
    contacts = 0
    favorable = 0.0
    for start in range(0, len(p), 64):
        q = p[start:start+64]
        d = np.linalg.norm(q[:,None,:] - r[None,:,:], axis=2)
        if d.size:
            min_d = min(min_d, float(d.min()))
            clash += int((d < 2.35).sum())
            contacts += int(((d >= 3.2) & (d <= 5.0)).sum())
            # Smooth contact reward centered near 3.8 A.
            mask = (d >= 2.6) & (d <= 6.0)
            if mask.any():
                vals = d[mask]
                favorable += float(np.exp(-((vals - 3.8) / 1.2) ** 2).sum())
    score = (clash * float(cfg.clash_penalty)) - (favorable * float(cfg.smooth_contact_weight)) - min(contacts, 500) * float(cfg.contact_count_weight)
    return float(score), int(clash), float(min_d), int(contacts)


def _score_interactions(evidence: pd.DataFrame) -> float:
    if evidence is None or evidence.empty:
        return 0.0
    weights = {
        "hydrogen_bond": -2.0,
        "hydrophobic": -0.7,
        "salt_bridge": -2.6,
        "pi_pi": -1.7,
        "cation_pi": -1.8,
        "van_der_Waals": -0.2,
        "disulfide": -0.5,  # evidence only; no covalent docking claim
        "clash": 8.0,
    }
    total = 0.0
    for _, row in evidence.iterrows():
        w = float(weights.get(str(row.get("interaction")), 0.0))
        if str(row.get("evidence_level")) == "not_confirmed" and w < 0:
            w *= 0.25
        total += w
    return float(total)


def _local_refine(receptor: pd.DataFrame, peptide: pd.DataFrame, cfg: NativeDockingConfig) -> tuple[pd.DataFrame, float, int, float, int]:
    best = peptide
    best_metrics = _quick_geometry_score(receptor, peptide, cfg)
    axes = np.eye(3, dtype=float)
    step = float(cfg.local_step_A)
    for _ in range(max(0, int(cfg.local_refine_steps))):
        improved = False
        for axis in axes:
            for sign in (-1.0, 1.0):
                trial = best.copy()
                trial.loc[:, ["x", "y", "z"]] = _coords(best) + axis[None, :] * (sign * step)
                metrics = _quick_geometry_score(receptor, trial, cfg)
                if metrics[0] < best_metrics[0]:
                    best, best_metrics, improved = trial, metrics, True
        step *= 0.5
        if not improved and step < 0.15:
            break
    return best, *best_metrics


def _surface_target(anchor: np.ndarray, receptor_center: np.ndarray, shell_A: float) -> np.ndarray:
    vec = anchor - receptor_center
    n = float(np.linalg.norm(vec))
    if n < 1e-8:
        vec = np.array([1.0, 0.0, 0.0])
    else:
        vec = vec / n
    return anchor + vec * float(shell_A)


def _cluster_candidates(candidates: list[PoseCandidate], limit: int, centroid_cutoff_A: float) -> list[PoseCandidate]:
    selected: list[PoseCandidate] = []
    for cand in sorted(candidates, key=lambda x: (x.score, x.clash_count, -x.contact_count, x.candidate_id)):
        c = np.asarray(cand.centroid, dtype=float)
        if any(np.linalg.norm(c - np.asarray(s.centroid, dtype=float)) < float(centroid_cutoff_A) for s in selected):
            continue
        selected.append(cand)
        if len(selected) >= int(limit):
            return selected
    # Explicit fallback preserves quality ranking if centroid diversity is scarce.
    chosen = {x.candidate_id for x in selected}
    for cand in sorted(candidates, key=lambda x: (x.score, x.clash_count, x.candidate_id)):
        if cand.candidate_id not in chosen:
            selected.append(cand); chosen.add(cand.candidate_id)
        if len(selected) >= int(limit):
            break
    return selected


def _pdb_line(serial: int, row: pd.Series, chain_override: str | None = None) -> str:
    atom = str(row.get("atom", "X"))[:4]
    resn = str(row.get("resn", "UNK"))[:3]
    chain = (chain_override if chain_override is not None else str(row.get("chain", "")))[:1] or "A"
    resi_raw = str(row.get("resi", "1"))
    digits = "".join(ch for ch in resi_raw if ch.isdigit() or ch == "-")
    try: resi = int(digits or 1)
    except Exception: resi = 1
    element = str(row.get("element", ""))[:2].upper()
    record = "HETATM" if resn not in {"ALA","ARG","ASN","ASP","CYS","GLN","GLU","GLY","HIS","ILE","LEU","LYS","MET","PHE","PRO","SER","THR","TRP","TYR","VAL"} else "ATOM  "
    return f"{record}{serial:5d} {atom:>4s} {resn:>3s} {chain:1s}{resi:4d}    {float(row.x):8.3f}{float(row.y):8.3f}{float(row.z):8.3f}  1.00  0.00          {element:>2s}"


def write_complex_pdb(receptor: pd.DataFrame, peptide: pd.DataFrame, path: str | Path) -> str:
    out = Path(path); out.parent.mkdir(parents=True, exist_ok=True)
    lines = ["REMARK 950 PEPFORGE_NATIVE_DOCKING EXPERIMENTAL_NATIVE", f"REMARK 951 VERSION {NATIVE_DOCKING_VERSION}"]
    serial = 1
    for _, row in receptor.iterrows():
        lines.append(_pdb_line(serial, row)); serial += 1
    lines.append("TER")
    for _, row in peptide.iterrows():
        lines.append(_pdb_line(serial, row, chain_override="P")); serial += 1
    lines += ["TER", "END"]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(out.resolve())


def run_native_docking(
    receptor_pdb: str | Path,
    peptide_pdb: str | Path,
    output_dir: str | Path,
    *,
    config: NativeDockingConfig | None = None,
    binding_residues: Sequence[str] | None = None,
) -> dict[str, Any]:
    cfg = config or NativeDockingConfig()
    if str(cfg.mode).lower() not in {"blind", "manual", "hotspot"}:
        raise ValueError("mode must be blind, manual, or hotspot")
    receptor_path = Path(receptor_pdb).expanduser().resolve()
    peptide_path = Path(peptide_pdb).expanduser().resolve()
    if receptor_path.suffix.lower() != ".pdb" or peptide_path.suffix.lower() != ".pdb":
        raise ValueError("Pepforge Native Docking v1 currently accepts PDB inputs only.")
    receptor = _validate_atoms(parse_pdb_atoms(receptor_path), "receptor")
    peptide = _validate_atoms(parse_pdb_atoms(peptide_path), "peptide")
    out = Path(output_dir).expanduser().resolve(); out.mkdir(parents=True, exist_ok=True)

    anchors = _anchor_points(receptor, cfg, binding_residues)
    rotations = _rotation_set(cfg.rotations_per_anchor)
    rc = _center(receptor)
    candidates: list[PoseCandidate] = []
    cid = 0
    for ai, anchor in enumerate(anchors):
        target = _surface_target(np.asarray(anchor, dtype=float), rc, cfg.shell_distance_A)
        for ri, rot in enumerate(rotations):
            if cid >= int(cfg.max_candidates):
                break
            placed = _place_peptide(peptide, rot, target)
            placed, qscore, clashes, min_d, contacts = _local_refine(receptor, placed, cfg)
            # Discard only catastrophic poses; modest clashes remain scored so
            # refinement/selection can discriminate instead of hiding failures.
            if clashes > max(25, len(peptide) // 2):
                cid += 1
                continue
            evidence = analyze_interaction_evidence(receptor, placed, profile_name=cfg.interaction_profile, representative_only=True)
            score = float(qscore + float(cfg.interaction_score_scale) * _score_interactions(evidence))
            center = tuple(float(x) for x in _center(placed))
            translation = tuple(float(x) for x in (np.asarray(center) - _center(peptide)))
            candidates.append(PoseCandidate(
                candidate_id=cid, anchor_index=ai, rotation_index=ri, score=score,
                clash_count=clashes, min_distance_A=min_d, contact_count=contacts,
                centroid=center, rotation_matrix=rot.tolist(), translation=translation,
                atoms=placed, summary=interaction_summary(evidence),
            ))
            cid += 1
        if cid >= int(cfg.max_candidates):
            break

    if not candidates:
        payload = {
            "version": NATIVE_DOCKING_VERSION, "status": "NO_USABLE_POSES",
            "evidence_grade": "EXPERIMENTAL_NATIVE", "config": asdict(cfg),
            "candidate_count": 0,
            "claim_guard": "No docking result was fabricated; all generated poses failed the native steric/search filters.",
        }
        (out / "native_docking_summary.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
        return payload

    selected = _cluster_candidates(candidates, max(1, int(cfg.poses)), cfg.cluster_centroid_A)
    pose_rows = []
    for rank, cand in enumerate(selected, 1):
        pose_dir = out / f"pose_{rank:02d}"
        pdb_path = write_complex_pdb(receptor, cand.atoms, pose_dir / f"native_pose_{rank:02d}.pdb")
        evidence = analyze_interaction_evidence(receptor, cand.atoms, profile_name=cfg.interaction_profile, representative_only=True)
        evidence_path = pose_dir / "interaction_evidence.csv"
        evidence.to_csv(evidence_path, index=False, encoding="utf-8-sig")
        isum=interaction_summary(evidence)
        quality=assess_native_docking_pose(clash_count=cand.clash_count,min_distance_A=cand.min_distance_A,contact_count=cand.contact_count,interaction_summary=isum)
        row = {
            "rank": rank, "candidate_id": cand.candidate_id,
            "pepforge_native_score": round(cand.score, 6),
            "clash_count": cand.clash_count,
            "min_distance_A": round(cand.min_distance_A, 4),
            "contact_count": cand.contact_count,
            "centroid": [round(x,4) for x in cand.centroid],
            "pose_pdb": pdb_path,
            "interaction_evidence_csv": str(evidence_path.resolve()),
            "interaction_summary": isum,
            "quality_gate": quality,
        }
        pose_rows.append(row)

    pd.DataFrame([{k:v for k,v in r.items() if k not in {"centroid","interaction_summary"}} for r in pose_rows]).to_csv(out / "native_pose_ranking.csv", index=False, encoding="utf-8-sig")
    payload = {
        "version": NATIVE_DOCKING_VERSION,
        "status": "COMPLETED",
        "engine": "Pepforge Native Docking v1",
        "evidence_grade": "EXPERIMENTAL_NATIVE",
        "receptor_pdb": str(receptor_path),
        "peptide_pdb": str(peptide_path),
        "config": asdict(cfg),
        "binding_residues": list(binding_residues or []),
        "generated_candidate_count": int(cid),
        "usable_candidate_count": len(candidates),
        "selected_pose_count": len(pose_rows),
        "quality_pass_pose_count": sum(1 for r in pose_rows if r.get("quality_gate",{}).get("status")=="PASS"),
        "quality_warn_pose_count": sum(1 for r in pose_rows if r.get("quality_gate",{}).get("status")=="WARN"),
        "quality_fail_pose_count": sum(1 for r in pose_rows if r.get("quality_gate",{}).get("status")=="FAIL"),
        "poses": pose_rows,
        "score_definition": "Pepforge-native dimensionless search score combining steric-overlap penalty, smooth contact reward, and interaction-evidence terms. Lower is better within the same run/configuration.",
        "claim_guard": "Pepforge Native Docking v1 is an experimental rigid-body coordinate search. Its score is not binding free energy, Kd, measured affinity, native-pose proof, or experimental validation.",
    }
    (out / "native_docking_summary.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    return payload


__all__ = ["NATIVE_DOCKING_VERSION", "NativeDockingConfig", "run_native_docking", "write_complex_pdb"]
