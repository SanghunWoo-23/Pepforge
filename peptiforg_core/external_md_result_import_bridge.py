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

from peptiforg_core.component_versions import EXTERNAL_MD_RESULT_IMPORT_BRIDGE_VERSION as MD_RESULT_IMPORT_BRIDGE_VERSION


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
    """Normalize imported external-MD metadata without duration-based grading.

    Pepforge no longer turns nominal ns, RMSD, contact persistence, or clash
    thresholds into A/B/C/D evidence grades.  Those values remain descriptive
    metadata until actual trajectories are analyzed with replicate/convergence
    diagnostics.
    """
    rows = list(rows)
    if not rows:
        return {
            "import_status": "empty",
            "validation_grade": "UNSCORED",
            "claim_status": "no_external_md_result_imported",
            "safe_interpretation": "No external MD/minimization evidence was imported.",
            "warnings": ["External result CSV had no rows."],
            "normalized_rows": [],
            "convergence_status": "not_assessed",
        }

    warnings: list[str] = []
    normalized_rows: list[dict[str, Any]] = []
    minimized_any = False
    production_any = False
    equil_any = False
    metric_fields_present = set()

    for i, row in enumerate(rows, start=1):
        prod = row.get("production_time_ns_num")
        rmsd = row.get("rmsd_A_num")
        persist = row.get("contact_persistence_fraction_num")
        clashes = row.get("clash_count_after_refinement_num")
        minimized = row.get("minimization_completed_bool")
        equil = row.get("equilibration_completed_bool")
        engine = row.get("engine") or "unknown"
        minimized_any = minimized_any or bool(minimized)
        equil_any = equil_any or bool(equil)
        production_any = production_any or bool(prod is not None and prod > 0)
        if prod is not None: metric_fields_present.add("production_time_ns")
        if rmsd is not None: metric_fields_present.add("rmsd_A")
        if persist is not None: metric_fields_present.add("contact_persistence_fraction")
        if clashes is not None: metric_fields_present.add("clash_count_after_refinement")
        if persist is not None and not (0.0 <= persist <= 1.0):
            warnings.append(f"row {i}: contact persistence should be a fraction in [0,1]; received {persist}.")
        if prod is not None and prod < 0:
            warnings.append(f"row {i}: negative production time is invalid metadata ({prod}).")
        if clashes is not None and clashes < 0:
            warnings.append(f"row {i}: negative clash count is invalid metadata ({clashes}).")
        normalized_rows.append({
            "row": i,
            "engine": engine,
            "production_time_ns": prod,
            "rmsd_A": rmsd,
            "contact_persistence_fraction": persist,
            "clash_count_after_refinement": clashes,
            "minimization_completed": minimized,
            "equilibration_completed": equil,
            "validation_grade": "UNSCORED",
            "validation_call": "external_metadata_imported_no_convergence_grade",
        })

    return {
        "import_status": "imported",
        "rows_imported": len(rows),
        "minimization_imported": minimized_any,
        "equilibration_imported": equil_any,
        "production_md_imported": production_any,
        "validation_grade": "UNSCORED",
        "claim_status": "external_md_metadata_imported_unscored",
        "convergence_status": "not_assessed_from_summary_table",
        "metric_fields_present": sorted(metric_fields_present),
        "safe_interpretation": (
            "External MD metadata were imported. Nominal duration or a single RMSD/contact/clash value is not a convergence grade. "
            "Use the V5 simulation workflow or an external trajectory-analysis tool on actual independent-replicate trajectories before making stability/convergence claims."
        ),
        "warnings": warnings,
        "normalized_rows": normalized_rows,
        "claim_boundary": (
            "Pepforge V4 imports external MD summary metadata but does not analyze trajectory files. "
            "It does not infer experimental Kd, force-field correctness, or convergence from run duration alone."
        ),
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
