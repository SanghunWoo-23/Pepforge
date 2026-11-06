"""V8 operator decision support: deterministic, non-prescriptive, provenance-aware.

No automatic chemistry changes, experimental performance claims or model training.
"""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from suite_gui.sequence_risk_map_v8 import build_sequence_risk_map

SCHEMA = "8.0.0-beta.1"
SOURCE_CLASSES = ("Experimental", "Rule-based", "User preset", "No evidence")
RULE_REVIEW = {
    "SEQ-ASPARTIMIDE": ("Deprotection / protecting-group review", "Review deprotection exposure and Asp protection under the approved SOP; investigate by LC-MS before adopting any change."),
    "SEQ-AGGREGATION": ("Aggregation / solvent review", "Review solvent swelling, mixing, resin loading and on-resin coupling-test evidence; do not assume aggregation is experimentally confirmed."),
    "SEQ-BETA-AGGREGATION-REVIEW": ("Aggregation / solvent review", "Check resin swelling, solvent compatibility and coupling-test results; sequence composition alone does not prove a beta-sheet."),
    "SEQ-DIFFICULT-COUPLING": ("Coupling confirmation", "Perform or review the validated coupling-completion test. Consider supervised repeat coupling only when actual evidence supports it."),
    "SEQ-LONG-DOUBLING-REVIEW": ("Long-chain coupling review", "Review the approved long-peptide protocol and actual coupling-test results before considering doubling."),
    "SEQ-CYS": ("Cys handling / cleavage review", "Verify Cys side-chain protecting group, target thiol/disulfide state and compatible cleavage conditions."),
    "SEQ-OXIDATION": ("Cleavage / storage oxidation review", "Check Met/Trp-sensitive workup and approved scavenger choices; verify oxidation using analytical measurements."),
    "SEQ-NTERM-QE": ("Identity / pyroglutamate review", "Check N-terminal product specification and relevant analytical peaks after workup and storage."),
    "SEQ-DEAMIDATION-REVIEW": ("Handling / deamidation review", "Evaluate sample handling and storage with analytical follow-up; no generic failure rate can be assigned."),
    "SEQ-EARLY-PRO": ("Resin-proximal sequence review", "Review linker, synthesis direction and early-cycle observations before changing conditions."),
}

def decision_report(sequence: str) -> dict[str, Any]:
    """Create an advisory report from one current sequence analysis."""
    return decision_report_from_risk(build_sequence_risk_map(sequence))


def decision_report_from_risk(risk: Mapping[str, Any]) -> dict[str, Any]:
    """Reuse an existing risk snapshot, avoiding duplicate parsing/rule evaluation."""
    if not isinstance(risk, Mapping) or not isinstance(risk.get("findings"), list):
        raise ValueError("Invalid sequence risk map")
    actions = []
    for finding in risk["findings"]:
        topic, suggestion = RULE_REVIEW.get(finding["rule_id"], ("Operator review", finding["operator_consideration"]))
        actions.append({"finding_id": finding["id"], "rule_id": finding["rule_id"], "positions": finding["positions"],
            "severity": finding["severity"], "topic": topic, "suggestion": suggestion,
            "source_class": "Rule-based", "source_id": finding["rule_id"],
            "confidence": "Uncalibrated heuristic; no measured outcome or success probability",
            "apply_automatically": False, "selected_coupling_cycles": None,
            "recommended_loading": None, "recommended_cleavage_time": None})
    return {"schema_version": SCHEMA, "risk_map": risk, "review_actions": actions,
        "chemistry_plan_modified": False, "evidence_verified": False,
        "advice": "Review only. Never auto-apply chemistry changes. Use approved SOP and measured results."}

REQUIRED = ("sequence", "batch_id", "recorded_at", "outcome", "analytical_method", "operator")
VALID_OUTCOMES = ("Pass", "Fail", "Inconclusive")

def validate_experiment_record(record: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(record, Mapping):
        raise ValueError("Record must be a mapping")
    row = {key: str(record.get(key, "")).strip() for key in REQUIRED}
    for key in REQUIRED:
        if not row[key]:
            raise ValueError(f"Missing required evidence field: {key}")
    if row["outcome"] not in VALID_OUTCOMES:
        raise ValueError("outcome must be Pass, Fail or Inconclusive")
    try:
        date = datetime.fromisoformat(row["recorded_at"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("recorded_at must be an ISO 8601 date/time") from exc
    if date.tzinfo is None:
        raise ValueError("recorded_at must include timezone")
    if len(row["sequence"]) > 4096:
        raise ValueError("sequence exceeds 4096 characters")
    if not build_sequence_risk_map(row["sequence"])["residue_count"]:
        raise ValueError("sequence must have at least one residue")
    if len(row["batch_id"]) > 128 or len(row["operator"]) > 128:
        raise ValueError("Identifier length exceeds 128 characters")
    optional = {key: str(record.get(key, "")).strip() for key in ("conditions", "observations", "data_reference", "reviewer", "reviewed_at")}
    if bool(optional["reviewer"]) != bool(optional["reviewed_at"]):
        raise ValueError("Reviewer and reviewed_at must be supplied together")
    if optional["reviewed_at"]:
        try:
            reviewed = datetime.fromisoformat(optional["reviewed_at"].replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("reviewed_at must be an ISO 8601 date/time") from exc
        if reviewed.tzinfo is None:
            raise ValueError("reviewed_at requires timezone")
        if not optional["data_reference"]:
            raise ValueError("Reviewed record requires a source data reference")
        if reviewed < date:
            raise ValueError("reviewed_at must not precede recorded_at")
    for key in ("conditions", "observations", "data_reference", "reviewer", "reviewed_at"):
        if len(optional[key]) > 10000:
            raise ValueError(f"{key} exceeds 10000 characters")
    canonical = {**row, **optional, "source_class": "Experimental",
                 "evidence_status": "Reviewed" if optional["reviewer"] else "Unreviewed",
                 "auto_promoted": False}
    canonical["record_sha256"] = sha256(json.dumps(canonical, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return canonical

def export_experiment_record(record: Mapping[str, Any], destination: str | Path) -> Path:
    """Validate and write a NEW record; never overwrite existing lab evidence."""
    validated = validate_experiment_record(record)
    path = Path(destination)
    if path.suffix.lower() != ".json":
        raise ValueError("Evidence export requires a .json file")
    with path.open("x", encoding="utf-8") as target:
        json.dump(validated, target, ensure_ascii=False, indent=2)
        target.write("\n")
    return path


def verify_experiment_record(record: Mapping[str, Any]) -> bool:
    """Check content digest and field schema; not an assertion that observations are true."""
    if not isinstance(record, Mapping) or not isinstance(record.get("record_sha256"), str):
        return False
    try:
        canonical = validate_experiment_record(record)
    except (ValueError, TypeError, KeyError):
        return False
    from hmac import compare_digest
    return compare_digest(canonical["record_sha256"], record["record_sha256"]) and (
        all(record.get(k) == canonical[k] for k in canonical)
    )
