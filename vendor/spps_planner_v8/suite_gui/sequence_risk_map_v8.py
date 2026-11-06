"""V8 Alpha 1: inspectable residue-level sequence risk representation.

Non-prescriptive: reflects existing V7 risk-engine findings, not experimental
failure probabilities, predictions, or automatically modified recipes.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping

from spps_planner.parser import parse_sequence
from suite_gui.risk_engine import evaluate_rules

RISK_MAP_VERSION = "8.0.0-alpha.1"
SEVERITY_ORDER = {"INFO": 1, "WARNING": 2, "HIGH": 3, "CRITICAL": 4}
SOURCE_CLASS = "Rule-based"


def build_sequence_risk_map(sequence: str) -> dict[str, Any]:
    """Create stable 1-based, N-to-C map, with explicit provenance per finding.

    No run history is supplied. All results are deterministic V7 heuristic flags.
    Unrecognised tokens are preserved; parser warnings remain visible.
    """
    parsed = parse_sequence(str(sequence or ""))
    tokens = list(parsed.core_tokens or [])
    baseline = evaluate_rules({"sequence": str(sequence or "")})
    per_position: dict[int, list[dict[str, Any]]] = defaultdict(list)
    unpositioned: list[dict[str, Any]] = []
    findings = []
    for original in baseline["findings"]:
        positions = sorted({p for p in original["sequence_positions"] if isinstance(p, int) and 1 <= p <= len(tokens)})
        finding = {
            "id": original["finding_id"],
            "rule_id": original["rule_id"],
            "title": original["title"],
            "severity": original["severity"],
            "category": original["category"],
            "positions": positions,
            "reason": original["evidence"],
            "potential_impact": original["impact"],
            "operator_consideration": original["recommendation"],
            "provenance": {"source_class": SOURCE_CLASS,
                           "source_id": original["rule_id"],
                           "experimental_observation": False,
                           "confidence": "Deterministic heuristic; no calibrated failure probability"},
            "action_applied": False,
        }
        findings.append(finding)
        if not positions:
            unpositioned.append(finding)
        for p in positions:
            per_position[p].append({"finding_id": finding["id"],
                                    "rule_id": finding["rule_id"],
                                    "severity": finding["severity"]})
    residues = []
    for i, token in enumerate(tokens, 1):
        refs = per_position.get(i, [])
        residues.append({"position": i, "token": token,
                         "risk_level": max((r["severity"] for r in refs),
                                           key=lambda x: SEVERITY_ORDER[x], default="NONE"),
                         "finding_refs": refs})
    return {
        "schema_version": RISK_MAP_VERSION,
        "sequence": str(sequence or ""),
        "nterm": parsed.nterm,
        "cterm": parsed.cterm_text,
        "residue_count": len(tokens),
        "residues": residues,
        "findings": findings,
        "unpositioned_findings": unpositioned,
        "parser_warnings": list(parsed.warnings),
        "score": baseline["rule_score"],
        "score_meaning": "Uncalibrated rule-triage score, NOT probability of synthesis failure",
        "recommendations_auto_applied": False,
        "evidence_policy": "Flags are Rule-based only. Experimental evidence requires exact separately verified records.",
    }


__all__ = ["RISK_MAP_VERSION", "build_sequence_risk_map"]
