
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional
import csv
import json

CANDIDATE_DASHBOARD_VERSION = "3.6.0"


def _read_csv_rows(path: str | Path | None) -> list[dict[str, Any]]:
    if not path:
        return []
    p = Path(path)
    if not p.exists():
        return []
    try:
        sample = p.read_text(encoding="utf-8", errors="ignore")[:4096]
        delimiter = "\t" if sample.count("\t") > sample.count(",") else ","
        with p.open("r", encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f, delimiter=delimiter))
    except Exception:
        return []


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: Optional[list[str]] = None) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = list(rows[0].keys()) if rows else ["note"]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return str(path)


def _write_json(path: Path, payload: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)


def _write_text(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


def _float_or_none(v: Any):
    try:
        if v is None:
            return None
        s = str(v).strip().replace(",", "")
        if not s or s.lower() in {"nan", "none", "null", "na", "n/a", "-"}:
            return None
        return float(s)
    except Exception:
        return None


def _candidate_id_from_row(row: dict[str, Any], fallback: str = "") -> str:
    for key in ["candidate_id", "id", "name", "peptide_id", "sequence_id", "rank_id", "pose_id"]:
        val = row.get(key)
        if val:
            return str(val)
    seq = row.get("sequence") or row.get("Sequence") or row.get("peptide") or row.get("clean_sequence")
    if seq:
        return str(seq)[:48]
    return fallback or "candidate_unknown"


def _sequence_from_row(row: dict[str, Any]) -> str:
    for key in ["sequence", "Sequence", "peptide", "clean_sequence", "candidate_sequence", "notation"]:
        if row.get(key):
            return str(row.get(key))
    return ""


def _rank_value(row: dict[str, Any]) -> float:
    for key in ["total_score", "score", "best_score", "pepforge_score", "calibration_score"]:
        v = _float_or_none(row.get(key))
        if v is not None:
            return v
    return 0.0


def normalize_design_candidates(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out = {}
    for i, r in enumerate(rows, start=1):
        cid = _candidate_id_from_row(r, f"design_{i:04d}")
        out.setdefault(cid, {"candidate_id": cid})
        out[cid].update({
            "candidate_id": cid,
            "sequence": _sequence_from_row(r),
            "design_score": _rank_value(r),
            "design_rank": r.get("rank") or r.get("Rank") or i,
            "design_source": "design_engine",
        })
    return out


def summarize_docking_rows(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by = {}
    for i, r in enumerate(rows, start=1):
        cid = _candidate_id_from_row(r, r.get("pose_id") or f"docking_{i:04d}")
        by.setdefault(cid, {"candidate_id": cid, "docking_contact_count": 0, "docking_clash_count": 0, "best_docking_score": None})
        contact = _float_or_none(r.get("contact_count"))
        clash = _float_or_none(r.get("clash_count"))
        score = _float_or_none(r.get("score_lower_better") or r.get("score"))
        if contact is not None:
            by[cid]["docking_contact_count"] = max(float(by[cid].get("docking_contact_count") or 0), contact)
        if clash is not None:
            by[cid]["docking_clash_count"] = max(float(by[cid].get("docking_clash_count") or 0), clash)
        if score is not None:
            old = by[cid].get("best_docking_score")
            by[cid]["best_docking_score"] = score if old is None else min(float(old), score)
        if r.get("pose_quality_grade"):
            by[cid]["pose_quality_grade"] = r.get("pose_quality_grade")
    return by


def summarize_external_docking(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by = {}
    for i, r in enumerate(rows, start=1):
        cid = _candidate_id_from_row(r, f"external_{i:04d}")
        score = _float_or_none(r.get("score"))
        group_rank = _float_or_none(r.get("normalized_group_rank"))
        by.setdefault(cid, {"candidate_id": cid, "external_docking_records": 0})
        by[cid]["external_docking_records"] += 1
        if score is not None:
            direction = str(r.get("direction") or r.get("score_type") or "").lower()
            key = "best_external_score"
            old = by[cid].get(key)
            if old is None:
                by[cid][key] = score
            elif "higher_better" in direction:
                by[cid][key] = max(float(old), score)
            else:
                by[cid][key] = min(float(old), score)
        if group_rank is not None:
            oldr = by[cid].get("best_external_group_rank")
            by[cid]["best_external_group_rank"] = group_rank if oldr is None else min(float(oldr), group_rank)
        if r.get("tool"):
            tools = set(str(by[cid].get("external_tools","")).split(";")) if by[cid].get("external_tools") else set()
            tools.add(str(r.get("tool")))
            by[cid]["external_tools"] = ";".join(sorted(t for t in tools if t))
    return by


def summarize_calibration(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by = {}
    for i, r in enumerate(rows, start=1):
        cid = _candidate_id_from_row(r, f"calibration_{i:04d}")
        by.setdefault(cid, {"candidate_id": cid})
        by[cid].update({
            "calibration_predicted_class": r.get("predicted_class") or r.get("potency_class") or "",
            "calibration_confidence": r.get("calibration_confidence") or r.get("confidence") or "",
            "calibration_score": _float_or_none(r.get("candidate_score") or r.get("calibration_score")),
        })
    return by



def summarize_experimental(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by = {}
    for i, r in enumerate(rows, start=1):
        cid = _candidate_id_from_row(r, f"experimental_{i:04d}")
        by.setdefault(cid, {"candidate_id": cid})
        by[cid].update({
            "experimental_median_nM": _float_or_none(r.get("median_nM") or r.get("value_nM")),
            "experimental_potency_class": r.get("potency_class") or "",
            "experimental_n": r.get("n") or "",
        })
    return by

def merge_candidate_maps(*maps: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for m in maps:
        for cid, row in m.items():
            merged.setdefault(cid, {"candidate_id": cid})
            for k, v in row.items():
                if v not in (None, "", []):
                    merged[cid][k] = v
    return list(merged.values())


def dashboard_score(row: dict[str, Any]) -> float:
    score = 0.0
    ds = _float_or_none(row.get("design_score"))
    if ds is not None:
        score += max(-5.0, min(5.0, ds)) * 0.4
    contacts = _float_or_none(row.get("docking_contact_count")) or 0
    clashes = _float_or_none(row.get("docking_clash_count")) or 0
    score += min(3.0, contacts / 6.0) - min(3.0, clashes / 3.0)
    ext_rank = _float_or_none(row.get("best_external_group_rank"))
    if ext_rank is not None:
        score += max(0, 2.0 - 0.2 * (ext_rank - 1))
    cls = str(row.get("calibration_predicted_class",""))
    if "very_strong" in cls:
        score += 2.0
    elif "strong" in cls:
        score += 1.5
    elif "moderate" in cls:
        score += 0.7
    exp_nm = _float_or_none(row.get("experimental_median_nM"))
    if exp_nm is not None:
        if exp_nm <= 100:
            score += 2.0
        elif exp_nm <= 1000:
            score += 1.0
        elif exp_nm <= 10000:
            score += 0.3
    pq = str(row.get("pose_quality_grade",""))
    if pq.startswith("A_"):
        score += 1.0
    elif pq.startswith("B_"):
        score += 0.5
    return round(score, 3)


def recommendation_label(row: dict[str, Any]) -> str:
    s = _float_or_none(row.get("dashboard_score")) or 0
    clashes = _float_or_none(row.get("docking_clash_count")) or 0
    if clashes >= 8:
        return "deprioritize_geometry_review"
    if s >= 4:
        return "top_priority_for_external_validation"
    if s >= 2:
        return "keep_for_review"
    if s >= 0.5:
        return "secondary_candidate"
    return "low_priority_or_missing_evidence"


def build_candidate_dashboard(
    design_candidates_csv: str | Path | None = None,
    docking_contacts_csv: str | Path | None = None,
    external_docking_scores_csv: str | Path | None = None,
    calibration_predictions_csv: str | Path | None = None,
    experimental_candidate_summary_csv: str | Path | None = None,
) -> list[dict[str, Any]]:
    design = normalize_design_candidates(_read_csv_rows(design_candidates_csv))
    docking = summarize_docking_rows(_read_csv_rows(docking_contacts_csv))
    external = summarize_external_docking(_read_csv_rows(external_docking_scores_csv))
    calibration = summarize_calibration(_read_csv_rows(calibration_predictions_csv))
    experimental = summarize_experimental(_read_csv_rows(experimental_candidate_summary_csv))
    rows = merge_candidate_maps(design, docking, external, calibration, experimental)
    for r in rows:
        r["dashboard_score"] = dashboard_score(r)
        r["recommendation"] = recommendation_label(r)
        r["claim_boundary"] = "dashboard triage only; external validation required"
    rows.sort(key=lambda r: _float_or_none(r.get("dashboard_score")) or -999, reverse=True)
    for i, r in enumerate(rows, start=1):
        r["dashboard_rank"] = i
    return rows


def make_dashboard_svg(rows: list[dict[str, Any]], output_path: str | Path, top_n: int = 20) -> str:
    top = rows[:top_n] if rows else []
    width = 900
    row_h = 32
    height = 70 + max(1, len(top)) * row_h
    max_score = max([abs(_float_or_none(r.get("dashboard_score")) or 0) for r in top] + [1])
    bars = []
    for i, r in enumerate(top):
        y = 40 + i * row_h
        cid = str(r.get("candidate_id",""))[:36].replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
        val = _float_or_none(r.get("dashboard_score")) or 0
        bar_w = int((width - 260) * (max(0, val) / max_score))
        bars.append(f'<text x="10" y="{y+17}" font-size="12">{cid}</text>')
        bars.append(f'<rect x="250" y="{y}" width="{bar_w}" height="20" fill="#6fa8dc" />')
        bars.append(f'<text x="{260 + bar_w}" y="{y+16}" font-size="12">{val:.2f}</text>')
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">
<rect width="100%" height="100%" fill="white"/>
<text x="10" y="24" font-size="17" font-weight="bold">Pepforge Candidate Comparison Dashboard</text>
{''.join(bars)}
<text x="10" y="{height-12}" font-size="11">Screening prioritization only; external validation required.</text>
</svg>
"""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(svg, encoding="utf-8")
    return str(output_path)


def dashboard_markdown(rows: list[dict[str, Any]], chart_name: str = "candidate_dashboard_top.svg") -> str:
    top = rows[:25]
    table = []
    for r in top:
        table.append(
            f"| {r.get('dashboard_rank','')} | {r.get('candidate_id','')} | {r.get('dashboard_score','')} | "
            f"{r.get('recommendation','')} | {r.get('pose_quality_grade','')} | "
            f"{r.get('calibration_predicted_class','')} | {r.get('best_external_group_rank','')} |"
        )
    if not table:
        table.append("| - | no candidates | - | - | - | - | - |")
    return f"""# Pepforge Candidate Comparison Dashboard

![Dashboard chart]({chart_name})

## Top candidates

| Rank | Candidate | Dashboard score | Recommendation | Pose quality | Calibration class | External rank |
|---:|---|---:|---|---|---|---:|
{chr(10).join(table)}

## How to interpret this dashboard

- The dashboard combines available evidence for triage.
- Missing evidence reduces interpretability.
- Different external docking tools are not treated as one universal score.
- Candidates still require external docking/MD and experimental validation for strong claims.

## Blocked wording

- final Kd proven by Pepforge
- true nM binder proven by Pepforge
- experimental validation not needed
"""


def export_candidate_dashboard(
    output_dir: str | Path,
    design_candidates_csv: str | Path | None = None,
    docking_contacts_csv: str | Path | None = None,
    external_docking_scores_csv: str | Path | None = None,
    calibration_predictions_csv: str | Path | None = None,
    experimental_candidate_summary_csv: str | Path | None = None,
) -> dict[str, str]:
    out = Path(output_dir) / "candidate_comparison_dashboard"
    out.mkdir(parents=True, exist_ok=True)
    rows = build_candidate_dashboard(
        design_candidates_csv=design_candidates_csv,
        docking_contacts_csv=docking_contacts_csv,
        external_docking_scores_csv=external_docking_scores_csv,
        calibration_predictions_csv=calibration_predictions_csv,
        experimental_candidate_summary_csv=experimental_candidate_summary_csv,
    )
    fieldnames = [
        "dashboard_rank","candidate_id","sequence","dashboard_score","recommendation",
        "design_score","design_rank","docking_contact_count","docking_clash_count",
        "best_docking_score","pose_quality_grade","external_docking_records",
        "external_tools","best_external_score","best_external_group_rank",
        "calibration_predicted_class","calibration_confidence","calibration_score","experimental_median_nM","experimental_potency_class","experimental_n",
        "claim_boundary",
    ]
    csv_path = out / "candidate_comparison_dashboard.csv"
    _write_csv(csv_path, rows, fieldnames)
    svg_path = out / "candidate_dashboard_top.svg"
    make_dashboard_svg(rows, svg_path)
    md_path = out / "candidate_comparison_dashboard.md"
    _write_text(md_path, dashboard_markdown(rows, svg_path.name))
    summary = {
        "pepforge_version": CANDIDATE_DASHBOARD_VERSION,
        "candidate_count": len(rows),
        "top_candidate": rows[0] if rows else None,
        "inputs": {
            "design_candidates_csv": str(design_candidates_csv) if design_candidates_csv else "",
            "docking_contacts_csv": str(docking_contacts_csv) if docking_contacts_csv else "",
            "external_docking_scores_csv": str(external_docking_scores_csv) if external_docking_scores_csv else "",
            "calibration_predictions_csv": str(calibration_predictions_csv) if calibration_predictions_csv else "",
            "experimental_candidate_summary_csv": str(experimental_candidate_summary_csv) if experimental_candidate_summary_csv else "",
        },
        "claim_boundary": "Candidate dashboard supports triage only; external validation remains required.",
    }
    summary_json = out / "candidate_dashboard_summary.json"
    _write_json(summary_json, summary)
    manifest = out / "candidate_dashboard_manifest.json"
    _write_json(manifest, {
        "pepforge_version": CANDIDATE_DASHBOARD_VERSION,
        "files": {
            "dashboard_csv": str(csv_path),
            "dashboard_markdown": str(md_path),
            "dashboard_chart": str(svg_path),
            "summary": str(summary_json),
        },
    })
    return {
        "candidate_comparison_dashboard_csv": str(csv_path),
        "candidate_comparison_dashboard_md": str(md_path),
        "candidate_dashboard_top_svg": str(svg_path),
        "candidate_dashboard_summary": str(summary_json),
        "candidate_dashboard_manifest": str(manifest),
    }


__all__ = [
    "CANDIDATE_DASHBOARD_VERSION",
    "build_candidate_dashboard",
    "export_candidate_dashboard",
    "make_dashboard_svg",
    "dashboard_score",
    "recommendation_label",
]
