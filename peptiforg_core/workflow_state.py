from __future__ import annotations

from typing import Any


WORKFLOW_STAGE_PROGRESS = {
    "READY": (0, "Ready"),
    "HOTSPOT_READY": (25, "Hot Spot ready"),
    "PDE_DIRTY": (25, "PDE settings changed — rerun PDE"),
    "PDE_COMPLETE": (60, "PDE complete"),
    "PSB_COMPLETE": (85, "Structures ready"),
    "COMPLETE": (100, "Workflow complete"),
}


def _nonempty_candidate(project: dict[str, Any]) -> tuple[str, str]:
    candidate_id = str(project.get("active_candidate_id") or "").strip()
    sequence = str(project.get("active_candidate_sequence") or "").strip()
    return candidate_id, sequence


def _has_structure_for_candidate(project: dict[str, Any], candidate_id: str) -> bool:
    if not candidate_id:
        return False
    result = dict((project.get("structure_results") or {}).get(candidate_id) or {})
    current_revision = int((project.get("workflow_state") or {}).get("pde_revision") or 0)
    result_revision = int(result.get("workflow_pde_revision") or 0)
    if current_revision and result_revision != current_revision:
        return False
    return any(str(result.get(key) or "").strip() for key in (
        "top1_pdb", "top1_canonical_view_pdb", "pdb", "canonical_view_pdb"
    ))


def _spps_matches_active_candidate(project: dict[str, Any], candidate_id: str, sequence: str) -> bool:
    if not sequence:
        return False
    settings = dict(project.get("spps_settings") or {})
    if not settings:
        return False
    current_revision = int((project.get("workflow_state") or {}).get("pde_revision") or 0)
    saved_revision = int(settings.get("workflow_pde_revision") or 0)
    if current_revision and saved_revision != current_revision:
        return False
    saved_id = str(settings.get("candidate_id") or "").strip()
    saved_sequence = str(settings.get("sequence") or "").strip()
    if saved_id and candidate_id:
        return saved_id == candidate_id and saved_sequence == sequence
    # Backward compatibility for R5 projects written before candidate_id was stored.
    return saved_sequence == sequence


def derive_workflow_progress(project: dict[str, Any]) -> tuple[str, int, str]:
    """Derive UI stage from active lineage instead of stale global outputs."""
    state = dict(project.get("workflow_state") or {})
    has_hotspot = bool(project.get("hotspot_ranked_regions"))
    if bool(state.get("pde_dirty")):
        stage = "PDE_DIRTY" if has_hotspot or state.get("pending_pde_settings") else "READY"
        value, text = WORKFLOW_STAGE_PROGRESS[stage]
        return stage, value, text

    candidate_id, sequence = _nonempty_candidate(project)
    if candidate_id and sequence:
        if _spps_matches_active_candidate(project, candidate_id, sequence):
            value, text = WORKFLOW_STAGE_PROGRESS["COMPLETE"]
            return "COMPLETE", value, text
        if _has_structure_for_candidate(project, candidate_id):
            value, text = WORKFLOW_STAGE_PROGRESS["PSB_COMPLETE"]
            return "PSB_COMPLETE", value, text
        value, text = WORKFLOW_STAGE_PROGRESS["PDE_COMPLETE"]
        return "PDE_COMPLETE", value, text

    if has_hotspot:
        value, text = WORKFLOW_STAGE_PROGRESS["HOTSPOT_READY"]
        return "HOTSPOT_READY", value, text
    value, text = WORKFLOW_STAGE_PROGRESS["READY"]
    return "READY", value, text


def mark_pde_dirty(project: dict[str, Any], pending_settings: dict[str, Any]) -> dict[str, Any]:
    """Invalidate only the active downstream lineage while preserving old artifacts."""
    state = dict(project.get("workflow_state") or {})
    state["pde_dirty"] = True
    state["pending_pde_settings"] = dict(pending_settings or {})
    project["workflow_state"] = state
    project["active_candidate_id"] = ""
    project["active_candidate_sequence"] = ""
    project["active_structure"] = {}
    return project


def mark_pde_clean(project: dict[str, Any]) -> dict[str, Any]:
    state = dict(project.get("workflow_state") or {})
    state["pde_dirty"] = False
    state["pde_revision"] = int(state.get("pde_revision") or 0) + 1
    state.pop("pending_pde_settings", None)
    project["workflow_state"] = state
    project["active_structure"] = {}
    return project
