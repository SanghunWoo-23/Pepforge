from __future__ import annotations

"""Pepforge Project Session Manager v3.5.0.

This module adds a lightweight project/session layer so a Pepforge workflow can be
saved, resumed, audited, and shared without relying on scattered output files.

It tracks:
- project identity,
- current workflow stage,
- important input/output file paths,
- generated evidence packages,
- next recommended actions,
- claim boundary notes.

The session file is JSON and intentionally portable.
"""

from pathlib import Path
from typing import Any, Dict, Optional
import json
import time
import csv

PROJECT_SESSION_VERSION = "3.5.0"

DEFAULT_STAGE_ORDER = [
    "design_engine",
    "spps_planner",
    "structure_builder",
    "rcsb_target_fetch",
    "target_preparation",
    "binding_site_selector",
    "docking_workbench",
    "external_docking_import",
    "external_md_import",
    "calibration_dataset_mode",
    "calibration_model_cards",
    "evidence_engine",
]


def now_timestamp() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def new_project_session(
    project_name: str,
    project_dir: str | Path,
    description: str = "",
    owner: str = "",
) -> dict[str, Any]:
    base = Path(project_dir)
    return {
        "pepforge_version": PROJECT_SESSION_VERSION,
        "session_schema": "pepforge_project_session_v1",
        "project_name": project_name or "Pepforge_Project",
        "project_dir": str(base),
        "description": description,
        "owner": owner,
        "created_at": now_timestamp(),
        "updated_at": now_timestamp(),
        "current_stage": "design_engine",
        "stage_order": list(DEFAULT_STAGE_ORDER),
        "stages": {stage: {"status": "not_started", "files": [], "notes": ""} for stage in DEFAULT_STAGE_ORDER},
        "inputs": {},
        "outputs": {},
        "evidence_files": {},
        "next_actions": [
            "Create or import peptide candidates.",
            "Generate SPPS plan if synthesis is intended.",
            "Prepare target structure before docking/contact interpretation.",
        ],
        "claim_boundary": "Project session tracks workflow state. It does not prove final Kd or true binding.",
    }


