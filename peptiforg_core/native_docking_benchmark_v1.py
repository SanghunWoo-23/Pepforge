from __future__ import annotations

"""Reference-based benchmark metrics for Pepforge native docking.

Independent implementation of established docking-evaluation concepts:
- fraction of reference/native residue contacts recovered (Fnat-like),
- ligand backbone RMSD after receptor superposition (LRMSD-like),
- interface backbone RMSD (iRMSD-like),
- DockQ-compatible continuous combination of those three measurements.

This module evaluates a predicted complex against an explicit reference complex.
It does not create or infer a reference and never treats a docking score as an
accuracy metric by itself.
"""

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable
import csv
import json
import math
import numpy as np
import pandas as pd

from .interface_quality import parse_pdb_atoms

NATIVE_DOCKING_BENCHMARK_VERSION = "0.1.0"
_BACKBONE = {"N", "CA", "C", "O"}


@dataclass(frozen=True)
class DockingBenchmarkConfig:
    receptor_chain: str = "A"
    ligand_chain: str = "P"
    peptide_contact_cutoff_A: float = 4.0
    protein_contact_cutoff_A: float = 5.0
    interface_cutoff_A: float = 10.0
    peptide_max_residues: int = 50
    dockq_irms_scale_A: float = 1.5
    dockq_lrms_scale_A: float = 8.5


def _heavy(df: pd.DataFrame) -> pd.DataFrame:
    return df[~df["element"].astype(str).str.upper().eq("H")].copy()


def _chain(df: pd.DataFrame, chain: str) -> pd.DataFrame:
    out = df[df["chain"].astype(str).eq(str(chain))].copy()
    if out.empty:
        raise ValueError(f"Chain {chain!r} was not found in structure")
    return out.reset_index(drop=True)


def _keyed_backbone(df: pd.DataFrame) -> dict[tuple[str, str], np.ndarray]:
    out: dict[tuple[str, str], np.ndarray] = {}
    for _, r in df.iterrows():
        atom = str(r["atom"]).strip().upper()
        if atom not in _BACKBONE:
            continue
        key = (str(r["resi"]), atom)
        out[key] = np.array([float(r["x"]), float(r["y"]), float(r["z"])], dtype=float)
    return out


def _match_coords(ref_df: pd.DataFrame, model_df: pd.DataFrame, *, residues: set[str] | None = None) -> tuple[np.ndarray, np.ndarray, list[tuple[str, str]]]:
    a = _keyed_backbone(ref_df)
    b = _keyed_backbone(model_df)
    keys = sorted(set(a).intersection(b), key=lambda x: (x[0], x[1]))
    if residues is not None:
        keys = [k for k in keys if k[0] in residues]
    if not keys:
        return np.zeros((0,3)), np.zeros((0,3)), []
    return np.vstack([a[k] for k in keys]), np.vstack([b[k] for k in keys]), keys


