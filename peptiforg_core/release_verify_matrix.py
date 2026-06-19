
from __future__ import annotations
from pathlib import Path
from typing import Any
import csv, json, subprocess, sys, py_compile

RELEASE_VERIFY_VERSION = "4.2.0"

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

def _write_json(path: Path, payload: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)

def _write_text(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)

def verify_release_matrix(root_dir: str | Path, output_dir: str | Path) -> dict[str, str]:
    root = Path(root_dir)
    out = Path(output_dir) / "release_verify_matrix"
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    def add(check: str, ok: bool, detail: str = ""):
        rows.append({"check": check, "status": "passed" if ok else "failed", "detail": str(detail)})

    # Version and required files
    version_file = root / "VERSION.txt"
    add("version_file", version_file.exists() and version_file.read_text(encoding="utf-8", errors="ignore").strip() == RELEASE_VERIFY_VERSION, version_file.read_text(encoding="utf-8", errors="ignore").strip() if version_file.exists() else "missing")

    required = [
        "pepforge_cli.py",
        "peptiforg_core/public_api.py",
        "peptiforg_core/runtime_validation.py",
        "peptiforg_core/full_package_audit.py",
        "peptiforg_core/regression_audit.py",
        "peptiforg_core/release_integrity.py",
        "docs/PUBLIC_API_CONTRACT.md",
        "docs/PUBLIC_OUTPUT_CONTRACT.md",
    ]
    for rel in required:
        add("required_" + rel, (root / rel).exists(), rel)

    # Compile key public modules instead of full tree for fast release gate
    compile_targets = [
        root / "pepforge_cli.py",
        root / "peptiforg_core" / "public_api.py",
        root / "peptiforg_core" / "runtime_validation.py",
        root / "peptiforg_core" / "full_package_audit.py",
        root / "peptiforg_core" / "regression_audit.py",
        root / "peptiforg_core" / "release_integrity.py",
    ]
    compile_errors = []
    for target in compile_targets:
        try:
            py_compile.compile(str(target), doraise=True)
        except Exception as exc:
            compile_errors.append({"file": str(target.relative_to(root)), "error": repr(exc)})
    add("compile_public_modules", not compile_errors, f"{len(compile_targets)} modules; {len(compile_errors)} errors")

    # CLI smoke matrix, bounded to lightweight commands only
    try:
        proc = subprocess.run([sys.executable, str(root / "pepforge_cli.py"), "version"], capture_output=True, text=True, timeout=30)
        add("cli_version", proc.returncode == 0 and RELEASE_VERIFY_VERSION in proc.stdout, proc.stdout.strip() or proc.stderr.strip())
    except Exception as exc:
        add("cli_version", False, repr(exc))

    try:
        proc = subprocess.run([sys.executable, str(root / "pepforge_cli.py"), "experimental-template", "--output-dir", str(out / "template")], capture_output=True, text=True, timeout=30)
        add("cli_experimental_template", proc.returncode == 0 and "experimental_data_import_template.csv" in proc.stdout, proc.stdout.strip()[-300:] or proc.stderr.strip()[-300:])
    except Exception as exc:
        add("cli_experimental_template", False, repr(exc))

    try:
        proc = subprocess.run([sys.executable, str(root / "pepforge_cli.py"), "init-workflow", "--project-dir", str(out / "workflow_init"), "--project-name", "VerifyMatrix"], capture_output=True, text=True, timeout=30)
        add("cli_init_workflow", proc.returncode == 0 and "workflow_run_config.json" in proc.stdout, proc.stdout.strip()[-300:] or proc.stderr.strip()[-300:])
    except Exception as exc:
        add("cli_init_workflow", False, repr(exc))

    # Packaging artifacts
    artifact_hits = []
    for p in root.rglob("*"):
        rel = p.relative_to(root).as_posix()
        if p.is_file() and p.suffix.lower() in {".pyc", ".pyo", ".exe"}:
            artifact_hits.append(rel)
        if p.is_dir() and p.name in {"__pycache__", ".pytest_cache", ".mypy_cache", "build", "dist", "outputs"}:
            artifact_hits.append(rel + "/")
    add("no_packaging_artifacts", not artifact_hits, f"{len(artifact_hits)} hits")

    passed = sum(1 for r in rows if r["status"] == "passed")
    failed = sum(1 for r in rows if r["status"] == "failed")
    summary = {
        "pepforge_version": RELEASE_VERIFY_VERSION,
        "passed": passed,
        "failed": failed,
        "compile_errors": compile_errors,
        "artifact_hits": artifact_hits,
        "claim_boundary": "Release verification matrix checks software/package entrypoints only; it is not scientific validation.",
    }

    results_csv = out / "release_verify_matrix_results.csv"
    summary_json = out / "release_verify_matrix_summary.json"
    report_md = out / "release_verify_matrix_report.md"
    _write_csv(results_csv, rows, ["check","status","detail"])
    _write_json(summary_json, summary)
    lines = ["# Pepforge Release Verification Matrix", "", f"Version: {RELEASE_VERIFY_VERSION}", "", f"- Passed: {passed}", f"- Failed: {failed}", "", "| Check | Status | Detail |", "|---|---|---|"]
    for row in rows:
        lines.append(f"| {row['check']} | {row['status']} | {str(row['detail']).replace('|','/')} |")
    lines.append("")
    lines.append("Claim boundary: this checks release entrypoints, not binding/affinity truth.")
    _write_text(report_md, "\n".join(lines) + "\n")
    return {
        "release_verify_matrix_results": str(results_csv),
        "release_verify_matrix_summary": str(summary_json),
        "release_verify_matrix_report": str(report_md),
    }

__all__ = ["RELEASE_VERIFY_VERSION", "verify_release_matrix"]
