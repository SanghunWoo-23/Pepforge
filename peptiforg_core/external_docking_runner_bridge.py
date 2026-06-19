from __future__ import annotations

"""External docking runner bridge utilities for Pepforge v2.2.0.

This module creates a low-spec, validation-ready docking runner package. It does
not execute AutoDock Vina, Smina, Gnina, OpenMM, GROMACS, AMBER, or any external
engine by itself.  It prepares traceable folders, config templates, scripts,
input manifests, and result-import schemas so the project can be moved to a
workstation, cloud notebook, HPC environment, or collaborator PC.
"""

from pathlib import Path
from typing import Any, Dict, Optional
import csv
import json
import re

from peptiforg_core.low_spec_validation_bridge import export_low_spec_validation_bridge

DOCKING_BRIDGE_VERSION = "2.2.0"


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name or "modified_peptide")).strip("_") or "modified_peptide"


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("\n", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_text(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


def _box_rows(center=(0.0, 0.0, 0.0), size=(22.0, 22.0, 22.0)) -> list[dict[str, Any]]:
    cx, cy, cz = center
    sx, sy, sz = size
    return [
        {"field": "center_x", "value": cx, "unit": "Angstrom", "note": "Set manually from binding site, ligand centroid, or hotspot residues."},
        {"field": "center_y", "value": cy, "unit": "Angstrom", "note": "Set manually from binding site, ligand centroid, or hotspot residues."},
        {"field": "center_z", "value": cz, "unit": "Angstrom", "note": "Set manually from binding site, ligand centroid, or hotspot residues."},
        {"field": "size_x", "value": sx, "unit": "Angstrom", "note": "Use a box large enough for the modified peptide and linker mobility."},
        {"field": "size_y", "value": sy, "unit": "Angstrom", "note": "Use a box large enough for the modified peptide and linker mobility."},
        {"field": "size_z", "value": sz, "unit": "Angstrom", "note": "Use a box large enough for the modified peptide and linker mobility."},
    ]


def export_external_docking_runner_bridge(
    sequence: str,
    output_dir: str | Path,
    name: str = "modified_peptide",
    receptor_path: Optional[str | Path] = None,
    center: tuple[float, float, float] = (0.0, 0.0, 0.0),
    size: tuple[float, float, float] = (22.0, 22.0, 22.0),
    exhaustiveness: int = 16,
    num_modes: int = 20,
    low_spec_num_confs: int = 8,
) -> Dict[str, str]:
    """Create a Pepforge v2.2.0 docking runner bridge package.

    The package contains:
    - v2.1 low-spec validation bridge outputs,
    - external docking folder with Vina/Smina/Gnina config templates,
    - run scripts for Windows and Linux/macOS,
    - receptor/ligand preparation checklist,
    - result import schema for docking scores,
    - claim guard table preventing final Kd/full-MD/replacement claims.
    """
    out = Path(output_dir)
    safe = _safe_name(name)
    out.mkdir(parents=True, exist_ok=True)

    # v2.0.0 recheck patch: respect GUI/user low-spec workload setting.
    # Earlier builds always requested 32 conformers here, which made Docking/MD
    # bridge buttons appear broken on low-spec PCs even when the user set Confs=8.
    low_spec_paths = export_low_spec_validation_bridge(sequence, out, safe, num_confs=max(1, int(low_spec_num_confs)))
    bridge_dir = out / "external_docking_runner_bridge"
    bridge_dir.mkdir(parents=True, exist_ok=True)

    # Copy/point to receptor if available.
    receptor_note = "No receptor PDB was provided. Add receptor_cleaned.pdb or receptor.pdbqt before running external docking."
    if receptor_path:
        rp = Path(receptor_path)
        if rp.exists() and rp.is_file():
            dest = bridge_dir / rp.name
            try:
                dest.write_bytes(rp.read_bytes())
                receptor_note = f"Receptor copied to {dest.name}. Prepare protonation/cleanup and convert to receptor.pdbqt externally."
            except Exception as exc:
                receptor_note = f"Receptor path was provided but could not be copied: {exc}"
        else:
            receptor_note = "Receptor path was provided but does not exist. Add receptor_cleaned.pdb or receptor.pdbqt before running external docking."

    box_csv = bridge_dir / "docking_box_suggestion.csv"
    _write_csv(box_csv, _box_rows(center, size))

    config_txt = bridge_dir / "vina_config_template.txt"
    _write_text(config_txt, f"""# Pepforge v2.2.0 external docking runner bridge
# This config is a template for AutoDock Vina-compatible workflows.
# Pepforge does not claim to replace AutoDock Vina/Smina/Gnina.

receptor = receptor.pdbqt
ligand = ligand.pdbqt

center_x = {center[0]}
center_y = {center[1]}
center_z = {center[2]}

size_x = {size[0]}
size_y = {size[1]}
size_z = {size[2]}

exhaustiveness = {int(exhaustiveness)}
num_modes = {int(num_modes)}
energy_range = 4

out = vina_out.pdbqt
log = vina_log.txt
""")

    win_bat = bridge_dir / "run_vina_windows.bat"
    _write_text(win_bat, """@echo off
REM Pepforge v2.2.0 external docking runner bridge
REM Place vina.exe in PATH or this folder, then run this script.
REM Required files: receptor.pdbqt, ligand.pdbqt, vina_config_template.txt
vina.exe --config vina_config_template.txt
pause
""")

    sh = bridge_dir / "run_vina_linux_mac.sh"
    _write_text(sh, """#!/usr/bin/env bash
set -e
# Pepforge v2.2.0 external docking runner bridge
# Required files: receptor.pdbqt, ligand.pdbqt, vina_config_template.txt
vina --config vina_config_template.txt
""")
    try:
        sh.chmod(0o755)
    except Exception:
        pass

    smina = bridge_dir / "smina_gnina_notes.txt"
    _write_text(smina, """Pepforge v2.2.0 Smina/Gnina notes
====================================

This folder can also be adapted to Smina or Gnina workflows. Use the generated
ligand SDF/PDB from Pepforge as the starting model, then prepare the proper
format required by the selected engine.

Recommended checks:
1. Confirm receptor protonation and chain selection.
2. Confirm ligand protonation/charge state and modified-token parameters.
3. Use docking_box_suggestion.csv as a starting point only; refine it manually.
4. Import final scores into external_docking_scores_import_schema.csv.

Do not report Pepforge bridge output as a final docking result unless an external
engine was actually run and its version/settings are documented.
""")

    prep = bridge_dir / "receptor_ligand_preparation_checklist.csv"
    _write_csv(prep, [
        {"item": "target_pdb_source", "status": "user_review_required", "note": "Record PDB ID/source, resolution if available, chain selection, and preprocessing."},
        {"item": "remove_or_keep_waters", "status": "user_review_required", "note": "Decide whether crystallographic waters are relevant."},
        {"item": "protonation_state", "status": "user_review_required", "note": "Check pH/protonation externally."},
        {"item": "receptor_pdbqt", "status": "external_tool_required", "note": "Prepare with AutoDockTools/MGLTools/Meeko/OpenBabel or equivalent."},
        {"item": "ligand_pdbqt", "status": "external_tool_required", "note": "Prepare from Pepforge SDF/PDB; confirm charges and rotatable bonds."},
        {"item": "modified_token_parameters", "status": "external_validation_required", "note": "Review modified_peptide_parameter_requirements.csv."},
        {"item": "docking_box", "status": "manual_review_required", "note": "Use binding site, hotspot residues, known ligand, or peptide centroid."},
    ])

    import_schema = bridge_dir / "external_docking_scores_import_schema.csv"
    _write_csv(import_schema, [{
        "engine": "vina|smina|gnina|other",
        "engine_version": "record exact version",
        "pose_id": "1",
        "score_kcal_mol": "external engine score only",
        "rmsd_lb": "optional",
        "rmsd_ub": "optional",
        "receptor_file": "receptor.pdbqt",
        "ligand_file": "ligand.pdbqt",
        "config_file": "vina_config_template.txt",
        "notes": "imported from external run; not generated by Pepforge internal scoring",
    }])

    claim_guard = bridge_dir / "docking_claim_guard_table.csv"
    _write_csv(claim_guard, [
        {"claim": "true nM binder", "status": "blocked", "safe_expression": "predicted nM-range candidate only after calibration/external validation"},
        {"claim": "final Kd", "status": "blocked", "safe_expression": "screening-level Kd-range estimate or externally measured Kd if available"},
        {"claim": "full MD result", "status": "blocked", "safe_expression": "low-spec bridge or external MD preparation result"},
        {"claim": "Pepforge replaces Vina/GROMACS/AMBER/OpenMM", "status": "blocked", "safe_expression": "Pepforge prepares and interprets validation-ready packages for external tools"},
        {"claim": "external docking result", "status": "allowed only if imported", "safe_expression": "report engine/version/config/score when external run is actually completed"},
    ])

    readme = bridge_dir / "README_EXTERNAL_DOCKING_BRIDGE.txt"
    _write_text(readme, f"""Pepforge v2.2.0 External Docking Runner Bridge
================================================

Input peptide notation:
{sequence}

Purpose
-------
This package helps move a Pepforge-generated modified peptide model into an
external docking workflow such as AutoDock Vina, Smina, or Gnina.

This bridge is designed for low-spec computers. Pepforge prepares the project,
configuration templates, ligand starting structure, claim guards, and result
import schema. The actual docking engine can be run later on a stronger PC,
cloud notebook, or HPC environment.

Receptor note
-------------
{receptor_note}

Important boundary
------------------
Pepforge v2.2.0 does not replace AutoDock Vina, Smina, Gnina, GROMACS, AMBER,
OpenMM, or experimental binding assays. It creates a reproducible preparation
and interpretation bridge.

Suggested workflow
------------------
1. Inspect modified peptide SDF/PDB/PML from the parent folder.
2. Review modified_peptide_parameter_requirements.csv.
3. Add or prepare receptor_cleaned.pdb and receptor.pdbqt.
4. Convert ligand to ligand.pdbqt using external tools.
5. Adjust vina_config_template.txt box center/size.
6. Run run_vina_windows.bat or run_vina_linux_mac.sh on a suitable machine.
7. Import results into external_docking_scores_import_schema.csv.
8. Use Pepforge contact/evidence reports as screening interpretation, not final proof.
""")

    manifest = {
        "bridge_version": DOCKING_BRIDGE_VERSION,
        "input_sequence": sequence,
        "name": safe,
        "low_spec_bridge_outputs": low_spec_paths,
        "external_docking_bridge_outputs": {
            "bridge_dir": str(bridge_dir),
            "vina_config_template": str(config_txt),
            "run_vina_windows": str(win_bat),
            "run_vina_linux_mac": str(sh),
            "docking_box_suggestion": str(box_csv),
            "receptor_ligand_preparation_checklist": str(prep),
            "external_docking_scores_import_schema": str(import_schema),
            "docking_claim_guard_table": str(claim_guard),
            "readme": str(readme),
            "smina_gnina_notes": str(smina),
        },
        "claim_boundary": "External docking claims require an actual external engine run with documented engine version, files, box, and score.",
    }
    manifest_path = out / f"{safe}_external_docking_runner_bridge_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    paths: Dict[str, str] = {f"low_spec_{k}": v for k, v in low_spec_paths.items()}
    paths.update(manifest["external_docking_bridge_outputs"])
    paths["external_docking_manifest"] = str(manifest_path)
    return paths
