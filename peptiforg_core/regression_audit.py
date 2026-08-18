
from __future__ import annotations
from pathlib import Path
from typing import Any
import csv, json, subprocess, sys

REGRESSION_AUDIT_VERSION = "3.0.0"

def _write_json(path: Path, payload: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)

def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames=None) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = list(rows[0].keys()) if rows else ["check","status","detail"]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)
    return str(path)

def _write_text(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)

def run_regression_audit(root_dir: str | Path, output_dir: str | Path) -> dict[str, str]:
    root = Path(root_dir)
    out = Path(output_dir) / "regression_audit"
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    def add(check: str, ok: bool, detail: str = ""):
        rows.append({"check": check, "status": "passed" if ok else "failed", "detail": str(detail)})

    try:
        from peptiforg_core.public_api import PUBLIC_API_VERSION
        add("public_api_version", PUBLIC_API_VERSION == REGRESSION_AUDIT_VERSION, PUBLIC_API_VERSION)
    except Exception as exc:
        add("public_api_version", False, repr(exc))

    try:
        from peptiforg_core.experimental_data_importer import export_experimental_import_package
        from peptiforg_core.candidate_comparison_dashboard import export_candidate_dashboard
        from peptiforg_core.run_comparison import export_run_comparison_package

        exp = out / "assay.csv"
        with exp.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["candidate_id","sequence","target","assay_type","value_type","value","unit"])
            w.writeheader()
            w.writerow({"candidate_id":"PDE_0001","sequence":"AAAA","target":"T","assay_type":"SPR","value_type":"Kd","value":"85","unit":"nM"})
            w.writerow({"candidate_id":"PDE_0002","sequence":"BBBB","target":"T","assay_type":"SPR","value_type":"Kd","value":"1.5","unit":"uM"})
        exp_paths = export_experimental_import_package(exp, out)
        add("experimental_import_summary_exists", Path(exp_paths["experimental_candidate_summary"]).exists(), exp_paths["experimental_candidate_summary"])

        design_old = out / "design_old.csv"
        design_new = out / "design_new.csv"
        for path, score1, score2 in [(design_old, "1.0", "0.5"), (design_new, "2.0", "0.5")]:
            with path.open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["candidate_id","sequence","total_score"])
                w.writeheader()
                w.writerow({"candidate_id":"PDE_0001","sequence":"AAAA","total_score":score1})
                w.writerow({"candidate_id":"PDE_0002","sequence":"BBBB","total_score":score2})
        old_dir = out / "old_project"
        new_dir = out / "new_project"
        old_paths = export_candidate_dashboard(old_dir, design_candidates_csv=design_old, experimental_candidate_summary_csv=exp_paths["experimental_candidate_summary"])
        new_paths = export_candidate_dashboard(new_dir, design_candidates_csv=design_new, experimental_candidate_summary_csv=exp_paths["experimental_candidate_summary"])
        add("old_dashboard_exists", Path(old_paths["candidate_comparison_dashboard_csv"]).exists(), old_paths["candidate_comparison_dashboard_csv"])
        add("new_dashboard_exists", Path(new_paths["candidate_comparison_dashboard_csv"]).exists(), new_paths["candidate_comparison_dashboard_csv"])

        cmp_paths = export_run_comparison_package(
            old_dir, new_dir, out,
            old_dashboard_csv=old_paths["candidate_comparison_dashboard_csv"],
            new_dashboard_csv=new_paths["candidate_comparison_dashboard_csv"],
        )
        add("run_comparison_exists", Path(cmp_paths["run_comparison_report"]).exists(), cmp_paths["run_comparison_report"])
    except Exception as exc:
        add("dataflow_experimental_dashboard_compare", False, repr(exc))

    try:
        from peptiforg_core.workflow_automation_runner import default_workflow_config, run_workflow
        wf_dir = out / "workflow_project"
        cfg = default_workflow_config("RegressionAudit")
        wf_paths = run_workflow(cfg, wf_dir)
        add("workflow_report_exists", Path(wf_paths["workflow_run_report"]).exists(), wf_paths["workflow_run_report"])
        add("workflow_manifest_exists", Path(wf_paths["workflow_run_manifest"]).exists(), wf_paths["workflow_run_manifest"])
    except Exception as exc:
        add("workflow_automation", False, repr(exc))

    try:
        cli = root / "pepforge_cli.py"
        proc = subprocess.run([sys.executable, str(cli), "validate-runtime", "--output-dir", str(out / "cli_runtime")], capture_output=True, text=True, timeout=120)
        add("cli_validate_runtime", proc.returncode == 0 and "runtime_validation_summary" in proc.stdout, proc.stdout[-300:] or proc.stderr[-300:])
    except Exception as exc:
        add("cli_validate_runtime", False, repr(exc))

    try:
        cli = root / "pepforge_cli.py"
        proc = subprocess.run([sys.executable, str(cli), "audit-package", "--root-dir", str(root), "--output-dir", str(out / "cli_audit")], capture_output=True, text=True, timeout=180)
        add("cli_audit_package", proc.returncode == 0 and "full_package_audit_summary" in proc.stdout, proc.stdout[-300:] or proc.stderr[-300:])
    except Exception as exc:
        add("cli_audit_package", False, repr(exc))

    passed = sum(1 for r in rows if r["status"] == "passed")
    failed = sum(1 for r in rows if r["status"] == "failed")
    summary = {
        "pepforge_version": REGRESSION_AUDIT_VERSION,
        "passed": passed,
        "failed": failed,
        "results": rows,
        "claim_boundary": "Regression audit checks representative software dataflows only; it is not scientific validation.",
    }

    results_csv = out / "regression_audit_results.csv"
    summary_json = out / "regression_audit_summary.json"
    report_md = out / "regression_audit_report.md"
    _write_csv(results_csv, rows, ["check","status","detail"])
    _write_json(summary_json, summary)
    lines = ["# Pepforge Regression Audit Report", "", f"Version: {REGRESSION_AUDIT_VERSION}", "", f"- Passed: {passed}", f"- Failed: {failed}", "", "| Check | Status | Detail |", "|---|---|---|"]
    for row in rows:
        lines.append(f"| {row['check']} | {row['status']} | {str(row['detail']).replace('|','/')} |")
    lines.append("")
    lines.append("Claim boundary: this checks software dataflow behavior, not binding/affinity truth.")
    _write_text(report_md, "\n".join(lines) + "\n")
    return {
        "regression_audit_results": str(results_csv),
        "regression_audit_summary": str(summary_json),
        "regression_audit_report": str(report_md),
    }

__all__ = ["REGRESSION_AUDIT_VERSION", "run_regression_audit"]
