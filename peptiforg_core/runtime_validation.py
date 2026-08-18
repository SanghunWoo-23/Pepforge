
from __future__ import annotations

"""Pepforge runtime validation checks v3.0.0.

This module provides lightweight runtime smoke checks for public CLI/API paths.
It is intended for release QA, not scientific validation.
"""

from pathlib import Path
from typing import Any
import csv
import json
import tempfile

RUNTIME_VALIDATION_VERSION = "3.0.0"


def run_runtime_validation(output_dir: str | Path) -> dict[str, Any]:
    out = Path(output_dir) / "runtime_validation"
    out.mkdir(parents=True, exist_ok=True)
    results = []

    def add(name: str, ok: bool, detail: str = ""):
        results.append({"check": name, "status": "passed" if ok else "failed", "detail": detail})

    try:
        from peptiforg_core.public_api import PUBLIC_API_VERSION, default_workflow_config
        add("public_api_version", PUBLIC_API_VERSION == RUNTIME_VALIDATION_VERSION, PUBLIC_API_VERSION)
        add("public_api_default_workflow", callable(default_workflow_config), "default_workflow_config import")
    except Exception as exc:
        add("public_api_import", False, repr(exc))

    try:
        from peptiforg_core.workflow_automation_runner import default_workflow_config, run_workflow
        wf_dir = out / "workflow_smoke"
        wf_dir.mkdir(parents=True, exist_ok=True)
        cfg = default_workflow_config("RuntimeSmoke")
        paths = run_workflow(cfg, wf_dir)
        add("workflow_stage_results", Path(paths["workflow_stage_results"]).exists(), paths.get("workflow_stage_results", ""))
        add("workflow_manifest", Path(paths["workflow_run_manifest"]).exists(), paths.get("workflow_run_manifest", ""))
    except Exception as exc:
        add("workflow_runner", False, repr(exc))

    try:
        from peptiforg_core.experimental_data_importer import export_experimental_import_package
        exp_dir = out / "experimental_smoke"
        exp_dir.mkdir(parents=True, exist_ok=True)
        assay = exp_dir / "assay.csv"
        with assay.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["candidate_id","sequence","target","assay_type","value_type","value","unit"])
            w.writeheader()
            w.writerow({"candidate_id":"PDE_0001","sequence":"AAAA","target":"T","assay_type":"SPR","value_type":"Kd","value":"85","unit":"nM"})
        paths = export_experimental_import_package(assay, exp_dir)
        add("experimental_candidate_summary", Path(paths["experimental_candidate_summary"]).exists(), paths.get("experimental_candidate_summary", ""))
    except Exception as exc:
        add("experimental_import", False, repr(exc))

    try:
        from peptiforg_core.candidate_comparison_dashboard import export_candidate_dashboard
        dash_dir = out / "dashboard_smoke"
        dash_dir.mkdir(parents=True, exist_ok=True)
        design = dash_dir / "design.csv"
        with design.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["candidate_id","sequence","total_score"])
            w.writeheader()
            w.writerow({"candidate_id":"PDE_0001","sequence":"AAAA","total_score":"2.0"})
        paths = export_candidate_dashboard(dash_dir, design_candidates_csv=design)
        add("candidate_dashboard_csv", Path(paths["candidate_comparison_dashboard_csv"]).exists(), paths.get("candidate_comparison_dashboard_csv", ""))
    except Exception as exc:
        add("candidate_dashboard", False, repr(exc))

    try:
        from peptiforg_core.run_comparison import export_run_comparison_package
        cmp_dir = out / "comparison_smoke"
        old = cmp_dir / "old"
        new = cmp_dir / "new"
        old.mkdir(parents=True, exist_ok=True)
        new.mkdir(parents=True, exist_ok=True)
        (old / "x.txt").write_text("old", encoding="utf-8")
        (new / "x.txt").write_text("new", encoding="utf-8")
        paths = export_run_comparison_package(old, new, cmp_dir)
        add("run_comparison_report", Path(paths["run_comparison_report"]).exists(), paths.get("run_comparison_report", ""))
    except Exception as exc:
        add("run_comparison", False, repr(exc))

    try:
        from peptiforg_core.public_release_stability import export_public_stability_report
        paths = export_public_stability_report(out)
        add("public_stability_report", Path(paths["public_release_stability_report"]).exists(), paths.get("public_release_stability_report", ""))
    except Exception as exc:
        add("public_stability", False, repr(exc))

    passed = sum(1 for r in results if r["status"] == "passed")
    failed = sum(1 for r in results if r["status"] == "failed")
    summary = {
        "pepforge_version": RUNTIME_VALIDATION_VERSION,
        "passed": passed,
        "failed": failed,
        "results": results,
        "claim_boundary": "Runtime validation checks software execution paths only; it is not scientific validation.",
    }

    summary_json = out / "runtime_validation_summary.json"
    summary_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    csv_path = out / "runtime_validation_results.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["check","status","detail"])
        w.writeheader()
        for r in results:
            w.writerow(r)

    report = out / "runtime_validation_report.md"
    lines = ["# Pepforge Runtime Validation Report", "", f"Version: {RUNTIME_VALIDATION_VERSION}", "", f"- Passed: {passed}", f"- Failed: {failed}", "", "| Check | Status | Detail |", "|---|---|---|"]
    for r in results:
        lines.append(f"| {r['check']} | {r['status']} | {str(r['detail']).replace('|','/')} |")
    lines.append("")
    lines.append("Claim boundary: this validates runtime paths, not binding/affinity claims.")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return {
        "runtime_validation_summary": str(summary_json),
        "runtime_validation_results": str(csv_path),
        "runtime_validation_report": str(report),
    }


__all__ = ["RUNTIME_VALIDATION_VERSION", "run_runtime_validation"]
