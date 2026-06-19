
from __future__ import annotations

import argparse
import json
from pathlib import Path

from peptiforg_core.public_api import PUBLIC_API_VERSION
from peptiforg_core.workflow_automation_runner import default_workflow_config, save_workflow_config, load_workflow_config, run_workflow
from peptiforg_core.experimental_data_importer import make_experimental_template, export_experimental_import_package
from peptiforg_core.candidate_comparison_dashboard import export_candidate_dashboard
from peptiforg_core.evidence_engine import export_evidence_engine_report_from_project
from peptiforg_core.run_comparison import export_run_comparison_package
from peptiforg_core.runtime_validation import run_runtime_validation
from peptiforg_core.full_package_audit import audit_package
from peptiforg_core.regression_audit import run_regression_audit
from peptiforg_core.release_integrity import audit_release_integrity
from peptiforg_core.release_verify_matrix import verify_release_matrix
from peptiforg_core.release_gate import release_gate_check


def cmd_version(args):
    print(f"Pepforge Public Research Release {PUBLIC_API_VERSION}")


def cmd_init_workflow(args):
    cfg = default_workflow_config(args.project_name)
    path = save_workflow_config(cfg, args.project_dir)
    print(path)


def cmd_run_workflow(args):
    if args.config:
        cfg = load_workflow_config(args.config)
    else:
        cfg = default_workflow_config(args.project_name)
    paths = run_workflow(cfg, args.project_dir)
    print(json.dumps(paths, indent=2, ensure_ascii=False))


def cmd_experimental_template(args):
    print(make_experimental_template(args.output_dir))


def cmd_import_experimental(args):
    paths = export_experimental_import_package(args.input_csv, args.output_dir)
    print(json.dumps(paths, indent=2, ensure_ascii=False))


def cmd_dashboard(args):
    paths = export_candidate_dashboard(
        output_dir=args.output_dir,
        design_candidates_csv=args.design_csv,
        docking_contacts_csv=args.docking_csv,
        external_docking_scores_csv=args.external_csv,
        calibration_predictions_csv=args.calibration_csv,
        experimental_candidate_summary_csv=args.experimental_csv,
    )
    print(json.dumps(paths, indent=2, ensure_ascii=False))


def cmd_evidence_autoscan(args):
    paths = export_evidence_engine_report_from_project(args.project_dir, output_dir=args.output_dir or args.project_dir)
    print(json.dumps(paths, indent=2, ensure_ascii=False))


def cmd_compare_runs(args):
    paths = export_run_comparison_package(
        old_project_dir=args.old_project,
        new_project_dir=args.new_project,
        output_dir=args.output_dir,
        old_dashboard_csv=args.old_dashboard,
        new_dashboard_csv=args.new_dashboard,
        old_evidence_summary_json=args.old_evidence,
        new_evidence_summary_json=args.new_evidence,
    )
    print(json.dumps(paths, indent=2, ensure_ascii=False))



def cmd_validate_runtime(args):
    paths = run_runtime_validation(args.output_dir)
    print(json.dumps(paths, indent=2, ensure_ascii=False))



def cmd_audit_package(args):
    paths = audit_package(args.root_dir, args.output_dir)
    print(json.dumps(paths, indent=2, ensure_ascii=False))



def cmd_regression_audit(args):
    paths = run_regression_audit(args.root_dir, args.output_dir)
    print(json.dumps(paths, indent=2, ensure_ascii=False))



def cmd_release_integrity(args):
    paths = audit_release_integrity(args.root_dir, args.output_dir, run_nested=args.run_nested)
    print(json.dumps(paths, indent=2, ensure_ascii=False))



def cmd_verify_matrix(args):
    paths = verify_release_matrix(args.root_dir, args.output_dir)
    print(json.dumps(paths, indent=2, ensure_ascii=False))



def cmd_release_gate(args):
    paths = release_gate_check(args.root_dir, args.output_dir)
    print(json.dumps(paths, indent=2, ensure_ascii=False))


def build_parser():
    p = argparse.ArgumentParser(
        prog="pepforge_cli",
        description="Pepforge public research CLI. Screening/planning/evidence workflow only; not final binding proof.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("version")
    sp.set_defaults(func=cmd_version)

    sp = sub.add_parser("init-workflow")
    sp.add_argument("--project-dir", required=True)
    sp.add_argument("--project-name", default="Pepforge_Project")
    sp.set_defaults(func=cmd_init_workflow)

    sp = sub.add_parser("run-workflow")
    sp.add_argument("--project-dir", required=True)
    sp.add_argument("--project-name", default="Pepforge_Project")
    sp.add_argument("--config", default="")
    sp.set_defaults(func=cmd_run_workflow)

    sp = sub.add_parser("experimental-template")
    sp.add_argument("--output-dir", required=True)
    sp.set_defaults(func=cmd_experimental_template)

    sp = sub.add_parser("import-experimental")
    sp.add_argument("--input-csv", required=True)
    sp.add_argument("--output-dir", required=True)
    sp.set_defaults(func=cmd_import_experimental)

    sp = sub.add_parser("dashboard")
    sp.add_argument("--output-dir", required=True)
    sp.add_argument("--design-csv", default="")
    sp.add_argument("--docking-csv", default="")
    sp.add_argument("--external-csv", default="")
    sp.add_argument("--calibration-csv", default="")
    sp.add_argument("--experimental-csv", default="")
    sp.set_defaults(func=cmd_dashboard)

    sp = sub.add_parser("evidence-autoscan")
    sp.add_argument("--project-dir", required=True)
    sp.add_argument("--output-dir", default="")
    sp.set_defaults(func=cmd_evidence_autoscan)

    sp = sub.add_parser("validate-runtime")
    sp.add_argument("--output-dir", required=True)
    sp.set_defaults(func=cmd_validate_runtime)

    sp = sub.add_parser("audit-package")
    sp.add_argument("--root-dir", default=str(Path(__file__).resolve().parent))
    sp.add_argument("--output-dir", required=True)
    sp.set_defaults(func=cmd_audit_package)

    sp = sub.add_parser("regression-audit")
    sp.add_argument("--root-dir", default=str(Path(__file__).resolve().parent))
    sp.add_argument("--output-dir", required=True)
    sp.set_defaults(func=cmd_regression_audit)

    sp = sub.add_parser("release-integrity")
    sp.add_argument("--root-dir", default=str(Path(__file__).resolve().parent))
    sp.add_argument("--output-dir", required=True)
    sp.add_argument("--run-nested", action="store_true")
    sp.set_defaults(func=cmd_release_integrity)

    sp = sub.add_parser("verify-matrix")
    sp.add_argument("--root-dir", default=str(Path(__file__).resolve().parent))
    sp.add_argument("--output-dir", required=True)
    sp.set_defaults(func=cmd_verify_matrix)

    sp = sub.add_parser("release-gate")
    sp.add_argument("--root-dir", default=str(Path(__file__).resolve().parent))
    sp.add_argument("--output-dir", required=True)
    sp.set_defaults(func=cmd_release_gate)

    sp = sub.add_parser("compare-runs")
    sp.add_argument("--old-project", required=True)
    sp.add_argument("--new-project", required=True)
    sp.add_argument("--output-dir", required=True)
    sp.add_argument("--old-dashboard", default="")
    sp.add_argument("--new-dashboard", default="")
    sp.add_argument("--old-evidence", default="")
    sp.add_argument("--new-evidence", default="")
    sp.set_defaults(func=cmd_compare_runs)

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    main()
