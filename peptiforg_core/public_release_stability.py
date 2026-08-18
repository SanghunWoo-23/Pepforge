
from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import csv

STABILITY_REPORT_VERSION = "3.0.0"

PUBLIC_OUTPUT_CONTRACT = {
    "workflow_automation": [
        "workflow_run_config.json",
        "workflow_stage_results.csv",
        "workflow_run_manifest.json",
        "workflow_claim_guard_table.csv",
        "workflow_run_report.md",
    ],
    "candidate_comparison_dashboard": [
        "candidate_comparison_dashboard.csv",
        "candidate_comparison_dashboard.md",
        "candidate_dashboard_top.svg",
        "candidate_dashboard_summary.json",
        "candidate_dashboard_manifest.json",
    ],
    "experimental_data_import": [
        "experimental_data_normalized.csv",
        "experimental_candidate_summary.csv",
        "experimental_import_summary.json",
        "experimental_claim_guard_table.csv",
        "experimental_import_report.md",
        "experimental_import_manifest.json",
    ],
    "run_comparison": [
        "changed_files_inventory.csv",
        "candidate_rank_delta.csv",
        "evidence_delta_summary.json",
        "run_comparison_claim_guard_table.csv",
        "run_comparison_report.md",
        "run_comparison_manifest.json",
    ],
    "pepforge_evidence_engine": [
        "evidence_components.csv",
        "evidence_summary.json",
        "evidence_claim_guard_table.csv",
        "missing_validation_checklist.csv",
        "evidence_report.md",
        "evidence_report_readable.md",
    ],
}


def export_public_stability_report(output_dir: str | Path) -> dict[str, str]:
    out = Path(output_dir) / "public_release_stability"
    out.mkdir(parents=True, exist_ok=True)

    contract_json = out / "public_output_contract.json"
    contract_json.write_text(json.dumps({
        "pepforge_version": STABILITY_REPORT_VERSION,
        "public_output_contract": PUBLIC_OUTPUT_CONTRACT,
        "claim_boundary": "Public output contract documents stable file names. It does not validate scientific claims.",
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    rows = []
    for module, files in PUBLIC_OUTPUT_CONTRACT.items():
        for f in files:
            rows.append({"module": module, "output_file": f, "status": "public_stable"})
    contract_csv = out / "public_output_contract.csv"
    with contract_csv.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["module", "output_file", "status"])
        w.writeheader()
        for r in rows:
            w.writerow(r)

    report = out / "public_release_stability_report.md"
    lines = ["# Pepforge Public Release Stability Report", "", f"Version: {STABILITY_REPORT_VERSION}", ""]
    for module, files in PUBLIC_OUTPUT_CONTRACT.items():
        lines.append(f"## {module}")
        for f in files:
            lines.append(f"- `{f}`")
        lines.append("")
    lines.append("Claim boundary: stable output naming is not scientific validation.")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return {
        "public_output_contract_json": str(contract_json),
        "public_output_contract_csv": str(contract_csv),
        "public_release_stability_report": str(report),
    }


__all__ = ["STABILITY_REPORT_VERSION", "PUBLIC_OUTPUT_CONTRACT", "export_public_stability_report"]
