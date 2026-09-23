from __future__ import annotations

"""Candidate comparison without collapsing evidence into an affinity-like score.

Pepforge V4.0.0 keeps heterogeneous evidence on separate axes.  This module
creates a comparison matrix with provenance/status fields and deliberately does
not calculate a single winner score from design, docking, SPPS or MD evidence.
"""

from pathlib import Path
from typing import Any, Iterable
import csv
import json

CANDIDATE_EVIDENCE_MATRIX_VERSION = "1.3.0"

AXES = (
    "design_intent", "structure", "synthesis", "interaction", "docking",
    "trajectory", "experimental",
)


def _safe(value: Any, default: str = "not_available") -> Any:
    if value in (None, "", [], {}):
        return default
    return value


def row_from_summary(summary: dict[str, Any]) -> dict[str, Any]:
    intent = summary.get("design_intent") or summary.get("pde") or {}
    structure = summary.get("structure") or summary.get("psb") or {}
    spps = summary.get("spps") or {}
    stage_status = summary.get("stage_status") or {}
    provenance = summary.get("provenance") or {}
    support = summary.get("modified_peptide_support") or {}
    interaction = summary.get("interaction_evidence") or {}
    interface_quality = summary.get("interface_quality_evidence") or {}
    protonation = summary.get("protonation_sensitivity") or {}
    aggregation = summary.get("spps_literature_aggregation_evidence") or {}
    beta_edge = summary.get("target_beta_edge_opportunity") or {}
    challenge = structure.get("independent_challenge_sampling") or {}
    role_counts = summary.get("evidence_role_counts") or {}
    dependency = summary.get("evidence_dependency_audit") or {}

    return {
        "candidate_id": _safe(summary.get("candidate_id") or (summary.get("candidate") or {}).get("candidate_id")),
        "sequence": _safe(summary.get("sequence") or (summary.get("candidate") or {}).get("sequence")),
        "design_objective": _safe(intent.get("mode") or intent.get("design_objective") or intent.get("objective_mode")),
        "preferred_structure": _safe(intent.get("preferred_structure")),
        "conformational_strategy": _safe(intent.get("conformational_strategy")),
        "psb_status": _safe(structure.get("status") or stage_status.get("PSB")),
        "psb_requested_family_valid": _safe(structure.get("requested_family_match_count") or structure.get("requested_family_valid_count")),
        "psb_challenge_status": _safe(challenge.get("status")),
        "psb_challenge_requested_family_matches": _safe(challenge.get("requested_family_match_count")),
        "psb_challenge_requested_family_sample_fraction": _safe(challenge.get("requested_family_fraction_of_sampled_ensemble")),
        "spps_status": _safe(spps.get("status") or stage_status.get("SPPS")),
        "spps_aggregation_literature_status": _safe(aggregation.get("status")),
        "spps_aggregation_literature_applicability": _safe(aggregation.get("applicability")),
        "spps_aggregation_canonical_residue_count": aggregation.get("canonical_residue_count", 0),
        "spps_aggregation_out_of_domain_core_count": aggregation.get("out_of_domain_core_count", aggregation.get("modified_or_unresolved_core_count", 0)),
        "spps_aggregation_canonical_subset_fraction": _safe(aggregation.get("canonical_subset_fraction_of_core")),
        "spps_aggregation_S_V_I_T_fraction_canonical_subset": _safe(aggregation.get("composition_fraction_S_V_I_T")),
        "protonation_review_status": _safe(protonation.get("status")),
        "protonation_review_priority": _safe(protonation.get("review_priority")),
        "interaction_status": _safe(interaction.get("status")),
        "interface_quality_status": _safe(interface_quality.get("status")),
        "interface_area_half_delta_SASA_A2": _safe(interface_quality.get("approx_interface_area_half_delta_SASA_A2")),
        "buried_unsatisfied_polar_candidate_count": _safe(interface_quality.get("buried_unsatisfied_polar_candidate_count")),
        "target_beta_edge_candidate_count": _safe(beta_edge.get("candidate_count"), 0),
        "docking_status": _safe(stage_status.get("Docking")),
        "trajectory_status": _safe(stage_status.get("Trajectory")),
        "experimental_status": _safe(stage_status.get("Experimental")),
        "modified_support_status": _safe(support.get("overall_status") or support.get("status")),
        "pde_provenance": _safe(provenance.get("PDE") or provenance.get("pde")),
        "psb_provenance": _safe(provenance.get("PSB") or provenance.get("psb")),
        "spps_provenance": _safe(provenance.get("SPPS") or provenance.get("spps")),
        "docking_provenance": _safe(provenance.get("Docking") or provenance.get("docking")),
        "trajectory_provenance": _safe(provenance.get("Trajectory") or provenance.get("trajectory")),
        "experimental_provenance": _safe(provenance.get("Experimental") or provenance.get("experimental")),
        "selection_driving_evidence_count": int(role_counts.get("selection_driving", 0) or 0),
        "independent_challenge_evidence_count": int(role_counts.get("independent", 0) or 0),
        "contradictory_evidence_count": int(role_counts.get("contradictory", 0) or 0),
        "missing_evidence_count": int(role_counts.get("missing", 0) or 0),
        "orthogonal_independent_source_count": int(dependency.get("orthogonal_independent_source_count", 0) or 0),
        "comparison_policy": "separate_evidence_axes_no_aggregate_affinity_score",
    }


