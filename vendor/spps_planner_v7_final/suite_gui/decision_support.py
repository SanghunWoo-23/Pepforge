"""SPPS Planner V6 decision-support helpers.

These helpers add provenance, A/B comparison, execution summaries and small-sample
analytics without changing chemistry calculations or silently mutating a Plan.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime
import json
import math
from statistics import mean
from typing import Any, Iterable, Mapping

VERSION = "6.0.0"
RECORD_STATES = ("draft", "completed", "verified", "excluded", "failed_informative")
SOURCE_LABELS = (
    "Exact experimental match",
    "Bounded interpolation",
    "Similar-sequence evidence",
    "Literature/rule",
    "Default fallback",
    "Manual override",
    "Insufficient evidence",
)


def _num(value: Any) -> float | None:
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except Exception:
        return None


def _text(value: Any) -> str:
    return str(value or "").strip()


def _parse_json(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    try:
        parsed = json.loads(str(value or "{}"))
        return dict(parsed) if isinstance(parsed, Mapping) else {}
    except Exception:
        return {}


def evidence_trace(result: Mapping[str, Any] | None, *, manual_override: bool = False) -> dict[str, Any]:
    """Normalize advisor-specific evidence metadata into one operator-facing trace."""
    row = dict(result or {})
    rec = dict(row.get("recommended_condition") or {})
    target = dict(row.get("target_recommendation") or {})
    summary = dict(row.get("evidence_summary") or {})
    kind = " ".join(
        _text(value).lower()
        for value in (
            row.get("recommendation_kind"), rec.get("recommendation_kind"),
            rec.get("condition_source"), summary.get("source_kind"), row.get("method"), target.get("recommendation_kind"),
        )
    )
    if manual_override or "manual" in kind:
        source = "Manual override"
    elif any(token in kind for token in (
        "exact_lab", "exact sequence", "operator-approved exact", "exact experimental",
        "exact record", "observed repeated condition", "observed exact condition",
    )):
        source = "Exact experimental match"
    elif "bounded" in kind or "interpolation" in kind:
        source = "Bounded interpolation"
    # An explicit default/fallback must win over a generic similarity method string.
    # Loading keeps broader similarity diagnostics in the result, but CHEMISTRY DEFAULT
    # is not experimental evidence for the requested loaded-AA identity.
    elif any(token in kind for token in ("fallback", "default")):
        source = "Default fallback"
    elif "similar" in kind or "similarity" in kind:
        source = "Similar-sequence evidence"
    elif any(token in kind for token in ("rule", "empirical", "literature", "operator cys")):
        source = "Literature/rule"
    elif row.get("apply_allowed") is False or target.get("apply_allowed") is False or "insufficient" in kind or "outside observed" in kind:
        source = "Insufficient evidence"
    else:
        # A generic V4/V5 historical consensus with real rows is closest to similar evidence.
        source = "Similar-sequence evidence" if any(row.get(k) for k in ("evidence_count", "independent_experiment_count")) else "Default fallback"

    evidence_count = next((int(v) for v in (
        target.get("evidence_count"), rec.get("evidence_count"), rec.get("condition_evidence_count"),
        row.get("evidence_count"), row.get("independent_experiment_count"), summary.get("evidence_count"),
    ) if _num(v) is not None), 0)
    verified_count = next((int(v) for v in (
        target.get("verified_evidence_count"), rec.get("verified_evidence_count"), row.get("verified_evidence_count"),
    ) if _num(v) is not None), 0)
    confidence = _text(target.get("confidence") or rec.get("confidence") or row.get("confidence") or (row.get("evidence_quality") or {}).get("level") or "LOW").upper()
    if confidence not in {"HIGH", "MEDIUM", "LOW"}:
        confidence = "LOW"
    lo = target.get("observed_aa_eq_min", rec.get("observed_aa_eq_min", row.get("observed_min")))
    hi = target.get("observed_aa_eq_max", rec.get("observed_aa_eq_max", row.get("observed_max")))
    apply_allowed = target.get("apply_allowed", rec.get("apply_allowed", row.get("apply_allowed", True)))
    blocked_reason = ""
    if apply_allowed is False:
        blocked_reason = _text(target.get("basis") or rec.get("basis") or row.get("basis") or "Recommendation is outside supported evidence or otherwise not actionable.")
    return {
        "source": source,
        "confidence": confidence,
        "evidence_count": evidence_count,
        "verified_evidence_count": verified_count,
        "observed_range": [lo, hi] if lo is not None or hi is not None else None,
        "apply_allowed": bool(apply_allowed),
        "blocked_reason": blocked_reason,
        "basis": _text(target.get("basis") or rec.get("basis") or row.get("basis") or row.get("ranking_policy") or row.get("method")),
        "provisional": bool(target.get("provisional") or rec.get("provisional") or row.get("provisional")),
    }


def attach_evidence_trace(result: Mapping[str, Any] | None, *, manual_override: bool = False) -> dict[str, Any]:
    out = dict(result or {})
    out["evidence_trace"] = evidence_trace(out, manual_override=manual_override)
    return out


def scenario_summary(values: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize one A/B scenario without claiming experimental prediction."""
    coupling_eq = _num(values.get("coupling_eq"))
    repeats = _num(values.get("coupling_repeats"))
    coupling_min = _num(values.get("coupling_time_min"))
    cleavage_eq = _num(values.get("cleavage_eq"))
    cleavage_h = _num(values.get("cleavage_time_h"))
    scale = _num(values.get("scale_mmol"))
    aa_steps = int(_num(values.get("aa_steps")) or 0)
    repeats_i = max(1, int(repeats or 1))
    # Relative burden indices are explicitly dimensionless. They compare A vs B
    # without inventing prices or reagent-specific molecular weights.
    coupling_burden = (coupling_eq or 0.0) * repeats_i * max(aa_steps, 1)
    cleavage_burden = (cleavage_eq or 0.0) * (scale or 1.0)
    time_min = (coupling_min or 0.0) * repeats_i * max(aa_steps, 1) + (cleavage_h or 0.0) * 60.0
    unit_cost = _num(values.get("estimated_cost"))
    return {
        "resin": _text(values.get("resin")), "loading_mmol_g": _num(values.get("loading_mmol_g")),
        "coupling_eq": coupling_eq, "coupling_repeats": repeats_i, "coupling_time_min": coupling_min,
        "cleavage_eq": cleavage_eq, "cleavage_time_h": cleavage_h,
        "scale_mmol": scale, "aa_steps": aa_steps,
        "relative_reagent_burden": round(coupling_burden + cleavage_burden, 4),
        "estimated_process_time_min": round(time_min, 2),
        "estimated_cost": unit_cost,
        "evidence_level": _text(values.get("evidence_level") or "Unknown"),
        "historical_support": int(_num(values.get("historical_support")) or 0),
        "historical_successes": int(_num(values.get("historical_successes")) or 0),
        "risk_level": _text(values.get("risk_level") or "Unknown"),
    }


