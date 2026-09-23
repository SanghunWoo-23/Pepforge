from __future__ import annotations

"""Evidence-scoped peptide simulation protocol planning.

This module plans *external* molecular-dynamics validation. It does not execute
OpenMM/GROMACS/AMBER/NAMD and it never converts protocol length into a quality
grade. The purpose is to make starting-state, replicate, environment, and force-
field sensitivity explicit before a trajectory is generated.
"""

from dataclasses import dataclass, asdict
from typing import Any, Iterable
import re
import importlib.util

SIMULATION_PROTOCOL_VERSION = "2.0.0"

_CANONICAL = set("ACDEFGHIKLMNPQRSTVWY")


@dataclass(frozen=True)
class ForceFieldCandidate:
    force_field: str
    solvent: str
    role: str
    evidence_scope: str


def _tokenize_loose(sequence: str | Iterable[str]) -> list[str]:
    if isinstance(sequence, str):
        text = sequence.strip()
        if not text:
            return []
        # Preserve common multi-character Pepforge tokens while still accepting
        # plain one-letter canonical sequences.
        if re.fullmatch(r"[ACDEFGHIKLMNPQRSTVWY]+", text):
            return list(text)
        parts = [p for p in re.split(r"[-\s,;|]+", text) if p]
        return parts
    return [str(x) for x in sequence]


def classify_simulation_chemistry(sequence: str | Iterable[str]) -> dict[str, Any]:
    tokens = _tokenize_loose(sequence)
    canonical = [t for t in tokens if len(t) == 1 and t in _CANONICAL]
    d_tokens = [t for t in tokens if len(t) == 2 and t.startswith("d") and t[1:] in _CANONICAL]
    modifiers = [t for t in tokens if t not in canonical and t not in d_tokens and t.upper() not in {"NH2", "OH"}]
    raw = "-".join(tokens)
    cyclic_markers = any(x.lower() in raw.lower() for x in ("cyclo", "cyclic", "head-to-tail"))
    disulfide_candidate = sum(1 for t in canonical if t == "C") >= 2
    return {
        "tokens": tokens,
        "canonical_residue_count": len(canonical),
        "d_residue_count": len(d_tokens),
        "modified_or_noncanonical_tokens": modifiers,
        "canonical_L_only": bool(tokens) and len(canonical) == len(tokens),
        "cyclic_marker_detected": cyclic_markers,
        "disulfide_candidate": disulfide_candidate,
        "parameterization_required": bool(d_tokens or modifiers or cyclic_markers),
    }


def _force_field_candidates(kind: str) -> list[ForceFieldCandidate]:
    if kind == "cyclic":
        return [
            ForceFieldCandidate("RSFF2", "TIP3P", "primary sensitivity candidate", "2024 cyclic-peptide NMR benchmark"),
            ForceFieldCandidate("RSFF2C", "TIP3P", "primary sensitivity candidate", "2024 cyclic-peptide NMR benchmark"),
            ForceFieldCandidate("Amber14SB", "TIP3P", "primary sensitivity candidate", "2024 cyclic-peptide NMR benchmark"),
            ForceFieldCandidate("Amber19SB", "OPC", "alternate sensitivity candidate", "2024 cyclic-peptide NMR benchmark"),
        ]
    return [
        ForceFieldCandidate("Amber19SB", "OPC", "modern structured/peptide sensitivity candidate", "2026 diverse-peptide benchmark; not universally optimal"),
        ForceFieldCandidate("Amber19SB", "TIP3P", "water-model sensitivity candidate", "2026 diverse-peptide benchmark"),
        ForceFieldCandidate("a99SB-disp", "a99SB-disp water", "flexibility/disorder sensitivity candidate", "peptide/IDP force-field literature"),
        ForceFieldCandidate("CHARMM36m", "TIP3P", "cross-family sensitivity candidate", "peptide/protein ensemble literature"),
    ]


