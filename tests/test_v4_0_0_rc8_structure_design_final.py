from __future__ import annotations

import json
from pathlib import Path

import pytest

from peptiforg_core.peptide_conformation import sequence_conformation_evidence
from pepforge_structure_tool.pepforge_core import (
    _covalent_graph_validation,
    _structure_generation_route,
    build_structure,
    expand_and_tokenize,
    tokens_to_smiles,
)


def _tokens_and_mol(sequence: str):
    Chem = pytest.importorskip("rdkit.Chem")
    raw = expand_and_tokenize(sequence)
    smiles, tokens, warnings, ranges = tokens_to_smiles(raw)
    mol = Chem.MolFromSmiles(smiles)
    assert mol is not None, warnings
    return mol, tokens, ranges


def test_context_aware_pro_gly_and_beta_charge_descriptors():
    _, tokens, _ = _tokens_and_mol("PAAAGGKKKDEVIVI")
    evidence = sequence_conformation_evidence(tokens)
    context = evidence["helix_breaker_context"]
    assert {row["position"] for row in context["terminal_or_cap_adjacent"]} == {1}
    assert {row["position"] for row in context["internal"]} == {5, 6}
    assert context["glycine_runs_2plus"]
    assert evidence["local_charge_patches"]
    beta = evidence["beta_face_context"]
    assert beta["odd_positions"] and beta["even_positions"]
    assert beta["odd_hydrophobic_fraction"] is not None


def test_generation_route_separates_plain_canonical_from_modified():
    _, tokens, ranges = _tokens_and_mol("Ac-EEMQRR-NH2")
    route = _structure_generation_route(tokens, ranges)
    assert route["canonical_L_linear"] is True
    assert "explicit_phi_psi" in route["route"]
    assert "PeptideBuilder" in route["peptidebuilder_concept_provenance"]

    _, modified_tokens, modified_ranges = _tokens_and_mol("K(FITC)-AEEA-dK-NH2")
    modified = _structure_generation_route(modified_tokens, modified_ranges)
    assert modified["canonical_L_linear"] is False
    assert modified["route"] == "explicit_chemistry_graph_RDKit_conformer_route"


def test_covalent_graph_validation_checks_every_adjacent_range():
    mol, tokens, ranges = _tokens_and_mol("K(FITC)-AEEA-dK-NH2")
    audit = _covalent_graph_validation(mol, tokens, ranges)
    assert audit["status"] == "passed"
    assert audit["valid"] is True
    assert audit["connected_components"] == 1
    assert audit["expected_adjacent_connections"] == len(ranges) - 1
    assert audit["validated_adjacent_connections"] == len(ranges) - 1
    assert not audit["failed_connections"]


def test_build_exports_seed_fidelity_graph_and_route(tmp_path: Path):
    result = build_structure(
        "AAAAA",
        output_dir=tmp_path,
        name="rc8_seed_audit",
        optimize=True,
        num_confs=3,
        max_iters=80,
        search_profile="evidence_fast",
        min_final_conformers=3,
        max_embedding_retries=1,
    )
    meta = json.loads(Path(result.meta_path).read_text(encoding="utf-8"))
    assert meta["structure_generation_route"]["canonical_L_linear"] is True
    assert meta["covalent_graph_validation"]["valid"] is True
    fidelity = meta["backbone_seed_fidelity_audit"]
    assert fidelity["status"] == "available"
    assert fidelity["records"]
    assert "PeptideBuilder" in fidelity["provenance"]
    report = Path(result.report_path).read_text(encoding="utf-8")
    assert "Covalent graph validation" in report
    assert "Explicit phi/psi seed fidelity" in report


def test_v4_docs_do_not_claim_active_trajectory_analysis():
    root = Path(__file__).resolve().parents[1]
    readme_ko = (root / "README_KO.md").read_text(encoding="utf-8")
    release = (root / "RELEASE_NOTES_V4.0.0.md").read_text(encoding="utf-8")
    simulation = (root / "docs/SIMULATION_STRUCTURE_EVIDENCE.md").read_text(encoding="utf-8")
    assert "V4에서는 production MD 실행과 trajectory 분석을 사용자 기능으로 제공하지 않습니다" in readme_ko
    assert "Real imported-trajectory analyzer" not in release
    assert "V4 does not expose production MD or trajectory analysis" in simulation