def compare_scenarios(a: Mapping[str, Any], b: Mapping[str, Any]) -> dict[str, Any]:
    """Compare two operator-defined conditions without changing either condition."""
    aa, bb = scenario_summary(a), scenario_summary(b)
    def delta(key: str) -> float | None:
        av, bv = _num(aa.get(key)), _num(bb.get(key))
        return None if av is None or bv is None else round(bv - av, 4)
    return {
        "version": VERSION, "scenario_a": aa, "scenario_b": bb,
        "delta_b_minus_a": {
            "relative_reagent_burden": delta("relative_reagent_burden"),
            "estimated_process_time_min": delta("estimated_process_time_min"),
            "estimated_cost": delta("estimated_cost"),
        },
        "cost_note": "Currency cost is shown only when explicit cost data are supplied; otherwise no price is invented.",
        "disclaimer": "A/B comparison is a planning comparison, not an experimental success prediction, and applies no automatic Plan changes.",
    }


def execution_summary(item: Mapping[str, Any]) -> dict[str, Any]:
    """Derive progress/timing/variance from the existing append-only execution ledger."""
    plan = [dict(row) for row in (item.get("selected_plan_rows") or []) if isinstance(row, Mapping)]
    events = [dict(row) for row in ((item.get("synthesis_execution") or {}).get("events") or []) if isinstance(row, Mapping)]
    statuses: dict[str, str] = {}
    starts: dict[str, str] = {}
    ends: dict[str, str] = {}
    actuals: dict[tuple[str, str], Any] = {}
    notes: dict[str, list[str]] = defaultdict(list)
    for event in events:
        step = _text(event.get("step_no"))
        field = _text(event.get("field"))
        after = event.get("after")
        if event.get("event_type") == "step_status" or field.lower() in {"status", "step_status"}:
            state = _text(after)
            statuses[step] = state
            if state.lower() == "in progress" and step not in starts:
                starts[step] = _text(event.get("timestamp"))
            if state.lower() in {"completed", "failed", "hold", "held"}:
                ends[step] = _text(event.get("timestamp"))
        if event.get("event_type") == "actual_material":
            actuals[(step, _text(event.get("unit")))] = after
        if _text(event.get("operator_note")):
            notes[step].append(_text(event.get("operator_note")))
    steps = []
    completed = held = failed = 0
    for index, row in enumerate(plan, 1):
        step = _text(row.get("No") or row.get("Step") or index)
        status = statuses.get(step, "Planned")
        low = status.lower()
        completed += int(low == "completed")
        held += int(low in {"hold", "held"})
        failed += int(low == "failed")
        steps.append({"step_no": step, "unit": _text(row.get("Unit") or row.get("Operation") or row.get("AA")),
                      "status": status, "started_at": starts.get(step, ""), "ended_at": ends.get(step, ""),
                      "notes": notes.get(step, [])})
    total = len(plan)
    resume = next((row["step_no"] for row in steps if row["status"].lower() != "completed"), "Complete" if total else "N/A")
    return {
        "version": VERSION, "total_steps": total, "completed_steps": completed,
        "progress_percent": round(100.0 * completed / total, 1) if total else 0.0,
        "held_steps": held, "failed_steps": failed, "resume_step": resume,
        "steps": steps, "event_count": len(events),
    }


