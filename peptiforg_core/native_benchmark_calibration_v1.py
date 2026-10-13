from __future__ import annotations

"""Split-aware calibration/reporting for Pepforge native docking benchmarks.

This module summarizes explicit reference-structure benchmark outputs. It does
not create benchmark truth, infer missing labels, or convert structural recovery
into affinity/biological claims.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable
import json
import math

import numpy as np
import pandas as pd

NATIVE_BENCHMARK_CALIBRATION_VERSION = "0.1.0"


@dataclass(frozen=True)
class CalibrationPolicy:
    acceptable_dockq: float = 0.23
    medium_dockq: float = 0.49
    high_dockq: float = 0.80
    bootstrap_iterations: int = 1000
    bootstrap_seed: int = 20261002
    min_pairs_for_correlation: int = 3
    note: str = (
        "Pepforge reporting policy. DockQ-compatible thresholds are used only as "
        "structural-recovery descriptors; they are not affinity or biological-validity thresholds."
    )


def _finite(x: Any) -> float | None:
    try:
        y = float(x)
        return y if math.isfinite(y) else None
    except Exception:
        return None


def _bootstrap_rate(values: list[bool], *, iterations: int, seed: int) -> dict[str, Any]:
    if not values:
        return {"n": 0, "estimate": None, "ci95_low": None, "ci95_high": None}
    arr = np.asarray(values, dtype=float)
    estimate = float(arr.mean())
    if len(arr) == 1 or iterations <= 0:
        return {"n": int(len(arr)), "estimate": estimate, "ci95_low": estimate, "ci95_high": estimate}
    rng = np.random.default_rng(int(seed))
    idx = rng.integers(0, len(arr), size=(int(iterations), len(arr)))
    means = arr[idx].mean(axis=1)
    lo, hi = np.quantile(means, [0.025, 0.975])
    return {"n": int(len(arr)), "estimate": estimate, "ci95_low": float(lo), "ci95_high": float(hi)}


def _safe_corr(x: pd.Series, y: pd.Series, min_pairs: int) -> tuple[float | None, int]:
    d = pd.DataFrame({"x": pd.to_numeric(x, errors="coerce"), "y": pd.to_numeric(y, errors="coerce")}).dropna()
    if len(d) < int(min_pairs):
        return None, int(len(d))
    # internal score is lower-is-better while DockQ-compatible is higher-is-better,
    # hence correlate internal-score rank against negative DockQ rank.
    c = d["x"].rank().corr((-d["y"]).rank(), method="pearson")
    return (_finite(c), int(len(d)))


def _load_target_summary(path: Path) -> dict[str, Any]:
    d = json.loads(path.read_text(encoding="utf-8"))
    meta = d.get("dataset_target") or {}
    csv_path = Path(str(d.get("benchmark_csv") or ""))
    if not csv_path.is_absolute():
        csv_path = (path.parent / csv_path).resolve()
    row: dict[str, Any] = {
        "target_id": str(meta.get("target_id") or path.parent.name),
        "split": str(meta.get("split") or "unspecified"),
        "source": str(meta.get("source") or ""),
        "experimental_id": str(meta.get("experimental_id") or ""),
        "reference_sha256": str(meta.get("reference_sha256") or ""),
        "models_evaluated": int(d.get("models_evaluated") or 0),
        "best_dockq": _finite(d.get("best_dockq_compatible")),
        "top1_dockq": _finite(d.get("top1_by_internal_score_dockq")),
        "top5_dockq": _finite(d.get("best_top5_by_internal_score_dockq")),
        "target_score_dockq_spearman": _finite(d.get("score_dockq_spearman")),
        "summary_json": str(path.resolve()),
        "benchmark_csv": str(csv_path),
    }
    pose_df = pd.DataFrame()
    if csv_path.is_file():
        try:
            pose_df = pd.read_csv(csv_path)
        except Exception:
            pose_df = pd.DataFrame()
    row["ranked_pose_count"] = int(pd.to_numeric(pose_df.get("internal_score"), errors="coerce").notna().sum()) if "internal_score" in pose_df else 0
    if not pose_df.empty and "ligand_residue_count" in pose_df:
        vals = pd.to_numeric(pose_df["ligand_residue_count"], errors="coerce").dropna()
        row["ligand_residue_count"] = int(vals.iloc[0]) if len(vals) else None
    else:
        row["ligand_residue_count"] = None
    return row


def discover_target_summaries(root: str | Path) -> list[str]:
    return [str(p) for p in sorted(Path(root).rglob("native_docking_reference_benchmark.json"))]


def calibrate_benchmark_results(
    benchmark_jsons: Iterable[str | Path],
    output_dir: str | Path,
    *,
    policy: CalibrationPolicy | None = None,
) -> dict[str, Any]:
    pol = policy or CalibrationPolicy()
    out = Path(output_dir).expanduser().resolve(); out.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    all_pose_rows: list[pd.DataFrame] = []
    for raw in benchmark_jsons:
        p = Path(raw).expanduser().resolve()
        try:
            row = _load_target_summary(p); rows.append(row)
            csv_path = Path(row["benchmark_csv"])
            if csv_path.is_file():
                df = pd.read_csv(csv_path)
                df["target_id"] = row["target_id"]
                df["split"] = row["split"]
                all_pose_rows.append(df)
        except Exception as exc:
            errors.append({"source": str(p), "error": str(exc)})

    targets = pd.DataFrame(rows)
    targets_csv = out / "native_benchmark_calibration_targets.csv"
    targets.to_csv(targets_csv, index=False, encoding="utf-8-sig")
    poses = pd.concat(all_pose_rows, ignore_index=True) if all_pose_rows else pd.DataFrame()
    poses_csv = out / "native_benchmark_calibration_poses.csv"
    poses.to_csv(poses_csv, index=False, encoding="utf-8-sig")

    def summarize(g: pd.DataFrame, label: str, seed_offset: int) -> dict[str, Any]:
        top1 = [_finite(x) for x in g.get("top1_dockq", pd.Series(dtype=float)).tolist()]
        top1 = [x for x in top1 if x is not None]
        top5 = [_finite(x) for x in g.get("top5_dockq", pd.Series(dtype=float)).tolist()]
        top5 = [x for x in top5 if x is not None]
        best = [_finite(x) for x in g.get("best_dockq", pd.Series(dtype=float)).tolist()]
        best = [x for x in best if x is not None]
        return {
            "split": label,
            "targets": int(len(g)),
            "ranked_targets": int(len(top1)),
            "top1_acceptable": _bootstrap_rate([x >= pol.acceptable_dockq for x in top1], iterations=pol.bootstrap_iterations, seed=pol.bootstrap_seed + seed_offset),
            "top5_acceptable": _bootstrap_rate([x >= pol.acceptable_dockq for x in top5], iterations=pol.bootstrap_iterations, seed=pol.bootstrap_seed + 100 + seed_offset),
            "top1_medium_or_better": _bootstrap_rate([x >= pol.medium_dockq for x in top1], iterations=pol.bootstrap_iterations, seed=pol.bootstrap_seed + 200 + seed_offset),
            "top5_medium_or_better": _bootstrap_rate([x >= pol.medium_dockq for x in top5], iterations=pol.bootstrap_iterations, seed=pol.bootstrap_seed + 300 + seed_offset),
            "median_best_dockq": float(np.median(best)) if best else None,
            "median_top1_dockq": float(np.median(top1)) if top1 else None,
            "median_top5_dockq": float(np.median(top5)) if top5 else None,
        }

    summaries = []
    if not targets.empty:
        summaries.append(summarize(targets, "ALL", 0))
        for i, (split, g) in enumerate(targets.groupby("split", dropna=False), start=1):
            summaries.append(summarize(g, str(split), i))

    pose_corr, pose_pairs = (None, 0)
    if not poses.empty and {"internal_score", "dockq_compatible"}.issubset(poses.columns):
        pose_corr, pose_pairs = _safe_corr(poses["internal_score"], poses["dockq_compatible"], pol.min_pairs_for_correlation)

    target_corr = None
    target_corr_pairs = 0
    if not targets.empty and "target_score_dockq_spearman" in targets:
        vals = pd.to_numeric(targets["target_score_dockq_spearman"], errors="coerce").dropna()
        target_corr_pairs = int(len(vals))
        target_corr = float(vals.median()) if len(vals) else None

    unique_refs = int(targets["reference_sha256"].replace("", np.nan).dropna().nunique()) if not targets.empty else 0
    refs_with_hash = int(targets["reference_sha256"].replace("", np.nan).dropna().shape[0]) if not targets.empty else 0
    duplicate_reference_hashes = max(0, refs_with_hash - unique_refs)
    splits = sorted(str(x) for x in targets["split"].dropna().unique().tolist()) if not targets.empty else []
    has_test_like = any(s.lower() in {"test", "holdout", "heldout", "external", "blind"} for s in splits)

    payload = {
        "version": NATIVE_BENCHMARK_CALIBRATION_VERSION,
        "status": "CALIBRATION_REPORT_READY" if len(targets) else "NO_BENCHMARK_EVIDENCE",
        "policy": asdict(pol),
        "targets": int(len(targets)),
        "poses": int(len(poses)),
        "splits": splits,
        "has_test_or_holdout_split": bool(has_test_like),
        "duplicate_reference_hash_count": int(duplicate_reference_hashes),
        "split_summaries": summaries,
        "global_pose_score_vs_structure_spearman": pose_corr,
        "global_pose_score_vs_structure_pairs": pose_pairs,
        "median_target_score_vs_structure_spearman": target_corr,
        "targets_with_score_structure_correlation": target_corr_pairs,
        "errors": errors,
        "targets_csv": str(targets_csv),
        "poses_csv": str(poses_csv),
        "claim_guard": (
            "This report summarizes structural recovery against explicit reference complexes. Bootstrap intervals reflect "
            "sampling variability within the supplied target set only; they do not establish population-level biological accuracy, affinity prediction, or production-MD validity."
        ),
    }
    (out / "native_benchmark_calibration.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Pepforge Native Benchmark Calibration", "", f"Status: **{payload['status']}**", "",
        f"Targets: {payload['targets']}", f"Poses: {payload['poses']}", f"Splits: {', '.join(splits) if splits else 'none'}",
        f"Test/holdout-like split present: {payload['has_test_or_holdout_split']}",
        f"Global internal-score vs DockQ-compatible Spearman: {pose_corr}", "", "## Split summary", "",
    ]
    for s in summaries:
        lines += [f"### {s['split']}", f"- targets: {s['targets']}", f"- ranked targets: {s['ranked_targets']}", f"- top-1 acceptable: {s['top1_acceptable']}", f"- top-5 acceptable: {s['top5_acceptable']}", f"- median best DockQ-compatible: {s['median_best_dockq']}", ""]
    lines += ["## Boundary", payload["claim_guard"], ""]
    (out / "NATIVE_BENCHMARK_CALIBRATION.md").write_text("\n".join(lines), encoding="utf-8")
    return payload


__all__ = ["NATIVE_BENCHMARK_CALIBRATION_VERSION", "CalibrationPolicy", "discover_target_summaries", "calibrate_benchmark_results"]
