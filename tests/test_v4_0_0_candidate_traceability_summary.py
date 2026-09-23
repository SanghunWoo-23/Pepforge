from __future__ import annotations

import csv
import json
from pathlib import Path

from peptiforg_core.candidate_manifest import new_candidate_manifest, resolve_candidate_id, add_artifacts
from peptiforg_core.candidate_summary_report import build_candidate_summary, write_candidate_summary
from peptiforg_core.design_intent import normalize_design_intent


def test_pde_objective_mode_normalizes_to_downstream_mode():
    intent = normalize_design_intent({
        "pde_objective_mode": "structure_guided",
        "preferred_structure": "alpha_helix",
        "structure_environment": "Aqueous",
    })
    assert intent["mode"] == "STRUCTURE_GUIDED"
    assert intent["pde_objective_mode"] == "STRUCTURE_GUIDED"
    assert intent["preferred_structure"] == "ALPHA_HELIX"
    assert intent["environment"] == "Aqueous"


def test_interaction_only_disables_preferred_fold_in_transfer_metadata():
    intent = normalize_design_intent({"pde_objective_mode": "INTERACTION_ONLY", "preferred_structure": "BETA_STRAND"})
    assert intent["mode"] == "INTERACTION_ONLY"
    assert intent["preferred_structure"] == "NONE"


def test_resolve_candidate_id_preserves_unique_pde_id():
    rows = [{"candidate_id": "PDE-CAND-0007", "sequence": "Ac-AAAA-NH2"}]
    assert resolve_candidate_id("Ac-AAAA-NH2", rows) == "PDE-CAND-0007"


def test_resolve_candidate_id_falls_back_if_same_sequence_has_ambiguous_ids():
    rows = [
        {"candidate_id": "PDE-A", "sequence": "AAAA"},
        {"candidate_id": "PDE-B", "sequence": "AAAA"},
    ]
    cid = resolve_candidate_id("AAAA", rows)
    assert cid.startswith("PF-CAND-")
    assert cid not in {"PDE-A", "PDE-B"}


def test_candidate_summary_only_reports_existing_evidence(tmp_path: Path):
    structure_meta = tmp_path / "psb.json"
    structure_meta.write_text(json.dumps({
        "conformation_analysis": {
            "requested_structure": "ALPHA_HELIX",
            "requested_structure_match_count": 3,
            "fallback_count": 0,
            "severe_clash_selected_count": 0,
            "requested_structure_audit": {"requested_structure": "ALPHA_HELIX", "limitations": []},
            "top_conformers": [{
                "conf_id": 5, "family": "alpha_helix_like", "requested_structure_match": True,
                "selection_fallback": False, "selection_reason": "measured requested-family geometry",
            }],
        },
        "pde_intent_claim_guard": "geometry audit only",
    }), encoding="utf-8")
    spps_csv = tmp_path / "summary.csv"
    with spps_csv.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["sequence", "length", "resin", "scale_mmol"])
        writer.writeheader(); writer.writerow({"sequence": "AAAA", "length": 4, "resin": "Amide", "scale_mmol": 0.1})

    manifest = new_candidate_manifest(
        "AAAA", candidate_id="PDE-CAND-1", source="PDE_results_top.csv",
        design_intent={"pde_objective_mode": "STRUCTURE_GUIDED", "preferred_structure": "ALPHA_HELIX"},
    )
    manifest = add_artifacts(manifest, "structure_builder", {"json": structure_meta})
    manifest = add_artifacts(manifest, "spps_planner", {"summary": spps_csv})
    summary = build_candidate_summary(manifest, project_dir=tmp_path)
    assert summary["candidate_id"] == "PDE-CAND-1"
    assert summary["stage_status"]["PDE"] == "available"
    assert summary["stage_status"]["PSB"] == "available"
    assert summary["stage_status"]["SPPS"] == "available"
    assert summary["stage_status"]["Docking"] == "not_available"
    assert summary["stage_status"]["Trajectory"] == "not_available"
    assert summary["structure"]["requested_family_match_count"] == 3
    assert "affinity" not in json.dumps(summary).lower() or "not experimental affinity" in summary["claim_boundary"].lower()

    paths = write_candidate_summary(tmp_path / "report", manifest, project_dir=tmp_path)
    assert Path(paths["summary_json"]).exists()
    assert Path(paths["summary_txt"]).exists()
    text = Path(paths["summary_txt"]).read_text(encoding="utf-8")
    assert "Docking: not_available" in text
    assert "Trajectory: not_available" in text


def test_new_design_intent_fields_survive_normalization_and_summary_text(tmp_path: Path):
    manifest = new_candidate_manifest(
        "AAAA", candidate_id="PDE-CAND-THEORY", source="PDE_results_top.csv",
        design_intent={
            "pde_objective_mode": "STRUCTURE_GUIDED",
            "preferred_structure": "ALPHA_HELIX",
            "conformational_strategy": "ADAPTIVE",
            "hotspot_complementarity_mode": "REPORT_ONLY",
        },
        sequence_context={
            "hotspot_chemistry_complementarity_score": 0.5,
            "hotspot_chemistry_complementarity_status": "available",
        },
    )
    summary = build_candidate_summary(manifest, project_dir=tmp_path)
    assert summary["design_intent"]["conformational_strategy"] == "ADAPTIVE"
    assert summary["design_intent"]["hotspot_complementarity_mode"] == "REPORT_ONLY"
    paths = write_candidate_summary(tmp_path / "theory_report", manifest, project_dir=tmp_path)
    text = Path(paths["summary_txt"]).read_text(encoding="utf-8")
    assert "conformational_strategy: ADAPTIVE" in text
    assert "hotspot_complementarity_mode: REPORT_ONLY" in text
