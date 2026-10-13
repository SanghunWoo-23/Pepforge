from __future__ import annotations

"""Pepforge V5 FINAL software-release audit and immutable package manifest.

This is an engineering release gate. It deliberately does not convert missing
external protein-peptide benchmark evidence into a scientific PASS.
"""

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
import csv
import hashlib
import json

from .release_gate import release_gate_check
from .public_peptide_benchmark_v1 import PUBLIC_57_CASES

V5_FINAL_RELEASE_AUDIT_VERSION = "1.0.0"
V5_FINAL_VERSION = "5.0.0"


@dataclass(frozen=True)
class V5FinalPolicy:
    expected_public_benchmark_cases: int = 57
    require_public_registry: bool = True
    require_claim_guards: bool = True
    require_final_cli_surfaces: bool = True
    note: str = "Engineering release criteria for Pepforge V5.0.0 FINAL; not a scientific accuracy standard."


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _registry_summary(root: Path) -> dict[str, Any]:
    path = root / "data" / "public_benchmarks" / "public_57_registry.csv"
    if not path.is_file():
        return {"status": "MISSING", "path": str(path), "count": 0}
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = [dict(r) for r in csv.DictReader(fh)]
    ids = [str(r.get("target_id") or "").upper() for r in rows]
    split_counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get("split") or "unspecified").lower()
        split_counts[key] = split_counts.get(key, 0) + 1
    return {
        "status": "PASS" if len(rows) == len(PUBLIC_57_CASES) and len(set(ids)) == len(rows) else "FAIL",
        "path": str(path),
        "count": len(rows),
        "unique_target_ids": len(set(ids)),
        "split_counts": split_counts,
        "sha256": _sha256(path),
    }


def _package_inventory(root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    bad: list[str] = []
    excluded_dirs = {"__pycache__", ".pytest_cache", ".git"}
    excluded_suffixes = {".pyc", ".pyo"}
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root)
        parts = set(rel.parts)
        if parts & excluded_dirs or path.suffix.lower() in excluded_suffixes:
            bad.append(str(rel))
            continue
        records.append({"path": str(rel).replace("\\", "/"), "size": path.stat().st_size, "sha256": _sha256(path)})
    return records, bad


def audit_v5_final_release(root_dir: str | Path, output_dir: str | Path, *, policy: V5FinalPolicy | None = None) -> dict[str, Any]:
    pol = policy or V5FinalPolicy()
    root = Path(root_dir).expanduser().resolve()
    out = Path(output_dir).expanduser().resolve(); out.mkdir(parents=True, exist_ok=True)

    gate_paths = release_gate_check(root, out / "release_gate")
    gate_json = Path(gate_paths["release_gate_summary"])
    gate = json.loads(gate_json.read_text(encoding="utf-8"))
    gate_pass = int(gate.get("failed", 1)) == 0 and int(gate.get("passed", 0)) > 0

    required = [
        "pepforge_cli.py", "main_launcher.py", "SCIENTIFIC_QUALITY_POLICY.md",
        "NATIVE_VALIDATION_PROTOCOL.md", "peptiforg_core/native_docking_v1.py",
        "peptiforg_core/public_peptide_benchmark_v1.py", "peptiforg_core/uniprot_bridge_v1.py",
        "peptiforg_core/native_docking_tuning_v1.py", "peptiforg_core/native_result_interpretation_v1.py",
        "peptiforg_core/native_release_dossier_v1.py",
    ]
    missing = [x for x in required if not (root / x).is_file()]
    registry = _registry_summary(root)
    cli_text = (root / "pepforge_cli.py").read_text(encoding="utf-8", errors="replace") if (root / "pepforge_cli.py").is_file() else ""
    cli_commands = [
        "v5-native-dock", "v5-public-benchmark-sync", "v5-public-benchmark-split-audit",
        "v5-uniprot-lookup", "v5-native-docking-tune", "v5-native-validation-finalize",
        "v5-native-result-interpret", "v5-native-validation-workspace", "v5-final-release-audit",
    ]
    missing_cli = [x for x in cli_commands if x not in cli_text]
    inventory, forbidden_artifacts = _package_inventory(root)

    claim_text = "\n".join((root / x).read_text(encoding="utf-8", errors="replace") for x in ["SCIENTIFIC_QUALITY_POLICY.md", "NATIVE_VALIDATION_PROTOCOL.md", "V5_FINAL_NOTES.md"] if (root / x).is_file())
    claim_terms = ["docking score", "production MD", "affinity", "Kd"]
    missing_claim_terms = [x for x in claim_terms if x.lower() not in claim_text.lower()]

    checks = {
        "release_gate": "PASS" if gate_pass else "FAIL",
        "required_files": "PASS" if not missing else "FAIL",
        "public_57_registry": registry.get("status") if pol.require_public_registry else "OPTIONAL",
        "final_cli_surfaces": "PASS" if not missing_cli else "FAIL",
        "claim_guard_documents": "PASS" if not missing_claim_terms else "FAIL",
        "package_hygiene": "PASS" if not forbidden_artifacts else "FAIL",
    }
    engineering_pass = all(v in {"PASS", "OPTIONAL"} for v in checks.values())
    status = "V5_0_0_FINAL_ENGINEERING_RELEASE_PASS" if engineering_pass else "V5_0_0_FINAL_ENGINEERING_RELEASE_BLOCKED"

    manifest = {
        "pepforge_version": V5_FINAL_VERSION,
        "audit_version": V5_FINAL_RELEASE_AUDIT_VERSION,
        "status": status,
        "engineering_release_pass": engineering_pass,
        "scientific_validation_status": "SEPARATE_EVIDENCE_GATE_REQUIRED",
        "policy": asdict(pol),
        "checks": checks,
        "missing_required_files": missing,
        "missing_cli_commands": missing_cli,
        "missing_claim_guard_terms": missing_claim_terms,
        "forbidden_packaging_artifacts": forbidden_artifacts,
        "public_benchmark_registry": registry,
        "release_gate": {"passed": int(gate.get("passed", 0)), "failed": int(gate.get("failed", 0)), "summary": str(gate_json)},
        "package_file_count": len(inventory),
        "claim_guard": (
            "V5.0.0 FINAL engineering release PASS means the software/package contract passed its release checks. "
            "It does not mean the native docking score is affinity/DeltaG/Kd, that public benchmark accuracy has met a scientific threshold, "
            "or that Native Mechanics is production molecular dynamics."
        ),
    }
    (out / "V5_FINAL_RELEASE_MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "V5_FINAL_FILE_HASHES.json").write_text(json.dumps({"version": V5_FINAL_VERSION, "files": inventory}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Pepforge V5.0.0 FINAL Release Audit", "", f"Status: **{status}**", "",
        f"Engineering release pass: **{engineering_pass}**", "",
        "## Checks", "",
    ]
    lines += [f"- {k}: **{v}**" for k, v in checks.items()]
    lines += ["", "## Scientific boundary", "", manifest["claim_guard"], ""]
    (out / "V5_FINAL_RELEASE_AUDIT.md").write_text("\n".join(lines), encoding="utf-8")
    return manifest


__all__ = ["V5_FINAL_RELEASE_AUDIT_VERSION", "V5_FINAL_VERSION", "V5FinalPolicy", "audit_v5_final_release"]
