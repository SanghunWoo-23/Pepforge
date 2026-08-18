from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PDE = ROOT / "apps" / "peptide_design_engine" / "Python"
sys.path.insert(0, str(PDE))

import peptide_engine as pe
from peptiforg_core.peptide_conformation import (
    evidence_guided_family_plan,
    sequence_conformation_evidence,
)
from suite_gui.pymol_structure_builder_gui import BUILD_PRESETS


def _tokens(sequence: str):
    return [{"raw": aa, "kind": "std_aa"} for aa in sequence]


def test_psb_presets_control_real_search_profiles_and_exact_top5_contract():
    assert BUILD_PRESETS["Fast Top 5 (recommended)"]["search_profile"] == "evidence_fast"
    assert BUILD_PRESETS["Balanced Top 5"]["search_profile"] == "evidence_balanced"
    assert BUILD_PRESETS["Thorough Top 5"]["search_profile"] == "evidence_thorough"
    assert all(config["min_final_conformers"] == 5 for config in BUILD_PRESETS.values())
    assert BUILD_PRESETS["Fast Top 5 (recommended)"]["num_confs"] < BUILD_PRESETS["Balanced Top 5"]["num_confs"] < BUILD_PRESETS["Thorough Top 5"]["num_confs"]


def test_literature_evidence_changes_family_search_priority():
    helical = evidence_guided_family_plan(sequence_conformation_evidence(_tokens("EEMQRR")), "evidence_fast")
    proline_rich = evidence_guided_family_plan(sequence_conformation_evidence(_tokens("PPGPPG")), "evidence_fast")
    assert helical["family_priority"].index("alpha_helix_like") < helical["family_priority"].index("coil_mixed")
    assert proline_rich["family_priority"].index("PPII_like") < proline_rich["family_priority"].index("alpha_helix_like")
    assert "population" in helical["claim_guard"]


def test_pde_public_defaults_have_no_hidden_target_or_locked_motif_examples():
    assert pe.CONFIG["TARGETS"] == []
    assert pe.CONFIG["MOTIF_LOCK"] is False
    assert pe.CONFIG["LOCKED_MOTIFS"] == []
    assert pe.CONFIG["DUAL_MOTIFS"] == []
    assert pe.CONFIG["AUTO_SEED_EACH_RUN"] is True


def test_pde_final_ranking_enforces_visible_sequence_diversity_before_relaxing():
    rows = [
        {"rank": 1, "clean_sequence": "AAAAAAAA", "sequence": "A-A-A-A-A-A-A-A", "total_score": 10.0},
        {"rank": 2, "clean_sequence": "AAAAAAAT", "sequence": "A-A-A-A-A-A-A-T", "total_score": 9.9},
        {"rank": 3, "clean_sequence": "RRRRRRRR", "sequence": "R-R-R-R-R-R-R-R", "total_score": 9.8},
    ]
    ranked = pe.diversify_final_ranking(rows, top_n=2, minimum_distance=0.20)
    assert [row["clean_sequence"] for row in ranked[:2]] == ["AAAAAAAA", "RRRRRRRR"]
    assert all(row["final_diversity_status"] == "distance_pass" for row in ranked[:2])


def test_psb_export_and_pde_seed_controls_are_static_not_runtime_patches():
    builder = (ROOT / "pepforge_structure_tool" / "pepforge_core.py").read_text(encoding="utf-8")
    desktop = (PDE / "desktop_gui.py").read_text(encoding="utf-8")
    assert "_append_conformers_until" in builder
    assert "PSB ranked {required_final} structures but exported only" in builder
    assert "secrets.randbelow" in desktop
    assert "Repeat Last Run" in desktop
