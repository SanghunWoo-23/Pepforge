
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "peptide_design_engine" / "Python"))
import peptide_engine as pe

def _small_config(**overrides):
    cfg = {
        "POP": 20, "GEN": 1, "FINAL_TOPK": 5, "SEED": 123,
        "LEN_MODE": "FIX", "FIX_LENGTH": 12, "MIN_LENGTH": 12, "MAX_LENGTH": 12,
        "USE_OPTIONAL_ML": False, "USE_ML_PRIOR": False,
        "PREPARE_PSEUDODOCKING_COLAB": False,
        "USE_TAG": False, "USE_LABEL": False, "USE_BASE_CHEM": False,
        "USE_D": False, "USE_NON_NAT": False,
        "USE_LINKER": False,
        "MOTIF_LOCK": False, "LOCKED_MOTIFS": [],
        "MOTIF_PLACEMENT_MODE": "OFF", "MOTIF_PLACEMENT_SPECS": "",
        "TARGETS": [list("DELIKFVRWA"), list("YYERWFCAA")],
    }
    cfg.update(overrides)
    return cfg

def test_fixed_motif_placement_does_not_crash_and_is_1_based():
    pe.update_config(_small_config(MOTIF_PLACEMENT_MODE="FIXED", MOTIF_PLACEMENT_SPECS="RGD@1,EEM@4"))
    seq = pe.repair_sequence(list("AAAAAAAAAAAA"))
    assert "".join(pe.clean_bases(seq)).startswith("RGDEEM")

def test_nterm_linker_blocked_when_linkers_enabled():
    pe.update_config(_small_config(USE_LINKER=True, LINKER_POS=[0,1,2], LINKER_MODE="FIX", FIX_LINKER_TYPE="PEG4", MAX_LINKERS=3))
    for _ in range(30):
        seq = pe.generate()
        assert not pe.has_nterm_linker(seq), seq

def test_bala_gala_are_amino_acid_like_not_linker_only():
    assert pe.base("bAla") == "A"
    assert pe.base("gAla") == "G"
    assert "bAla" not in pe.CONFIG.get("LINKER_TYPES", [])
    assert "gAla" not in pe.CONFIG.get("LINKER_TYPES", [])


def test_amino_acid_like_tokens_are_not_counted_as_linker_only():
    assert pe.is_linker_token("PEG4")
    assert not pe.is_linker_token("bAla")
    assert not pe.is_linker_token("gAla")
    assert not pe.is_linker_token("Sar")
    assert pe.linker_tokens_in_sequence(["Sar", "PEG4", "K"]) == ["PEG4"]
