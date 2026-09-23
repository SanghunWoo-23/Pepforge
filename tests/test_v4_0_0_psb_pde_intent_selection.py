from __future__ import annotations

import json
from pathlib import Path

from peptiforg_core.peptide_conformation import select_top_conformers, sequence_conformation_evidence
from pepforge_structure_tool.pepforge_core import build_structure


def _tokens(seq: str):
    return [{"raw": aa, "kind": "std_aa"} for aa in seq]


def test_requested_alpha_prefers_same_family_without_artificial_diversity():
    rows = [
        {"conf_id": 1, "family": "alpha_helix_seed_candidate", "energy": 5.0, "severe_steric_clashes": 0},
        {"conf_id": 2, "family": "alpha_helix_like", "energy": 2.0, "severe_steric_clashes": 0},
        {"conf_id": 3, "family": "alpha_helix_like", "energy": 3.0, "severe_steric_clashes": 0},
        {"conf_id": 4, "family": "coil_mixed", "energy": 0.1, "severe_steric_clashes": 0},
        {"conf_id": 5, "family": "beta_extended_like", "energy": 0.2, "severe_steric_clashes": 0},
    ]
    selected = select_top_conformers(
        {"conformers": rows}, sequence_conformation_evidence(_tokens("VRLLREFQEIC")),
        limit=3, preferred_structure="ALPHA_HELIX", design_mode="STRUCTURE_GUIDED",
    )
    assert len(selected) == 3
    assert all(row["requested_structure_match"] for row in selected)
    assert all("alpha" in row["family"] or row["family"] == "helical_backbone_like" for row in selected)
    assert all(not row["selection_fallback"] for row in selected)


def test_requested_family_uses_explicit_clean_fallback_not_clashing_match():
    rows = [
        {"conf_id": 1, "family": "alpha_helix_like", "energy": 1.0, "severe_steric_clashes": 0},
        {"conf_id": 2, "family": "alpha_helix_like", "energy": 0.1, "severe_steric_clashes": 2},
        {"conf_id": 3, "family": "coil_mixed", "energy": 2.0, "severe_steric_clashes": 0},
    ]
    selected = select_top_conformers(
        {"conformers": rows}, sequence_conformation_evidence(_tokens("VRLLREFQEIC")),
        limit=2, preferred_structure="ALPHA_HELIX", design_mode="STRUCTURE_GUIDED",
    )
    assert [row["conf_id"] for row in selected] == [1, 3]
    assert selected[1]["selection_fallback"] is True
    assert all(row["severe_steric_clashes"] == 0 for row in selected)


def test_interaction_only_does_not_force_family_diversity():
    rows = [
        {"conf_id": 1, "family": "coil_mixed", "energy": 1.0, "severe_steric_clashes": 0},
        {"conf_id": 2, "family": "coil_mixed", "energy": 2.0, "severe_steric_clashes": 0},
        {"conf_id": 3, "family": "alpha_helix_like", "energy": 5.0, "severe_steric_clashes": 0},
    ]
    selected = select_top_conformers(
        {"conformers": rows}, sequence_conformation_evidence(_tokens("VRLLREFQEIC")),
        limit=2, preferred_structure="ALPHA_HELIX", design_mode="INTERACTION_ONLY",
    )
    assert [row["conf_id"] for row in selected] == [1, 2]
    assert all(row["candidate_role"] == "interaction_ready_geometry_candidate" for row in selected)


def test_pde_alpha_build_prefers_alpha_and_default_pdb_omits_hydrogen(tmp_path: Path):
    result = build_structure(
        "VRLLREFQEIC", tmp_path, name="intent_alpha", num_confs=8, max_iters=120,
        search_profile="evidence_balanced", min_final_conformers=5, max_embedding_retries=3,
        environment_conditions={"pde_design_intent": {"mode": "STRUCTURE_GUIDED", "preferred_structure": "ALPHA_HELIX"}},
    )
    meta = json.loads(Path(result.meta_path).read_text(encoding="utf-8"))
    top = meta["conformation_analysis"]["top_conformers"]
    assert top
    assert top[0]["requested_structure_match"] is True
    assert top[0]["severe_steric_clashes"] == 0
    assert meta["conformation_analysis"]["severe_clash_selected_count"] == 0
    assert meta["conformation_analysis"]["rmsd_diversity_used_for_selection"] is False
    pdb = Path(result.pdb_path).read_text(encoding="utf-8", errors="ignore")
    atom_lines = [line for line in pdb.splitlines() if line.startswith(("ATOM", "HETATM"))]
    # PDB element column 77-78 must not contain hydrogen. SDF/optimization still retain H.
    assert atom_lines
    assert all(line[76:78].strip().upper() != "H" for line in atom_lines if len(line) >= 78)
