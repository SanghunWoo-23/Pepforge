from __future__ import annotations

"""Docking Workbench access/provenance contract.

This module keeps UI visibility separate from execution readiness.  Features are
listed even when an optional backend/resource is unavailable, and each input
partner carries explicit provenance so the four supported input combinations
share one auditable contract.
"""

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
import importlib.util

DOCKING_ACCESS_CONTRACT_VERSION = "1.2.0"


@dataclass(frozen=True)
class PartnerProvenance:
    role: str
    input_mode: str
    source_kind: str
    source_value: str
    structure_source: str
    evidence_grade: str
    readiness: str
    claim_guard: str


def canonical_input_matrix_label(target_mode: str, peptide_mode: str) -> str:
    t = "PDB" if str(target_mode).strip().upper() == "PDB" else "Sequence"
    p = "PDB" if str(peptide_mode).strip().upper() == "PDB" else "Sequence"
    return f"{t} / {p}"


def partner_provenance(
    *,
    role: str,
    input_mode: str,
    path: str = "",
    sequence: str = "",
    runtime_source: str = "",
    runtime_evidence_grade: str = "",
    runtime_claim_guard: str = "",
) -> PartnerProvenance:
    mode = "PDB" if str(input_mode).strip().upper() == "PDB" else "Sequence"
    role = str(role or "partner")
    if mode == "PDB":
        clean = str(path or "").strip()
        exists = bool(clean and Path(clean).expanduser().exists())
        return PartnerProvenance(
            role=role,
            input_mode=mode,
            source_kind="structure_file",
            source_value=clean,
            structure_source=runtime_source or "user_supplied_structure",
            evidence_grade=runtime_evidence_grade or "SUPPLIED_STRUCTURE",
            readiness="READY" if exists else "MISSING_INPUT",
            claim_guard=runtime_claim_guard or "Supplied coordinates retain their original experimental/predicted provenance; Pepforge does not upgrade their evidence grade.",
        )
    seq = "".join(str(sequence or "").split())
    return PartnerProvenance(
        role=role,
        input_mode=mode,
        source_kind="sequence",
        source_value=seq,
        structure_source=runtime_source or "sequence_to_3d_pending",
        evidence_grade=runtime_evidence_grade or "SEQUENCE_INPUT_PENDING_STRUCTURE",
        readiness="READY_FOR_LOCAL_PREPARATION" if seq else "MISSING_INPUT",
        claim_guard=runtime_claim_guard or "Sequence-derived coordinates require an explicit local structure-preparation provenance and are not experimental structures.",
    )


def input_matrix_contract(
    *,
    target_mode: str,
    peptide_mode: str,
    target_path: str = "",
    target_sequence: str = "",
    peptide_path: str = "",
    peptide_sequence: str = "",
    target_runtime: dict[str, Any] | None = None,
    peptide_runtime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    target_runtime = dict(target_runtime or {})
    peptide_runtime = dict(peptide_runtime or {})
    target = partner_provenance(
        role="target",
        input_mode=target_mode,
        path=target_path,
        sequence=target_sequence,
        runtime_source=str(target_runtime.get("source") or target_runtime.get("structure_source") or ""),
        runtime_evidence_grade=str(target_runtime.get("evidence_grade") or ""),
        runtime_claim_guard=str(target_runtime.get("claim_guard") or ""),
    )
    peptide = partner_provenance(
        role="peptide",
        input_mode=peptide_mode,
        path=peptide_path,
        sequence=peptide_sequence,
        runtime_source=str(peptide_runtime.get("source") or peptide_runtime.get("structure_source") or ""),
        runtime_evidence_grade=str(peptide_runtime.get("evidence_grade") or ""),
        runtime_claim_guard=str(peptide_runtime.get("claim_guard") or ""),
    )
    ready = target.readiness.startswith("READY") and peptide.readiness.startswith("READY")
    return {
        "version": DOCKING_ACCESS_CONTRACT_VERSION,
        "matrix": canonical_input_matrix_label(target_mode, peptide_mode),
        "status": "READY" if ready else "INPUT_REQUIRED",
        "target": asdict(target),
        "peptide": asdict(peptide),
        "claim_guard": "All four PDB/Sequence input combinations share one provenance contract. Sequence-derived geometry remains explicitly distinguished from supplied structures.",
    }


def feature_access_rows() -> list[dict[str, str]]:
    """Return an always-visible capability inventory.

    Availability does not control visibility.  Optional resources can change the
    execution status but the feature remains listed in the UI with a reason.
    """
    rdkit = importlib.util.find_spec("rdkit") is not None
    transformers = importlib.util.find_spec("transformers") is not None
    rows = [
        ("PDB / PDB docking", "AVAILABLE", "core", "Direct coordinate analysis/search."),
        ("PDB / Sequence docking", "AVAILABLE", "core", "Local peptide structure preparation then common docking workflow."),
        ("Sequence / PDB docking", "AVAILABLE", "core", "Local target structure preparation then common docking workflow."),
        ("Sequence / Sequence docking", "AVAILABLE", "core", "Both partners are prepared locally before docking."),
        ("Pepforge Native Docking", "AVAILABLE_DEFAULT", "core", "Default Docking Workbench engine. Experimental Pepforge-native coordinate search; score is not affinity."),
        ("Interaction evidence", "AVAILABLE", "core", "Geometry-aware H-bond/hydrophobic/salt/pi/clash review."),
        ("Native mechanics / trajectory", "AVAILABLE_ONE_CLICK", "core", "Visible post-docking follow-up from the best usable native pose; experimental mechanics/descriptive trajectory evidence only, not validated production MD."),
        ("RDKit quality enhancement", "AVAILABLE" if rdkit else "OPTIONAL_NOT_INSTALLED", "optional", "Quality/chemistry enhancement only; core paths remain usable without it."),
        ("Local ESMFold enhancement", "AVAILABLE_IF_MODEL_CACHED" if transformers else "OPTIONAL_NOT_INSTALLED", "optional", "Offline local/cached predictor enhancement; native sequence-derived fallback remains visible."),
        ("Legacy geometry screen", "AVAILABLE_ADVANCED", "diagnostic", "Retained for compatibility/comparison; Pepforge Native Docking is the default search engine."),
        ("Shared docking result contract", "AVAILABLE", "core", "PSB and Docking Workbench export one normalized pose/evidence/provenance schema."),
        ("External result import", "AVAILABLE", "optional_validation", "External docking/affinity/MD evidence remains separate from native evidence."),
        ("RCSB online search", "ONLINE_OPTIONAL", "online_optional", "Online convenience only; not required for local docking workflows."),
    ]
    return [
        {"feature": f, "status": s, "tier": t, "note": n}
        for f, s, t, n in rows
    ]


__all__ = [
    "DOCKING_ACCESS_CONTRACT_VERSION",
    "PartnerProvenance",
    "canonical_input_matrix_label",
    "partner_provenance",
    "input_matrix_contract",
    "feature_access_rows",
]
