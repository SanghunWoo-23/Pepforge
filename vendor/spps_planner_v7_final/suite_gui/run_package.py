"""Portable one-Run export package for SPPS Planner V6."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Mapping
import json
import os
import tempfile
import zipfile

import pandas as pd


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [dict(row) for row in value if isinstance(row, Mapping)]
    return []


def _write_xlsx(path: Path, rows: list[dict[str, Any]], sheet: str) -> None:
    frame = pd.DataFrame(rows)
    if frame.empty:
        frame = pd.DataFrame([{"status": "No records"}])
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        frame.to_excel(writer, index=False, sheet_name=sheet[:31])


def build_package(payload: Mapping[str, Any], output_zip: str | Path, *,
                  materials: list[dict[str, Any]] | None = None,
                  checklist: list[dict[str, Any]] | None = None) -> Path:
    """Write PLAN/MATERIALS/CHECKLIST/ACTUAL/RESULTS/ISSUES plus JSON manifest."""
    data = dict(payload or {})
    frozen = dict(data.get("planner_snapshot_frozen") or {})
    execution = dict(data.get("execution") or {})
    linked = dict(data.get("linked_records") or {})
    actual = dict(data.get("actual_condition") or {})
    run = dict(data.get("run") or {})
    destination = Path(output_zip).expanduser()
    if destination.suffix.lower() != ".zip":
        destination = destination.with_suffix(".zip")
    destination.parent.mkdir(parents=True, exist_ok=True)

    with TemporaryDirectory(prefix="spps_run_package_") as tmp:
        folder = Path(tmp)
        _write_xlsx(folder / "PLAN.xlsx", _rows(frozen.get("selected_plan_rows")), "Plan")
        _write_xlsx(folder / "MATERIALS.xlsx", _rows(materials), "Materials")
        _write_xlsx(folder / "CHECKLIST.xlsx", _rows(checklist), "Checklist")
        actual_rows = _rows(execution.get("steps"))
        # Include deviations after step rows in a dedicated second sheet.
        with pd.ExcelWriter(folder / "ACTUAL_EXECUTION.xlsx", engine="openpyxl") as writer:
            pd.DataFrame(actual_rows or [{"status": "No step execution records"}]).to_excel(writer, index=False, sheet_name="Steps")
            pd.DataFrame(_rows(actual.get("deviations")) or [{"status": "No explicit deviations"}]).to_excel(writer, index=False, sheet_name="Deviations")
            pd.DataFrame(_rows(actual.get("planner_changes_since_start")) or [{"status": "No Planner edits after Start"}]).to_excel(writer, index=False, sheet_name="Planner changes")
        with pd.ExcelWriter(folder / "RESULTS.xlsx", engine="openpyxl") as writer:
            pd.DataFrame(_rows(linked.get("outcomes")) or [{"status": "No final outcome records"}]).to_excel(writer, index=False, sheet_name="Final outcomes")
            pd.DataFrame(_rows(linked.get("loading")) or [{"status": "No loading result records"}]).to_excel(writer, index=False, sheet_name="Loading")
            pd.DataFrame(_rows(linked.get("cleavage")) or [{"status": "No cleavage result records"}]).to_excel(writer, index=False, sheet_name="Cleavage")
            pd.DataFrame(_rows(linked.get("analytical")) or [{"status": "No analytical result records"}]).to_excel(writer, index=False, sheet_name="Analytical")
            pd.DataFrame(_rows(linked.get("recommendation_traces")) or [{"status": "No recommendation trace records"}]).to_excel(writer, index=False, sheet_name="Recommendation trace")
        _write_xlsx(folder / "ISSUES.xlsx", _rows(linked.get("issues")), "Issues")
        (folder / "RUN_SUMMARY.json").write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        manifest = [
            "SPPS Planner V6 Run Package",
            f"Run ID: {run.get('run_id','')}",
            f"Run name: {run.get('run_name','')}",
            f"Status: {run.get('status','')}",
            f"Repeat of Run ID: {run.get('repeat_of_run_id','')}",
            "",
            "Files:",
            "- PLAN.xlsx",
            "- MATERIALS.xlsx",
            "- CHECKLIST.xlsx",
            "- ACTUAL_EXECUTION.xlsx",
            "- RESULTS.xlsx",
            "- ISSUES.xlsx",
            "- RUN_SUMMARY.json",
        ]
        (folder / "MANIFEST.txt").write_text("\n".join(manifest) + "\n", encoding="utf-8")
        # Build the archive beside the destination and publish it atomically.
        # A compression/write failure must never leave a truncated package at
        # the user-selected output path or destroy a previously valid package.
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{destination.name}.", suffix=".tmp", dir=str(destination.parent)
        )
        os.close(fd)
        temp_zip = Path(temp_name)
        try:
            with zipfile.ZipFile(temp_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(folder.iterdir(), key=lambda p: p.name):
                    archive.write(path, arcname=path.name)
            os.replace(temp_zip, destination)
        except Exception:
            try:
                temp_zip.unlink(missing_ok=True)
            except OSError:
                pass
            raise
    return destination


__all__ = ["build_package"]
