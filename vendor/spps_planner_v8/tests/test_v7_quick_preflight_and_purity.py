from __future__ import annotations

from pathlib import Path

from suite_gui import quick_synthesis


class Var:
    def __init__(self, value):
        self.value = value
    def get(self):
        return self.value
    def set(self, value):
        self.value = value


class Gui:
    def __init__(self):
        self.pm_sequence = Var("Ac-EEMQRR-NH2")
        self.pm_scale = Var("0.2")
        self.pm_copies = Var("1")
        self.pm_loading = Var("0.8")
        self.pm_chemistry = Var("HBTU/NMM")
        self.default_reagent = Var("HBTU")
        self.batch_solution_conc = Var("0.4")
        self.batch_coupling_eq = Var("2")
        self.batch_hbtu_conc = Var("0.4")
        self.batch_hbtu_eq = Var("2")
        self.batch_nmm_conc = Var("0.8")
        self.batch_nmm_eq = Var("4")
        self.batch_actual_round_ml = Var("0.5")
        self.batch_actual_extra_ml = Var("1.0")
        self.quick_expert_enabled = Var(False)
        self.cleavage_eq_override = Var("0")
        self.cleavage_time_h = Var("0")


def test_quick_preflight_accepts_valid_hbtu_nmm_condition():
    check = quick_synthesis.preflight(Gui())
    assert check["errors"] == []


def test_quick_preflight_blocks_invalid_nmm_stock():
    gui = Gui()
    gui.batch_nmm_conc.set("0")
    check = quick_synthesis.preflight(gui)
    assert any("NMM stock concentration" in item for item in check["errors"])


def test_quick_preflight_warns_about_unusually_large_mmol_scale():
    gui = Gui()
    gui.pm_scale.set("400")
    check = quick_synthesis.preflight(gui)
    assert check["errors"] == []
    assert any("verify the unit" in item for item in check["warnings"])


def test_v7_production_purity_gate_passes_current_tree():
    import importlib.util
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("verify_v7_integrity", root / "tools" / "verify_v7_integrity.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    module.verify_production_purity()