def analytics_snapshot(*, loading_rows: Iterable[Mapping[str, Any]] = (), outcome_rows: Iterable[Mapping[str, Any]] = (),
                       issue_rows: Iterable[Mapping[str, Any]] = (), cleavage_rows: Iterable[Mapping[str, Any]] = (),
                       min_trend_n: int = 3) -> dict[str, Any]:
    """Small-sample-safe descriptive dashboard data; never reports inferential claims."""
    loading = [dict(r) for r in loading_rows]
    outcomes = [dict(r) for r in outcome_rows]
    issues = [dict(r) for r in issue_rows]
    cleavage = [dict(r) for r in cleavage_rows]

    def group_mean(rows: list[dict[str, Any]], key: str, value: str) -> list[dict[str, Any]]:
        grouped: dict[str, list[float]] = defaultdict(list)
        for row in rows:
            label = _text(row.get(key)) or "(missing)"
            num = _num(row.get(value))
            if num is not None:
                grouped[label].append(num)
        return [{"group": k, "n": len(v), "mean": round(mean(v), 4), "trend_ready": len(v) >= min_trend_n} for k, v in sorted(grouped.items())]

    lengths = Counter()
    success_by_len: dict[str, list[int]] = defaultdict(list)
    sequence_stats: dict[str, list[dict[str, Any]]] = defaultdict(list)
    coupling_repeat_stats: dict[str, list[dict[str, Any]]] = defaultdict(list)
    month_counts: Counter[str] = Counter()
    for row in outcomes:
        seq = _text(row.get("sequence"))
        length = len([c for c in seq if c.isalpha() and c.isupper()]) if seq else 0
        bucket = "1-9" if 0 < length < 10 else "10-19" if length < 20 else "20+" if length else "Unknown"
        lengths[bucket] += 1
        if row.get("success_flag") in (0, 1):
            success_by_len[bucket].append(int(row.get("success_flag")))
        if seq:
            sequence_stats[seq].append(row)
        created=_text(row.get("created_at"))
        if len(created) >= 7:
            month_counts[created[:7]] += 1
        snapshot=_parse_json(row.get("planner_snapshot_json"))
        repeats=[]
        for step in snapshot.get("selected_plan_rows") or []:
            if not isinstance(step, Mapping):
                continue
            label=" ".join(_text(step.get(k)).lower() for k in ("Unit name","Unit","Operation","AA","Step"))
            if "coupl" not in label:
                continue
            rep=_num(step.get("Repeat") if step.get("Repeat") is not None else step.get("repeat"))
            if rep is not None:
                repeats.append(max(1, int(rep)))
        if repeats:
            coupling_repeat_stats[str(max(repeats))].append(row)
    success = [{"group": k, "n": len(v), "success_percent": round(100 * mean(v), 1), "trend_ready": len(v) >= min_trend_n} for k, v in sorted(success_by_len.items())]

    sequence_repeats=[]
    for seq, rows in sorted(sequence_stats.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        success_values=[int(r.get("success_flag")) for r in rows if r.get("success_flag") in (0,1)]
        yields=[v for v in (_num(r.get("yield_percent")) for r in rows) if v is not None]
        purities=[v for v in (_num(r.get("purity_percent")) for r in rows) if v is not None]
        sequence_repeats.append({
            "group":seq, "n":len(rows),
            "success_percent":round(100*mean(success_values),1) if success_values else None,
            "mean_yield":round(mean(yields),4) if yields else None,
            "mean_purity":round(mean(purities),4) if purities else None,
            "trend_ready":len(rows)>=min_trend_n,
        })

    coupling_repeats=[]
    for rep, rows in sorted(coupling_repeat_stats.items(), key=lambda kv: int(kv[0])):
        success_values=[int(r.get("success_flag")) for r in rows if r.get("success_flag") in (0,1)]
        yields=[v for v in (_num(r.get("yield_percent")) for r in rows) if v is not None]
        coupling_repeats.append({
            "group":rep, "n":len(rows),
            "success_percent":round(100*mean(success_values),1) if success_values else None,
            "mean_yield":round(mean(yields),4) if yields else None,
            "trend_ready":len(rows)>=min_trend_n,
        })

    cleavage_conditions: dict[str, int] = Counter()
    cleavage_operators: Counter[str] = Counter()
    for row in cleavage:
        eq=_num(row.get("cleavage_eq") if row.get("cleavage_eq") is not None else row.get("tfa_eq"))
        hours=_num(row.get("cleavage_time_h") if row.get("cleavage_time_h") is not None else row.get("time_h"))
        cocktail=_text(row.get("cocktail") or row.get("cocktail_ratio") or row.get("tfa_tis_dw"))
        label=f"{eq:g} eq" if eq is not None else "eq ?"
        if hours is not None: label += f" / {hours:g} h"
        if cocktail: label += f" / {cocktail}"
        cleavage_conditions[label] += 1
        operator=_text(row.get("operator"))
        if operator: cleavage_operators[operator] += 1

    issue_types = Counter(_text(r.get("issue_type")) or "Other" for r in issues)
    issue_stages = Counter(_text(r.get("stage")) or "Unknown" for r in issues)
    sensitive=Counter()
    for row in issues:
        hay=" ".join(_text(row.get(k)).lower() for k in ("issue_type","observation","raw_observation","note"))
        if any(token in hay for token in ("oxid", "산화")): sensitive["Oxidation-related"] += 1
        if any(token in hay for token in ("cys", "cyste", "thiol", "시스테인")): sensitive["Cys/thiol-related"] += 1

    return {
        "version": VERSION, "minimum_trend_n": min_trend_n,
        "counts": {"loading": len(loading), "outcome": len(outcomes), "issue": len(issues), "cleavage": len(cleavage)},
        "unique_runs": len({_text(r.get("run_id")) for r in outcomes + issues if _text(r.get("run_id"))}),
        "loading_by_resin": group_mean(loading, "resin_type", "loading_rate_mmol_g"),
        "loading_by_loaded_aa": group_mean(loading, "amino_acid_normalized", "loading_rate_mmol_g"),
        "outcome_success_by_length": success,
        "yield_by_stage": group_mean(outcomes, "stage", "yield_percent"),
        "purity_by_stage": group_mean(outcomes, "stage", "purity_percent"),
        "same_sequence_history": sequence_repeats,
        "outcome_by_coupling_repeats": coupling_repeats,
        "cleavage_condition_counts": [{"group":k,"n":v,"trend_ready":v>=min_trend_n} for k,v in cleavage_conditions.most_common()],
        "cleavage_operator_counts": [{"group":k,"n":v,"trend_ready":v>=min_trend_n} for k,v in cleavage_operators.most_common()],
        "outcome_by_month": [{"group":k,"n":v,"trend_ready":v>=min_trend_n} for k,v in sorted(month_counts.items())],
        "issue_types": [{"group": k, "n": v, "trend_ready": v >= min_trend_n} for k, v in issue_types.most_common()],
        "issue_stages": [{"group": k, "n": v, "trend_ready": v >= min_trend_n} for k, v in issue_stages.most_common()],
        "sensitive_issue_counts": [{"group": k, "n": v, "trend_ready": v >= min_trend_n} for k, v in sensitive.most_common()],
        "small_sample_note": f"Groups with n < {min_trend_n} are shown as descriptive records only; no trend claim is made.",
    }


def record_quality_issues(*, loading_rows: Iterable[Mapping[str, Any]] = (), outcome_rows: Iterable[Mapping[str, Any]] = (),
                          issue_rows: Iterable[Mapping[str, Any]] = ()) -> list[dict[str, Any]]:
    """Return auditable review flags; flags never auto-exclude a record."""
    findings: list[dict[str, Any]] = []
    seen: Counter[tuple[str, str, str]] = Counter()
    for row in loading_rows:
        record_id = _text(row.get("record_id"))
        value = _num(row.get("loading_rate_mmol_g"))
        if value is not None and value < 0:
            findings.append({"record_id": record_id, "kind": "loading", "code": "NEGATIVE_LOADING", "detail": f"Measured loading={value:g} mmol/g"})
        if int(_num(row.get("outlier_flag")) or 0):
            findings.append({"record_id": record_id, "kind": "loading", "code": "LOADING_OUTLIER_FLAG", "detail": "This loading record is already flagged as an outlier and should be reviewed before recommendation/model use."})
        if not _text(row.get("resin_type")) or not _text(row.get("amino_acid_normalized") or row.get("amino_acid_raw")):
            findings.append({"record_id": record_id, "kind": "loading", "code": "MISSING_CONDITION", "detail": "Resin or loaded amino-acid identity is missing."})
        if not _text(row.get("run_id")):
            findings.append({"record_id": record_id, "kind": "loading", "code": "MISSING_RUN_LINK", "detail": "No run_id is attached."})
        key = (_text(row.get("run_id")), _text(row.get("resin_key")), _text(row.get("amino_acid_key")))
        if any(key): seen[("loading", *key)] += 1
    for row in outcome_rows:
        record_id = _text(row.get("record_id"))
        for field in ("yield_percent", "purity_percent"):
            value = _num(row.get(field))
            if value is not None and not (0 <= value <= 100):
                findings.append({"record_id": record_id, "kind": "outcome", "code": "PERCENT_RANGE", "detail": f"{field}={value:g} is outside 0-100%."})
        if not _text(row.get("sequence")):
            findings.append({"record_id": record_id, "kind": "outcome", "code": "MISSING_SEQUENCE", "detail": "Sequence is missing."})
        if not _text(row.get("run_id")):
            findings.append({"record_id": record_id, "kind": "outcome", "code": "MISSING_RUN_LINK", "detail": "No run_id is attached."})
        state = _text(row.get("record_state")).lower()
        if state == "failed_informative" and not _text(row.get("observation")):
            findings.append({"record_id": record_id, "kind": "outcome", "code": "FAILED_WITHOUT_CAUSE", "detail": "Failed-but-informative record has no observation/cause note."})
        key = (_text(row.get("run_id")), _text(row.get("stage")), _text(row.get("result")))
        if any(key): seen[("outcome", *key)] += 1
        planned = _parse_json(row.get("planner_snapshot_json")); actual = _parse_json(row.get("actual_condition_json"))
        deviation_count=int(_num(actual.get("deviation_count")) or 0) if actual else 0
        planner_change_count=int(_num(actual.get("planner_change_count")) or 0) if actual else 0
        if deviation_count > 0:
            findings.append({"record_id": record_id, "kind": "outcome", "code": "PLAN_ACTUAL_DEVIATION_RECORDED", "detail": f"{deviation_count} explicit execution deviation(s) are recorded against the frozen Planner condition."})
        if planner_change_count > 0:
            findings.append({"record_id": record_id, "kind": "outcome", "code": "PLANNER_CHANGED_AFTER_START", "detail": f"{planner_change_count} Planner field(s) changed after the Run started. These edits are review context only and are not treated as performed experimental conditions without execution evidence."})
        elif actual and planned and any(k in planned and planned.get(k) != v for k, v in actual.items()):
            # Compatibility with older V6 preview records that stored a flat actual-condition mapping.
            findings.append({"record_id": record_id, "kind": "outcome", "code": "PLAN_ACTUAL_MISMATCH", "detail": "Legacy actual-condition data differs from the stored Planner snapshot."})
    for row in issue_rows:
        if not _text(row.get("run_id")):
            findings.append({"record_id": _text(row.get("record_id")), "kind": "issue", "code": "MISSING_RUN_LINK", "detail": "No run_id is attached."})
    for key, count in seen.items():
        if count > 1:
            kind, *parts = key
            findings.append({"record_id": "", "kind": kind, "code": "POSSIBLE_DUPLICATE", "detail": f"{count} records share key: {' / '.join(parts)}"})
    return findings


__all__ = [
    "VERSION", "RECORD_STATES", "SOURCE_LABELS", "evidence_trace", "attach_evidence_trace",
    "scenario_summary", "compare_scenarios", "execution_summary", "analytics_snapshot", "record_quality_issues",
]
