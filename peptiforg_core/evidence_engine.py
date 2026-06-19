from __future__ import annotations

"""Pepforge Evidence Engine v3.0.0.

This module aggregates Pepforge-generated screening, structure, SPPS, docking,
target-quality, calibration, external-validation, and publication-report evidence
into one conservative evidence-grade summary.

It is designed to answer:
- What evidence exists?
- What evidence is missing?
- What claims are allowed?
- What claims are blocked?
- What next validation step is recommended?

It does not prove true binding, final Kd, or publication-grade MD.
"""

from pathlib import Path
from typing import Any, Dict, Iterable, Optional
import csv
import json
import re

EVIDENCE_ENGINE_VERSION = "3.0.0"


def _write_text(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


def _write_json(path: Path, payload: Dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: Optional[list[str]] = None) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = list(rows[0].keys()) if rows else ["note"]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)
    return str(path)


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


def _read_csv_rows(path: str | Path | None) -> list[dict[str, Any]]:
    if not path:
        return []
    p = Path(path)
    if not p.exists():
        return []
    try:
        with p.open("r", encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    except Exception:
        return []


def _exists(path: str | Path | None) -> bool:
    return bool(path) and Path(path).exists()


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except Exception:
        return None


def score_component(name: str, present: bool, quality: str = "unknown", weight: int = 1, note: str = "") -> dict[str, Any]:
    """Build a standardized evidence component row."""
    q = str(quality or "unknown").lower()
    if not present:
        points = 0
        status = "missing"
    elif q in {"strong", "high", "pass", "good", "a"}:
        points = weight
        status = "strong"
    elif q in {"medium", "partial", "review", "b", "c"}:
        points = max(1, round(weight * 0.6))
        status = "partial"
    elif q in {"weak", "low", "fail", "d"}:
        points = max(0, round(weight * 0.3))
        status = "weak"
    else:
        points = max(1, round(weight * 0.5))
        status = "present_review"
    return {
        "component": name,
        "present": bool(present),
        "quality": quality,
        "weight": weight,
        "points": points,
        "status": status,
        "note": note,
    }


def evidence_grade(total_points: int, max_points: int) -> str:
    if max_points <= 0:
        return "D"
    ratio = total_points / max_points
    if ratio >= 0.85:
        return "A"
    if ratio >= 0.65:
        return "B"
    if ratio >= 0.40:
        return "C"
    return "D"


def claim_level_from_grade(grade: str, experimental_present: bool = False) -> str:
    if experimental_present and grade in {"A", "B"}:
        return "experimentally_supported"
    if grade == "A":
        return "strong_computational_screening_package"
    if grade == "B":
        return "computational_screening_package"
    if grade == "C":
        return "triage_or_preparation_package"
    return "insufficient_evidence_package"


def allowed_claims_for_level(level: str) -> list[str]:
    base = [
        "Pepforge workflow package prepared",
        "screening-level candidate prioritization",
        "external validation required",
    ]
    if level == "strong_computational_screening_package":
        return base + [
            "strong computational screening candidate",
            "predicted nM-range candidate only if calibration/external evidence supports that wording",
            "validation bridge and publication report package available",
        ]
    if level == "computational_screening_package":
        return base + [
            "computationally prioritized peptide candidate",
            "screening evidence supports further validation",
        ]
    if level == "triage_or_preparation_package":
        return base + [
            "candidate requires additional docking/MD/experimental validation before strong wording",
        ]
    if level == "experimentally_supported":
        return base + [
            "experimentally supported only if external assay details and values are explicitly cited",
        ]
    return base


def blocked_claims() -> list[str]:
    return [
        "Pepforge proves true nM binding",
        "Pepforge provides final experimental Kd",
        "Pepforge replaces AutoDock Vina/Smina/Gnina",
        "Pepforge replaces GROMACS/AMBER/OpenMM/NAMD",
        "Pepforge internally performed full publication-grade all-atom MD",
        "experimental validation is unnecessary",
    ]


def build_evidence_components(
    hotspot_csv: str | Path | None = None,
    spps_plan_csv: str | Path | None = None,
    structure_metrics_csv: str | Path | None = None,
    target_quality_csv: str | Path | None = None,
    docking_contacts_csv: str | Path | None = None,
    calibration_summary_json: str | Path | None = None,
    external_md_summary_json: str | Path | None = None,
    publication_report_json: str | Path | None = None,
    experimental_evidence_csv: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Build evidence components from optional Pepforge output files."""
    comps: list[dict[str, Any]] = []

    comps.append(score_component("sequence_hotspot_evidence", _exists(hotspot_csv), "present", 1, "Hotspot or sequence-priority output."))
    comps.append(score_component("spps_planning_evidence", _exists(spps_plan_csv), "present", 1, "Synthesis plan/material table exists."))
    comps.append(score_component("modified_structure_evidence", _exists(structure_metrics_csv), "present", 2, "Modified peptide structure/conformer metrics exist."))

    # Target quality: fewer warning rows is better, but warning report presence itself is useful.
    tq_rows = _read_csv_rows(target_quality_csv)
    if tq_rows:
        serious = [r for r in tq_rows if str(r.get("level", "")).lower() in {"error", "fail"}]
        review = [r for r in tq_rows if str(r.get("level", "")).lower() in {"review"}]
        q = "high" if not serious and len(review) <= 2 else ("medium" if not serious else "weak")
        comps.append(score_component("target_quality_evidence", True, q, 2, f"{len(tq_rows)} target-preparation warning rows."))
    else:
        comps.append(score_component("target_quality_evidence", False, "missing", 2, "No target quality report."))

    # Docking contact rows
    dc_rows = _read_csv_rows(docking_contacts_csv)
    if dc_rows:
        q = "high" if len(dc_rows) >= 20 else ("medium" if len(dc_rows) >= 5 else "weak")
        comps.append(score_component("docking_contact_evidence", True, q, 2, f"{len(dc_rows)} contact rows."))
    else:
        comps.append(score_component("docking_contact_evidence", False, "missing", 2, "No docking/contact table."))

    cal = _read_json(calibration_summary_json)
    if cal:
        conf = cal.get("confidence") or cal.get("calibration_confidence") or "low"
        comps.append(score_component("calibration_dataset_evidence", True, conf, 2, f"Calibration confidence={conf}."))
    else:
        comps.append(score_component("calibration_dataset_evidence", False, "missing", 2, "No calibration model summary."))

    md = _read_json(external_md_summary_json)
    if md:
        grade = str(md.get("validation_grade", "D")).upper()
        comps.append(score_component("external_md_evidence", True, grade, 2, f"External MD validation grade={grade}."))
    else:
        comps.append(score_component("external_md_evidence", False, "missing", 2, "No external MD validation summary."))

    pub = _read_json(publication_report_json)
    if pub:
        readiness = (pub.get("publication_readiness") or {}).get("publication_readiness_grade", "C")
        comps.append(score_component("publication_report_evidence", True, readiness, 1, f"Publication readiness grade={readiness}."))
    else:
        comps.append(score_component("publication_report_evidence", False, "missing", 1, "No publication validation report."))

    exp_rows = _read_csv_rows(experimental_evidence_csv)
    if exp_rows:
        comps.append(score_component("experimental_evidence", True, "high", 4, f"{len(exp_rows)} experimental evidence rows imported."))
    else:
        comps.append(score_component("experimental_evidence", False, "missing", 4, "No experimental assay evidence imported."))

    return comps


def summarize_evidence(components: list[dict[str, Any]]) -> dict[str, Any]:
    total = int(sum(int(c.get("points", 0) or 0) for c in components))
    max_points = int(sum(int(c.get("weight", 0) or 0) for c in components))
    grade = evidence_grade(total, max_points)
    experimental_present = any(c.get("component") == "experimental_evidence" and c.get("present") for c in components)
    level = claim_level_from_grade(grade, experimental_present=experimental_present)
    missing = [c["component"] for c in components if not c.get("present")]
    weak = [c["component"] for c in components if str(c.get("status","")).lower() in {"weak", "partial"}]
    return {
        "pepforge_version": EVIDENCE_ENGINE_VERSION,
        "total_points": total,
        "max_points": max_points,
        "evidence_grade": grade,
        "claim_level": level,
        "experimental_evidence_present": experimental_present,
        "allowed_claims": allowed_claims_for_level(level),
        "blocked_claims": blocked_claims(),
        "missing_evidence": missing,
        "weak_or_partial_evidence": weak,
        "next_steps": recommended_next_steps(missing, weak, experimental_present),
        "claim_boundary": "Evidence Engine organizes evidence and claim wording. It does not prove final Kd or true binding without external/experimental validation.",
    }


def recommended_next_steps(missing: list[str], weak: list[str], experimental_present: bool) -> list[str]:
    steps: list[str] = []
    if "target_quality_evidence" in missing:
        steps.append("Run Target Structure Preparation and review chain/heteroatom/quality warnings.")
    if "docking_contact_evidence" in missing:
        steps.append("Run Docking Workbench contact screening or import external docking results.")
    if "calibration_dataset_evidence" in missing:
        steps.append("Import a calibration dataset with measured Kd/IC50/EC50-like records if relative potency wording is needed.")
    if "external_md_evidence" in missing:
        steps.append("Run or import external MD/minimization validation for stronger computational support.")
    if not experimental_present:
        steps.append("Perform or cite experimental binding validation before final Kd or true binder claims.")
    if weak:
        steps.append("Review weak/partial evidence components before using strong wording.")
    if not steps:
        steps.append("Evidence package is organized; use claim guard table before publication wording.")
    return steps


def export_evidence_engine_report(
    output_dir: str | Path,
    hotspot_csv: str | Path | None = None,
    spps_plan_csv: str | Path | None = None,
    structure_metrics_csv: str | Path | None = None,
    target_quality_csv: str | Path | None = None,
    docking_contacts_csv: str | Path | None = None,
    calibration_summary_json: str | Path | None = None,
    external_md_summary_json: str | Path | None = None,
    publication_report_json: str | Path | None = None,
    experimental_evidence_csv: str | Path | None = None,
) -> Dict[str, str]:
    out = Path(output_dir)
    ev_dir = out / "pepforge_evidence_engine"
    ev_dir.mkdir(parents=True, exist_ok=True)

    components = build_evidence_components(
        hotspot_csv=hotspot_csv,
        spps_plan_csv=spps_plan_csv,
        structure_metrics_csv=structure_metrics_csv,
        target_quality_csv=target_quality_csv,
        docking_contacts_csv=docking_contacts_csv,
        calibration_summary_json=calibration_summary_json,
        external_md_summary_json=external_md_summary_json,
        publication_report_json=publication_report_json,
        experimental_evidence_csv=experimental_evidence_csv,
    )
    summary = summarize_evidence(components)

    comp_csv = ev_dir / "evidence_components.csv"
    _write_csv(comp_csv, components, ["component","present","quality","weight","points","status","note"])

    summary_json = ev_dir / "evidence_summary.json"
    _write_json(summary_json, summary)

    claim_guard_csv = ev_dir / "evidence_claim_guard_table.csv"
    rows = []
    for claim in summary["allowed_claims"]:
        rows.append({"claim_type": "allowed_with_qualification", "claim": claim, "status": "allowed_with_qualification"})
    for claim in summary["blocked_claims"]:
        rows.append({"claim_type": "blocked", "claim": claim, "status": "blocked"})
    _write_csv(claim_guard_csv, rows)

    next_steps_csv = ev_dir / "missing_validation_checklist.csv"
    _write_csv(next_steps_csv, [{"step": s} for s in summary["next_steps"]])

    report_md = ev_dir / "evidence_report.md"
    allowed = "\n".join(f"- {c}" for c in summary["allowed_claims"])
    blocked = "\n".join(f"- {c}" for c in summary["blocked_claims"])
    missing = "\n".join(f"- {c}" for c in summary["missing_evidence"]) or "- none"
    steps = "\n".join(f"- {s}" for s in summary["next_steps"])
    _write_text(report_md, f"""# Pepforge Evidence Engine Report

**Pepforge version:** {EVIDENCE_ENGINE_VERSION}

## Evidence grade

- Grade: **{summary["evidence_grade"]}**
- Claim level: **{summary["claim_level"]}**
- Score: **{summary["total_points"]}/{summary["max_points"]}**

## Allowed wording

{allowed}

## Blocked wording

{blocked}

## Missing evidence

{missing}

## Recommended next steps

{steps}

## Claim boundary

{summary["claim_boundary"]}
""")

    manifest = ev_dir / "evidence_engine_manifest.json"
    _write_json(manifest, {
        "pepforge_version": EVIDENCE_ENGINE_VERSION,
        "files": {
            "components": str(comp_csv),
            "summary": str(summary_json),
            "claim_guard": str(claim_guard_csv),
            "missing_validation_checklist": str(next_steps_csv),
            "report": str(report_md),
        },
    })

    return {
        "evidence_components": str(comp_csv),
        "evidence_summary_json": str(summary_json),
        "evidence_claim_guard_table": str(claim_guard_csv),
        "missing_validation_checklist": str(next_steps_csv),
        "evidence_report_md": str(report_md),
        "evidence_engine_manifest": str(manifest),
    }


# -----------------------------------------------------------------------------
# v3.1.0 Project Auto-Scan and Readability Helpers
# -----------------------------------------------------------------------------

EVIDENCE_FILE_PATTERNS = {
    "hotspot_csv": [
        "hotspot*.csv", "*hotspot*report*.csv", "*sequence*hotspot*.csv"
    ],
    "spps_plan_csv": [
        "editable_spps_plan.csv", "*spps*plan*.csv", "*material_usage*.csv"
    ],
    "structure_metrics_csv": [
        "*conformer_metrics.csv", "*structure_metrics*.csv", "*parameter_requirements.csv"
    ],
    "target_quality_csv": [
        "target_quality_warnings.csv", "*target*quality*.csv"
    ],
    "docking_contacts_csv": [
        "docking_residue_contact_report.csv", "*contact_report*.csv", "*contacts*.csv"
    ],
    "calibration_summary_json": [
        "calibration_model_summary.json", "*calibration*summary*.json"
    ],
    "external_md_summary_json": [
        "external_md_validation_summary.json", "*md*validation*summary*.json"
    ],
    "publication_report_json": [
        "publication_validation_report.json", "*publication*report*.json"
    ],
    "experimental_evidence_csv": [
        "*experimental*.csv", "*assay*.csv", "*binding*.csv"
    ],
}


def _candidate_files(project_dir: str | Path, patterns: list[str]) -> list[Path]:
    base = Path(project_dir)
    out: list[Path] = []
    if not base.exists():
        return out
    for pat in patterns:
        out.extend([p for p in base.rglob(pat) if p.is_file()])
    # Prefer more specific/latest-looking files by path length and modification time.
    seen = set()
    uniq = []
    for p in sorted(out, key=lambda x: (len(str(x)), -x.stat().st_mtime if x.exists() else 0)):
        rp = str(p.resolve())
        if rp not in seen:
            seen.add(rp)
            uniq.append(p)
    return uniq


def autoscan_project_folder(project_dir: str | Path) -> dict[str, Any]:
    """Auto-detect Pepforge evidence files in a project/output folder.

    The scan is intentionally conservative: one best candidate is selected per
    evidence slot, and all candidate paths are kept in the trace report.
    """
    base = Path(project_dir)
    scan: dict[str, Any] = {
        "project_dir": str(base),
        "exists": base.exists(),
        "selected": {},
        "candidates": {},
        "warnings": [],
    }
    if not base.exists():
        scan["warnings"].append("Project folder does not exist.")
        return scan
    for key, patterns in EVIDENCE_FILE_PATTERNS.items():
        candidates = _candidate_files(base, patterns)
        scan["candidates"][key] = [str(p) for p in candidates[:20]]
        scan["selected"][key] = str(candidates[0]) if candidates else None
    if not any(scan["selected"].values()):
        scan["warnings"].append("No recognizable Pepforge evidence files were found.")
    return scan


def export_evidence_engine_report_from_project(project_dir: str | Path, output_dir: str | Path | None = None) -> Dict[str, str]:
    """Auto-scan a project folder and export Evidence Engine report."""
    scan = autoscan_project_folder(project_dir)
    out = Path(output_dir) if output_dir else Path(project_dir)
    selected = scan.get("selected", {})
    paths = export_evidence_engine_report(
        output_dir=out,
        hotspot_csv=selected.get("hotspot_csv"),
        spps_plan_csv=selected.get("spps_plan_csv"),
        structure_metrics_csv=selected.get("structure_metrics_csv"),
        target_quality_csv=selected.get("target_quality_csv"),
        docking_contacts_csv=selected.get("docking_contacts_csv"),
        calibration_summary_json=selected.get("calibration_summary_json"),
        external_md_summary_json=selected.get("external_md_summary_json"),
        publication_report_json=selected.get("publication_report_json"),
        experimental_evidence_csv=selected.get("experimental_evidence_csv"),
    )
    ev_dir = Path(paths["evidence_report_md"]).parent
    scan_json = ev_dir / "project_autoscan_trace.json"
    _write_json(scan_json, scan)

    readable = ev_dir / "evidence_report_readable.md"
    summary = _read_json(paths["evidence_summary_json"])
    components = _read_csv_rows(paths["evidence_components"])
    _write_text(readable, render_readable_evidence_report(summary, components, scan))

    paths["project_autoscan_trace"] = str(scan_json)
    paths["evidence_report_readable_md"] = str(readable)
    return paths


def render_readable_evidence_report(summary: dict[str, Any], components: list[dict[str, Any]], scan: dict[str, Any] | None = None) -> str:
    """Create a more readable, human-facing Evidence Engine report."""
    grade = summary.get("evidence_grade", "D")
    level = summary.get("claim_level", "unknown")
    total = summary.get("total_points", 0)
    maxp = summary.get("max_points", 0)

    def _component_line(c):
        mark = "OK" if str(c.get("present")).lower() == "true" else "MISSING"
        return f"| {c.get('component','')} | {mark} | {c.get('quality','')} | {c.get('points','0')}/{c.get('weight','0')} | {c.get('note','')} |"

    comp_table = "\n".join([_component_line(c) for c in components]) or "| none | - | - | - | - |"
    allowed = "\n".join(f"- {x}" for x in summary.get("allowed_claims", [])) or "- none"
    blocked = "\n".join(f"- {x}" for x in summary.get("blocked_claims", [])) or "- none"
    steps = "\n".join(f"- {x}" for x in summary.get("next_steps", [])) or "- none"
    selected = (scan or {}).get("selected", {})
    selected_lines = "\n".join(f"- {k}: `{v}`" for k, v in selected.items() if v) or "- no auto-detected files"

    return f"""# Pepforge Evidence Engine Readable Report

## Overall conclusion

**Evidence grade:** `{grade}`  
**Claim level:** `{level}`  
**Score:** `{total}/{maxp}`

This report summarizes what evidence exists, what is missing, and what wording is safe.

## Auto-detected evidence files

{selected_lines}

## Evidence component table

| Component | Status | Quality | Points | Note |
|---|---:|---:|---:|---|
{comp_table}

## Allowed wording

{allowed}

## Blocked wording

{blocked}

## Recommended next steps

{steps}

## Boundary

This report improves readability and traceability. It does not prove final Kd, true nM binding, or replace external docking/MD/experimental validation.
"""



__all__ = [
    "EVIDENCE_ENGINE_VERSION",
    "score_component",
    "build_evidence_components",
    "summarize_evidence",
    "export_evidence_engine_report",
    "autoscan_project_folder",
    "export_evidence_engine_report_from_project",
    "render_readable_evidence_report",
    "allowed_claims_for_level",
    "blocked_claims",
]
