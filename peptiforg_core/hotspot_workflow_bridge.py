from __future__ import annotations

"""Shared Hot Spot -> PDE workflow hand-off helpers.

This module contains the file/project bridge used by both Workflow Mode and the
standalone Hot Spot Finder. It does not launch GUIs and it does not score or
reinterpret Hot Spot evidence.
"""

from pathlib import Path
from typing import Any, Iterable
import csv

from peptiforg_core.hotspot_design_transfer import export_hotspot_chemistry_profile
from peptiforg_core.project_io import load_project, save_project, relpath
from peptiforg_core.workflow_schema import SELECTED_HOTSPOT_COLUMNS


def ranked_region_to_transfer(row: dict[str, Any]) -> dict[str, Any]:
    """Convert one ranked Hot Spot region to the stable PDE transfer schema."""
    return {
        "rank": row.get("rank", ""),
        "region_start": row.get("region_start", ""),
        "region_end": row.get("region_end", ""),
        "sequence": row.get("region_sequence", row.get("sequence", "")),
        "hotspot_score": row.get("priority_score", row.get("hotspot_score", "")),
        "record_name": row.get("record_name", ""),
        "secondary_structure": row.get("secondary_structure", ""),
        "beta_edge_candidate": row.get("beta_edge_candidate", ""),
        "beta_edge_evidence": row.get("beta_edge_evidence", ""),
        "beta_edge_backbone_pairing_atoms": row.get("beta_edge_backbone_pairing_atoms", ""),
        "beta_edge_local_strand_axis_xyz": row.get("beta_edge_local_strand_axis_xyz", ""),
        "beta_edge_register_status": row.get("beta_edge_register_status", "not_inferred"),
        "note": (
            f"Ranked Hot Spot region #{row.get('rank', '')}; priority is a within-run heuristic, "
            "not binding probability or affinity."
        ),
    }


def write_design_handoff(
    project_dir: str | Path,
    selected_rows: Iterable[dict[str, Any]],
    *,
    ranked_rows: Iterable[dict[str, Any]] | None = None,
) -> dict[str, str]:
    """Persist selected Hot Spot rows and PDE hand-off files in a project.

    The caller supplies already-selected rows. No ranking or scientific inference
    is performed here.
    """
    folder = Path(project_dir)
    project = load_project(folder)
    selected = [dict(row) for row in selected_rows if str(row.get("sequence", "")).strip()]
    project["selected_hotspots"] = selected
    if ranked_rows is not None:
        project["hotspot_ranked_regions"] = [dict(row) for row in ranked_rows]

    design_dir = folder / "design"
    design_dir.mkdir(parents=True, exist_ok=True)
    csv_path = design_dir / "selected_hotspots_for_design.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=SELECTED_HOTSPOT_COLUMNS)
        writer.writeheader()
        for row in selected:
            writer.writerow({key: row.get(key, "") for key in SELECTED_HOTSPOT_COLUMNS})

    profile_paths = export_hotspot_chemistry_profile(selected, design_dir)
    output_files = project.setdefault("output_files", {})
    output_files["selected_hotspots_for_design"] = relpath(folder, csv_path)
    if profile_paths.get("profile_json"):
        output_files["hotspot_chemistry_profile_json"] = relpath(folder, Path(profile_paths["profile_json"]))
    if profile_paths.get("profile_csv"):
        output_files["hotspot_chemistry_profile_csv"] = relpath(folder, Path(profile_paths["profile_csv"]))
    save_project(folder, project)
    return {
        "selected_hotspots_csv": str(csv_path),
        "profile_json": str(profile_paths.get("profile_json", "")),
        "profile_csv": str(profile_paths.get("profile_csv", "")),
    }


__all__ = ["ranked_region_to_transfer", "write_design_handoff"]
