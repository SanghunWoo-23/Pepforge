from __future__ import annotations

import numpy as np

from peptiforg_core.esm_peptide_embedding import backend_readiness, prepare_sequence_for_esm
from peptiforg_core.psb_ai_ranker import assemble_feature_vector, conformer_numeric_features


def test_esm_preparation_allows_terminal_modifier_with_disclosure():
    prep = prepare_sequence_for_esm("Ac-EEMQRR-NH2")
    assert prep.canonical_sequence == "EEMQRR"
    assert prep.status == "CANONICAL_BACKBONE_WITH_UNMODELED_MODIFIERS"
    assert prep.ignored_nonresidue_modifiers
    assert not prep.unsupported_residue_tokens


def test_esm_preparation_blocks_d_and_linker_chemistry():
    prep = prepare_sequence_for_esm("Pal-AEEA-dK-NH2")
    assert prep.status == "UNSUPPORTED_MODIFIED_BACKBONE_FOR_DIRECT_ESM"
    assert "AEEA" in prep.unsupported_residue_tokens
    assert any(token.lower() == "dk" for token in prep.unsupported_residue_tokens)


def test_backend_readiness_is_explicit_not_fake():
    state = backend_readiness()
    assert state["status"] in {"READY", "OPTIONAL_DEPENDENCY_MISSING"}
    assert isinstance(state["ready_for_inference"], bool)


def test_ranker_features_combine_numeric_and_embedding_without_probability_semantics():
    numeric = conformer_numeric_features({
        "energy": -12.5,
        "severe_steric_clashes": 0,
        "helical_basin_fraction": 0.75,
        "family": "alpha_helix_like",
    })
    vector, names = assemble_feature_vector(numeric, embedding=np.array([0.1, 0.2, 0.3]))
    assert vector.shape == (len(names),)
    assert "energy" in names
    assert names[-1] == "esm_0002"
