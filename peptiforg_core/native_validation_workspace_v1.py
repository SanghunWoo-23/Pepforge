from __future__ import annotations

"""Validation workspace health/index for Pepforge V5 native evidence."""

from pathlib import Path
from typing import Any
import hashlib
import json

NATIVE_VALIDATION_WORKSPACE_VERSION = "0.1.0"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def inspect_validation_workspace(root: str | Path, output_dir: str | Path | None = None) -> dict[str, Any]:
    base = Path(root).expanduser().resolve()
    summaries = sorted(base.rglob("native_docking_reference_benchmark.json")) if base.exists() else []
    calibration = sorted(base.rglob("native_benchmark_calibration.json")) if base.exists() else []
    dossiers = sorted(base.rglob("native_v5_release_dossier.json")) if base.exists() else []
    manifest_audits = sorted(base.rglob("native_benchmark_manifest_audit.json")) if base.exists() else []
    mechanics = sorted(base.rglob("native_mechanics_validation.json")) if base.exists() else []
    release_gates = sorted(base.rglob("*release_gate*.json")) if base.exists() else []

    target_rows = []
    split_counts: dict[str, int] = {}
    malformed = []
    for p in summaries:
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            target = str(d.get("target_id") or p.parent.name)
            split = str(d.get("split") or d.get("dataset_split") or "UNDECLARED").upper()
            split_counts[split] = split_counts.get(split, 0) + 1
            csv_raw = str(d.get("benchmark_csv") or "")
            csv_p = Path(csv_raw)
            csv_ok = csv_p.is_file() if csv_p.is_absolute() else (p.parent / csv_p).is_file()
            target_rows.append({"target_id": target, "split": split, "summary_json": str(p), "benchmark_csv_present": bool(csv_ok)})
        except Exception as exc:
            malformed.append({"path": str(p), "error": str(exc)})

    actions = []
    status = "READY_FOR_EXTERNAL_BENCHMARK_INPUT"
    if malformed:
        status = "WORKSPACE_NEEDS_REPAIR"
        actions.append("Repair malformed benchmark summary JSON files before calibration.")
    if summaries and not calibration:
        actions.append("Run v5-native-validation-finalize to generate calibration and release dossier artifacts.")
        status = "BENCHMARKS_PRESENT_FINALIZATION_PENDING" if status != "WORKSPACE_NEEDS_REPAIR" else status
    if not summaries:
        actions.append("Add independently sourced benchmark target results; no reference benchmark summaries were found.")
    undeclared = split_counts.get("UNDECLARED", 0)
    if summaries and undeclared:
        actions.append(f"Declare train/validation/test/holdout split for {undeclared} target(s) to support leakage-aware evaluation.")
    if calibration and not dossiers:
        actions.append("Build the native release dossier from calibration, mechanics validation, and software release-gate evidence.")
    if dossiers:
        try:
            latest = json.loads(dossiers[-1].read_text(encoding="utf-8"))
            if not bool(latest.get("scientific_promotion_gate_pass")):
                actions.append("Scientific promotion remains pending; inspect dossier checks rather than overriding the gate.")
            status = str(latest.get("status") or status)
        except Exception:
            pass

    artifacts = []
    for p in sorted(set(summaries + calibration + dossiers + manifest_audits + mechanics + release_gates)):
        if p.is_file():
            artifacts.append({"path": str(p), "size_bytes": p.stat().st_size, "sha256": _sha256(p)})

    payload = {
        "version": NATIVE_VALIDATION_WORKSPACE_VERSION,
        "root": str(base),
        "status": status,
        "counts": {
            "benchmark_targets": len(target_rows), "calibration_files": len(calibration), "release_dossiers": len(dossiers),
            "manifest_audits": len(manifest_audits), "mechanics_validations": len(mechanics), "release_gate_files": len(release_gates),
            "malformed_benchmark_summaries": len(malformed),
        },
        "split_counts": split_counts,
        "targets": target_rows,
        "malformed": malformed,
        "recommended_actions": actions,
        "artifacts": artifacts,
        "claim_guard": "Workspace completeness and file integrity do not establish scientific accuracy; external benchmark quality and independence still govern interpretation.",
    }
    if output_dir:
        out = Path(output_dir).expanduser().resolve(); out.mkdir(parents=True, exist_ok=True)
        (out / "native_validation_workspace.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        lines = ["# Pepforge Native Validation Workspace", "", f"Status: **{status}**", "", "## Counts"]
        lines += [f"- {k}: {v}" for k, v in payload["counts"].items()]
        lines += ["", "## Dataset splits"] + ([f"- {k}: {v}" for k, v in split_counts.items()] or ["- No benchmark targets discovered."])
        lines += ["", "## Recommended actions"] + ([f"- {x}" for x in actions] or ["- No workspace action generated."])
        lines += ["", "## Boundary", payload["claim_guard"], ""]
        (out / "NATIVE_VALIDATION_WORKSPACE.md").write_text("\n".join(lines), encoding="utf-8")
    return payload


__all__ = ["NATIVE_VALIDATION_WORKSPACE_VERSION", "inspect_validation_workspace"]
