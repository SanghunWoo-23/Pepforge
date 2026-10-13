from __future__ import annotations

"""Evidence-gated V5 native scientific release dossier.

Produces a code-complete/readiness decision without upgrading unvalidated
scientific claims. Missing external evidence remains explicitly pending.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import json

NATIVE_RELEASE_DOSSIER_VERSION = "0.1.0"


@dataclass(frozen=True)
class ReleaseDossierPolicy:
    min_external_targets: int = 20
    min_ranked_targets: int = 10
    require_holdout_split: bool = True
    min_top5_acceptable_rate: float = 0.50
    require_score_structure_pairs: int = 30
    require_mechanics_numerical_pass: bool = True
    note: str = "Project engineering promotion criteria; not an external scientific standard."


def _load(path: str | Path | None) -> dict[str, Any] | None:
    if not path:
        return None
    p = Path(path).expanduser().resolve()
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def build_release_dossier(
    output_dir: str | Path,
    *,
    calibration_json: str | Path | None = None,
    mechanics_validation_json: str | Path | None = None,
    release_gate_json: str | Path | None = None,
    policy: ReleaseDossierPolicy | None = None,
) -> dict[str, Any]:
    pol = policy or ReleaseDossierPolicy(); out = Path(output_dir).expanduser().resolve(); out.mkdir(parents=True, exist_ok=True)
    cal = _load(calibration_json); mech = _load(mechanics_validation_json); gate = _load(release_gate_json)

    checks: list[dict[str, Any]] = []
    def add(name: str, status: str, evidence: Any = None, required: bool = True):
        checks.append({"name": name, "status": status, "required": bool(required), "evidence": evidence})

    gate_pass = bool(gate and (str(gate.get("status", "")).upper() in {"PASS", "READY", "RELEASE_READY"} or (int(gate.get("failed", 1)) == 0 and int(gate.get("passed", 0)) > 0)))
    add("software_release_gate", "PASS" if gate_pass else ("NOT_PROVIDED" if gate is None else "FAIL"), gate.get("status") if gate else None)

    targets = int((cal or {}).get("targets") or 0)
    add("external_benchmark_target_count", "PASS" if targets >= pol.min_external_targets else "PENDING", {"observed": targets, "required": pol.min_external_targets})
    has_holdout = bool((cal or {}).get("has_test_or_holdout_split"))
    add("holdout_or_test_split", "PASS" if (has_holdout or not pol.require_holdout_split) else "PENDING", has_holdout)

    all_summary = None
    for s in (cal or {}).get("split_summaries", []):
        if str(s.get("split")) == "ALL": all_summary = s; break
    ranked = int((all_summary or {}).get("ranked_targets") or 0)
    add("ranked_target_count", "PASS" if ranked >= pol.min_ranked_targets else "PENDING", {"observed": ranked, "required": pol.min_ranked_targets})
    top5 = (((all_summary or {}).get("top5_acceptable") or {}).get("estimate"))
    top5_pass = top5 is not None and float(top5) >= pol.min_top5_acceptable_rate
    add("top5_structural_recovery_project_gate", "PASS" if top5_pass else "PENDING", {"observed": top5, "required": pol.min_top5_acceptable_rate})

    pairs = int((cal or {}).get("global_pose_score_vs_structure_pairs") or 0)
    add("score_structure_calibration_pairs", "PASS" if pairs >= pol.require_score_structure_pairs else "PENDING", {"observed": pairs, "required": pol.require_score_structure_pairs})

    mech_pass = bool(mech and str(mech.get("status", "")).upper() == "PASS")
    add("native_mechanics_numerical_validation", "PASS" if (mech_pass or not pol.require_mechanics_numerical_pass) else "PENDING", mech.get("status") if mech else None)

    required = [c for c in checks if c["required"]]
    software_complete = gate_pass
    scientific_complete = bool(required and all(c["status"] == "PASS" for c in required))
    if scientific_complete:
        status = "V5_NATIVE_RESEARCH_PROMOTION_GATE_PASS"
    elif software_complete:
        status = "V5_CODE_COMPLETE_EXTERNAL_SCIENTIFIC_VALIDATION_PENDING"
    else:
        status = "V5_RELEASE_READINESS_INCOMPLETE"

    payload = {
        "version": NATIVE_RELEASE_DOSSIER_VERSION,
        "status": status,
        "policy": asdict(pol),
        "software_code_complete": software_complete,
        "scientific_promotion_gate_pass": scientific_complete,
        "checks": checks,
        "claim_guard": (
            "Code completeness and software release readiness are separate from scientific validation. A scientific promotion gate PASS here remains an internal research criterion over supplied reference benchmarks and does not establish affinity accuracy, clinical utility, or production molecular-dynamics validity."
        ),
    }
    (out / "native_v5_release_dossier.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# Pepforge V5 Native Release Dossier", "", f"Status: **{status}**", "", f"Software code complete: {software_complete}", f"Scientific promotion gate pass: {scientific_complete}", "", "## Checks", ""]
    lines += [f"- {c['name']}: **{c['status']}** — {c['evidence']}" for c in checks]
    lines += ["", "## Boundary", payload["claim_guard"], ""]
    (out / "NATIVE_V5_RELEASE_DOSSIER.md").write_text("\n".join(lines), encoding="utf-8")
    return payload


__all__ = ["NATIVE_RELEASE_DOSSIER_VERSION", "ReleaseDossierPolicy", "build_release_dossier"]
