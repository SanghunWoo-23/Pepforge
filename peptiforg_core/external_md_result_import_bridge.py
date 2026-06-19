from __future__ import annotations

"""External MD result import and validation summary bridge for Pepforge v2.4.0.

This module does not run OpenMM, GROMACS, AMBER, NAMD, or any final MD engine.
It imports externally generated MD/minimization summary tables, normalizes them,
computes a conservative validation summary, and writes claim-guarded reports.
"""

from pathlib import Path
from typing import Any, Dict, Iterable, Optional
import csv
import json
import re

from peptiforg_core.all_atom_md_preparation_bridge import export_all_atom_md_preparation_bridge

MD_RESULT_IMPORT_BRIDGE_VERSION = "2.4.0"


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name or "modified_peptide")).strip("_") or "modified_peptide"


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
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return str(path)


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.lower() in {"na", "n/a", "none", "null", "-"}:
        return None
    try:
        return float(s)
    except Exception:
        return None


def _to_bool(value: Any) -> Optional[bool]:
    if value is None:
        return None
    s = str(value).strip().lower()
    if s in {"yes", "true", "1", "y", "completed", "done"}:
        return True
    if s in {"no", "false", "0", "n", "not_completed", "not done"}:
        return False
    return None


def import_external_md_results(path: str | Path) -> list[dict[str, Any]]:
    """Import a user-filled external MD result CSV."""
    p = Path(path)
    rows: list[dict[str, Any]] = []
    if not p.exists():
        raise FileNotFoundError(f"External MD result file not found: {p}")
    with p.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            row = {str(k).strip(): (v.strip() if isinstance(v, str) else v) for k, v in raw.items() if k is not None}
            row["production_time_ns_num"] = _to_float(row.get("production_time_ns"))
            row["rmsd_A_num"] = _to_float(row.get("rmsd_A") or row.get("rmsd"))
            row["contact_persistence_fraction_num"] = _to_float(row.get("contact_persistence_fraction") or row.get("contact_persistence"))
            row["clash_count_after_refinement_num"] = _to_float(row.get("clash_count_after_refinement") or row.get("clash_count"))
            row["minimization_completed_bool"] = _to_bool(row.get("minimization_completed"))
            row["equilibration_completed_bool"] = _to_bool(row.get("equilibration_completed"))
            rows.append(row)
    return rows


