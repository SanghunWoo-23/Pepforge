from __future__ import annotations

"""Calibration Dataset Mode for Pepforge v2.9.0.

This module lets users import known peptide-target assay records and build a
conservative calibration summary that maps Pepforge-style screening scores to
relative activity classes.

It is intentionally lightweight and local:
- reads a CSV calibration dataset,
- normalizes Kd/IC50/EC50-like values to nM when possible,
- creates potency classes,
- summarizes score distributions by class,
- predicts a conservative class for new candidates by nearest calibrated score.

This does not produce final experimental Kd. It supports within-dataset candidate
prioritization and claim-bounded reporting.
"""

from pathlib import Path
from typing import Any, Dict, Iterable, Optional
import csv
import json
import math
import statistics
import re

CALIBRATION_MODE_VERSION = "2.9.0"


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


def _float_or_none(value: Any) -> Optional[float]:
    if value is None:
        return None
    s = str(value).strip().replace(",", "")
    if not s or s.lower() in {"na", "n/a", "none", "null", "-", "not tested"}:
        return None
    s = re.sub(r"^[<>~= ]+", "", s)
    try:
        return float(s)
    except Exception:
        return None


def normalize_affinity_to_nM(value: Any, unit: str = "nM") -> Optional[float]:
    """Normalize Kd/IC50/EC50-like values to nM."""
    v = _float_or_none(value)
    if v is None:
        return None
    u = str(unit or "nM").strip().lower().replace("μ", "u")
    if u in {"nm", "nanomolar"}:
        return v
    if u in {"um", "µm", "micromolar", "uM".lower()}:
        return v * 1000.0
    if u in {"mm", "millimolar"}:
        return v * 1_000_000.0
    if u in {"pm", "picomolar"}:
        return v / 1000.0
    if u in {"m", "molar"}:
        return v * 1_000_000_000.0
    return v


def potency_class_from_nM(value_nM: Optional[float]) -> str:
    if value_nM is None or value_nM <= 0:
        return "unknown"
    if value_nM <= 10:
        return "very_strong_nM"
    if value_nM <= 100:
        return "strong_nM"
    if value_nM <= 1000:
        return "moderate_uM_edge"
    if value_nM <= 10000:
        return "weak_uM"
    return "very_weak_or_inactive"


def _score_from_row(row: dict[str, Any]) -> Optional[float]:
    for key in [
        "pepforge_score",
        "score",
        "score_lower_better",
        "screening_score",
        "affinity_score",
        "contact_score",
    ]:
        if key in row:
            v = _float_or_none(row.get(key))
            if v is not None:
                return v
    contacts = _float_or_none(row.get("contact_count"))
    clashes = _float_or_none(row.get("clash_count"))
    hb = _float_or_none(row.get("hydrogen_bond_contacts"))
    hyd = _float_or_none(row.get("hydrophobic_contacts"))
    if contacts is not None:
        return -(contacts + 0.5*(hb or 0) + 0.25*(hyd or 0) - 1.5*(clashes or 0))
    return None


