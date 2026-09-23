from __future__ import annotations

"""Conservative protonation-sensitivity evidence for peptide candidates.

This module flags ionizable groups whose protonation state may alter charge,
H-bond/salt-bridge/cation-pi interpretation or conformational behaviour.  It
never estimates a pKa, chooses a protonation microstate, or reports a pH-dependent
structure probability.
"""

from typing import Any
import re

PROTONATION_SENSITIVITY_VERSION = "1.0.0"
IONIZABLE = {
    "D": ("acidic_side_chain", ["salt_bridge", "H_bond"]),
    "E": ("acidic_side_chain", ["salt_bridge", "H_bond"]),
    "H": ("histidine", ["salt_bridge", "H_bond", "cation_pi", "aromatic_interaction"]),
    "K": ("basic_side_chain", ["salt_bridge", "H_bond", "cation_pi"]),
    "R": ("basic_side_chain", ["salt_bridge", "H_bond", "cation_pi"]),
    "C": ("thiol", ["H_bond", "redox_or_disulfide_context"]),
    "Y": ("phenol", ["H_bond", "aromatic_interaction"]),
}


def _construct_tokens(sequence: str) -> list[str]:
    try:
        from peptiforg_core.candidate_manifest import canonical_construct_tokens
        return [str(x) for x in canonical_construct_tokens(sequence)]
    except Exception:
        # Notation-only fallback: preserve explicit dX, do not map named
        # non-natural residues to canonical surrogates.
        raw = re.sub(r"\s+", "", str(sequence or ""))
        raw = re.sub(r"(?i)-(?:NH2|CONH2|COOH|CO2H|OH|AMIDE)$", "", raw)
        raw = re.sub(r"(?i)^(?:Ac|FITC|Biotin|Pal|Myr)-", "", raw)
        if "-" in raw:
            return [x for x in raw.split("-") if x]
        out=[]; i=0
        while i < len(raw):
            if raw[i] == "d" and i+1 < len(raw) and raw[i+1].upper() in "ACDEFGHIKLMNPQRSTVWY":
                out.append(raw[i:i+2]); i += 2; continue
            if raw[i].upper() in "ACDEFGHIKLMNPQRSTVWY" and raw[i].isalpha(): out.append(raw[i].upper())
            i += 1
        return out


def protonation_sensitivity_report(sequence: str) -> dict[str, Any]:
    tokens = _construct_tokens(sequence)
    groups=[]; residue_index=0
    canonical_like=[]
    for token in tokens:
        t=str(token).strip()
        aa=""
        if len(t)==1 and t.upper() in "ACDEFGHIKLMNPQRSTVWY": aa=t.upper()
        elif len(t)==2 and t[0].lower()=="d" and t[1].upper() in "ACDEFGHIKLMNPQRSTVWY": aa=t[1].upper()
        if not aa:
            continue
        residue_index += 1; canonical_like.append(aa)
        if aa in IONIZABLE:
            kind, interactions = IONIZABLE[aa]
            groups.append({
                "position": residue_index, "token": t, "residue": aa,
                "group_kind": kind, "potentially_affected_interactions": interactions,
                "state": "protonation_sensitive_context",
            })
    raw=str(sequence or "")
    nterm_blocked=bool(re.match(r"(?i)^\s*(Ac|FITC|Biotin|Pal|Myr)[-\s]", raw))
    cterm_amide=bool(re.search(r"(?i)(NH2|CONH2|AMIDE)\s*$", raw))
    termini=[]
    if canonical_like and not nterm_blocked:
        termini.append({"terminus":"N", "state":"free_or_unspecified_N_terminus", "potentially_affected_interactions":["salt_bridge","H_bond"]})
    if canonical_like and not cterm_amide:
        termini.append({"terminus":"C", "state":"free_or_unspecified_C_terminus", "potentially_affected_interactions":["salt_bridge","H_bond"]})
    high_attention = any(x["residue"] == "H" for x in groups) or bool(termini)
    return {
        "version": PROTONATION_SENSITIVITY_VERSION,
        "status": "review_recommended" if groups or termini else "no_common_ionizable_group_detected",
        "ionizable_groups": groups,
        "terminal_groups": termini,
        "histidine_present": any(x["residue"] == "H" for x in groups),
        "review_priority": "elevated" if high_attention else ("contextual" if groups else "low"),
        "literature_scope": ["PMID:42267453", "PMID:23170889"],
        "claim_guard": (
            "Sequence-level sensitivity flag only. Pepforge does not infer pKa values, assign a protonation microstate, "
            "or predict pH-dependent folded fractions or a folding probability from this report."
        ),
    }


__all__ = ["PROTONATION_SENSITIVITY_VERSION", "protonation_sensitivity_report"]
