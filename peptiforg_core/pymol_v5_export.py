from __future__ import annotations

"""PyMOL-compatible export for Pepforge V5 PSB/docking ensembles."""

from pathlib import Path
from typing import Any, Iterable
import csv
import json
import re
import shutil

PYMOL_V5_EXPORT_VERSION = "5.0.0-rc2"


def _safe(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(text or "item")).strip("_") or "item"


def export_pymol_docking_ensemble(
    model_results: Iterable[dict[str, Any]],
    output_dir: str | Path,
    *,
    candidate_id: str = "candidate",
) -> dict[str, str]:
    out = Path(output_dir).expanduser().resolve()
    structures = out / "complexes"
    structures.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    pml: list[str] = [
        "# Pepforge V5 PSB docking ensemble",
        "reinitialize",
        "set retain_order, 1",
        "set cartoon_fancy_helices, 1",
        "bg_color white",
    ]
    for result in sorted((dict(x) for x in model_results), key=lambda x: int(x.get("model_rank", 9999))):
        model_rank = int(result.get("model_rank", 0))
        group = f"PSB_Model_{model_rank:02d}"
        for pose in result.get("poses", []) or []:
            src = Path(str(pose.get("pose_pdb", "")))
            if not src.exists() or src.stat().st_size <= 0:
                continue
            pose_rank = int(pose.get("rank", len(rows) + 1))
            dest_dir = structures / f"model_{model_rank:02d}"
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / f"pose_{pose_rank:02d}.pdb"
            shutil.copy2(src, dest)
            obj = _safe(f"M{model_rank:02d}_P{pose_rank:02d}")
            rel = dest.relative_to(out).as_posix()
            pml.extend([
                f'load "{rel}", {obj}',
                f"hide everything, {obj}",
                f"show cartoon, {obj}",
                f"show sticks, {obj} and polymer and not name C+N+O+CA",
                f"group {group}, {obj}",
            ])
            rows.append({
                "candidate_id": candidate_id,
                "model_rank": model_rank,
                "pose_rank": pose_rank,
                "score": pose.get("score"),
                "score_type": pose.get("score_type", ""),
                "pdb": str(dest),
                "pymol_object": obj,
            })
    if not rows:
        raise ValueError("No verified docking pose PDBs were supplied for PyMOL export.")
    pml.extend([
        "orient",
        "zoom all",
        "# Scores are docking-engine scores, not experimental affinity.",
    ])
    pml_path = out / "open_all_docking_results.pml"
    pml_path.write_text("\n".join(pml) + "\n", encoding="utf-8")
    csv_path = out / "pymol_pose_index.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); writer.writeheader(); writer.writerows(rows)
    manifest = out / "pymol_export_manifest.json"
    manifest.write_text(json.dumps({
        "version": PYMOL_V5_EXPORT_VERSION,
        "candidate_id": candidate_id,
        "pose_count": len(rows),
        "files": {"pml": str(pml_path), "index_csv": str(csv_path), "complex_dir": str(structures)},
        "claim_guard": "PyMOL files visualize computational models only.",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"pml": str(pml_path), "pose_index_csv": str(csv_path), "complex_dir": str(structures), "manifest": str(manifest)}


__all__ = ["PYMOL_V5_EXPORT_VERSION", "export_pymol_docking_ensemble"]
