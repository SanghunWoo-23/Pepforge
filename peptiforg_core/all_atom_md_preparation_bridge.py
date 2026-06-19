from __future__ import annotations

"""All-atom refinement / MD preparation bridge utilities for Pepforge v2.3.0.

This module does not execute OpenMM, GROMACS, AMBER, NAMD, or any final MD
engine. It prepares traceable folders, templates, checklists, result-import
schemas, and claim guards so a Pepforge modified-peptide project can be moved to
an external all-atom refinement/MD environment when hardware is available.
"""

from pathlib import Path
from typing import Any, Dict, Optional
import csv
import json
import re

from peptiforg_core.external_docking_runner_bridge import export_external_docking_runner_bridge

MD_PREP_BRIDGE_VERSION = "2.3.0"


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name or "modified_peptide")).strip("_") or "modified_peptide"


def _write_text(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("\n", encoding="utf-8")
        return str(path)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return str(path)


def _write_json(path: Path, payload: Dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)


def export_all_atom_md_preparation_bridge(
    sequence: str,
    output_dir: str | Path,
    name: str = "modified_peptide",
    receptor_path: Optional[str | Path] = None,
    center: tuple[float, float, float] = (0.0, 0.0, 0.0),
    size: tuple[float, float, float] = (22.0, 22.0, 22.0),
    low_spec_num_confs: int = 8,
) -> Dict[str, str]:
    """Create a Pepforge v2.3.0 all-atom refinement / MD preparation package."""
    out = Path(output_dir)
    safe = _safe_name(name)
    out.mkdir(parents=True, exist_ok=True)

    upstream = export_external_docking_runner_bridge(
        sequence=sequence,
        output_dir=out,
        name=safe,
        receptor_path=receptor_path,
        center=center,
        size=size,
        low_spec_num_confs=low_spec_num_confs,
    )

    bridge_dir = out / "all_atom_refinement_md_preparation_bridge"
    bridge_dir.mkdir(parents=True, exist_ok=True)

    openmm_template = bridge_dir / "openmm_minimization_refinement_template.py"
    _write_text(openmm_template, '''"""Pepforge v2.3.0 OpenMM refinement template.

This template is intentionally conservative. It is a starting point for an
external all-atom workflow and must be reviewed by an experienced user before
publication-grade use.
"""

from pathlib import Path

PROJECT = Path(__file__).resolve().parent
INPUT_COMPLEX = PROJECT / "complex_candidate.pdb"

print("Pepforge v2.3.0 OpenMM template")
print("Input complex:", INPUT_COMPLEX)
print("This script is a reviewed-template placeholder, not a completed MD protocol.")
print("Install and configure OpenMM externally, then replace placeholders with force-field-ready topology files.")

# Suggested external workflow outline:
# 1. Prepare protein with a standard force field such as AMBER/CHARMM-compatible files.
# 2. Parameterize modified peptide units externally when needed.
# 3. Build solvated system, add ions, minimize energy.
# 4. Run short NVT/NPT equilibration if appropriate.
# 5. Export RMSD/contact/clash summaries into external_md_result_import_schema.csv.
''')

    gromacs_template = bridge_dir / "gromacs_workflow_template.txt"
    _write_text(gromacs_template, '''Pepforge v2.3.0 GROMACS workflow template
=========================================

Purpose
-------
This is a preparation bridge, not a completed GROMACS run. Use it on a stronger
PC, workstation, cloud notebook, or HPC system after force-field and topology
review.

Suggested folder inputs
-----------------------
complex_candidate.pdb
receptor_cleaned.pdb
peptide_prepared.sdf or peptide_prepared.pdb
modified_peptide_parameter_requirements.csv

Suggested external steps
------------------------
1. Prepare protein topology with a selected force field.
2. Parameterize modified peptide units using an appropriate method.
3. Merge complex topology carefully.
4. Solvate and add ions.
5. Energy minimize.
6. Optional short equilibration.
7. Optional short production run.
8. Export summary metrics into external_md_result_import_schema.csv.

Claim boundary
--------------
Do not report this Pepforge template as a full MD result. Report only completed
external MD runs with software version, force field, parameters, time step,
thermostat/barostat, total simulation length, and analysis method.
''')

    amber_notes = bridge_dir / "ambertools_parameterization_notes.txt"
    _write_text(amber_notes, '''Pepforge v2.3.0 AmberTools / parameterization notes
===================================================

Modified peptides may contain D-residues, non-natural residues, linkers, dyes,
lipid-like tails, or side-chain labels. These components often require external
parameter generation and manual review before all-atom MD.

Common review items:
- D-form residue chirality and topology
- non-natural residue atom naming and connectivity
- linker topology and charges
- dye/label partial charges and protonation
- terminal patches such as Ac and NH2
- consistency between SDF/PDB/CIF and topology files

Pepforge prepares requirements and templates. It does not guarantee all-atom
force-field readiness internally.
''')

    ff_checklist = bridge_dir / "force_field_parameterization_checklist.csv"
    _write_csv(ff_checklist, [
        {"item": "protein_force_field", "status": "select_externally", "note": "Record AMBER/CHARMM/OPLS/etc. and exact version."},
        {"item": "modified_peptide_topology", "status": "external_required", "note": "Review modified_peptide_parameter_requirements.csv."},
        {"item": "partial_charges", "status": "external_required", "note": "Check charge method for labels/linkers/non-natural units."},
        {"item": "protonation_state", "status": "manual_review_required", "note": "Record pH and protonation decisions."},
        {"item": "terminal_patches", "status": "manual_review_required", "note": "Confirm Ac/NH2 and termini match peptide notation."},
        {"item": "solvation_box", "status": "external_required", "note": "Define water model, padding, ions, neutralization."},
        {"item": "minimization_protocol", "status": "external_required", "note": "Record steps, convergence, restraints."},
        {"item": "short_md_protocol", "status": "optional_external", "note": "Only report if actually run externally."},
    ])

    md_schema = bridge_dir / "external_md_result_import_schema.csv"
    _write_csv(md_schema, [{
        "engine": "OpenMM|GROMACS|AMBER|NAMD|other",
        "engine_version": "record exact version",
        "force_field": "record force field and version",
        "water_model": "record water model",
        "system_atoms": "integer",
        "minimization_completed": "yes|no",
        "equilibration_completed": "yes|no",
        "production_time_ns": "numeric if completed",
        "final_potential_energy": "optional",
        "rmsd_A": "optional",
        "contact_persistence_fraction": "optional",
        "clash_count_after_refinement": "optional",
        "notes": "external run details and limitations",
    }])

    md_claim_guard = bridge_dir / "md_claim_guard_table.csv"
    _write_csv(md_claim_guard, [
        {"claim": "full MD completed", "status": "blocked unless external run imported", "safe_expression": "all-atom MD preparation bridge generated"},
        {"claim": "Pepforge replaces GROMACS/AMBER/OpenMM", "status": "blocked", "safe_expression": "Pepforge prepares external MD-ready templates and import schema"},
        {"claim": "final Kd from MD", "status": "blocked", "safe_expression": "screening or externally validated estimate only"},
        {"claim": "publication-grade MD", "status": "allowed only after external validation", "safe_expression": "report external engine, parameters, duration, and analysis"},
        {"claim": "minimized/refined externally", "status": "allowed if imported", "safe_expression": "external minimization/refinement result imported into Pepforge report"},
    ])

    readme = bridge_dir / "README_ALL_ATOM_MD_PREPARATION_BRIDGE.txt"
    _write_text(readme, f'''Pepforge v2.3.0 All-Atom Refinement / MD Preparation Bridge
================================================================

Input peptide notation
----------------------
{sequence}

Purpose
-------
This package prepares a modified-peptide project for external all-atom
refinement or molecular dynamics. It is designed for users whose local computer
cannot comfortably run Vina, OpenMM, GROMACS, AMBER, or similar tools.

What this bridge does
---------------------
- keeps v2.1.0 low-spec peptide simulation outputs,
- keeps v2.2.0 external docking runner templates,
- adds all-atom refinement / MD preparation templates,
- records force-field and parameterization requirements,
- provides an external MD result import schema,
- blocks unsafe full-MD/final-Kd claims unless external validation is actually completed.

What this bridge does not do
----------------------------
- it does not execute final all-atom MD,
- it does not replace OpenMM, GROMACS, AMBER, NAMD, or experimental assays,
- it does not prove true nM binding,
- it does not provide final publication-grade Kd values.

Recommended use
---------------
Use Pepforge on a low-spec PC to prepare the project, inspect the peptide model,
create conformer/evidence/parameter reports, and then move the prepared folder to
a stronger machine or collaborator for external validation.
''')

    manifest = {
        "bridge_version": MD_PREP_BRIDGE_VERSION,
        "input_sequence": sequence,
        "name": safe,
        "purpose": "all-atom refinement and MD preparation bridge; external run required for final MD claims",
        "claim_boundary": "screening/preparation only unless external engine outputs are imported",
        "upstream_files": upstream,
        "files": {
            "openmm_template": str(openmm_template),
            "gromacs_template": str(gromacs_template),
            "ambertools_notes": str(amber_notes),
            "force_field_parameterization_checklist": str(ff_checklist),
            "external_md_result_import_schema": str(md_schema),
            "md_claim_guard_table": str(md_claim_guard),
            "readme": str(readme),
        },
    }
    manifest_path = bridge_dir / "all_atom_md_preparation_manifest.json"
    _write_json(manifest_path, manifest)

    paths: Dict[str, str] = dict(upstream)
    paths.update({
        "all_atom_md_preparation_bridge_dir": str(bridge_dir),
        "openmm_template": str(openmm_template),
        "gromacs_template": str(gromacs_template),
        "ambertools_notes": str(amber_notes),
        "force_field_parameterization_checklist": str(ff_checklist),
        "external_md_result_import_schema": str(md_schema),
        "md_claim_guard_table": str(md_claim_guard),
        "all_atom_md_preparation_readme": str(readme),
        "all_atom_md_preparation_manifest": str(manifest_path),
    })
    return paths
