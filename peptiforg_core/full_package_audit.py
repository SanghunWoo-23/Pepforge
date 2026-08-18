
from __future__ import annotations
import logging
LOGGER = logging.getLogger(__name__)

"""Pepforge full package audit for the V3.0.0 public package.

This module performs a packaging/runtime/documentation audit for the public
research package. It does not perform scientific validation.
"""

from pathlib import Path
from typing import Any
import csv
import json
import py_compile
import re
import subprocess
import sys

FULL_PACKAGE_AUDIT_VERSION = "3.0.0"

TEXT_EXTS = {".md",".txt",".py",".iss",".spec",".yml",".yaml",".json",".bat",".cff",".ini"}


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
        for r in rows:
            w.writerow(r)
    return str(path)


def _write_text(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


def audit_package(root_dir: str | Path, output_dir: str | Path) -> dict[str, str]:
    root = Path(root_dir)
    out = Path(output_dir) / "full_package_audit"
    out.mkdir(parents=True, exist_ok=True)

    rows = []
    def add(check: str, ok: bool, detail: str = ""):
        rows.append({"check": check, "status": "passed" if ok else "failed", "detail": str(detail)})

    # metadata checks
    version_file = root / "VERSION.txt"
    add("version_file_exists", version_file.exists(), version_file)
    if version_file.exists():
        add("version_file_matches_release", version_file.read_text(encoding="utf-8", errors="ignore").strip() == FULL_PACKAGE_AUDIT_VERSION, version_file.read_text(encoding="utf-8", errors="ignore").strip())

    citation = root / "CITATION.cff"
    add("citation_exists", citation.exists(), citation)
    if citation.exists():
        s = citation.read_text(encoding="utf-8", errors="ignore")
        add("citation_cff_schema_1_2_0", 'cff-version: "1.2.0"' in s or "cff-version: 1.2.0" in s, "cff-version")
        add("citation_software_version_matches_release", f'version: "{FULL_PACKAGE_AUDIT_VERSION}"' in s or f"version: {FULL_PACKAGE_AUDIT_VERSION}" in s, "software version")

    # required public files
    required = [
        "README.md", "README_KO.md", "MANUAL_EN.md", "MANUAL_KO.md",
        "pepforge_cli.py", "peptiforg_core/public_api.py", "peptiforg_core/runtime_validation.py",
        "peptiforg_core/public_release_stability.py", "docs/PUBLIC_API_CONTRACT.md",
        "docs/PUBLIC_OUTPUT_CONTRACT.md",
    ]
    for rel in required:
        add(f"required_file_{rel}", (root / rel).exists(), rel)

    # compile all python files except generated hidden cache
    compile_errors = []
    py_count = 0
    for p in sorted(root.rglob("*.py")):
        if "__pycache__" in p.as_posix():
            continue
        py_count += 1
        try:
            py_compile.compile(str(p), doraise=True)
        except Exception as exc:
            compile_errors.append({"file": str(p.relative_to(root)), "error": repr(exc)})
    add("python_compile_all", not compile_errors, f"{py_count} files checked; {len(compile_errors)} errors")

    # CLI smoke
    try:
        proc = subprocess.run([sys.executable, str(root / "pepforge_cli.py"), "version"], capture_output=True, text=True, timeout=30)
        add("cli_version_command", proc.returncode == 0 and FULL_PACKAGE_AUDIT_VERSION in proc.stdout, proc.stdout.strip() or proc.stderr.strip())
    except Exception as exc:
        add("cli_version_command", False, repr(exc))

    # runtime validation smoke
    try:
        proc = subprocess.run([sys.executable, str(root / "pepforge_cli.py"), "validate-runtime", "--output-dir", str(out / "cli_runtime")], capture_output=True, text=True, timeout=90)
        add("cli_validate_runtime_command", proc.returncode == 0 and "runtime_validation_summary" in proc.stdout, proc.stdout.strip()[-500:] or proc.stderr.strip()[-500:])
    except Exception as exc:
        add("cli_validate_runtime_command", False, repr(exc))

    # Clean Python cache generated during audit before packaging scan.
    for cache_name in ["__pycache__", ".pytest_cache", ".mypy_cache"]:
        for cache_dir in list(root.rglob(cache_name)):
            if cache_dir.is_dir():
                import shutil
                shutil.rmtree(cache_dir, ignore_errors=True)
    for generated in list(root.rglob("*.pyc")) + list(root.rglob("*.pyo")):
        try:
            generated.unlink()
        except Exception:
            LOGGER.debug("Optional operation skipped", exc_info=True)
    # stale/bad artifact scan
    stale_hits = []
    bad_artifacts = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if p.suffix.lower() in {".pyc",".pyo",".exe"}:
            bad_artifacts.append(rel)
        if any(part in rel for part in ["__pycache__", ".pytest_cache", "/build/", "/dist/", "/outputs/"]):
            bad_artifacts.append(rel)
        if p.suffix.lower() in TEXT_EXTS:
            text = p.read_text(encoding="utf-8", errors="ignore")
            if re.search(r"\\bv8[._-]" + r"7\\b|\\bv8[._-]" + r"8\\b|\\bV8[_-]", text, re.I):
                stale_hits.append(rel)
            if ("cff-version: " + "\"4.0.3\"") in text:
                stale_hits.append(rel + " bad cff-version")
    add("no_stale_internal_names", not stale_hits, f"{len(stale_hits)} hits")
    add("no_runtime_artifacts", not bad_artifacts, f"{len(bad_artifacts)} hits")

    passed = sum(1 for r in rows if r["status"] == "passed")
    failed = sum(1 for r in rows if r["status"] == "failed")
    summary = {
        "pepforge_version": FULL_PACKAGE_AUDIT_VERSION,
        "passed": passed,
        "failed": failed,
        "compile_errors": compile_errors,
        "stale_hits": stale_hits,
        "bad_artifacts": bad_artifacts,
        "claim_boundary": "Full package audit validates software/package execution paths only; it is not scientific validation.",
    }

    results_csv = out / "full_package_audit_results.csv"
    summary_json = out / "full_package_audit_summary.json"
    report_md = out / "full_package_audit_report.md"
    _write_csv(results_csv, rows, ["check","status","detail"])
    _write_json(summary_json, summary)

    lines = [
        "# Pepforge Full Package Audit Report",
        "",
        f"Version: {FULL_PACKAGE_AUDIT_VERSION}",
        "",
        f"- Passed: {passed}",
        f"- Failed: {failed}",
        "",
        "| Check | Status | Detail |",
        "|---|---|---|",
    ]
    for r in rows:
        lines.append(f"| {r['check']} | {r['status']} | {str(r['detail']).replace('|','/')} |")
    lines.append("")
    lines.append("Claim boundary: this report checks package/runtime integrity, not binding or affinity claims.")
    _write_text(report_md, "\n".join(lines) + "\n")

    return {
        "full_package_audit_results": str(results_csv),
        "full_package_audit_summary": str(summary_json),
        "full_package_audit_report": str(report_md),
    }


__all__ = ["FULL_PACKAGE_AUDIT_VERSION", "audit_package"]
