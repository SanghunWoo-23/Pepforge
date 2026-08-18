"""Transparent SPPS synthesis-risk rules for operator review.

The engine reports observable sequence/plan patterns.  It never changes a plan
and its score is a deterministic triage score, not a probability of failure.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any, Iterable, Mapping

from spps_planner.parser import parse_sequence


ENGINE_VERSION = "3.0.0-rules.1"
SEVERITY_WEIGHT = {"INFO": 5, "WARNING": 12, "HIGH": 24, "CRITICAL": 40}
HYDROPHOBIC = set("AVILMFWY")
BETA_BRANCHED = set("ITV")
CHARGED = set("DEKR")


def _natural(token: Any) -> str:
    text = str(token or "").strip()
    if len(text) == 1 and text.upper() in set("ARNDCQEGHILKMFPSTWYV"):
        return text.upper()
    if len(text) == 2 and text.startswith("d") and text[1].upper() in set("ARNDCQEGHILKMFPSTWYV"):
        return text[1].upper()
    return ""


def _finding(rule_id: str, severity: str, category: str, title: str, positions: Iterable[int],
             evidence: str, impact: str, recommendation: str) -> dict[str, Any]:
    pos = sorted(set(int(value) for value in positions))
    identity = json.dumps([rule_id, pos, evidence], ensure_ascii=False, sort_keys=True)
    return {
        "finding_id": sha256(identity.encode("utf-8")).hexdigest()[:16],
        "rule_id": rule_id, "severity": severity, "category": category,
        "title": title, "sequence_positions": pos, "evidence": evidence,
        "impact": impact, "recommendation": recommendation,
        "source": "rule", "confidence": "deterministic pattern",
        "requires_review": True,
    }


def _runs(values: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = values.get("runs", [])
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def evaluate_rules(item: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate sequence, visible Plan and observed run history without mutation."""
    parsed = parse_sequence(str(item.get("sequence", "")))
    tokens = list(parsed.core_tokens or [])
    natural = [_natural(token) for token in tokens]
    findings: list[dict[str, Any]] = []

    aspartimide_positions = [
        i + 1 for i in range(len(natural) - 1)
        if natural[i] == "D" and natural[i + 1] in {"G", "N", "S", "T", "C"}
    ]
    if aspartimide_positions:
        motifs = [f"D{natural[i]} at {i + 1}-{i + 2}" for i in (p - 1 for p in aspartimide_positions)]
        findings.append(_finding(
            "SEQ-ASPARTIMIDE", "HIGH", "Side reaction", "Aspartimide-prone motif review",
            [p for start in aspartimide_positions for p in (start, start + 1)], ", ".join(motifs),
            "Repeated base exposure can increase sequence-dependent aspartimide-related by-products.",
            "Review protecting groups and deprotection/coupling exposure against the approved SOP; any mitigation is operator-approved and never applied automatically.",
        ))

    longest, run_start, best_start = 0, 0, 0
    for index, aa in enumerate(natural + [""]):
        if aa in HYDROPHOBIC:
            if index == 0 or natural[index - 1] not in HYDROPHOBIC:
                run_start = index
            if index - run_start + 1 > longest:
                longest, best_start = index - run_start + 1, run_start
    hydro_count = sum(aa in HYDROPHOBIC for aa in natural)
    charged_count = sum(aa in CHARGED for aa in natural)
    if longest >= 5 or (len(natural) >= 15 and hydro_count / max(1, len(natural)) >= 0.45 and charged_count / len(natural) <= 0.20):
        positions = range(best_start + 1, best_start + longest + 1) if longest else ()
        findings.append(_finding(
            "SEQ-AGGREGATION", "HIGH" if longest >= 6 else "WARNING", "Aggregation",
            "Hydrophobic aggregation pattern", positions,
            f"length={len(natural)}, hydrophobic={hydro_count}, charged={charged_count}, longest hydrophobic run={longest}",
            "Resin-bound chain association can reduce reagent access and apparent coupling completion.",
            "Review resin choice, loading, solvent/swelling, mixing and coupling monitoring in the approved SOP; consider a supervised repeat only after evidence is recorded.",
        ))

    difficult = [i + 1 for i, aa in enumerate(natural) if aa in BETA_BRANCHED or aa == "P"]
    bulky_pairs = [i + 1 for i in range(len(natural) - 1) if natural[i] in (BETA_BRANCHED | {"F", "W", "Y", "P"}) and natural[i + 1] in (BETA_BRANCHED | {"F", "W", "Y", "P"})]
    nonstandard = [i + 1 for i, token in enumerate(tokens) if not _natural(token)]
    if len(difficult) >= 4 or bulky_pairs or nonstandard:
        positions = difficult + nonstandard + [p + 1 for p in bulky_pairs]
        findings.append(_finding(
            "SEQ-DIFFICULT-COUPLING", "WARNING", "Coupling", "Difficult coupling candidates",
            positions, f"beta-branched/Pro={len(difficult)}, adjacent bulky pairs={len(bulky_pairs)}, non-standard tokens={len(nonstandard)}",
            "Steric demand or non-standard building blocks can produce incomplete coupling.",
            "Use coupling-test or chromatographic evidence to decide whether a repeat/doubling is required; record the reason in Run / Corrections.",
        ))

    cys = [i + 1 for i, aa in enumerate(natural) if aa == "C"]
    if cys:
        findings.append(_finding(
            "SEQ-CYS", "WARNING", "Oxidation / protection", "Cysteine handling review", cys,
            f"Cys positions: {', '.join(map(str, cys))}",
            "Thiol protection/deprotection and oxidation state can affect product identity and recovery.",
            "Confirm protecting-group compatibility and intended disulfide/thiol state against the synthesis and cleavage SOP.",
        ))
    oxidation = [i + 1 for i, aa in enumerate(natural) if aa in {"M", "W"}]
    if oxidation:
        findings.append(_finding(
            "SEQ-OXIDATION", "INFO", "Oxidation", "Oxidation-sensitive residue review", oxidation,
            f"Met/Trp positions: {', '.join(map(str, oxidation))}",
            "Oxidation-sensitive residues can contribute to mass or purity variants during handling and cleavage.",
            "Review exposure and scavenger/handling choices under the approved SOP and verify by analytical data.",
        ))

    early_dkp = [i + 1 for i in range(min(3, len(natural) - 1)) if natural[i + 1] == "P"]
    if early_dkp:
        findings.append(_finding(
            "SEQ-EARLY-PRO", "WARNING", "Side reaction", "Early Pro motif review", early_dkp,
            "Pro occurs near the resin-proximal early sequence region.",
            "Some early dipeptide contexts can be susceptible to sequence-dependent cyclization or loss.",
            "Confirm the actual synthesis direction, resin/linker and early-cycle handling; treat this as a review flag, not a diagnosis.",
        ))

    repeat_steps, held_steps = [], []
    for row in item.get("selected_plan_rows", []) or []:
        try:
            if float(str(row.get("Repeat", 1)).strip() or 1) >= 2:
                repeat_steps.append(str(row.get("No", "")))
        except (TypeError, ValueError):
            pass
    for run in [item, *_runs(item)]:
        for event in (run.get("synthesis_execution") or {}).get("events", []) or []:
            if str(event.get("after", "")).lower() in {"failed", "hold", "held"}:
                held_steps.append(str(event.get("step_no", "")))
    if repeat_steps:
        findings.append(_finding(
            "PLAN-REPEAT", "INFO", "Plan", "Planned repeat/doubling present", [],
            f"Plan steps: {', '.join(repeat_steps)}", "Material use and cycle exposure are already increased at these steps.",
            "Confirm that the repeat is intentional and its evidence/reason is preserved in Run / Corrections.",
        ))
    if held_steps:
        findings.append(_finding(
            "RUN-FAILED-HOLD", "HIGH", "Execution", "Recorded failed/held execution step", [],
            f"Observed steps: {', '.join(held_steps)}", "A prior observed execution issue may recur under similar conditions.",
            "Review the recorded event, corrective action and analytical evidence before continuing or reusing the plan.",
        ))

    # Stable ordering and a transparent non-probabilistic score.
    findings.sort(key=lambda row: (-SEVERITY_WEIGHT[row["severity"]], row["rule_id"], row["finding_id"]))
    score = min(100, sum(SEVERITY_WEIGHT[row["severity"]] for row in findings))
    level = "CRITICAL" if score >= 70 else "HIGH" if score >= 45 else "WARNING" if score >= 20 else "INFO"
    return {
        "engine_version": ENGINE_VERSION, "rule_score": score, "rule_level": level,
        "finding_count": len(findings), "findings": findings,
        "parser_warnings": list(parsed.warnings),
        "disclaimer": "Triage support only. Review SOP/SDS, instrument data and operator judgement before use; no change is applied automatically.",
    }


__all__ = ["ENGINE_VERSION", "evaluate_rules"]
