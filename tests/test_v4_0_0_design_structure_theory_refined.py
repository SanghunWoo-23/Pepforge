from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
PDE = ROOT / "apps" / "peptide_design_engine" / "Python"
if str(PDE) not in sys.path:
    sys.path.insert(0, str(PDE))
import peptide_engine as eng

from peptiforg_core.design_intent import normalize_design_intent
from peptiforg_core.peptide_conformation import sequence_conformation_evidence
from pepforge_structure_tool.pepforge_core import build_structure, expand_and_tokenize, tokens_to_smiles


@pytest.fixture(autouse=True)
def _restore_engine_config():
    snapshot = copy.deepcopy(eng.CONFIG)
    yield
    eng.CONFIG.clear()
    eng.CONFIG.update(snapshot)


def _set(**kwargs):
    cfg = {
        "TARGETS": [list("DDEFW")],
        "PDE_OBJECTIVE_MODE": "BALANCED",
        "PREFERRED_STRUCTURE": "NONE",
        "STRUCTURE_BIAS": "BALANCED",
        "STRUCTURE_ENVIRONMENT": "AQUEOUS",
        "CONFORMATIONAL_STRATEGY": "PREORGANIZED",
        "HOTSPOT_COMPLEMENTARITY_MODE": "REPORT_ONLY",
    }
    cfg.update(kwargs)
    eng.update_config(cfg)


def test_conformational_strategy_changes_optimizer_policy_not_claim():
    seq = list("AELAELAK") + ["NH2"]
    _set(PDE_OBJECTIVE_MODE="STRUCTURE_GUIDED", PREFERRED_STRUCTURE="ALPHA_HELIX", CONFORMATIONAL_STRATEGY="PREORGANIZED")
    pre = eng.nsga_objectives(seq, [seq])
    assert "objective_structure_preference" in pre
    _set(PDE_OBJECTIVE_MODE="STRUCTURE_GUIDED", PREFERRED_STRUCTURE="ALPHA_HELIX", CONFORMATIONAL_STRATEGY="ADAPTIVE")
    adaptive = eng.nsga_objectives(seq, [seq])
    assert "objective_structure_preference" not in adaptive
    assert "objective_accessible_requested_basin" in adaptive
    _set(PDE_OBJECTIVE_MODE="STRUCTURE_GUIDED", PREFERRED_STRUCTURE="ALPHA_HELIX", CONFORMATIONAL_STRATEGY="FLEXIBLE")
    flexible = eng.nsga_objectives(seq, [seq])
    assert "objective_flexible_structure_guard" in flexible
    assert "probability" not in eng.design_objective_contract()["strategy_claim_guard"].lower() or "not" in eng.design_objective_contract()["strategy_claim_guard"].lower()


def test_interaction_only_still_removes_structure_for_all_strategies():
    seq = list("AELAELAK") + ["NH2"]
    for strategy in ("PREORGANIZED", "ADAPTIVE", "FLEXIBLE"):
        _set(PDE_OBJECTIVE_MODE="INTERACTION_ONLY", PREFERRED_STRUCTURE="BETA_HAIRPIN", CONFORMATIONAL_STRATEGY=strategy)
        assert list(eng.nsga_objectives(seq, [seq])) == ["objective_interaction"]
        assert eng.design_objective_contract()["preferred_structure"] == "NONE"


def test_pace_scholtz_and_ncap_acetylation_are_exported_without_ccap_overclaim():
    unacetylated = eng.sequence_structure_context_report(list("NAELAELA"))
    acetylated = eng.sequence_structure_context_report(["Ac"] + list("AAELAELA") + ["NH2"])
    assert unacetylated["pace_scholtz_mean_ddg_kcal_mol"] is not None
    assert unacetylated["ncap_context"] == "Asn_favorable"
    assert acetylated["ncap_context"] == "acetylated_N_cap_effect_cancelled"
    assert acetylated["ccap_identity_weighted"] is False


def test_ppii_uses_nonproline_context_and_flags_pro_aromatic_risk():
    linear = eng.sequence_structure_context_report(list("LALALALA"))
    aromatic = eng.sequence_structure_context_report(list("PFPYPWP"))
    assert linear["scores"]["PPII_EXTENDED"] > 0.0
    assert aromatic["ppii_pro_aromatic_adjacency_count"] >= 3
    assert aromatic["ppii_cis_trans_risk_descriptor"] > 0.0


def test_explicit_noncanonical_turn_motifs_are_evidence_not_surrogates():
    dpg = eng.sequence_structure_context_report(["L", "V", "V", "dP", "G", "L", "V", "V", "NH2"])
    aibg = eng.sequence_structure_context_report(["L", "V", "V", "Aib", "G", "L", "V", "V", "NH2"])
    assert dpg["d_pro_gly_type_II_prime_turn_candidates"]
    assert aibg["aib_gly_type_I_prime_turn_candidates"]
    assert "dP" in dpg["unsupported_structure_tokens"]
    assert "Aib" in aibg["unsupported_structure_tokens"]
    assert dpg["scores"]["BETA_HAIRPIN"] > 0.0
    assert aibg["scores"]["BETA_HAIRPIN"] > 0.0


