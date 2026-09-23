from __future__ import annotations

"""Candidate-centered evidence summary for connected Pepforge workflow runs.

The report only summarizes artifacts and metadata that actually exist. Missing
Docking/trajectory/experimental stages remain explicitly unavailable; no score,
confidence, affinity, yield, or stability value is synthesized.
"""

from pathlib import Path
from typing import Any, Mapping
import csv
import json

from peptiforg_core.design_intent import normalize_design_intent
from peptiforg_core.modified_peptide_support import build_support_matrix
from peptiforg_core.scientific_evidence_registry import EVIDENCE_REGISTRY_VERSION
from peptiforg_core.protonation_sensitivity import protonation_sensitivity_report
from peptiforg_core.evidence_provenance import evidence_record, dependency_audit

SCHEMA = "pepforge_candidate_summary_v4"


def _existing_path(value: Any, project_dir: str | Path | None = None) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    p = Path(text)
    if not p.is_absolute() and project_dir is not None:
        p = Path(project_dir) / p
    return p if p.exists() else None


def _stage_artifacts(manifest: Mapping[str, Any], project_dir: str | Path | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for stage, rows in dict(manifest.get("artifacts") or {}).items():
        available: dict[str, str] = {}
        missing: list[str] = []
        for key, value in dict(rows or {}).items():
            p = _existing_path(value, project_dir)
            if p is None:
                missing.append(str(key))
            else:
                available[str(key)] = str(p)
        out[str(stage)] = {
            "available": bool(available),
            "artifact_count": len(available),
            "artifacts": available,
            "missing_manifest_artifacts": missing,
        }
    return out


def _structure_summary(stages: Mapping[str, Any]) -> dict[str, Any]:
    stage = dict(stages.get("structure_builder") or {})
    meta_value = dict(stage.get("artifacts") or {}).get("json")
    if not meta_value:
        return {"status": "not_available"}
    try:
        meta = json.loads(Path(meta_value).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "unreadable", "reason": str(exc)}
    analysis = dict(meta.get("conformation_analysis") or {})
    audit = dict(analysis.get("requested_structure_audit") or {})
    top = list(analysis.get("top_conformers") or [])
    return {
        "status": "available",
        "requested_structure": analysis.get("requested_structure") or audit.get("requested_structure") or "NONE",
        "requested_family_match_count": analysis.get("requested_structure_match_count", audit.get("requested_family_match_count")),
        "fallback_count": analysis.get("fallback_count", audit.get("fallback_count")),
        "severe_clash_selected_count": analysis.get("severe_clash_selected_count"),
        "top_conformer_count": len(top),
        "rank1": ({
            "conf_id": top[0].get("conf_id"),
            "family": top[0].get("family"),
            "requested_structure_match": top[0].get("requested_structure_match"),
            "selection_fallback": top[0].get("selection_fallback"),
            "selection_reason": top[0].get("selection_reason"),
        } if top else None),
        "requested_structure_audit": audit,
        "independent_challenge_sampling": dict(analysis.get("independent_challenge_sampling") or {}),
        "claim_guard": meta.get("pde_intent_claim_guard") or meta.get("conformation_claim_guard"),
    }


def _spps_summary(stages: Mapping[str, Any]) -> dict[str, Any]:
    stage = dict(stages.get("spps_planner") or {})
    value = dict(stage.get("artifacts") or {}).get("summary")
    if not value:
        return {"status": "not_available"}
    try:
        with Path(value).open(newline="", encoding="utf-8-sig") as handle:
            row = next(csv.DictReader(handle), None)
    except OSError as exc:
        return {"status": "unreadable", "reason": str(exc)}
    if not row:
        return {"status": "available", "summary": {}}
    safe_keys = [
        "sequence", "length", "resin", "resin_type", "scale_mmol", "tfa_eq",
        "cleavage_tfa_eq", "cys_count", "cys_rule", "double_coupling_from",
    ]
    selected = {key: row.get(key) for key in safe_keys if key in row and str(row.get(key) or "") != ""}
    return {
        "status": "available",
        "summary": selected,
        "claim_guard": "SPPS planning output is a planning/recommendation record, not measured synthesis yield or batch success.",
    }


def _interaction_evidence_summary(stages: Mapping[str, Any]) -> dict[str, Any]:
    for _, stage in stages.items():
        artifacts = dict(stage.get("artifacts") or {})
        for key, value in artifacts.items():
            name = str(key).lower()
            path = Path(str(value))
            if "interaction" not in name or not path.exists():
                continue
            if path.suffix.lower() == ".json":
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(payload, dict):
                        return {"status":"available", **payload}
                except (OSError, json.JSONDecodeError):
                    continue
            if path.suffix.lower() == ".csv":
                try:
                    with path.open(newline="", encoding="utf-8-sig") as handle:
                        rows=list(csv.DictReader(handle))
                    counts={}
                    for row in rows:
                        kind=str(row.get("interaction") or row.get("contact_class") or "unknown")
                        counts[kind]=counts.get(kind,0)+1
                    return {"status":"available", "row_count":len(rows), "counts":counts, "claim_guard":"Coordinate-derived interaction evidence only; no affinity or energy is inferred."}
                except OSError:
                    continue
    return {"status":"not_available"}


def _interface_quality_summary(stages: Mapping[str, Any]) -> dict[str, Any]:
    """Load interface-quality evidence only when an actual exported artifact exists."""
    for _, stage in stages.items():
        artifacts = dict(stage.get("artifacts") or {})
        for key, value in artifacts.items():
            if "interface_quality" not in str(key).lower():
                continue
            path = Path(str(value))
            if not path.exists() or path.suffix.lower() != ".json":
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    return {"status": str(payload.get("status") or "available"), **payload}
            except (OSError, json.JSONDecodeError):
                continue
    return {"status":"not_available"}


def _beta_edge_context(manifest: Mapping[str, Any]) -> dict[str, Any]:
    context = dict(manifest.get("sequence_context") or {})
    try:
        count = int(float(context.get("target_beta_edge_candidate_count") or 0))
    except (TypeError, ValueError):
        count = 0
    return {
        "status": "review_opportunity" if count > 0 else "not_detected_or_not_available",
        "candidate_count": count,
        "selection_active": False,
        "claim_guard": str(context.get("target_beta_edge_claim_guard") or "Exposed beta-edge evidence is report-only in V4.0.0; it is not a binding-site prediction, beta-pairing proof, or affinity estimate."),
    }


def _docking_lineage_summary(stages: Mapping[str, Any]) -> dict[str, Any]:
    for stage_name, stage in stages.items():
        artifacts = dict(stage.get("artifacts") or {})
        candidate = artifacts.get("lineage_json") or artifacts.get("docking_lineage_json")
        if not candidate:
            continue
        try:
            payload = json.loads(Path(candidate).read_text(encoding="utf-8"))
            rows = list(payload.get("records") or [])
            return {"status":"available", "record_count":len(rows), "records":rows[:20], "claim_guard":payload.get("claim_guard","")}
        except (OSError, json.JSONDecodeError) as exc:
            return {"status":"unreadable", "reason":str(exc)}
    return {"status":"not_available"}


def _spps_literature_aggregation(sequence: str) -> dict[str, Any]:
    try:
        from spps_v4_gui.aggregation_evidence_v5 import literature_aggregation_evidence
        return literature_aggregation_evidence(sequence)
    except Exception as exc:
        return {"status": "unavailable", "reason": str(exc), "claim_guard": "Literature aggregation evidence could not be generated; no substitute probability is inferred."}


def _provenance_records(manifest: Mapping[str, Any], structure: Mapping[str, Any], stage_status: Mapping[str, str],
                        protonation: Mapping[str, Any], aggregation: Mapping[str, Any], interaction: Mapping[str, Any],
                        interface_quality: Mapping[str, Any], beta_edge: Mapping[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if manifest.get("design_intent"):
        records.append(evidence_record(name="PDE design intent", role="selection_driving", kind="heuristic",
            source_id="PDE_design_intent", status="available", detail=dict(manifest.get("design_intent") or {}),
            limitations="Design intent guides selection and therefore is not independent validation."))
    if structure.get("status") == "available":
        records.append(evidence_record(name="PSB intent-guided conformer selection", role="selection_driving", kind="calculated",
            source_id="PSB_same_backend", status="available", detail={
                "requested_family_match_count": structure.get("requested_family_match_count"),
                "fallback_count": structure.get("fallback_count"),
            }, depends_on=["PDE_design_intent"], limitations="Requested-family seeds and ranking are conditioned on PDE intent."))
        challenge=dict(structure.get("independent_challenge_sampling") or {})
        if challenge.get("status") == "ok":
            records.append(evidence_record(name="PSB intent-independent challenge sampling", role="independent", kind="calculated",
                source_id="PSB_same_backend", status="available", detail=challenge,
                limitations="Intent-independent with respect to guided seeds, but uses the same PSB chemistry/backend and is not an external orthogonal method."))
            guided=int(structure.get("requested_family_match_count") or 0)
            independent=int(challenge.get("requested_family_match_count") or 0)
            if guided > 0 and independent == 0 and str(challenge.get("requested_structure") or "NONE") != "NONE":
                records.append(evidence_record(name="Guided/challenge structural disagreement", role="contradictory", kind="calculated",
                    source_id="PSB_same_backend", status="method_disagreement", detail={"guided_requested_matches": guided, "challenge_requested_matches": independent},
                    limitations="Method disagreement is a review signal, not proof that either structure is correct or incorrect."))
    if interaction.get("status") == "available":
        records.append(evidence_record(name="Coordinate interaction evidence", role="contextual", kind="calculated",
            source_id="coordinate_interaction_analysis", status="available", detail={"counts": interaction.get("counts") or interaction.get("interaction_counts")},
            limitations="Coordinate screening evidence is not affinity or binding free energy."))
    if interface_quality.get("status") == "available":
        records.append(evidence_record(name="Interface quality descriptors", role="contextual", kind="calculated",
            source_id="coordinate_interface_quality", status="available", detail={
                "approx_interface_area_half_delta_SASA_A2": interface_quality.get("approx_interface_area_half_delta_SASA_A2"),
                "buried_unsatisfied_polar_candidate_count": interface_quality.get("buried_unsatisfied_polar_candidate_count"),
                "hotspot_coverage": interface_quality.get("hotspot_coverage"),
                "interaction_counts": interface_quality.get("interaction_counts"),
            }, limitations="Separate coordinate-derived descriptors only; not affinity, binding free energy, Rosetta Sc, or experimental validation."))
    if int(beta_edge.get("candidate_count") or 0) > 0:
        records.append(evidence_record(name="Target exposed beta-edge opportunity", role="contextual", kind="calculated",
            source_id="target_structure_beta_edge_screen", status="review_opportunity", detail=beta_edge,
            limitations="Report-only in V4.0.0 and not used as a PDE selection bonus."))
    if protonation.get("status") != "no_common_ionizable_group_detected":
        records.append(evidence_record(name="Protonation sensitivity review", role="contextual", kind="literature_derived",
            source_id="sequence_protonation_context", status=str(protonation.get("status") or "available"), detail=protonation,
            limitations="No pKa or protonation microstate is predicted."))
    if aggregation.get("status") in {"available", "partial_out_of_domain", "out_of_domain"}:
        records.append(evidence_record(name="SPPS aggregation literature context", role="contextual", kind="literature_derived",
            source_id="DOI:10.1038/s41557-026-02090-0", status=str(aggregation.get("status")), detail=aggregation,
            limitations="AFPS canonical-L literature context only; out-of-domain positions are excluded, no universal failure probability is inferred, and synthesis plans are never auto-changed."))
    for stage, status in stage_status.items():
        if status != "available" and stage in {"Docking", "Trajectory", "Experimental"}:
            records.append(evidence_record(name=f"{stage} evidence", role="missing", kind="unavailable",
                source_id=f"{stage.lower()}_stage", status="not_available", limitations="Stage evidence is absent and is not inferred."))
    return records


def build_candidate_summary(manifest: Mapping[str, Any], project_dir: str | Path | None = None) -> dict[str, Any]:
    stages = _stage_artifacts(manifest, project_dir)
    intent = normalize_design_intent(manifest.get("design_intent") or {})
    known = set(stages)
    sequence = str(manifest.get("sequence") or "")
    support = build_support_matrix(sequence)
    structure = _structure_summary(stages)
    spps = _spps_summary(stages)
    interaction = _interaction_evidence_summary(stages)
    interface_quality = _interface_quality_summary(stages)
    beta_edge = _beta_edge_context(manifest)
    protonation = protonation_sensitivity_report(sequence)
    aggregation = _spps_literature_aggregation(sequence)
    stage_status = {
        "PDE": "available" if manifest.get("source") == "PDE_results_top.csv" or bool(manifest.get("design_intent")) else "not_available",
        "PSB": "available" if stages.get("structure_builder", {}).get("available") else "not_available",
        "SPPS": "available" if stages.get("spps_planner", {}).get("available") else "not_available",
        "Docking": "available" if any(k.lower().startswith("docking") and stages[k].get("available") for k in known) else "not_available",
        "Trajectory": "available" if any("trajectory" in k.lower() and stages[k].get("available") for k in known) else "not_available",
        "Experimental": "available" if any("experimental" in k.lower() and stages[k].get("available") for k in known) else "not_available",
    }
    records = _provenance_records(manifest, structure, stage_status, protonation, aggregation, interaction, interface_quality, beta_edge)
    role_counts: dict[str, int] = {}
    for row in records:
        role=str(row.get("role") or "contextual"); role_counts[role]=role_counts.get(role,0)+1
    return {
        "schema": SCHEMA,
        "candidate_id": str(manifest.get("candidate_id") or ""),
        "sequence": sequence,
        "design_intent": intent,
        "sequence_context": dict(manifest.get("sequence_context") or {}),
        "structure": structure,
        "spps": spps,
        "protonation_sensitivity": protonation,
        "spps_literature_aggregation_evidence": aggregation,
        "modified_peptide_support": support,
        "interaction_evidence": interaction,
        "interface_quality_evidence": interface_quality,
        "target_beta_edge_opportunity": beta_edge,
        "docking_lineage": _docking_lineage_summary(stages),
        "scientific_evidence_registry_version": EVIDENCE_REGISTRY_VERSION,
        "scientific_evidence_registry_refs": ["STRUCT_HELIX_PACE_SCHOLTZ_1998", "STRUCT_PPII_BROWN_ZONDLO_2012", "STRUCT_DPRO_GLY_HAIRPIN", "STRUCT_AIB_GLY_TURN_2007", "STRUCT_COILED_COIL_HEPTAD", "INTERACTION_MANUAL_CUTOFF_GUIDE_2026", "INTERACTION_PLIP_TOOL_PROFILE", "VALIDATION_ADVERSARIAL_EVIDENCE_2025", "ENSEMBLE_PEPFLOW_2024", "INTERFACE_BINDCRAFT_2025", "BETA_EDGE_PAIRING_2025", "SPPS_AGGREGATION_COMPOSITION_2026", "PROTONATION_SENSITIVITY_2026"],
        "evidence_records": records,
        "evidence_role_counts": role_counts,
        "evidence_by_role": {role: [row for row in records if row.get("role") == role] for role in ("selection_driving", "independent", "contradictory", "contextual", "missing")},
        "evidence_dependency_audit": dependency_audit(records),
        "provenance": {
            "PDE": "heuristic_and_literature_derived_design_evidence",
            "PSB": "calculated_conformer_geometry_and_local_MM_cleanup",
            "SPPS": "rule_based_historical_and_literature_scoped_planning_evidence",
            "Docking": "coordinate_or_external_engine_evidence_only_when_present",
            "Trajectory": "measured_from_imported_trajectory_only_when_present",
            "Experimental": "operator_imported_or_recorded_experimental_data_only",
            "policy": "Selection-driving, intent-independent challenge, contradictory, contextual, and missing evidence are separated. Same-source metrics are not promoted to independent validation merely by appearing twice.",
            "PSB_independent_challenge_scope": "intent-independent sampling within the same PSB backend; not external orthogonal validation",
        },
        "stage_status": stage_status,
        "artifacts": stages,
        "claim_boundary": (
            "Candidate-centered audit summary only. Missing stages remain unavailable; computational scores/ranks are not "
            "experimental affinity, activity, yield, pharmacokinetics, or native-structure proof. Literature evidence retains its stated applicability limits."
        ),
    }


def _text_report(summary: Mapping[str, Any]) -> str:
    lines = [
        "Pepforge Candidate Summary Report",
        "===============================",
        f"Candidate ID: {summary.get('candidate_id','')}",
        f"Sequence: {summary.get('sequence','')}",
        "", "Design Intent", "-------------",
    ]
    intent = dict(summary.get("design_intent") or {})
    for key in ["mode", "preferred_structure", "structure_bias", "environment", "conformational_strategy", "hotspot_complementarity_mode"]:
        lines.append(f"{key}: {intent.get(key,'')}")
    lines += ["", "Stage Status", "------------"]
    for stage, status in dict(summary.get("stage_status") or {}).items(): lines.append(f"{stage}: {status}")
    structure = dict(summary.get("structure") or {})
    lines += ["", "PSB", "---", f"status: {structure.get('status','not_available')}"]
    if structure.get("status") == "available":
        for key in ["requested_structure", "requested_family_match_count", "fallback_count", "severe_clash_selected_count", "top_conformer_count"]: lines.append(f"{key}: {structure.get(key)}")
        challenge=dict(structure.get("independent_challenge_sampling") or {})
        if challenge:
            lines += ["", "Intent-independent Challenge Sampling", "-------------------------------------", f"status: {challenge.get('status','not_available')}", f"sampled_conformer_count: {challenge.get('sampled_conformer_count')}", f"requested_family_match_count: {challenge.get('requested_family_match_count')}", f"requested_family_fraction_of_sampled_ensemble: {challenge.get('requested_family_fraction_of_sampled_ensemble')}", "NOTE: sampling occupancy is not an equilibrium probability or external validation."]
    spps = dict(summary.get("spps") or {})
    lines += ["", "SPPS", "----", f"status: {spps.get('status','not_available')}"]
    for key, value in dict(spps.get("summary") or {}).items(): lines.append(f"{key}: {value}")
    protonation=dict(summary.get("protonation_sensitivity") or {})
    lines += ["", "Protonation Sensitivity", "-----------------------", f"status: {protonation.get('status','not_available')}", f"review_priority: {protonation.get('review_priority','')}"]
    agg=dict(summary.get("spps_literature_aggregation_evidence") or {})
    lines += [
        "", "SPPS Literature Aggregation Evidence", "------------------------------------",
        f"status: {agg.get('status','not_available')}",
        f"applicability: {agg.get('applicability','')}",
        f"canonical_residue_count: {agg.get('canonical_residue_count',0)}",
        f"out_of_domain_core_count: {agg.get('out_of_domain_core_count', agg.get('modified_or_unresolved_core_count',0))}",
        f"canonical_subset_fraction_of_core: {agg.get('canonical_subset_fraction_of_core','')}",
        f"composition_fraction_S_V_I_T_canonical_subset: {agg.get('composition_fraction_S_V_I_T','')}",
        f"domain_interpretation: {agg.get('domain_interpretation','')}",
        "NOTE: literature/context evidence only; no aggregation probability or automatic pseudoproline substitution.",
    ]
    interaction = dict(summary.get("interaction_evidence") or {})
    lines += ["", "Interaction Evidence", "--------------------", f"status: {interaction.get('status','not_available')}"]
    interface_quality = dict(summary.get("interface_quality_evidence") or {})
    lines += ["", "Interface Quality Evidence", "--------------------------", f"status: {interface_quality.get('status','not_available')}"]
    if interface_quality.get("status") == "available":
        lines += [f"approx_interface_area_half_delta_SASA_A2: {interface_quality.get('approx_interface_area_half_delta_SASA_A2')}", f"buried_unsatisfied_polar_candidate_count: {interface_quality.get('buried_unsatisfied_polar_candidate_count')}", f"hotspot_coverage_status: {(interface_quality.get('hotspot_coverage') or {}).get('status','not_supplied')}", "NOTE: separate coordinate descriptors only; not affinity, binding free energy, or Rosetta shape complementarity."]
    beta_edge = dict(summary.get("target_beta_edge_opportunity") or {})
    lines += ["", "Target Beta-edge Opportunity", "----------------------------", f"status: {beta_edge.get('status','not_available')}", f"candidate_count: {beta_edge.get('candidate_count',0)}", "selection_active: False"]
    if interaction.get("counts"):
        for key, value in dict(interaction.get("counts") or {}).items(): lines.append(f"{key}: {value}")
    records=list(summary.get("evidence_records") or [])
    for role,title in [("selection_driving","Selection-driving Evidence"),("independent","Independent / Challenge Evidence"),("contradictory","Contradictory / Disagreement Evidence"),("missing","Missing Evidence"),("contextual","Contextual Evidence")]:
        lines += ["", title, "-"*len(title)]
        subset=[r for r in records if r.get("role")==role]
        if not subset: lines.append("none")
        for row in subset: lines.append(f"- {row.get('name')}: {row.get('status')} [{row.get('kind')}; source={row.get('source_id')}]")
    audit=dict(summary.get("evidence_dependency_audit") or {})
    lines += ["", "Evidence Dependency Audit", "-------------------------", f"shared_source_ids: {', '.join(audit.get('shared_source_ids') or []) or 'none'}", str(audit.get("policy") or "")]
    lines += ["", "Claim Boundary", "--------------", str(summary.get("claim_boundary") or ""), ""]
    return "\n".join(lines)


def write_candidate_summary(
    output_dir: str | Path,
    manifest: Mapping[str, Any],
    project_dir: str | Path | None = None,
) -> dict[str, str]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    summary = build_candidate_summary(manifest, project_dir=project_dir)
    json_path = out / "Summary_Report.json"
    txt_path = out / "Summary_Report.txt"
    json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    txt_path.write_text(_text_report(summary), encoding="utf-8")
    return {"summary_json": str(json_path), "summary_txt": str(txt_path)}


__all__ = ["SCHEMA", "build_candidate_summary", "write_candidate_summary"]
