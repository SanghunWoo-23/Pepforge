from __future__ import annotations

"""Headless export wrapper around the existing Docking Workbench contact core."""

from pathlib import Path
from typing import Any, Iterable
import json

DOCKBENCH_EXPORT_VERSION = "5.0.0-rc2"


def analyze_complex_pose(pdb_path: str | Path, output_dir: str | Path, *, name: str = "pose") -> dict[str, Any]:
    import pandas as pd
    from suite_gui.docking_workbench_gui import analyze_complex_structure_contacts

    path = Path(pdb_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(path)
    out = Path(output_dir).expanduser().resolve(); out.mkdir(parents=True, exist_ok=True)
    poses, contacts, atom_contacts, peptide_points = analyze_complex_structure_contacts(path)
    prefix = str(name or "pose")
    pose_csv = out / f"{prefix}_dockbench_pose_summary.csv"
    contact_csv = out / f"{prefix}_dockbench_residue_contacts.csv"
    atom_csv = out / f"{prefix}_dockbench_atom_contacts.csv"
    poses.to_csv(pose_csv, index=False, encoding="utf-8-sig")
    contacts.to_csv(contact_csv, index=False, encoding="utf-8-sig")
    atom_contacts.to_csv(atom_csv, index=False, encoding="utf-8-sig")
    contact_classes: dict[str, int] = {}
    if not atom_contacts.empty and "contact_class" in atom_contacts:
        for cell in atom_contacts["contact_class"].astype(str):
            for cls in [x.strip() for x in cell.split(";") if x.strip()]:
                contact_classes[cls] = contact_classes.get(cls, 0) + 1
    summary = {
        "version": DOCKBENCH_EXPORT_VERSION,
        "status": "COMPLETED",
        "input_pdb": str(path),
        "residue_contact_rows": int(len(contacts)),
        "atom_contact_rows": int(len(atom_contacts)),
        "contact_class_counts": contact_classes,
        "files": {"pose_summary": str(pose_csv), "residue_contacts": str(contact_csv), "atom_contacts": str(atom_csv)},
        "claim_guard": "DockBench reports coordinate-derived interaction evidence. Distance candidates are not measured affinity and H-bond geometry is not fully asserted without angular analysis.",
    }
    summary_path = out / f"{prefix}_dockbench_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary["files"]["summary"] = str(summary_path)
    return summary


def analyze_pose_collection(model_results: Iterable[dict[str, Any]], output_dir: str | Path) -> dict[str, Any]:
    out = Path(output_dir).expanduser().resolve(); out.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for model in model_results:
        mrank = int(model.get("model_rank", 0))
        for pose in model.get("poses", []) or []:
            prank = int(pose.get("rank", 0))
            pdb = pose.get("pose_pdb")
            if not pdb:
                continue
            analysis = analyze_complex_pose(pdb, out / f"model_{mrank:02d}" / f"pose_{prank:02d}", name=f"m{mrank:02d}_p{prank:02d}")
            rows.append({"model_rank": mrank, "pose_rank": prank, "pose_pdb": str(pdb), "analysis": analysis})
    manifest = out / "dockbench_collection_manifest.json"
    payload = {"version": DOCKBENCH_EXPORT_VERSION, "status": "COMPLETED" if rows else "NO_POSES", "pose_count": len(rows), "results": rows}
    manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"status": payload["status"], "pose_count": len(rows), "manifest": str(manifest), "results": rows}


__all__ = ["DOCKBENCH_EXPORT_VERSION", "analyze_complex_pose", "analyze_pose_collection"]