def _kabsch_transform(mobile: np.ndarray, target: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return R,t such that mobile @ R + t best aligns to target."""
    if len(mobile) != len(target) or len(mobile) < 3:
        raise ValueError("At least 3 matched coordinates are required for superposition")
    cm = mobile.mean(axis=0); ct = target.mean(axis=0)
    x = mobile - cm; y = target - ct
    u, _, vt = np.linalg.svd(x.T @ y)
    r = u @ vt
    if np.linalg.det(r) < 0:
        u[:, -1] *= -1
        r = u @ vt
    t = ct - cm @ r
    return r, t


def _rmsd(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) == 0 or len(a) != len(b):
        return float("nan")
    d = a - b
    return float(np.sqrt(np.mean(np.sum(d*d, axis=1))))


def _residue_contacts(rec: pd.DataFrame, lig: pd.DataFrame, cutoff: float) -> set[tuple[str, str]]:
    rec = _heavy(rec); lig = _heavy(lig)
    if rec.empty or lig.empty:
        return set()
    rc = rec[["x","y","z"]].to_numpy(float); lc = lig[["x","y","z"]].to_numpy(float)
    pairs: set[tuple[str, str]] = set()
    # Chunk ligand atoms to avoid large temporary arrays.
    for start in range(0, len(lc), 64):
        q = lc[start:start+64]
        d = np.linalg.norm(q[:,None,:] - rc[None,:,:], axis=2)
        ii, jj = np.where(d <= float(cutoff))
        for qi, rj in zip(ii.tolist(), jj.tolist()):
            lr = str(lig.iloc[start + qi]["resi"])
            rr = str(rec.iloc[rj]["resi"])
            pairs.add((rr, lr))
    return pairs


def _interface_residues(rec: pd.DataFrame, lig: pd.DataFrame, cutoff: float) -> tuple[set[str], set[str]]:
    rec = _heavy(rec); lig = _heavy(lig)
    if rec.empty or lig.empty:
        return set(), set()
    rc = rec[["x","y","z"]].to_numpy(float); lc = lig[["x","y","z"]].to_numpy(float)
    rr: set[str] = set(); lr: set[str] = set()
    for start in range(0, len(lc), 64):
        q = lc[start:start+64]
        d = np.linalg.norm(q[:,None,:] - rc[None,:,:], axis=2)
        ii, jj = np.where(d <= float(cutoff))
        for qi, rj in zip(ii.tolist(), jj.tolist()):
            lr.add(str(lig.iloc[start + qi]["resi"]))
            rr.add(str(rec.iloc[rj]["resi"]))
    return rr, lr


def _ligand_residue_count(lig: pd.DataFrame) -> int:
    return int(lig[["chain", "resi"]].drop_duplicates().shape[0])


def classify_capri_like(fnat: float, lrmsd: float, irmsd: float) -> str:
    """Apply the commonly used CAPRI-style quality thresholds in reverse order."""
    if fnat >= 0.5 and (lrmsd <= 1.0 or irmsd <= 1.0):
        return "HIGH"
    if fnat >= 0.3 and (lrmsd <= 5.0 or irmsd <= 2.0):
        return "MEDIUM"
    if fnat >= 0.1 and (lrmsd <= 10.0 or irmsd <= 4.0):
        return "ACCEPTABLE"
    return "INCORRECT"


def dockq_compatible(fnat: float, lrmsd: float, irmsd: float, *, a: float=1.5, b: float=8.5) -> float:
    if not (np.isfinite(fnat) and np.isfinite(lrmsd) and np.isfinite(irmsd)):
        return float("nan")
    si = 1.0 / (1.0 + (float(irmsd)/float(a))**2)
    sl = 1.0 / (1.0 + (float(lrmsd)/float(b))**2)
    return float((float(fnat) + si + sl) / 3.0)


def evaluate_complex_against_reference(reference_pdb: str|Path, model_pdb: str|Path, *, config: DockingBenchmarkConfig|None=None) -> dict[str, Any]:
    cfg = config or DockingBenchmarkConfig()
    ref = parse_pdb_atoms(reference_pdb); mdl = parse_pdb_atoms(model_pdb)
    rr = _chain(ref, cfg.receptor_chain); rl = _chain(ref, cfg.ligand_chain)
    mr = _chain(mdl, cfg.receptor_chain); ml = _chain(mdl, cfg.ligand_chain)

    ref_rec_bb, mdl_rec_bb, rec_keys = _match_coords(rr, mr)
    if len(rec_keys) < 3:
        raise ValueError("Insufficient matched receptor backbone atoms for benchmark superposition")
    R, t = _kabsch_transform(mdl_rec_bb, ref_rec_bb)

    # LRMSD after receptor superposition.
    ref_lig_bb, mdl_lig_bb, lig_keys = _match_coords(rl, ml)
    if len(lig_keys) < 3:
        raise ValueError("Insufficient matched ligand backbone atoms for LRMSD")
    mdl_lig_aligned = mdl_lig_bb @ R + t
    lrmsd = _rmsd(mdl_lig_aligned, ref_lig_bb)

    # Interface RMSD: interface residues are defined from the reference, then
    # the interface backbone atom set is independently superposed.
    ref_i_rec, ref_i_lig = _interface_residues(rr, rl, cfg.interface_cutoff_A)
    ar, br, _ = _match_coords(rr, mr, residues=ref_i_rec)
    al, bl, _ = _match_coords(rl, ml, residues=ref_i_lig)
    if len(ar) + len(al) >= 3:
        ref_iface = np.vstack([x for x in (ar, al) if len(x)])
        mdl_iface = np.vstack([x for x in (br, bl) if len(x)])
        Ri, ti = _kabsch_transform(mdl_iface, ref_iface)
        irmsd = _rmsd(mdl_iface @ Ri + ti, ref_iface)
    else:
        irmsd = float("nan")

    peptide_like = _ligand_residue_count(rl) <= int(cfg.peptide_max_residues)
    contact_cutoff = float(cfg.peptide_contact_cutoff_A if peptide_like else cfg.protein_contact_cutoff_A)
    native_contacts = _residue_contacts(rr, rl, contact_cutoff)
    model_contacts = _residue_contacts(mr, ml, contact_cutoff)
    recovered = native_contacts.intersection(model_contacts)
    fnat = float(len(recovered)/len(native_contacts)) if native_contacts else float("nan")
    precision = float(len(recovered)/len(model_contacts)) if model_contacts else 0.0
    dq = dockq_compatible(fnat, lrmsd, irmsd, a=cfg.dockq_irms_scale_A, b=cfg.dockq_lrms_scale_A)
    capri = classify_capri_like(fnat, lrmsd, irmsd) if np.isfinite(fnat) and np.isfinite(irmsd) else "UNCLASSIFIED"

    return {
        "version": NATIVE_DOCKING_BENCHMARK_VERSION,
        "reference_pdb": str(Path(reference_pdb).resolve()),
        "model_pdb": str(Path(model_pdb).resolve()),
        "receptor_chain": cfg.receptor_chain,
        "ligand_chain": cfg.ligand_chain,
        "ligand_residue_count": _ligand_residue_count(rl),
        "contact_cutoff_A": contact_cutoff,
        "fnat_like": fnat,
        "contact_precision": precision,
        "native_contact_count": len(native_contacts),
        "model_contact_count": len(model_contacts),
        "recovered_native_contact_count": len(recovered),
        "lrmsd_A": lrmsd,
        "irmsd_A": irmsd,
        "dockq_compatible": dq,
        "capri_like_class": capri,
        "matched_receptor_backbone_atoms": len(rec_keys),
        "matched_ligand_backbone_atoms": len(lig_keys),
        "reference_interface_receptor_residues": len(ref_i_rec),
        "reference_interface_ligand_residues": len(ref_i_lig),
        "claim_guard": "Reference-comparison geometry metric only. This does not establish biological validity, affinity, or experimental binding.",
    }


def benchmark_model_set(reference_pdb: str|Path, model_pdbs: Iterable[str|Path], output_dir: str|Path, *, config: DockingBenchmarkConfig|None=None, score_csv: str|Path|None=None) -> dict[str, Any]:
    cfg = config or DockingBenchmarkConfig(); out = Path(output_dir).expanduser().resolve(); out.mkdir(parents=True, exist_ok=True)
    internal_scores: dict[str, float] = {}
    if score_csv:
        try:
            sdf = pd.read_csv(score_csv)
            for _, r in sdf.iterrows():
                p = str(r.get("pose_pdb") or r.get("model_pdb") or r.get("pdb") or "")
                s = r.get("score", r.get("native_score", r.get("docking_score")))
                if p and s is not None:
                    try: internal_scores[Path(p).name] = float(s)
                    except Exception: pass
        except Exception:
            pass
    rows = []
    errors = []
    for p in model_pdbs:
        try:
            m = evaluate_complex_against_reference(reference_pdb, p, config=cfg)
            m["model_name"] = Path(p).name
            if Path(p).name in internal_scores:
                m["internal_score"] = internal_scores[Path(p).name]
            rows.append(m)
        except Exception as exc:
            errors.append({"model": str(p), "error": str(exc)})
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["dockq_compatible", "fnat_like"], ascending=[False, False], na_position="last").reset_index(drop=True)
    csv_path = out/"native_docking_reference_benchmark.csv"; df.to_csv(csv_path,index=False,encoding="utf-8-sig")

    summary: dict[str, Any] = {
        "version": NATIVE_DOCKING_BENCHMARK_VERSION,
        "reference_pdb": str(Path(reference_pdb).resolve()),
        "models_evaluated": int(len(df)),
        "errors": errors,
        "config": asdict(cfg),
        "benchmark_csv": str(csv_path.resolve()),
        "claim_guard": "Benchmark measures model/reference structural similarity; it does not validate affinity or generalization by itself.",
    }
    if not df.empty:
        summary.update({
            "best_dockq_compatible": float(df["dockq_compatible"].max()),
            "median_dockq_compatible": float(df["dockq_compatible"].median()),
            "best_fnat_like": float(df["fnat_like"].max()),
            "best_lrmsd_A": float(df["lrmsd_A"].min()),
            "best_irmsd_A": float(df["irmsd_A"].min()),
            "class_counts": {str(k): int(v) for k,v in df["capri_like_class"].value_counts().to_dict().items()},
        })
        if "internal_score" in df.columns and df["internal_score"].notna().sum() >= 1:
            ranked=df[df["internal_score"].notna()].sort_values("internal_score",ascending=True).reset_index(drop=True)
            summary["top1_by_internal_score_dockq"] = float(ranked.iloc[0]["dockq_compatible"])
            summary["top1_by_internal_score_class"] = str(ranked.iloc[0]["capri_like_class"])
            summary["best_top5_by_internal_score_dockq"] = float(ranked.head(5)["dockq_compatible"].max())
            summary["best_top5_by_internal_score_class"] = str(ranked.head(5).sort_values("dockq_compatible",ascending=False).iloc[0]["capri_like_class"])
            if len(ranked) >= 3:
                sub=ranked[["internal_score","dockq_compatible"]].dropna()
                # Native docking uses lower-is-better score, DockQ higher-is-better.
                summary["score_dockq_spearman"] = float(sub["internal_score"].rank().corr((-sub["dockq_compatible"]).rank(), method="pearson"))
                summary["score_dockq_pairs"] = int(len(sub))
    summary_path=out/"native_docking_reference_benchmark.json"; summary_path.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return summary


__all__ = [
    "NATIVE_DOCKING_BENCHMARK_VERSION", "DockingBenchmarkConfig",
    "evaluate_complex_against_reference", "benchmark_model_set",
    "classify_capri_like", "dockq_compatible",
]
