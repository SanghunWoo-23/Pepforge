from pathlib import Path

from pepforge_structure_tool.pepforge_core import expand_and_tokenize
from suite_gui.pymol_structure_builder_gui import BUILD_PRESETS, CONDITION_PRESETS


ROOT = Path(__file__).resolve().parents[1]


def test_terminal_chemical_shorthand_wins_over_compact_residue_splitting():
    assert expand_and_tokenize("AC-EEMQRR-NH2")[0] == "Ac"
    assert expand_and_tokenize("PAL-EEMQRR-NH2")[0] == "Pal"
    assert expand_and_tokenize("A-C-NH2")[:2] == ["A", "C"]
    assert expand_and_tokenize("P-A-L-NH2")[:3] == ["P", "A", "L"]


def test_psb_presets_are_real_bounded_worker_settings():
    assert "Physiological aqueous" in CONDITION_PRESETS
    assert CONDITION_PRESETS["Physiological aqueous"]["pH"] == "7.4"
    assert "Fast Top 5 (recommended)" in BUILD_PRESETS
    fast = BUILD_PRESETS["Fast Top 5 (recommended)"]
    assert fast["num_confs"] >= 5
    assert fast["num_threads"] > 0
    assert fast["max_iters"] > 0
    assert fast["min_final_conformers"] == 5
    assert fast["search_profile"] == "evidence_fast"


def test_launcher_exposes_one_docking_workbench_and_v3_worker_route():
    source = (ROOT / "main_launcher.py").read_text(encoding="utf-8")
    assert source.count('"Docking Workbench"') == 1
    assert 'APP_VERSION = "3.0.0"' in source
    assert '"--structure-worker"' in source


def test_active_spps_v4_surface_excludes_batch_and_lot_controls():
    adapter = (ROOT / "suite_gui" / "spps_tk_gui.py").read_text(encoding="utf-8")
    build = (ROOT / "spps_v4_gui" / "ui_build.py").read_text(encoding="utf-8")
    alternate = (ROOT / "spps_v4_gui" / "modern_tk_gui.py").read_text(encoding="utf-8")
    assert "from spps_v4_gui.release import SPPSGui" in adapter
    assert "spps_v2_gui" not in adapter
    assert "build_batch_tab" not in build
    assert "build_batch_tab" not in alternate
    assert 'text="New LOT"' not in alternate
    assert '("LOT No.",' not in alternate
