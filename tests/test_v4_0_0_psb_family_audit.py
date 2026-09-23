from __future__ import annotations

import json
from pathlib import Path

import pytest

from peptiforg_core.peptide_conformation import (
    preferred_structure_families,
    preferred_structure_seed_labels,
    requested_structure_audit,
    select_top_conformers,
    sequence_conformation_evidence,
)
from pepforge_structure_tool.pepforge_core import build_structure


def _tokens(seq: str):
    return [{"raw": aa, "kind": "std_aa"} for aa in seq]


@pytest.mark.parametrize("preferred", [
    "ALPHA_HELIX", "AMPHIPATHIC_ALPHA", "HELIX_310", "BETA_HAIRPIN",
    "BETA_STRAND", "PPII_EXTENDED", "TURN_RICH", "COILED_COIL",
])
def test_all_preferred_structure_modes_have_explicit_selection_contract(preferred: str):
    families = preferred_structure_families(preferred)
    assert families
    rows = [
        {"conf_id": 1, "family": families[0], "energy": 5.0, "severe_steric_clashes": 0,
         "helical_basin_fraction": 0.9, "beta_extended_fraction": 0.9, "PPII_fraction": 0.9,
         "turn_like_fraction": 0.9, "nonlocal_backbone_contacts": 2, "alpha_i_i4_contacts": 2,
         "helix310_i_i3_contacts": 2},
        {"conf_id": 2, "family": "coil_mixed", "energy": 0.1, "severe_steric_clashes": 0},
    ]
    selected = select_top_conformers(
        {"conformers": rows}, sequence_conformation_evidence(_tokens("AAAAAA")), limit=1,
        preferred_structure=preferred, design_mode="STRUCTURE_GUIDED",
    )
    assert selected[0]["conf_id"] == 1
    assert selected[0]["requested_structure_match"] is True
    assert selected[0]["selection_fallback"] is False


def test_family_limitations_are_explicit_not_fabricated():
    hairpin = requested_structure_audit("BETA_HAIRPIN", "STRUCTURE_GUIDED", [])
    turn = requested_structure_audit("TURN_RICH", "STRUCTURE_GUIDED", [])
    coiled = requested_structure_audit("COILED_COIL", "STRUCTURE_GUIDED", [])
    assert preferred_structure_seed_labels("BETA_HAIRPIN") == []
    assert preferred_structure_seed_labels("TURN_RICH") == []
    assert any("No invented exact torsion template" in x for x in hairpin["limitations"])
    assert any("No invented exact torsion template" in x for x in turn["limitations"])
    assert any("monomer conformer generator" in x for x in coiled["limitations"])


def test_proline_rich_ppii_seed_survives_ring_constrained_torsions(tmp_path: Path):
    result = build_structure(
        "PPAPPPAP", tmp_path, name="ppii_regression", num_confs=5, max_iters=60, num_threads=2,
        search_profile="evidence_fast", min_final_conformers=3, max_embedding_retries=2,
        environment_conditions={"pde_design_intent": {
            "pde_objective_mode": "STRUCTURE_GUIDED", "preferred_structure": "PPII_EXTENDED",
        }},
    )
    meta = json.loads(Path(result.meta_path).read_text(encoding="utf-8"))
    assert meta["pde_design_intent"]["mode"] == "STRUCTURE_GUIDED"
    top = meta["conformation_analysis"]["top_conformers"]
    assert top
    assert meta["conformation_analysis"]["requested_structure"] == "PPII_EXTENDED"
    assert meta["conformer_summary"]["applied_backbone_seed_count"] > 0
    assert any(str(v).startswith("PPII_seed") for v in meta["conformer_summary"]["applied_backbone_seed_labels"])
    assert meta["conformation_analysis"]["requested_structure_audit"]["requested_structure"] == "PPII_EXTENDED"
