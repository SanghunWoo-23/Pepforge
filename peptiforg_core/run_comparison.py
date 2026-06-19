
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional
import csv
import json
import hashlib
import os

RUN_COMPARISON_VERSION = "3.9.0"


def _read_csv_rows(path: str | Path | None) -> list[dict[str, Any]]:
    if not path:
        return []
    p = Path(path)
    if not p.exists():
        return []
    sample = p.read_text(encoding="utf-8", errors="ignore")[:4096]
    delimiter = "\t" if sample.count("\t") > sample.count(",") else ","
    with p.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=delimiter))


def _read_json(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}


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


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def inventory_files(folder: str | Path) -> list[dict[str, Any]]:
    base = Path(folder)
    rows = []
    if not base.exists():
        return rows
    for p in sorted(base.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(base).as_posix()
        # Skip volatile caches if a user compares a live folder.
        if "__pycache__" in rel or ".pytest_cache" in rel or rel.endswith(".pyc"):
            continue
        rows.append({
            "relative_path": rel,
            "size_bytes": p.stat().st_size,
            "sha256": _sha256(p),
        })
    return rows


def compare_file_inventories(old_folder: str | Path, new_folder: str | Path) -> list[dict[str, Any]]:
    old = {r["relative_path"]: r for r in inventory_files(old_folder)}
    new = {r["relative_path"]: r for r in inventory_files(new_folder)}
    paths = sorted(set(old) | set(new))
    rows = []
    for rel in paths:
        if rel not in old:
            status = "added"
        elif rel not in new:
            status = "removed"
        elif old[rel]["sha256"] != new[rel]["sha256"]:
            status = "modified"
        else:
            status = "unchanged"
        if status != "unchanged":
            rows.append({
                "relative_path": rel,
                "status": status,
                "old_size_bytes": old.get(rel, {}).get("size_bytes", ""),
                "new_size_bytes": new.get(rel, {}).get("size_bytes", ""),
                "old_sha256": old.get(rel, {}).get("sha256", ""),
                "new_sha256": new.get(rel, {}).get("sha256", ""),
            })
    return rows


def _candidate_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out = {}
    for i, r in enumerate(rows, start=1):
        cid = str(r.get("candidate_id") or r.get("id") or r.get("sequence") or f"candidate_{i:04d}")
        out[cid] = r
    return out


def compare_candidate_dashboards(old_csv: str | Path, new_csv: str | Path) -> list[dict[str, Any]]:
    old = _candidate_map(_read_csv_rows(old_csv))
    new = _candidate_map(_read_csv_rows(new_csv))
    ids = sorted(set(old) | set(new))
    rows = []
    for cid in ids:
        if cid not in old:
            status = "added_candidate"
        elif cid not in new:
            status = "removed_candidate"
        else:
            status = "retained_candidate"
        old_rank = _float_or_none(old.get(cid, {}).get("dashboard_rank"))
        new_rank = _float_or_none(new.get(cid, {}).get("dashboard_rank"))
        old_score = _float_or_none(old.get(cid, {}).get("dashboard_score"))
        new_score = _float_or_none(new.get(cid, {}).get("dashboard_score"))
        rank_delta = ""
        score_delta = ""
        if old_rank is not None and new_rank is not None:
            # negative is improved rank, positive is worse rank
            rank_delta = new_rank - old_rank
        if old_score is not None and new_score is not None:
            score_delta = round(new_score - old_score, 4)
        rows.append({
            "candidate_id": cid,
            "status": status,
            "old_rank": old_rank if old_rank is not None else "",
            "new_rank": new_rank if new_rank is not None else "",
            "rank_delta": rank_delta,
            "old_score": old_score if old_score is not None else "",
            "new_score": new_score if new_score is not None else "",
            "score_delta": score_delta,
            "old_recommendation": old.get(cid, {}).get("recommendation", ""),
            "new_recommendation": new.get(cid, {}).get("recommendation", ""),
            "old_class": old.get(cid, {}).get("calibration_predicted_class", "") or old.get(cid, {}).get("experimental_potency_class", ""),
            "new_class": new.get(cid, {}).get("calibration_predicted_class", "") or new.get(cid, {}).get("experimental_potency_class", ""),
        })
    rows.sort(key=lambda r: (str(r["status"]), _float_or_none(r.get("new_rank")) or 999999))
    return rows


def compare_evidence_summaries(old_json: str | Path | None, new_json: str | Path | None) -> dict[str, Any]:
    old = _read_json(old_json)
    new = _read_json(new_json)
    keys = sorted(set(old) | set(new))
    changed = {}
    for k in keys:
        if old.get(k) != new.get(k):
            changed[k] = {"old": old.get(k), "new": new.get(k)}
    return {
        "old_evidence_grade": old.get("evidence_grade"),
        "new_evidence_grade": new.get("evidence_grade"),
        "old_claim_level": old.get("claim_level"),
        "new_claim_level": new.get("claim_level"),
        "old_total_points": old.get("total_points"),
        "new_total_points": new.get("total_points"),
        "changed_fields": changed,
    }


def run_comparison_report_text(candidate_rows: list[dict[str, Any]], file_rows: list[dict[str, Any]], evidence_delta: dict[str, Any]) -> str:
    added = sum(1 for r in candidate_rows if r.get("status") == "added_candidate")
    removed = sum(1 for r in candidate_rows if r.get("status") == "removed_candidate")
    retained = sum(1 for r in candidate_rows if r.get("status") == "retained_candidate")
    modified_files = sum(1 for r in file_rows if r.get("status") == "modified")
    added_files = sum(1 for r in file_rows if r.get("status") == "added")
    removed_files = sum(1 for r in file_rows if r.get("status") == "removed")
    top_lines = []
    for r in candidate_rows[:20]:
        top_lines.append(f"| {r.get('candidate_id')} | {r.get('status')} | {r.get('old_rank')} | {r.get('new_rank')} | {r.get('rank_delta')} | {r.get('score_delta')} |")
    if not top_lines:
        top_lines.append("| - | no candidate dashboard comparison | - | - | - | - |")
    return f"""# Pepforge Run Comparison Report

## Candidate changes

- Added candidates: {added}
- Removed candidates: {removed}
- Retained candidates: {retained}

## File changes

- Added files: {added_files}
- Removed files: {removed_files}
- Modified files: {modified_files}

## Evidence delta

- Old grade: {evidence_delta.get("old_evidence_grade")}
- New grade: {evidence_delta.get("new_evidence_grade")}
- Old claim level: {evidence_delta.get("old_claim_level")}
- New claim level: {evidence_delta.get("new_claim_level")}

## Candidate rank/score delta

| Candidate | Status | Old rank | New rank | Rank delta | Score delta |
|---|---|---:|---:|---:|---:|
{chr(10).join(top_lines)}

## Claim boundary

This report compares outputs between runs. It does not prove final Kd, true binding, or experimental validation.
"""


def export_run_comparison_package(
    old_project_dir: str | Path,
    new_project_dir: str | Path,
    output_dir: str | Path,
    old_dashboard_csv: str | Path | None = None,
    new_dashboard_csv: str | Path | None = None,
    old_evidence_summary_json: str | Path | None = None,
    new_evidence_summary_json: str | Path | None = None,
) -> dict[str, str]:
    out = Path(output_dir) / "run_comparison"
    out.mkdir(parents=True, exist_ok=True)

    file_rows = compare_file_inventories(old_project_dir, new_project_dir)
    files_csv = out / "changed_files_inventory.csv"
    _write_csv(files_csv, file_rows, ["relative_path","status","old_size_bytes","new_size_bytes","old_sha256","new_sha256"])

    candidate_rows = []
    if old_dashboard_csv and new_dashboard_csv:
        candidate_rows = compare_candidate_dashboards(old_dashboard_csv, new_dashboard_csv)
    candidate_csv = out / "candidate_rank_delta.csv"
    _write_csv(candidate_csv, candidate_rows, [
        "candidate_id","status","old_rank","new_rank","rank_delta","old_score","new_score","score_delta",
        "old_recommendation","new_recommendation","old_class","new_class"
    ])

    evidence_delta = compare_evidence_summaries(old_evidence_summary_json, new_evidence_summary_json)
    evidence_json = out / "evidence_delta_summary.json"
    _write_json(evidence_json, evidence_delta)

    report = out / "run_comparison_report.md"
    _write_text(report, run_comparison_report_text(candidate_rows, file_rows, evidence_delta))

    claim_guard = out / "run_comparison_claim_guard_table.csv"
    _write_csv(claim_guard, [
        {"claim": "new run proves true binder because rank improved", "status": "blocked", "safe_expression": "rank improved within the selected Pepforge evidence set"},
        {"claim": "file diff proves scientific improvement", "status": "blocked", "safe_expression": "file diff documents workflow/output changes"},
        {"claim": "run comparison supports audit trail", "status": "allowed", "safe_expression": "run comparison supports audit trail and review"},
    ])

    manifest = out / "run_comparison_manifest.json"
    _write_json(manifest, {
        "pepforge_version": RUN_COMPARISON_VERSION,
        "old_project_dir": str(old_project_dir),
        "new_project_dir": str(new_project_dir),
        "files": {
            "changed_files_inventory": str(files_csv),
            "candidate_rank_delta": str(candidate_csv),
            "evidence_delta_summary": str(evidence_json),
            "run_comparison_report": str(report),
            "claim_guard": str(claim_guard),
        },
        "claim_boundary": "Run comparison supports audit/review only; it does not prove final binding claims.",
    })

    return {
        "changed_files_inventory": str(files_csv),
        "candidate_rank_delta": str(candidate_csv),
        "evidence_delta_summary": str(evidence_json),
        "run_comparison_report": str(report),
        "run_comparison_claim_guard_table": str(claim_guard),
        "run_comparison_manifest": str(manifest),
    }


__all__ = [
    "RUN_COMPARISON_VERSION",
    "inventory_files",
    "compare_file_inventories",
    "compare_candidate_dashboards",
    "compare_evidence_summaries",
    "export_run_comparison_package",
]
