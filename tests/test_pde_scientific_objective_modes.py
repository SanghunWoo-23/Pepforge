from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
PDE = ROOT / "apps" / "peptide_design_engine" / "Python"
if str(PDE) not in sys.path:
    sys.path.insert(0, str(PDE))
import peptide_engine as eng
import copy
import pytest

@pytest.fixture(autouse=True)
def _restore_engine_config():
    snapshot = copy.deepcopy(eng.CONFIG)
    yield
    eng.CONFIG.clear()
    eng.CONFIG.update(snapshot)


def _set(**kwargs):
    cfg={
        "TARGETS":[list("DELIKFVRWA")],
        "PDE_OBJECTIVE_MODE":"BALANCED",
        "PREFERRED_STRUCTURE":"NONE",
        "STRUCTURE_BIAS":"BALANCED",
        "STRUCTURE_ENVIRONMENT":"AQUEOUS",
    }
    cfg.update(kwargs)
    eng.update_config(cfg)
    return cfg


def test_interaction_only_has_no_structure_objective():
    _set(PDE_OBJECTIVE_MODE="INTERACTION_ONLY", PREFERRED_STRUCTURE="ALPHA_HELIX")
    seq=list("ALEKLAEALA")+["NH2"]
    obj=eng.nsga_objectives(seq,[seq])
    assert list(obj) == ["objective_interaction"]
    assert eng.design_objective_contract()["preferred_structure"] == "NONE"


def test_structure_guided_requires_explicit_structure():
    _set(PDE_OBJECTIVE_MODE="STRUCTURE_GUIDED", PREFERRED_STRUCTURE="NONE")
    try:
        eng.design_objective_contract()
    except ValueError as exc:
        assert "requires an explicit PREFERRED_STRUCTURE" in str(exc)
    else:
        raise AssertionError("Structure Guided must not invent a preferred structure")


def test_position_context_changes_helix_evidence():
    _set(PDE_OBJECTIVE_MODE="STRUCTURE_GUIDED", PREFERRED_STRUCTURE="ALPHA_HELIX")
    clean=eng.sequence_structure_context_report(list("ALEKLAEALA")+["NH2"])
    broken=eng.sequence_structure_context_report(list("ALEKPAEALA")+["NH2"])
    assert clean["scores"]["ALPHA_HELIX"] > broken["scores"]["ALPHA_HELIX"]


def test_noncanonical_is_not_silently_substituted_for_structure_scoring():
    _set(PDE_OBJECTIVE_MODE="STRUCTURE_GUIDED", PREFERRED_STRUCTURE="ALPHA_HELIX")
    rep=eng.sequence_structure_context_report(["dA","Aib","L","E","NH2"])
    assert rep["canonical_L_coverage"] < 1.0
    assert "dA" in rep["unsupported_structure_tokens"]
    assert "Aib" in rep["unsupported_structure_tokens"]


def test_environment_is_context_not_permeability_claim():
    seq=list("LLKLLKLL")+["NH2"]
    _set(STRUCTURE_ENVIRONMENT="AQUEOUS")
    aq=eng.environment_compatibility_report(seq)
    _set(STRUCTURE_ENVIRONMENT="MEMBRANE_INTERFACE")
    mem=eng.environment_compatibility_report(seq)
    assert aq["environment"] != mem["environment"]
    assert "not permeability" in mem["claim_guard"]


def test_positional_spps_risk_categories_remain_separate():
    rep=eng.spps_positional_risk_report(list("DGVITMWC"))
    assert rep["flag_count"] >= 3
    assert rep["assembly_risk_positions"]
    assert rep["cleavage_risk_positions"]
    assert "not predicted crude purity" in rep["claim_guard"]


def test_interaction_only_hard_validity_does_not_reject_difficult_sequence_only():
    _set(PDE_OBJECTIVE_MODE="INTERACTION_ONLY", LEN_MODE="FIX", FIX_LENGTH=8, MIN_LENGTH=8, MAX_LENGTH=8)
    rep=eng.interaction_only_hard_validity_report(list("VVVVVVVV")+["NH2"])
    assert rep["valid"] is True
    assert rep["policy"] == "chemistry_and_topology_only"


def test_structure_bias_changes_guided_blend_without_becoming_probability():
    seq=list("ALEKLAEALA")+["NH2"]
    _set(PDE_OBJECTIVE_MODE="STRUCTURE_GUIDED", PREFERRED_STRUCTURE="ALPHA_HELIX", STRUCTURE_BIAS="MILD")
    mild=eng.nsga_objectives(seq,[seq])["objective_interaction_structure_balance"]
    _set(PDE_OBJECTIVE_MODE="STRUCTURE_GUIDED", PREFERRED_STRUCTURE="ALPHA_HELIX", STRUCTURE_BIAS="STRONG")
    strong=eng.nsga_objectives(seq,[seq])["objective_interaction_structure_balance"]
    assert mild != strong


def test_desktop_scientific_controls_do_not_overlap_output_rows():
    source=(ROOT / "apps" / "peptide_design_engine" / "Python" / "desktop_gui.py").read_text(encoding="utf-8")
    assert 'text="Output Folder").grid(row=12' in source
    assert 'textvariable=self.var_outdir).grid(row=12' in source
    assert 'text="Optional Settings JSON").grid(row=13' in source
    assert 'textvariable=self.var_config_file).grid(row=13' in source