def summarize_external_md_results(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Compute conservative validation summary from imported external results."""
    rows = list(rows)
    if not rows:
        return {
            "import_status": "empty",
            "validation_grade": "D",
            "claim_status": "no external MD result imported",
            "safe_interpretation": "No external MD/minimization evidence was imported.",
            "warnings": ["External result CSV had no rows."],
            "normalized_rows": [],
        }

    warnings: list[str] = []
    best_grade = "D"
    completed_any = False
    minimized_any = False
    production_any = False
    stable_like = False
    normalized_rows = []

    def grade_rank(g: str) -> int:
        return {"A": 0, "B": 1, "C": 2, "D": 3}.get(g, 3)

    for i, row in enumerate(rows, start=1):
        prod = row.get("production_time_ns_num")
        rmsd = row.get("rmsd_A_num")
        persist = row.get("contact_persistence_fraction_num")
        clashes = row.get("clash_count_after_refinement_num")
        minimized = row.get("minimization_completed_bool")
        equil = row.get("equilibration_completed_bool")
        engine = row.get("engine") or "unknown"

        if minimized:
            minimized_any = True
        if prod is not None and prod > 0:
            production_any = True
        if minimized or (prod is not None and prod > 0):
            completed_any = True

        row_grade = "D"
        row_call = "insufficient_external_evidence"
        if minimized:
            row_grade = "C"
            row_call = "external_minimization_imported"
        if prod is not None and prod >= 1.0:
            row_grade = "B"
            row_call = "short_external_md_imported"
        if prod is not None and prod >= 10.0 and persist is not None and persist >= 0.50 and (clashes is None or clashes <= 5):
            row_grade = "A"
            row_call = "external_md_supports_stable_candidate"
        if rmsd is not None and rmsd > 8.0:
            warnings.append(f"row {i}: high RMSD ({rmsd} A) may indicate unstable pose or protocol issue.")
            if row_grade == "A":
                row_grade = "B"
        if persist is not None and persist < 0.25:
            warnings.append(f"row {i}: low contact persistence ({persist}) weakens interaction evidence.")
            if row_grade in {"A", "B"}:
                row_grade = "C"
        if clashes is not None and clashes > 20:
            warnings.append(f"row {i}: many clashes after refinement ({clashes}) require structure review.")
            row_grade = "D"

        if row_grade == "A":
            stable_like = True
        if grade_rank(row_grade) < grade_rank(best_grade):
            best_grade = row_grade

        normalized_rows.append({
            "row": i,
            "engine": engine,
            "production_time_ns": prod,
            "rmsd_A": rmsd,
            "contact_persistence_fraction": persist,
            "clash_count_after_refinement": clashes,
            "minimization_completed": minimized,
            "equilibration_completed": equil,
            "validation_grade": row_grade,
            "validation_call": row_call,
        })

    if not completed_any:
        claim_status = "preparation_only"
        safe = "External MD/minimization results were not completed or were not clearly marked as completed."
    elif best_grade == "A":
        claim_status = "external_validation_supports_candidate"
        safe = "Imported external MD evidence supports a stable computational candidate, but does not prove experimental binding or final Kd."
    elif best_grade == "B":
        claim_status = "external_short_md_supports_review"
        safe = "Imported external short-MD evidence is supportive for screening, but remains validation-dependent."
    elif best_grade == "C":
        claim_status = "external_minimization_or_partial_evidence"
        safe = "Imported external evidence is partial and should be reported as minimization/limited-validation evidence only."
    else:
        claim_status = "weak_or_problematic_external_evidence"
        safe = "Imported external evidence is weak or problematic; avoid strong binding or stability claims."

    return {
        "import_status": "imported",
        "rows_imported": len(rows),
        "minimization_imported": minimized_any,
        "production_md_imported": production_any,
        "stable_like_external_md": stable_like,
        "validation_grade": best_grade,
        "claim_status": claim_status,
        "safe_interpretation": safe,
        "warnings": warnings,
        "normalized_rows": normalized_rows,
        "claim_boundary": "Pepforge imports and summarizes external MD results. It does not replace the external MD engine or prove experimental Kd.",
    }


def export_external_md_result_import_bridge(
    sequence: str,
    output_dir: str | Path,
    name: str = "modified_peptide",
    external_md_csv: Optional[str | Path] = None,
    receptor_path: Optional[str | Path] = None,
    center: tuple[float, float, float] = (0.0, 0.0, 0.0),
    size: tuple[float, float, float] = (22.0, 22.0, 22.0),
    low_spec_num_confs: int = 8,
) -> Dict[str, str]:
    """Create v2.4.0 external MD import and validation summary package."""
    out = Path(output_dir)
    safe = _safe_name(name)
    out.mkdir(parents=True, exist_ok=True)

    upstream = export_all_atom_md_preparation_bridge(
        sequence=sequence,
        output_dir=out,
        name=safe,
        receptor_path=receptor_path,
        center=center,
        size=size,
        low_spec_num_confs=low_spec_num_confs,
    )

    bridge_dir = out / "external_md_result_import_validation_bridge"
    bridge_dir.mkdir(parents=True, exist_ok=True)

    import_schema = bridge_dir / "external_md_result_import_template.csv"
    _write_csv(import_schema, [{
        "engine": "OpenMM",
        "engine_version": "example: 8.x",
        "force_field": "example: amber14/protein.ff14SB + custom modified peptide params",
        "water_model": "example: TIP3P",
        "system_atoms": "example: 58210",
        "minimization_completed": "yes",
        "equilibration_completed": "yes",
        "production_time_ns": "example: 10",
        "final_potential_energy": "optional",
        "rmsd_A": "example: 2.4",
        "contact_persistence_fraction": "example: 0.63",
        "clash_count_after_refinement": "example: 1",
        "notes": "Replace example row with actual external MD/minimization summary.",
    }])

    rows = import_external_md_results(external_md_csv) if external_md_csv else []
    summary = summarize_external_md_results(rows)

    normalized_csv = bridge_dir / "external_md_results_normalized.csv"
    _write_csv(normalized_csv, summary.get("normalized_rows") or [], fieldnames=[
        "row", "engine", "production_time_ns", "rmsd_A",
        "contact_persistence_fraction", "clash_count_after_refinement",
        "minimization_completed", "equilibration_completed",
        "validation_grade", "validation_call",
    ])

    summary_json = bridge_dir / "external_md_validation_summary.json"
    _write_json(summary_json, summary)

    summary_txt = bridge_dir / "external_md_validation_summary.txt"
    warnings_text = "\n".join(f"- {w}" for w in summary.get("warnings", [])) or "- none"
    _write_text(summary_txt, f"""Pepforge v2.4.0 External MD Result Import & Validation Summary
=================================================================

Input peptide notation
----------------------
{sequence}

Import status
-------------
{summary.get("import_status")}

Validation grade
----------------
{summary.get("validation_grade")}

Claim status
------------
{summary.get("claim_status")}

Safe interpretation
-------------------
{summary.get("safe_interpretation")}

Warnings
--------
{warnings_text}

Claim boundary
--------------
Pepforge imports and summarizes external MD/minimization results. It does not
perform final all-atom MD internally, does not replace OpenMM/GROMACS/AMBER/NAMD,
and does not prove experimental Kd or true nM binding without external/experimental
validation.
""")

    claim_guard = bridge_dir / "external_md_claim_guard_table.csv"
    _write_csv(claim_guard, [
        {"claim": "Pepforge completed full MD", "status": "blocked", "safe_expression": "Pepforge imported externally generated MD/minimization results"},
        {"claim": "final Kd from Pepforge", "status": "blocked", "safe_expression": "screening/evidence grade; experimental validation required"},
        {"claim": "true nM binder", "status": "blocked", "safe_expression": "predicted nM-range candidate if calibrated evidence supports it"},
        {"claim": "external MD supports candidate stability", "status": "conditional", "safe_expression": "allowed only if external MD result import contains adequate protocol and metrics"},
        {"claim": "Vina/GROMACS/OpenMM replacement", "status": "blocked", "safe_expression": "validation bridge and result-import workflow"},
    ])

    readme = bridge_dir / "README_EXTERNAL_MD_RESULT_IMPORT_BRIDGE.txt"
    _write_text(readme, f"""Pepforge v2.4.0 External MD Result Import & Validation Summary
================================================================

Purpose
-------
This bridge is for users who cannot run heavy all-atom MD locally but may later
receive OpenMM/GROMACS/AMBER/NAMD results from a stronger computer, cloud
environment, collaborator, or HPC system.

What v2.4.0 adds
----------------
- external MD/minimization result import template,
- normalized external MD result table,
- conservative validation-grade summary,
- warnings for weak or problematic imported results,
- claim guard table for final Kd, true binder, and full-MD claims.

Recommended use
---------------
1. Generate v2.1/v2.2/v2.3 bridge packages in Pepforge.
2. Run external docking or MD elsewhere if possible.
3. Fill external_md_result_import_template.csv with actual external run metrics.
4. Re-run this v2.4.0 import bridge with the filled CSV.
5. Use the validation summary as supporting computational evidence only.

This bridge improves traceability and interpretation. It does not make Pepforge a
replacement for external MD engines or experimental assays.
""")

    manifest = bridge_dir / "external_md_import_manifest.json"
    _write_json(manifest, {
        "pepforge_version": MD_RESULT_IMPORT_BRIDGE_VERSION,
        "sequence": sequence,
        "name": safe,
        "external_md_csv": str(external_md_csv) if external_md_csv else None,
        "files": {
            "import_template": str(import_schema),
            "normalized_results": str(normalized_csv),
            "summary_json": str(summary_json),
            "summary_txt": str(summary_txt),
            "claim_guard": str(claim_guard),
            "readme": str(readme),
        },
        "upstream_bridge_files": upstream,
    })

    paths = dict(upstream)
    paths.update({
        "external_md_result_import_template": str(import_schema),
        "external_md_results_normalized": str(normalized_csv),
        "external_md_validation_summary_json": str(summary_json),
        "external_md_validation_summary_txt": str(summary_txt),
        "external_md_claim_guard_table": str(claim_guard),
        "external_md_import_readme": str(readme),
        "external_md_import_manifest": str(manifest),
    })
    return paths


__all__ = [
    "MD_RESULT_IMPORT_BRIDGE_VERSION",
    "import_external_md_results",
    "summarize_external_md_results",
    "export_external_md_result_import_bridge",
]
