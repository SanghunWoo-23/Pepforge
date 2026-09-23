from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PDE = ROOT / "apps" / "peptide_design_engine" / "Python"
COLAB = ROOT / "apps" / "peptide_design_engine" / "Colab" / "Ultimate_Peptide_Final_Engine.py"
sys.path.insert(0, str(PDE))

import peptide_engine as pe
from peptiforg_core.candidate_manifest import (
    add_artifacts,
    canonical_construct_tokens,
    new_candidate_manifest,
    stable_candidate_id,
)
from pepforge_structure_tool.pepforge_core import expand_and_tokenize


def _small_nsga_config():
    return {
        "ENGINE_MODE": "NSGA2",
        "POP": 12,
        "GEN": 2,
        "FINAL_TOPK": 5,
        "SEED": 20260819,
        "LEN_MODE": "FIX",
        "FIX_LENGTH": 8,
        "MIN_LENGTH": 8,
        "MAX_LENGTH": 8,
        "AUTO_SEED_EACH_RUN": False,
        "USE_OPTIONAL_ML": False,
        "USE_ML_PRIOR": False,
        "PREPARE_PSEUDODOCKING_COLAB": False,
        "USE_TAG": False,
        "USE_LABEL": False,
        "USE_BASE_CHEM": False,
        "USE_D": True,
        "D_PCT": 0.15,
        "USE_NON_NAT": False,
        "USE_LINKER": False,
        "MOTIF_LOCK": False,
        "LOCKED_MOTIFS": [],
        "DUAL_MOTIFS": [],
        "TARGETS": [],
        "MOTIF_PLACEMENT_MODE": "OFF",
        "MOTIF_PLACEMENT_SPECS": "",
    }


def test_nsga2_locked_seed_is_reproducible_and_reports_real_pareto_front():
    baseline = copy.deepcopy(pe.CONFIG)
    try:
        pop1, progress1 = pe.evolve(_small_nsga_config(), verbose=False)
        top1 = [row["candidate_id"] for row in pe.population_rows(pop1)[:5]]
        pe.CONFIG.clear(); pe.CONFIG.update(copy.deepcopy(baseline))
        pop2, progress2 = pe.evolve(_small_nsga_config(), verbose=False)
        top2 = [row["candidate_id"] for row in pe.population_rows(pop2)[:5]]
    finally:
        pe.CONFIG.clear(); pe.CONFIG.update(baseline)
    assert top1 == top2
    assert progress1 == progress2
    assert all(row["engine_mode"] == "NSGA2" for row in progress1)
    assert all(int(row["pareto_front_size"]) > 0 for row in progress1)


def test_candidate_identity_preserves_terminal_and_stereochemical_chemistry():
    plain = stable_candidate_id(["K", "A", "C", "NH2"])
    d_form = stable_candidate_id(["dK", "A", "C", "NH2"])
    acetyl = stable_candidate_id(["Ac", "K", "A", "C", "NH2"])
    assert len({plain, d_form, acetyl}) == 3
    assert pe.stable_candidate_id(["dK", "A", "C", "NH2"]) == d_form


def test_compact_canonical_sequence_wins_over_case_insensitive_terminal_alias():
    assert expand_and_tokenize("ACDE-NH2") == ["A", "C", "D", "E", "NH2"]
    assert expand_and_tokenize("A-C-D-E-NH2") == ["A", "C", "D", "E", "NH2"]
    assert expand_and_tokenize("AC-D-E-NH2") == ["Ac", "D", "E", "NH2"]
    assert expand_and_tokenize("PAL-A-C-NH2") == ["Pal", "A", "C", "NH2"]
    assert expand_and_tokenize("P-A-L-NH2") == ["P", "A", "L", "NH2"]
    assert canonical_construct_tokens("ACDE-NH2") == ["A", "C", "D", "E", "NH2"]


def test_manifest_records_only_existing_artifacts(tmp_path):
    candidate = new_candidate_manifest("ACDE-NH2")
    actual = tmp_path / "actual.pdb"
    actual.write_text("MODEL\nENDMDL\n", encoding="utf-8")
    missing = tmp_path / "missing.pdb"
    updated = add_artifacts(candidate, "structure", {"rank1": actual, "rank2": missing})
    assert updated["artifacts"]["structure"] == {"rank1": str(actual)}
    assert updated["candidate_id"] == stable_candidate_id("ACDE-NH2")


def test_desktop_and_colab_pde_engines_are_source_identical():
    assert PDE.joinpath("peptide_engine.py").read_bytes() == COLAB.read_bytes()


def test_public_pepforge_contains_no_private_spps_seed_payload():
    seed = ROOT / "apps" / "spps_planner_app" / "data" / "experimental_seed"
    files = sorted(p.relative_to(seed).as_posix() for p in seed.rglob("*") if p.is_file())
    assert files == ["README.md"]
    forbidden = ["DO_NOT_PUBLISH_PRIVATE_BUILD.txt", "PRIVATE_DATA_POLICY.md"]
    assert not any(any(ROOT.rglob(name)) for name in forbidden)


def test_package_index_records_current_public_evidence_boundary():
    data = json.loads((ROOT / "PACKAGE_INDEX.json").read_text(encoding="utf-8"))
    joined = "\n".join(data.get("patch_notes", []))
    assert "SPPS Planner V5.0.0 Public/Data-Sanitized logic" in joined
    assert "without private experimental seed data" in joined
    assert "NSGA-II" in joined
