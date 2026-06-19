
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional
import csv
import json
import time

WORKFLOW_AUTOMATION_VERSION = "3.8.0"

DEFAULT_WORKFLOW_STAGES = [
    "project_session",
    "experimental_template",
    "experimental_import",
    "candidate_dashboard",
    "evidence_autoscan",
]

STAGE_DESCRIPTIONS = {
    "project_session": "Create/update portable project session summary.",
    "experimental_template": "Create an assay CSV template for later experimental import.",
    "experimental_import": "Import experimental assay CSV if configured.",
    "candidate_dashboard": "Build candidate comparison dashboard from configured CSV inputs.",
    "evidence_autoscan": "Auto-scan project folder and build Evidence Engine reports.",
}


def now_timestamp() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def default_workflow_config(project_name: str = "Pepforge_Project") -> dict[str, Any]:
    return {
        "pepforge_version": WORKFLOW_AUTOMATION_VERSION,
        "workflow_schema": "pepforge_workflow_config_v1",
        "project_name": project_name,
        "enabled_stages": list(DEFAULT_WORKFLOW_STAGES),
        "inputs": {
            "experimental_csv": "",
            "design_candidates_csv": "",
            "docking_contacts_csv": "",
            "external_docking_scores_csv": "",
            "calibration_predictions_csv": "",
            "experimental_candidate_summary_csv": "",
        },
        "options": {
            "run_evidence_autoscan": True,
            "create_experimental_template_if_missing": True,
            "build_candidate_dashboard": True,
        },
        "claim_boundary": "Workflow automation orchestrates existing Pepforge outputs. It does not prove final Kd or true binding.",
    }


def save_workflow_config(config: dict[str, Any], output_dir: str | Path) -> str:
    out = Path(output_dir) / "workflow_automation"
    out.mkdir(parents=True, exist_ok=True)
    path = out / "workflow_run_config.json"
    path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)


def load_workflow_config(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Workflow config not found: {p}")
    data = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
    base = default_workflow_config(data.get("project_name", "Pepforge_Project"))
    base.update(data)
    base.setdefault("inputs", {}).update(data.get("inputs", {}))
    base.setdefault("options", {}).update(data.get("options", {}))
    return base


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: Optional[list[str]] = None) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = list(rows[0].keys()) if rows else ["stage", "status", "note"]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return str(path)


def _write_json(path: Path, payload: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)