def load_project_session(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Project session not found: {p}")
    data = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
    return normalize_project_session(data, p.parent)


def normalize_project_session(data: dict[str, Any], project_dir: str | Path | None = None) -> dict[str, Any]:
    data = dict(data or {})
    data.setdefault("pepforge_version", PROJECT_SESSION_VERSION)
    data.setdefault("session_schema", "pepforge_project_session_v1")
    data.setdefault("project_name", "Pepforge_Project")
    data.setdefault("project_dir", str(project_dir or "."))
    data.setdefault("created_at", now_timestamp())
    data["updated_at"] = now_timestamp()
    data.setdefault("current_stage", "design_engine")
    data.setdefault("stage_order", list(DEFAULT_STAGE_ORDER))
    data.setdefault("stages", {})
    for stage in data["stage_order"]:
        data["stages"].setdefault(stage, {"status": "not_started", "files": [], "notes": ""})
    data.setdefault("inputs", {})
    data.setdefault("outputs", {})
    data.setdefault("evidence_files", {})
    data.setdefault("next_actions", [])
    data.setdefault("claim_boundary", "Project session tracks workflow state. It does not prove final Kd or true binding.")
    return data


def save_project_session(session: dict[str, Any], path: str | Path | None = None) -> str:
    session = normalize_project_session(session, session.get("project_dir", "."))
    p = Path(path) if path else Path(session["project_dir"]) / "pepforge_project_session.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(session, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(p)


def mark_stage(
    session: dict[str, Any],
    stage: str,
    status: str = "completed",
    files: Optional[list[str]] = None,
    notes: str = "",
) -> dict[str, Any]:
    session = normalize_project_session(session, session.get("project_dir", "."))
    if stage not in session["stages"]:
        session["stage_order"].append(stage)
        session["stages"][stage] = {"status": "not_started", "files": [], "notes": ""}
    entry = session["stages"][stage]
    entry["status"] = status
    if files:
        existing = list(entry.get("files", []))
        for f in files:
            if f and f not in existing:
                existing.append(f)
        entry["files"] = existing
    if notes:
        entry["notes"] = notes
    session["current_stage"] = stage
    session["updated_at"] = now_timestamp()
    session["next_actions"] = recommend_next_actions(session)
    return session


def attach_file(session: dict[str, Any], category: str, key: str, path: str | Path) -> dict[str, Any]:
    session = normalize_project_session(session, session.get("project_dir", "."))
    session.setdefault(category, {})
    session[category][key] = str(path)
    session["updated_at"] = now_timestamp()
    session["next_actions"] = recommend_next_actions(session)
    return session


def stage_progress_rows(session: dict[str, Any]) -> list[dict[str, Any]]:
    session = normalize_project_session(session, session.get("project_dir", "."))
    rows = []
    for idx, stage in enumerate(session.get("stage_order", []), start=1):
        entry = session.get("stages", {}).get(stage, {})
        files = entry.get("files", []) or []
        rows.append({
            "order": idx,
            "stage": stage,
            "status": entry.get("status", "not_started"),
            "file_count": len(files),
            "files": ";".join(files[:5]),
            "notes": entry.get("notes", ""),
        })
    return rows


def recommend_next_actions(session: dict[str, Any]) -> list[str]:
    session = normalize_project_session(session, session.get("project_dir", "."))
    stages = session.get("stages", {})
    actions = []
    def done(stage):
        return stages.get(stage, {}).get("status") in {"completed", "done", "passed"}

    if not done("design_engine"):
        actions.append("Run Design Engine or import candidate peptides.")
    if done("design_engine") and not done("spps_planner"):
        actions.append("Generate SPPS Planner output for synthesis feasibility.")
    if not done("target_preparation"):
        actions.append("Fetch/load target and run Target Preparation before interpreting contacts.")
    if done("target_preparation") and not done("binding_site_selector"):
        actions.append("Run Binding Site Selector to document selected chains/ligand/seed region.")
    if done("binding_site_selector") and not done("docking_workbench"):
        actions.append("Run Docking Workbench screening/contact analysis.")
    if done("docking_workbench") and not done("external_docking_import"):
        actions.append("Import external docking scores if stronger computational evidence is needed.")
    if done("external_docking_import") and not done("calibration_dataset_mode"):
        actions.append("Build Calibration Dataset Mode if measured/literature assay records are available.")
    if not done("evidence_engine"):
        actions.append("Run Evidence Engine at the end to generate claim guard and missing-validation checklist.")
    if not actions:
        actions.append("Workflow is complete enough for review; check claim guard before any publication wording.")
    return actions


def export_session_summary(session: dict[str, Any], output_dir: str | Path) -> dict[str, str]:
    out = Path(output_dir) / "project_session"
    out.mkdir(parents=True, exist_ok=True)
    session = normalize_project_session(session, session.get("project_dir", out))

    session_json = out / "pepforge_project_session.json"
    save_project_session(session, session_json)

    rows = stage_progress_rows(session)
    progress_csv = out / "project_stage_progress.csv"
    with progress_csv.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["order","stage","status","file_count","files","notes"])
        w.writeheader()
        for r in rows:
            w.writerow(r)

    next_csv = out / "project_next_actions.csv"
    with next_csv.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["next_action"])
        w.writeheader()
        for a in session.get("next_actions", []):
            w.writerow({"next_action": a})

    summary_md = out / "project_session_summary.md"
    table = "\n".join(
        f"| {r['order']} | {r['stage']} | {r['status']} | {r['file_count']} | {r['notes']} |"
        for r in rows
    )
    actions = "\n".join(f"- {a}" for a in session.get("next_actions", []))
    summary_md.write_text(f"""# Pepforge Project Session Summary

## Project

- Name: `{session.get("project_name")}`
- Current stage: `{session.get("current_stage")}`
- Updated: `{session.get("updated_at")}`

## Stage progress

| Order | Stage | Status | Files | Notes |
|---:|---|---|---:|---|
{table}

## Next actions

{actions}

## Claim boundary

{session.get("claim_boundary")}
""", encoding="utf-8")

    manifest = out / "project_session_manifest.json"
    manifest.write_text(json.dumps({
        "pepforge_version": PROJECT_SESSION_VERSION,
        "files": {
            "session_json": str(session_json),
            "stage_progress": str(progress_csv),
            "next_actions": str(next_csv),
            "summary": str(summary_md),
        },
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "session_json": str(session_json),
        "project_stage_progress": str(progress_csv),
        "project_next_actions": str(next_csv),
        "project_session_summary": str(summary_md),
        "project_session_manifest": str(manifest),
    }


def create_project_session_package(
    project_name: str,
    project_dir: str | Path,
    description: str = "",
    owner: str = "",
) -> dict[str, str]:
    session = new_project_session(project_name, project_dir, description=description, owner=owner)
    return export_session_summary(session, project_dir)


__all__ = [
    "PROJECT_SESSION_VERSION",
    "DEFAULT_STAGE_ORDER",
    "new_project_session",
    "load_project_session",
    "save_project_session",
    "mark_stage",
    "attach_file",
    "stage_progress_rows",
    "recommend_next_actions",
    "export_session_summary",
    "create_project_session_package",
]