def test_explicit_aib_has_310_evidence_without_ala_conversion():
    rep = eng.sequence_structure_context_report(["Aib", "A", "Aib", "L", "Aib", "NH2"])
    assert rep["explicit_Aib_count"] == 3
    assert "Aib" in rep["unsupported_structure_tokens"]
    assert rep["family_evidence_coverage"]["HELIX_310"] > rep["canonical_L_coverage"]


def test_beta_intrinsic_and_face_organization_are_separate_descriptors():
    rep = eng.sequence_structure_context_report(list("VVVVVVVV"))
    assert "beta_intrinsic_descriptor" in rep
    assert "beta_amphipathic_alternation_descriptor" in rep
    assert rep["beta_intrinsic_descriptor"] != rep["beta_amphipathic_alternation_descriptor"]


def test_hotspot_chemistry_is_report_only_until_explicitly_selected():
    seq = list("KKKLF")
    eng.CONFIG["_EXTRACTED_HOTSPOTS"] = [{"motif": "DDEFW", "score": 1.0}]
    eng.CONFIG["HOTSPOT_COMPLEMENTARITY_MODE"] = "REPORT_ONLY"
    report = eng.hotspot_chemistry_complementarity_report(seq)
    assert report["status"] == "available"
    assert report["score"] > 0.0
    assert report["selection_active"] is False
    assert eng.raw_fitness(seq)["fit_hotspot_complementarity"] == 0.0
    eng.CONFIG["HOTSPOT_COMPLEMENTARITY_MODE"] = "EVIDENCE_AND_SELECTION"
    report2 = eng.hotspot_chemistry_complementarity_report(seq)
    assert report2["selection_active"] is True
    assert eng.raw_fitness(seq)["fit_hotspot_complementarity"] > 0.0
    assert "not a contact map" in report2["claim_guard"]


def test_design_intent_transfers_strategy_to_psb_boundary():
    out = normalize_design_intent({
        "pde_objective_mode": "STRUCTURE_GUIDED",
        "preferred_structure": "BETA_HAIRPIN",
        "conformational_strategy": "ADAPTIVE",
        "hotspot_complementarity_mode": "REPORT_ONLY",
    })
    assert out["mode"] == "STRUCTURE_GUIDED"
    assert out["conformational_strategy"] == "ADAPTIVE"
    assert out["hotspot_complementarity_mode"] == "REPORT_ONLY"


def test_psb_sequence_evidence_recognizes_nonproline_ppii_context_and_coiled_heptad():
    _smiles, tokens, _warnings, _ranges = tokens_to_smiles(expand_and_tokenize("LALALALA"))
    ev = sequence_conformation_evidence(tokens)
    assert ev["nonproline_positions_for_PPII_context"]
    assert "coiled_coil_heptad_evidence" in ev


def test_dpro_gly_hairpin_build_uses_literature_seed_but_requires_measured_geometry(tmp_path: Path):
    result = build_structure(
        "LVV-dP-G-LVV-NH2", tmp_path, name="dpg_hairpin", num_confs=6, max_iters=100,
        search_profile="evidence_fast", min_final_conformers=3, max_embedding_retries=2,
        environment_conditions={"pde_design_intent": {"mode": "STRUCTURE_GUIDED", "preferred_structure": "BETA_HAIRPIN", "conformational_strategy": "PREORGANIZED"}},
    )
    meta = json.loads(Path(result.meta_path).read_text(encoding="utf-8"))
    seed_summary = meta["conformer_summary"].get("backbone_seed_relaxation", {})
    assert int(seed_summary.get("literature_turn_seed_count", 0)) >= 1
    analysis = meta["conformation_analysis"]
    top = analysis["top_conformers"]
    assert top
    assert int(seed_summary.get("literature_turn_seed_count", 0)) >= 4
    assert int(analysis.get("requested_structure_match_count", 0)) >= 1
    # A seed label alone is insufficient: a requested-family match must carry
    # measured turn/backbone-contact geometry after relaxation.
    for row in top:
        if row.get("requested_structure_match"):
            assert row.get("beta_turn_CA_i_i3_contacts", 0) >= 1
            assert row.get("nonlocal_backbone_contacts", 0) >= 1


def test_explicit_aib_310_build_uses_special_seed_without_canonicalization(tmp_path: Path):
    result = build_structure(
        "Aib-A-Aib-L-Aib-NH2", tmp_path, name="aib310", num_confs=5, max_iters=80,
        search_profile="evidence_fast", min_final_conformers=3, max_embedding_retries=2,
        environment_conditions={"pde_design_intent": {"mode": "STRUCTURE_GUIDED", "preferred_structure": "HELIX_310"}},
    )
    meta = json.loads(Path(result.meta_path).read_text(encoding="utf-8"))
    seed_summary = meta["conformer_summary"].get("backbone_seed_relaxation", {})
    assert int(seed_summary.get("explicit_Aib_310_seed_count", 0)) >= 1
    assert any(str(x).startswith("3_10_Aib_explicit_seed") for x in meta["conformer_summary"].get("backbone_seed_conformers", {}).values())


def test_invalid_hotspot_complementarity_mode_falls_back_with_raw_audit():
    out = normalize_design_intent({
        "mode": "BALANCED",
        "hotspot_complementarity_mode": "invented_mode",
    })
    assert out["hotspot_complementarity_mode"] == "REPORT_ONLY"
    assert out["hotspot_complementarity_mode_raw"] == "INVENTED_MODE"