def build_simulation_protocol(
    sequence: str | Iterable[str],
    *,
    design_mode: str = "BALANCED",
    preferred_structure: str = "NONE",
    environment: str = "AQUEOUS",
    peptide_class: str | None = None,
    conformational_strategy: str = "ADAPTIVE",
) -> dict[str, Any]:
    chemistry = classify_simulation_chemistry(sequence)
    mode = str(design_mode or "BALANCED").upper()
    preferred = str(preferred_structure or "NONE").upper()
    env = str(environment or "AQUEOUS").upper()
    strategy = str(conformational_strategy or "ADAPTIVE").upper()
    if strategy not in {"PREORGANIZED", "ADAPTIVE", "FLEXIBLE"}:
        strategy = "ADAPTIVE"
    if peptide_class:
        kind = str(peptide_class).lower()
    elif chemistry["cyclic_marker_detected"]:
        kind = "cyclic"
    elif chemistry["parameterization_required"]:
        kind = "modified"
    else:
        kind = "linear"

    start_states: list[dict[str, str]] = []
    if mode == "INTERACTION_ONLY" or preferred == "NONE":
        start_states.append({"state": "best_clash_free_psb", "purpose": "structure-agnostic interaction-ready start"})
        start_states.append({"state": "alternate_clash_free_psb", "purpose": "test local-start sensitivity"})
    elif strategy == "PREORGANIZED":
        start_states.append({"state": "requested_structure_psb", "purpose": "test retention of the intentionally preorganized PDE-requested basin"})
        start_states.append({"state": "alternate_requested_family_psb", "purpose": "test sensitivity within the requested family"})
    elif strategy == "FLEXIBLE":
        start_states.append({"state": "best_clash_free_psb", "purpose": "sample from a structure-flexible starting hypothesis"})
        start_states.append({"state": "requested_structure_psb_challenge", "purpose": "test whether the requested bound-like basin remains accessible without assuming free-state preorganization"})
    else:
        start_states.append({"state": "requested_structure_psb", "purpose": "test the requested/bound-like basin without assuming it is the unique free-state structure"})
        start_states.append({"state": "alternate_psb_conformer", "purpose": "test local-basin dependence and adaptive folding/binding sensitivity"})
    start_states.append({"state": "extended_or_independent_start", "purpose": "challenge initial-condition bias"})

    enhanced: list[dict[str, str]] = [
        {"method": "independent_unbiased_MD", "status": "recommended first", "when": "default validation path"},
    ]
    if kind in {"linear", "modified"}:
        enhanced.append({
            "method": "OPES_multiT",
            "status": "optional advanced external backend",
            "when": "flexible/disordered peptide or poor basin exchange after independent MD",
        })
    enhanced.append({
        "method": "temperature_REMD_or_REST_family",
        "status": "optional advanced external backend",
        "when": "persistent initial-state dependence after ordinary replicate MD; validate reweighting/ensemble artifacts",
    })

    parameterization = {
        "status": "review_required" if chemistry["parameterization_required"] else "standard_canonical_candidate",
        "reason": (
            "D/non-natural/modifier/cyclic chemistry requires explicit topology, charges, and force-field parameter review."
            if chemistry["parameterization_required"]
            else "Plain canonical-L linear chemistry can enter a standard protein/peptide parameterization workflow, subject to termini/protonation review."
        ),
    }

    try:
        from peptiforg_core.modified_peptide_support import build_support_matrix
        support_matrix = build_support_matrix("-".join(chemistry.get("tokens") or []))
    except Exception as exc:
        support_matrix = {"status": "unavailable", "reason": str(exc)}
    backend_availability = {
        "OpenMM": bool(importlib.util.find_spec("openmm")),
        "execution_policy": "Pepforge V4 protocol/planning only unless an explicitly available backend is invoked by a future validated execution path.",
    }

    return {
        "protocol_version": SIMULATION_PROTOCOL_VERSION,
        "design_mode": mode,
        "preferred_structure": preferred if mode != "INTERACTION_ONLY" else "NONE",
        "environment": env,
        "peptide_class": kind,
        "conformational_strategy": strategy,
        "chemistry": chemistry,
        "parameterization_readiness": parameterization,
        "modified_peptide_support_matrix": support_matrix,
        "backend_availability": backend_availability,
        "minimum_independent_replicates": 3,
        "start_state_plan": start_states,
        "force_field_sensitivity_candidates": [asdict(x) for x in _force_field_candidates("cyclic" if kind == "cyclic" else "linear")],
        "enhanced_sampling_escalation": enhanced,
        "convergence_policy": {
            "rule": "Do not assign A/B/C/D quality from nominal simulation time.",
            "required_diagnostics": [
                "replicate agreement", "first-half vs second-half drift", "RMSD/Rg distributions",
                "secondary-structure distributions when meaningful", "contact/H-bond persistence when defined",
                "clustering/representative-state stability", "effective-sample-size/autocorrelation diagnostics",
            ],
            "extension_rule": "Extend or enhance sampling when independent starts disagree materially or diagnostics remain non-stationary.",
        },
        "structure_cross_checks": [
            "PSB internal geometry audit",
            "external PEP-FOLD4 candidate when applicable",
            "external CABS-flex candidate when applicable",
            "AF3/other model only as an independent consensus diagnostic, never ground truth",
        ],
        "claim_guard": (
            "Protocol planning only. Pepforge does not claim that a trajectory was run until an actual trajectory is imported and analyzed. "
            "Force-field candidates are sensitivity options, not a universal ranking."
        ),
    }
