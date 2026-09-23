from __future__ import annotations

"""Stage-by-stage modified-peptide capability audit for Pepforge V4.0.0.

A token being recognized is not equivalent to every downstream method being
validated for that chemistry.  This module makes those boundaries explicit.
"""

from pathlib import Path
from typing import Any
import csv
import json

MODIFIED_SUPPORT_VERSION = "1.0.0"


def _tokens(sequence: str) -> list[dict[str, Any]]:
    try:
        from pepforge_structure_tool.pepforge_core import expand_and_tokenize, classify_token, supported_token_table
        raw = expand_and_tokenize(sequence)
        table = supported_token_table()
        ready = set((table.get("template_registry") or {}).keys())
        out=[]
        for tok in raw:
            try:
                obj=classify_token(tok)
                out.append({"token": tok, "kind": str(getattr(obj,"kind","unknown")), "template_ready": tok in ready or bool((table.get("template_registry") or {}).get(tok,{}).get("template_available"))})
            except Exception as exc:
                out.append({"token":tok,"kind":"unsupported","template_ready":False,"parse_note":str(exc)})
        return out
    except Exception:
        # Lightweight fallback used only when the structure-tool registry cannot
        # be imported. It must not silently canonicalize unknown chemistry.
        return [{"token": str(sequence or ""), "kind":"registry_unavailable", "template_ready":False}]


def _stage_status(kind: str, template_ready: bool) -> dict[str, str]:
    if kind == "std_aa":
        return {
            "PDE": "supported_canonical_evidence",
            "PSB_topology": "supported_explicit",
            "PSB_MM": "supported_MMFF_UFF_candidate",
            "SPPS": "supported_subject_to_reagent_database",
            "Docking_export": "supported_coordinates",
            "MD": "standard_forcefield_candidate_review_termini_protonation",
        }
    if kind == "d_std_aa":
        return {
            "PDE": "limited_no_L_scale_substitution",
            "PSB_topology": "supported_explicit_D_chirality" if template_ready else "review_required",
            "PSB_MM": "supported_local_MM_candidate" if template_ready else "parameterization_review",
            "SPPS": "supported_subject_to_reagent_database",
            "Docking_export": "supported_coordinates_if_PSB_builds",
            "MD": "backend_specific_parameterization_review",
        }
    if kind in {"non_natural_aa", "sidechain_label_aa"}:
        return {
            "PDE": "explicit_evidence_only_or_limited",
            "PSB_topology": "supported_explicit_template" if template_ready else "curated_graph_required",
            "PSB_MM": "local_MM_candidate_not_forcefield_validation" if template_ready else "not_available",
            "SPPS": "supported_if_material_and_protection_rules_exist",
            "Docking_export": "supported_coordinates_if_PSB_builds",
            "MD": "parameterization_required",
        }
    if kind == "linker":
        return {
            "PDE": "context_metadata_not_canonical_residue_scale",
            "PSB_topology": "supported_explicit_template" if template_ready else "curated_graph_required",
            "PSB_MM": "local_MM_candidate_not_forcefield_validation" if template_ready else "not_available",
            "SPPS": "supported_if_reagent_database_entry_exists",
            "Docking_export": "supported_coordinates_if_PSB_builds",
            "MD": "parameterization_required",
        }
    if kind in {"label", "chemical", "n_terminal", "c_terminal"}:
        return {
            "PDE": "excluded_from_canonical_structure_scales",
            "PSB_topology": "supported_only_if_explicit_derivative_template" if template_ready else "curated_derivative_required",
            "PSB_MM": "local_MM_candidate_if_explicit_graph" if template_ready else "not_available",
            "SPPS": "operator_workflow_or_reagent_database_dependent",
            "Docking_export": "supported_if_explicit_coordinates_exist",
            "MD": "parameterization_required",
        }
    return {stage: "unsupported_or_review_required" for stage in ["PDE","PSB_topology","PSB_MM","SPPS","Docking_export","MD"]}


def build_support_matrix(sequence: str) -> dict[str, Any]:
    toks=_tokens(sequence)
    rows=[]
    for item in toks:
        row={"token":item.get("token",""),"kind":item.get("kind","unknown"),"explicit_structure_template":bool(item.get("template_ready"))}
        row.update(_stage_status(row["kind"], row["explicit_structure_template"]))
        if item.get("parse_note"): row["note"]=item["parse_note"]
        rows.append(row)
    kinds={str(r.get("kind") or "") for r in rows}
    if not rows or "registry_unavailable" in kinds:
        overall="registry_unavailable"
    elif kinds == {"std_aa"}:
        overall="canonical_standard_candidate"
    elif any("unsupported" in str(v).lower() or "required" in str(v).lower() or "review" in str(v).lower() for r in rows for v in r.values()):
        overall="mixed_or_modified_review_required"
    else:
        overall="explicit_modified_support_available"
    return {
        "version": MODIFIED_SUPPORT_VERSION,
        "sequence": str(sequence or ""),
        "overall_status": overall,
        "tokens": rows,
        "claim_guard": "Recognition/buildability/parameterization are separate states. No unsupported chemistry is silently replaced by a canonical residue for a scientific claim.",
    }


def export_support_matrix(sequence: str, output_dir: str | Path) -> dict[str, str]:
    out=Path(output_dir); out.mkdir(parents=True,exist_ok=True)
    payload=build_support_matrix(sequence); rows=payload["tokens"]
    j=out/"modified_peptide_support_matrix.json"; c=out/"modified_peptide_support_matrix.csv"
    j.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    fields=list(rows[0]) if rows else ["token","kind","PDE","PSB_topology","PSB_MM","SPPS","Docking_export","MD"]
    with c.open("w",encoding="utf-8-sig",newline="") as h:
        w=csv.DictWriter(h,fieldnames=fields,extrasaction="ignore"); w.writeheader(); w.writerows(rows)
    return {"support_json":str(j),"support_csv":str(c)}


__all__=["MODIFIED_SUPPORT_VERSION","build_support_matrix","export_support_matrix"]
