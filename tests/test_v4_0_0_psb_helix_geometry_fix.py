from __future__ import annotations

import json
from pathlib import Path

from pepforge_structure_tool.pepforge_core import build_structure, expand_and_tokenize, tokens_to_smiles
from peptiforg_core.peptide_conformation import sequence_conformation_evidence, evidence_guided_family_plan


def _tokens(seq: str):
    _smiles, tokens, _warnings, _ranges = tokens_to_smiles(expand_and_tokenize(seq))
    return tokens


def test_helix_supported_sequence_does_not_rank_coil_ahead_of_alpha_seed():
    evidence = sequence_conformation_evidence(_tokens("VRLLREFQEIC"))
    assert evidence["family_support"]["alpha_helix_seed_candidate"] == "retain"
    assert evidence["family_support"]["coil_mixed"] == "contextual"
    plan = evidence_guided_family_plan(evidence, "evidence_fast")
    assert plan["family_priority"].index("alpha_helix_seed_candidate") < plan["family_priority"].index("coil_mixed")


def test_fast_psb_relaxes_alpha_seed_and_exports_zero_severe_clash_rank1(tmp_path: Path):
    result = build_structure(
        "VRLLREFQEIC",
        tmp_path,
        name="helix_regression",
        num_confs=5,
        max_iters=80,
        num_threads=2,
        search_profile="evidence_fast",
        min_final_conformers=5,
        max_embedding_retries=2,
    )
    meta = json.loads(Path(result.meta_path).read_text(encoding="utf-8"))
    top = meta["conformation_analysis"]["top_conformers"]
    assert len(top) == 5
    assert top[0]["family"] == "alpha_helix_seed_candidate"
    assert top[0]["helical_basin_fraction"] >= 0.8
    assert top[0]["severe_steric_clashes"] == 0

    relaxation = meta["conformer_summary"]["backbone_seed_relaxation"]["records"]
    alpha = [r for r in relaxation if str(r.get("source", "")).startswith("alpha_seed")]
    assert alpha
    assert all(r.get("relaxation") != "failed" for r in alpha)
    assert any(r.get("severe_steric_clashes_after_relaxation") == 0 for r in alpha)

    canonical = meta.get("canonical_view_pdb_path")
    assert canonical
    text = Path(canonical).read_text(encoding="utf-8", errors="ignore")
    assert "ATOM" in text
    assert " VAL A   1" in text
    assert " CYS A  11" in text