def read_calibration_dataset(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Calibration dataset not found: {p}")
    rows: list[dict[str, Any]] = []
    with p.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for i, raw in enumerate(reader, start=1):
            row = {str(k).strip(): (v.strip() if isinstance(v, str) else v) for k, v in raw.items() if k is not None}
            unit = row.get("affinity_unit") or row.get("unit") or "nM"
            value = row.get("affinity_value") or row.get("Kd") or row.get("IC50") or row.get("EC50") or row.get("kd_nm")
            value_nM = normalize_affinity_to_nM(value, unit)
            score = _score_from_row(row)
            row["_row"] = i
            row["affinity_nM"] = value_nM
            row["potency_class"] = potency_class_from_nM(value_nM)
            row["calibration_score"] = score
            row["usable_for_calibration"] = bool(score is not None and value_nM is not None and value_nM > 0)
            rows.append(row)
    return rows


def build_calibration_model(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(rows)
    usable = [r for r in rows if r.get("usable_for_calibration")]
    by_class: dict[str, list[float]] = {}
    pairs = []
    for r in usable:
        cls = str(r.get("potency_class", "unknown"))
        score = float(r["calibration_score"])
        by_class.setdefault(cls, []).append(score)
        pairs.append({
            "sequence": r.get("sequence", ""),
            "target": r.get("target", ""),
            "affinity_nM": r.get("affinity_nM"),
            "potency_class": cls,
            "calibration_score": score,
        })

    class_stats = []
    for cls, vals in sorted(by_class.items()):
        class_stats.append({
            "potency_class": cls,
            "n": len(vals),
            "score_mean": statistics.mean(vals),
            "score_median": statistics.median(vals),
            "score_min": min(vals),
            "score_max": max(vals),
        })

    warnings = []
    if len(usable) < 5:
        warnings.append("Calibration dataset has fewer than 5 usable records; confidence should be treated as low.")
    if len(by_class) < 2:
        warnings.append("Calibration dataset has fewer than 2 potency classes; class separation is weak.")
    if not usable:
        warnings.append("No usable calibration records with both affinity and score were found.")

    return {
        "pepforge_version": CALIBRATION_MODE_VERSION,
        "total_records": len(rows),
        "usable_records": len(usable),
        "class_count": len(by_class),
        "class_statistics": class_stats,
        "calibration_pairs": pairs,
        "warnings": warnings,
        "confidence": "high" if len(usable) >= 20 and len(by_class) >= 3 else ("medium" if len(usable) >= 8 and len(by_class) >= 2 else "low"),
        "claim_boundary": "Calibration supports within-dataset prioritization. It does not prove final Kd or true binding.",
    }


def predict_candidate_class(model: dict[str, Any], candidate_score: Any) -> dict[str, Any]:
    score = _float_or_none(candidate_score)
    if score is None:
        return {
            "predicted_class": "unknown",
            "confidence": "none",
            "note": "Candidate score was missing or invalid.",
        }
    stats = model.get("class_statistics") or []
    if not stats:
        return {
            "predicted_class": "unknown",
            "confidence": "none",
            "note": "No calibration model class statistics available.",
        }
    nearest = sorted(stats, key=lambda s: abs(float(s.get("score_median", 0)) - score))[0]
    cls = nearest.get("potency_class", "unknown")
    conf = model.get("confidence", "low")
    safe = (
        "calibrated_screening_candidate"
        if cls in {"very_strong_nM", "strong_nM"} else
        "screening_candidate_for_review"
    )
    return {
        "candidate_score": score,
        "predicted_class": cls,
        "calibration_confidence": conf,
        "safe_interpretation": safe,
        "allowed_wording": "predicted nM-range candidate, external validation required" if cls in {"very_strong_nM", "strong_nM"} else "screening-level candidate, external validation required",
        "blocked_wording": "true nM binder or final Kd without external validation",
    }


def export_calibration_dataset_template(output_dir: str | Path) -> str:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "pepforge_calibration_dataset_template.csv"
    rows = [
        {
            "target": "example_target",
            "sequence": "Ac-EEMQRR-NH2",
            "modifications": "Ac,NH2",
            "assay_type": "SPR",
            "affinity_type": "Kd",
            "affinity_value": "85",
            "affinity_unit": "nM",
            "pepforge_score": "-7.2",
            "contact_count": "12",
            "clash_count": "1",
            "hydrogen_bond_contacts": "3",
            "hydrophobic_contacts": "5",
            "source": "replace_with_reference_or_internal_id",
            "notes": "example row; replace with real measured or literature data",
        }
    ]
    _write_csv(path, rows)
    return str(path)


def export_calibration_report(
    dataset_csv: str | Path,
    output_dir: str | Path,
    candidate_score: Any = None,
) -> Dict[str, str]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    cal_dir = out / "calibration_dataset_mode"
    cal_dir.mkdir(parents=True, exist_ok=True)

    rows = read_calibration_dataset(dataset_csv)
    model = build_calibration_model(rows)

    normalized_csv = cal_dir / "calibration_dataset_normalized.csv"
    normalized_fields = [
        "_row", "target", "sequence", "modifications", "assay_type", "affinity_type",
        "affinity_value", "affinity_unit", "affinity_nM", "potency_class",
        "calibration_score", "usable_for_calibration", "source", "notes",
    ]
    _write_csv(normalized_csv, rows, normalized_fields)

    stats_csv = cal_dir / "calibration_class_statistics.csv"
    _write_csv(stats_csv, model.get("class_statistics") or [], [
        "potency_class", "n", "score_mean", "score_median", "score_min", "score_max"
    ])

    model_json = cal_dir / "calibration_model_summary.json"
    _write_json(model_json, model)

    prediction = predict_candidate_class(model, candidate_score) if candidate_score is not None else {
        "predicted_class": "not_requested",
        "note": "No candidate score was provided.",
    }
    prediction_json = cal_dir / "candidate_calibration_prediction.json"
    _write_json(prediction_json, prediction)

    claim_guard = cal_dir / "calibration_claim_guard_table.csv"
    _write_csv(claim_guard, [
        {"claim": "Pepforge calibrated model proves final Kd", "status": "blocked", "safe_expression": "calibrated screening class; external validation required"},
        {"claim": "candidate is a true nM binder", "status": "blocked", "safe_expression": "predicted nM-range candidate only if class/confidence supports it"},
        {"claim": "within-dataset prioritization", "status": "allowed", "safe_expression": "relative candidate ranking within the calibration dataset"},
        {"claim": "experimental validation not needed", "status": "blocked", "safe_expression": "experimental validation remains required for final claims"},
    ])

    report_md = cal_dir / "calibration_report.md"
    warnings = "\n".join(f"- {w}" for w in model.get("warnings", [])) or "- none"
    _write_text(report_md, f"""# Pepforge Calibration Dataset Report

**Pepforge version:** {CALIBRATION_MODE_VERSION}

## Dataset summary

- Total records: {model.get("total_records")}
- Usable records: {model.get("usable_records")}
- Potency classes: {model.get("class_count")}
- Calibration confidence: {model.get("confidence")}

## Candidate prediction

```json
{json.dumps(prediction, indent=2, ensure_ascii=False)}
```

## Warnings

{warnings}

## Claim boundary

Calibration supports within-dataset prioritization. It does not prove final Kd,
true binding, or experimental activity without external validation.
""")

    manifest = cal_dir / "calibration_manifest.json"
    _write_json(manifest, {
        "pepforge_version": CALIBRATION_MODE_VERSION,
        "dataset_csv": str(dataset_csv),
        "files": {
            "normalized_dataset": str(normalized_csv),
            "class_statistics": str(stats_csv),
            "model_summary": str(model_json),
            "candidate_prediction": str(prediction_json),
            "claim_guard": str(claim_guard),
            "report": str(report_md),
        },
    })

    return {
        "calibration_dataset_normalized": str(normalized_csv),
        "calibration_class_statistics": str(stats_csv),
        "calibration_model_summary": str(model_json),
        "candidate_calibration_prediction": str(prediction_json),
        "calibration_claim_guard_table": str(claim_guard),
        "calibration_report_md": str(report_md),
        "calibration_manifest": str(manifest),
    }


__all__ = [
    "CALIBRATION_MODE_VERSION",
    "normalize_affinity_to_nM",
    "potency_class_from_nM",
    "read_calibration_dataset",
    "build_calibration_model",
    "predict_candidate_class",
    "export_calibration_dataset_template",
    "export_calibration_report",
]
