from __future__ import annotations

"""One-shot finalization of Pepforge V5 native benchmark evidence."""

from pathlib import Path
from typing import Any
import json

from .native_benchmark_calibration_v1 import CalibrationPolicy, calibrate_benchmark_results, discover_target_summaries
from .native_release_dossier_v1 import ReleaseDossierPolicy, build_release_dossier
from .native_validation_workspace_v1 import inspect_validation_workspace

NATIVE_VALIDATION_FINALIZE_VERSION = "0.2.0"


def finalize_native_validation(
    benchmarks_root: str | Path,
    output_dir: str | Path,
    *,
    mechanics_validation_json: str | Path | None = None,
    release_gate_json: str | Path | None = None,
    calibration_policy: CalibrationPolicy | None = None,
    dossier_policy: ReleaseDossierPolicy | None = None,
) -> dict[str, Any]:
    root = Path(benchmarks_root).expanduser().resolve()
    out = Path(output_dir).expanduser().resolve(); out.mkdir(parents=True, exist_ok=True)
    summaries = discover_target_summaries(root)
    cal_dir = out / "calibration"
    cal = calibrate_benchmark_results(summaries, cal_dir, policy=calibration_policy)
    dossier_dir = out / "release_dossier"
    dossier = build_release_dossier(
        dossier_dir,
        calibration_json=cal_dir / "native_benchmark_calibration.json",
        mechanics_validation_json=mechanics_validation_json,
        release_gate_json=release_gate_json,
        policy=dossier_policy,
    )
    workspace = inspect_validation_workspace(root, out / "workspace")
    payload = {
        "version": NATIVE_VALIDATION_FINALIZE_VERSION,
        "status": dossier["status"],
        "benchmark_summaries_discovered": len(summaries),
        "calibration_json": str((cal_dir / "native_benchmark_calibration.json").resolve()),
        "release_dossier_json": str((dossier_dir / "native_v5_release_dossier.json").resolve()),
        "software_code_complete": dossier["software_code_complete"],
        "scientific_promotion_gate_pass": dossier["scientific_promotion_gate_pass"],
        "workspace_status": workspace["status"],
        "workspace_json": str((out / "workspace" / "native_validation_workspace.json").resolve()),
        "claim_guard": dossier["claim_guard"],
    }
    (out / "native_validation_finalize.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


__all__ = ["NATIVE_VALIDATION_FINALIZE_VERSION", "finalize_native_validation"]