def build_candidate_evidence_matrix(summaries: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row_from_summary(x) for x in summaries]



def build_blind_review_matrix(summaries: Iterable[dict[str, Any]], *, hide_sequence: bool = True) -> dict[str, Any]:
    """Return de-identified evidence rows plus a separate mapping for later reveal.

    This is a review aid only. It does not randomize scientific results or alter
    candidate ranking; it hides candidate identity/rank cues while evidence axes
    are inspected.
    """
    source=list(summaries)
    rows=[]; mapping=[]
    for idx, summary in enumerate(source):
        label=f"Candidate {chr(65+idx) if idx < 26 else idx+1}"
        row=row_from_summary(summary)
        mapping.append({"blind_label":label,"candidate_id":row.get("candidate_id"),"sequence":row.get("sequence")})
        row["blind_label"]=label
        row["candidate_id"]="hidden_for_blind_review"
        if hide_sequence: row["sequence"]="hidden_for_blind_review"
        rows.append(row)
    return {
        "version":CANDIDATE_EVIDENCE_MATRIX_VERSION,
        "policy":"Blind review hides identity cues only; evidence axes remain unchanged and no aggregate winner score is generated.",
        "rows":rows,
        "reveal_mapping":mapping,
    }


def export_blind_review_matrix(summaries: Iterable[dict[str, Any]], output_dir: str | Path, *, hide_sequence: bool = True) -> dict[str,str]:
    out=Path(output_dir); out.mkdir(parents=True,exist_ok=True)
    payload=build_blind_review_matrix(summaries,hide_sequence=hide_sequence)
    review_json=out/"candidate_evidence_blind_review.json"
    review_csv=out/"candidate_evidence_blind_review.csv"
    mapping_json=out/"candidate_evidence_blind_reveal_mapping.json"
    review_json.write_text(json.dumps({k:v for k,v in payload.items() if k!="reveal_mapping"},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    mapping_json.write_text(json.dumps({"version":payload["version"],"mapping":payload["reveal_mapping"]},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    rows=payload["rows"]; fields=list(rows[0].keys()) if rows else ["blind_label","candidate_id","comparison_policy"]
    with review_csv.open("w",encoding="utf-8-sig",newline="") as h:
        w=csv.DictWriter(h,fieldnames=fields); w.writeheader(); w.writerows(rows)
    return {"blind_json":str(review_json),"blind_csv":str(review_csv),"reveal_mapping_json":str(mapping_json)}

def export_candidate_evidence_matrix(summaries: Iterable[dict[str, Any]], output_dir: str | Path) -> dict[str, str]:
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    rows = build_candidate_evidence_matrix(summaries)
    json_path = out / "candidate_evidence_matrix.json"
    csv_path = out / "candidate_evidence_matrix.csv"
    payload = {
        "version": CANDIDATE_EVIDENCE_MATRIX_VERSION,
        "policy": "Evidence axes remain separate. No aggregate binding/affinity/confidence score is generated.",
        "rows": rows,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fields = list(rows[0].keys()) if rows else ["candidate_id", "sequence", "comparison_policy"]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader()
        for row in rows: writer.writerow(row)
    return {"json": str(json_path), "csv": str(csv_path)}


__all__ = ["CANDIDATE_EVIDENCE_MATRIX_VERSION", "AXES", "row_from_summary", "build_candidate_evidence_matrix", "build_blind_review_matrix", "export_candidate_evidence_matrix", "export_blind_review_matrix"]
