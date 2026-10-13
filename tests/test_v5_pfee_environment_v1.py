from __future__ import annotations

import pytest

from peptiforg_core.peptide_conformation import evidence_guided_family_plan, sequence_conformation_evidence
from peptiforg_core.pfee_v1 import canonical_charge_proxy, normalize_pfee_environment, pfee_search_plan


def _tokens(sequence: str):
    return [{"raw": aa, "kind": "std_aa"} for aa in sequence]


def test_pfee_default_environment_preserves_family_priority():
    evidence = sequence_conformation_evidence(_tokens("EEMQRR"))
    base = evidence_guided_family_plan(evidence, "evidence_fast")
    plan = pfee_search_plan(evidence, base, None)
    assert plan["engine"] == "PFEE_v1"
    assert plan["family_priority"] == base["family_priority"]
    assert plan["family_priority_changed_by_environment"] is False
    assert plan["environment"]["pH"] == 7.0
    assert plan["environment"]["ionic_strength_mM"] == 150.0


def test_low_salt_high_charge_expands_sampling_not_fold_ranking():
    evidence = sequence_conformation_evidence(_tokens("KKKKKK"))
    base = evidence_guided_family_plan(evidence, "evidence_fast")
    plan = pfee_search_plan(evidence, base, {"pH": 7.0, "ionic_strength_mM": 10.0})
    assert plan["budget"]["etkdg_multiplier"] == base["budget"]["etkdg_multiplier"] + 1
    assert plan["family_priority"] == base["family_priority"]
    assert plan["canonical_charge_proxy"]["net_charge_proxy"] > 3.0
    assert any(row["type"] == "sampling_expansion" for row in plan["adjustments"])


def test_modified_sequence_never_gets_canonical_charge_surrogate():
    evidence = sequence_conformation_evidence([
        {"raw": "Cha", "kind": "non_natural_aa"},
        {"raw": "dK", "kind": "d_std_aa"},
    ])
    base = evidence_guided_family_plan(evidence, "evidence_fast")
    plan = pfee_search_plan(evidence, base, {"pH": 6.5, "ionic_strength_mM": 20})
    assert plan["canonical_charge_proxy"] is None
    assert plan["budget"] == base["budget"]
    assert plan["adjustments"][0]["type"] == "no_charge_proxy"


def test_environment_validation_is_explicit():
    with pytest.raises(ValueError, match="pH"):
        normalize_pfee_environment({"pH": 15})
    with pytest.raises(ValueError, match="ionic_strength_mM"):
        normalize_pfee_environment({"ionic_strength_mM": -1})


def test_charge_proxy_is_descriptor_not_probability():
    row = canonical_charge_proxy("EEMQRR", 7.0)
    assert isinstance(row["net_charge_proxy"], float)
    assert "not a protonation microstate" in row["claim_guard"]

from peptiforg_core.pfee_v1 import build_candidate_pool, diversify_ranked_representatives


def test_candidate_pool_rejects_only_explicit_severe_clashes():
    pool = build_candidate_pool({"conformers": [
        {"conf_id": 1, "family": "alpha_helix_like", "severe_steric_clashes": 0, "source": "ETKDG"},
        {"conf_id": 2, "family": "coil_mixed", "severe_steric_clashes": 2, "source": "seed"},
        {"conf_id": 3, "family": "alpha_helix_like", "severe_steric_clashes": 0, "source": "seed"},
    ]})
    assert pool["total_candidates"] == 3
    assert pool["usable_candidates"] == 2
    assert pool["usable_conf_ids"] == [1, 3]
    assert pool["rejections"][0]["conf_id"] == 2


def test_diversity_selector_preserves_quality_order_and_falls_back_explicitly():
    ranked = [
        {"conf_id": 1, "family": "alpha_helix_like", "rank": 1},
        {"conf_id": 2, "family": "alpha_helix_like", "rank": 2},
        {"conf_id": 3, "family": "coil_mixed", "rank": 3},
        {"conf_id": 4, "family": "turn_rich", "rank": 4},
    ]
    rmsd = {(1, 2): 0.2, (1, 3): 1.5, (1, 4): 1.8, (3, 4): 0.4, (2, 3): 1.6, (2, 4): 1.7}
    selected, audit = diversify_ranked_representatives(ranked, rmsd, limit=3, minimum_rmsd_A=1.0)
    assert [r["conf_id"] for r in selected] == [1, 3, 2]
    assert selected[0]["pfee_diversity_fallback"] is False
    assert selected[1]["pfee_diversity_fallback"] is False
    assert selected[2]["pfee_diversity_fallback"] is True
    assert audit["fallback_count"] == 1
    assert audit["force_family_diversity"] is False


def test_diversity_selector_never_treats_missing_rmsd_as_proof_of_diversity():
    ranked = [{"conf_id": 1}, {"conf_id": 2}, {"conf_id": 3}]
    selected, audit = diversify_ranked_representatives(ranked, {}, limit=2, minimum_rmsd_A=1.0)
    assert [r["conf_id"] for r in selected] == [1, 2]
    assert selected[1]["pfee_diversity_fallback"] is True
    assert audit["status"] == "fallback_required"


def test_pfee_adaptive_sampling_requests_real_search_only_when_needed():
    from peptiforg_core.pfee_v1 import adaptive_sampling_request
    req = adaptive_sampling_request(
        {"status": "fallback_required", "selected_count": 5, "fallback_count": 2},
        {"usable_candidates": 8}, requested_representatives=5, round_index=0,
    )
    assert req["request_additional_sampling"] is True
    assert req["requested_additional_conformers"] > 0
    assert "thermodynamic" in req["claim_guard"]
    done = adaptive_sampling_request(
        {"status": "threshold_met", "selected_count": 5, "fallback_count": 0},
        {"usable_candidates": 12}, requested_representatives=5, round_index=0,
    )
    assert done["request_additional_sampling"] is False
    capped = adaptive_sampling_request(
        {"status": "fallback_required", "selected_count": 5, "fallback_count": 1},
        {"usable_candidates": 12}, requested_representatives=5, round_index=2, max_rounds=2,
    )
    assert capped["request_additional_sampling"] is False
