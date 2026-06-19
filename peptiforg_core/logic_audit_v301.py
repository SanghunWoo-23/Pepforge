from __future__ import annotations

"""Pepforge v3.0.1 logic audit helpers.

This module records the reasoning behind the v3.0.1 micro-upgrade:
- Docking Workbench already had a useful screening workflow but needed clearer
  pose-quality annotation.
- Peptide Design Engine already had strong SPPS/chemistry logic but needed an
  explicit developability guard in ranking.
"""

from pathlib import Path
from typing import Dict, Any
import json


LOGIC_AUDIT_VERSION = "3.0.1"


def v301_logic_analysis() -> dict[str, Any]:
    return {
        "pepforge_version": LOGIC_AUDIT_VERSION,
        "docking_workbench_assessment": {
            "status": "sound_for_screening_and_triage",
            "strengths": [
                "target/peptide PDB and sequence input modes",
                "RCSB fetch and target preparation workflow",
                "residue and atom contact reporting",
                "affinity-style report with explicit screening boundary",
                "validation bridge and evidence engine integration",
            ],
            "improvements_applied": [
                "pose_quality_grade added to pose outputs",
                "pose_quality_note added to explain why a pose is A/B/C/D-level for screening",
            ],
            "still_not_claimed": [
                "final docking pose",
                "experimental Kd",
                "replacement for AutoDock Vina/Smina/Gnina",
                "full all-atom MD",
            ],
        },
        "peptide_design_engine_assessment": {
            "status": "strong_candidate_generation_logic_with_new_developability_guard",
            "strengths": [
                "motif and hotspot-guided design",
                "D-form, non-natural, linker, tag, label, and terminal chemistry handling",
                "SPPS compatibility filtering",
                "ML-prior and diversity terms",
                "docking readiness reports",
            ],
            "improvements_applied": [
                "design_developability_report added",
                "design_developability_score added to raw_fitness",
                "DESIGN_DEVELOPABILITY_WEIGHT introduced as ranking guard",
            ],
            "penalized_risks": [
                "long hydrophobic stretch",
                "extreme net charge",
                "high aromatic density",
                "high proline density",
                "too many non-residue tokens",
                "too many linker tokens",
            ],
        },
        "upgrade_direction_after_v301": [
            "v3.1.0: project-folder auto-scan for Evidence Engine",
            "v3.2.0: chain/ligand-aware binding site selector",
            "v3.3.0: external docking result parser expansion",
            "v3.4.0: calibration dataset visualization and per-target model cards",
        ],
    }


def export_v301_logic_audit(output_dir: str | Path) -> Dict[str, str]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    payload = v301_logic_analysis()
    json_path = out / "pepforge_v3_0_1_logic_audit.json"
    txt_path = out / "pepforge_v3_0_1_logic_audit.txt"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    txt_path.write_text(
        "Pepforge v3.0.1 Logic Audit\n"
        "===========================\n\n"
        "Docking Workbench: sound for screening/triage; pose-quality annotation added.\n"
        "Design Engine: strong candidate-generation logic; developability guard added to ranking.\n"
        "Scientific boundary: no final Kd, true binder proof, or replacement of external docking/MD engines.\n",
        encoding="utf-8",
    )
    return {"logic_audit_json": str(json_path), "logic_audit_txt": str(txt_path)}


__all__ = ["LOGIC_AUDIT_VERSION", "v301_logic_analysis", "export_v301_logic_audit"]
