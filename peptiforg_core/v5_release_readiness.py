from __future__ import annotations

"""Pepforge V5 release-readiness aggregation.

This module separates software/package readiness from native scientific
validation. Missing external engines remain blockers; they are never replaced
with simulated success states.
"""
from pathlib import Path
from typing import Any
import json

from peptiforg_core.psb_v5_full_pipeline import backend_status
from peptiforg_core.release_gate import release_gate_check

READINESS_VERSION = "5.0.0-rc2"


def _load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def assess_v5_release_readiness(
    root_dir: str | Path,
    output_dir: str | Path,
    *,
    execution_mode: str = "offline",
    resource_root: str | Path | None = None,
    ranker_metadata: str | Path | None = None,
    run_release_gate: bool = True,
) -> dict[str, Any]:
    root = Path(root_dir).expanduser().resolve()
    out = Path(output_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)

    software_gate: dict[str, Any]
    gate_paths: dict[str, str] = {}
    if run_release_gate:
        gate_paths = release_gate_check(root, out / "release_gate")
        gate_summary = _load_json(gate_paths["release_gate_summary"])
        software_gate = {
            "status": "PASS" if int(gate_summary.get("failed", 0)) == 0 else "FAIL",
            "passed": int(gate_summary.get("passed", 0)),
            "failed": int(gate_summary.get("failed", 0)),
            "summary": gate_paths["release_gate_summary"],
        }
    else:
        software_gate = {"status": "NOT_RUN"}

    backends = backend_status(execution_mode, resource_root)
    native = {
        "haddock3": str((backends.get("haddock3") or {}).get("status") or "UNKNOWN"),
        "openmm": str((backends.get("openmm") or {}).get("status") or "UNKNOWN"),
        "trajectory_analysis": str((backends.get("trajectory_analysis") or {}).get("status") or "UNKNOWN"),
    }
    native_required_ready = native["haddock3"] == "READY" and native["openmm"] == "READY"

    ranker = {
        "status": "NO_PRODUCTION_MODEL_DECLARED",
        "metadata": None,
        "promotion_status": None,
    }
    if ranker_metadata:
        path = Path(ranker_metadata).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(path)
        meta = _load_json(path)
        ranker = {
            "status": "METADATA_LOADED",
            "metadata": str(path),
            "promotion_status": meta.get("promotion_status") or "LEGACY_OR_UNDECLARED",
            "target_name": meta.get("target_name"),
            "cross_validation": meta.get("cross_validation"),
            "baseline_comparison": meta.get("baseline_comparison"),
        }

    blockers: list[dict[str, str]] = []
    if software_gate.get("status") != "PASS":
        blockers.append({"code": "SOFTWARE_RELEASE_GATE", "detail": f"release gate status={software_gate.get('status')}"})
    if native["haddock3"] != "READY":
        blockers.append({"code": "HADDOCK3_NATIVE_VALIDATION", "detail": f"backend status={native['haddock3']}"})
    if native["openmm"] != "READY":
        blockers.append({"code": "OPENMM_NATIVE_VALIDATION", "detail": f"backend status={native['openmm']}"})
    if ranker.get("promotion_status") not in {"EXTERNALLY_VALIDATED_FOR_DECLARED_DOMAIN"}:
        blockers.append({"code": "RANKER_EXTERNAL_VALIDATION", "detail": str(ranker.get("promotion_status") or ranker.get("status"))})
    blockers.append({"code": "WINDOWS_WSL_FRESH_UNZIP_NATIVE_SMOKE", "detail": "must be executed on the target installation before final public scientific release claim"})

    software_complete = software_gate.get("status") == "PASS"
    if software_complete and not native_required_ready:
        overall = "SOFTWARE_COMPLETE_NATIVE_VALIDATION_PENDING"
    elif software_complete and native_required_ready and len(blockers) <= 2:
        overall = "NATIVE_BACKENDS_READY_ADDITIONAL_RELEASE_VALIDATION_REQUIRED"
    else:
        overall = "NOT_RELEASE_READY"

    payload = {
        "version": READINESS_VERSION,
        "overall_status": overall,
        "software_gate": software_gate,
        "native_backends": native,
        "ranker": ranker,
        "blockers": blockers,
        "release_gate_paths": gate_paths,
        "claim_guard": (
            "A software-complete status does not mean scientific validation is complete. "
            "Pepforge V5 must not be called a natively validated scientific release until required external engines "
            "and target-machine smoke tests have actually run successfully."
        ),
    }
    json_path = out / "V5_RELEASE_READINESS.json"
    md_path = out / "V5_RELEASE_READINESS.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Pepforge V5 Release Readiness", "", f"Overall: **{overall}**", "",
        f"- Software release gate: {software_gate.get('status')}",
        f"- HADDOCK3: {native['haddock3']}",
        f"- OpenMM: {native['openmm']}",
        f"- Trajectory analysis: {native['trajectory_analysis']}",
        f"- Ranker promotion: {ranker.get('promotion_status') or ranker.get('status')}", "",
        "## Remaining blockers",
    ]
    lines += [f"- `{b['code']}`: {b['detail']}" for b in blockers]
    lines += ["", "## Claim boundary", payload["claim_guard"], ""]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    payload["report_json"] = str(json_path)
    payload["report_md"] = str(md_path)
    return payload


__all__ = ["READINESS_VERSION", "assess_v5_release_readiness"]