def _write_text(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


def _safe_imports():
    modules = {}
    try:
        from peptiforg_core.project_session_manager import create_project_session_package
        modules["create_project_session_package"] = create_project_session_package
    except Exception as exc:
        modules["project_session_error"] = repr(exc)

    try:
        from peptiforg_core.experimental_data_importer import make_experimental_template, export_experimental_import_package
        modules["make_experimental_template"] = make_experimental_template
        modules["export_experimental_import_package"] = export_experimental_import_package
    except Exception as exc:
        modules["experimental_error"] = repr(exc)

    try:
        from peptiforg_core.candidate_comparison_dashboard import export_candidate_dashboard
        modules["export_candidate_dashboard"] = export_candidate_dashboard
    except Exception as exc:
        modules["dashboard_error"] = repr(exc)

    try:
        from peptiforg_core.evidence_engine import export_evidence_engine_report_from_project
        modules["export_evidence_engine_report_from_project"] = export_evidence_engine_report_from_project
    except Exception as exc:
        modules["evidence_error"] = repr(exc)

    return modules


def run_workflow(config: dict[str, Any], project_dir: str | Path) -> dict[str, Any]:
    project_dir = Path(project_dir)
    out = project_dir / "workflow_automation"
    out.mkdir(parents=True, exist_ok=True)
    cfg = default_workflow_config(config.get("project_name", "Pepforge_Project"))
    cfg.update(config)
    cfg["inputs"] = {**default_workflow_config().get("inputs", {}), **config.get("inputs", {})}
    cfg["options"] = {**default_workflow_config().get("options", {}), **config.get("options", {})}
    enabled = cfg.get("enabled_stages", list(DEFAULT_WORKFLOW_STAGES))

    mods = _safe_imports()
    stage_rows = []
    artifacts = {}
    started = now_timestamp()

    def add(stage, status, note="", files=None):
        stage_rows.append({
            "stage": stage,
            "status": status,
            "note": note,
            "files": ";".join(files or []),
        })
        if files:
            artifacts[stage] = files

    for stage in enabled:
        if stage == "project_session":
            func = mods.get("create_project_session_package")
            if callable(func):
                try:
                    paths = func(cfg.get("project_name", "Pepforge_Project"), project_dir)
                    add(stage, "completed", STAGE_DESCRIPTIONS.get(stage, ""), list(paths.values()))
                except Exception as exc:
                    add(stage, "failed", repr(exc))
            else:
                add(stage, "skipped", mods.get("project_session_error", "project session module unavailable"))

        elif stage == "experimental_template":
            if not cfg.get("options", {}).get("create_experimental_template_if_missing", True):
                add(stage, "skipped", "disabled in workflow config")
                continue
            func = mods.get("make_experimental_template")
            if callable(func):
                try:
                    path = func(out / "templates")
                    add(stage, "completed", "experimental template generated", [path])
                except Exception as exc:
                    add(stage, "failed", repr(exc))
            else:
                add(stage, "skipped", mods.get("experimental_error", "experimental module unavailable"))

        elif stage == "experimental_import":
            src = cfg.get("inputs", {}).get("experimental_csv", "")
            func = mods.get("export_experimental_import_package")
            if not src:
                add(stage, "skipped", "no experimental_csv configured")
            elif callable(func):
                try:
                    paths = func(src, project_dir)
                    cfg["inputs"]["experimental_candidate_summary_csv"] = paths.get("experimental_candidate_summary", "")
                    add(stage, "completed", "experimental data imported", list(paths.values()))
                except Exception as exc:
                    add(stage, "failed", repr(exc))
            else:
                add(stage, "skipped", mods.get("experimental_error", "experimental module unavailable"))

        elif stage == "candidate_dashboard":
            if not cfg.get("options", {}).get("build_candidate_dashboard", True):
                add(stage, "skipped", "disabled in workflow config")
                continue
            func = mods.get("export_candidate_dashboard")
            if callable(func):
                try:
                    paths = func(
                        output_dir=project_dir,
                        design_candidates_csv=cfg["inputs"].get("design_candidates_csv") or None,
                        docking_contacts_csv=cfg["inputs"].get("docking_contacts_csv") or None,
                        external_docking_scores_csv=cfg["inputs"].get("external_docking_scores_csv") or None,
                        calibration_predictions_csv=cfg["inputs"].get("calibration_predictions_csv") or None,
                        experimental_candidate_summary_csv=cfg["inputs"].get("experimental_candidate_summary_csv") or None,
                    )
                    add(stage, "completed", "candidate dashboard exported", list(paths.values()))
                except Exception as exc:
                    add(stage, "failed", repr(exc))
            else:
                add(stage, "skipped", mods.get("dashboard_error", "dashboard module unavailable"))

        elif stage == "evidence_autoscan":
            if not cfg.get("options", {}).get("run_evidence_autoscan", True):
                add(stage, "skipped", "disabled in workflow config")
                continue
            func = mods.get("export_evidence_engine_report_from_project")
            if callable(func):
                try:
                    paths = func(project_dir, output_dir=project_dir)
                    add(stage, "completed", "Evidence Engine auto-scan completed", list(paths.values()))
                except Exception as exc:
                    add(stage, "failed", repr(exc))
            else:
                add(stage, "skipped", mods.get("evidence_error", "evidence module unavailable"))

        else:
            add(stage, "skipped", "unknown stage")

    completed = now_timestamp()
    status_counts = {}
    for r in stage_rows:
        status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1

    manifest = {
        "pepforge_version": WORKFLOW_AUTOMATION_VERSION,
        "project_name": cfg.get("project_name"),
        "project_dir": str(project_dir),
        "started_at": started,
        "completed_at": completed,
        "stage_status_counts": status_counts,
        "artifacts": artifacts,
        "claim_boundary": cfg.get("claim_boundary"),
    }

    config_path = out / "workflow_run_config.json"
    _write_json(config_path, cfg)
    stage_csv = out / "workflow_stage_results.csv"
    _write_csv(stage_csv, stage_rows, ["stage", "status", "note", "files"])
    manifest_path = out / "workflow_run_manifest.json"
    _write_json(manifest_path, manifest)
    claim_guard = out / "workflow_claim_guard_table.csv"
    _write_csv(claim_guard, [
        {"claim": "workflow automation proves binding", "status": "blocked", "safe_expression": "workflow automation organizes existing evidence"},
        {"claim": "all stages passed means final Kd is proven", "status": "blocked", "safe_expression": "all stages passed means workflow artifacts were generated"},
        {"claim": "workflow report can support review", "status": "allowed_with_qualification", "safe_expression": "review with method limitations and external validation"},
    ])
    report = out / "workflow_run_report.md"
    stage_lines = "\n".join([f"| {r['stage']} | {r['status']} | {r['note']} |" for r in stage_rows])
    _write_text(report, f"""# Pepforge Workflow Automation Report

## Summary

- Project: `{cfg.get("project_name")}`
- Started: {started}
- Completed: {completed}

## Stage results

| Stage | Status | Note |
|---|---|---|
{stage_lines}

## Claim boundary

{cfg.get("claim_boundary")}
""")
    return {
        "workflow_run_config": str(config_path),
        "workflow_stage_results": str(stage_csv),
        "workflow_run_manifest": str(manifest_path),
        "workflow_claim_guard_table": str(claim_guard),
        "workflow_run_report": str(report),
    }


def create_default_workflow_package(project_dir: str | Path, project_name: str = "Pepforge_Project") -> dict[str, str]:
    cfg = default_workflow_config(project_name)
    config_path = save_workflow_config(cfg, project_dir)
    paths = run_workflow(cfg, project_dir)
    paths["workflow_run_config"] = config_path
    return paths


__all__ = [
    "WORKFLOW_AUTOMATION_VERSION",
    "DEFAULT_WORKFLOW_STAGES",
    "default_workflow_config",
    "save_workflow_config",
    "load_workflow_config",
    "run_workflow",
    "create_default_workflow_package",
]
