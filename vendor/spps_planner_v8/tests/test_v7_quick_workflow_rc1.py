from pathlib import Path
from types import SimpleNamespace

from suite_gui import quick_synthesis


class Var:
    def __init__(self, value=""):
        self.value = str(value)

    def get(self):
        return self.value

    def set(self, value):
        self.value = str(value)


def _method_gui():
    values = {
        "pm_chemistry": "HBTU/NMM",
        "batch_solution_conc": "0.4",
        "batch_coupling_eq": "2",
        "batch_hbtu_conc": "0.4",
        "batch_hbtu_eq": "2",
        "batch_nmm_conc": "0.8",
        "batch_nmm_eq": "4",
        "batch_actual_round_ml": "0.5",
        "batch_actual_extra_ml": "0",
        "default_reagent": "HBTU",
        "default_reagent_eq": "2",
        "default_catalyst": "",
        "default_catalyst_eq": "0",
        "default_base": "NMM",
        "default_base_eq": "4",
        "default_coupling_solution_solvent": "DMF",
        "coupling_repeats": "1",
    }
    gui = SimpleNamespace(**{name: Var(value) for name, value in values.items()})
    gui.schedule_autosave = lambda: None
    return gui


def test_method_preset_roundtrip_and_apply(tmp_path: Path):
    gui = _method_gui()
    preset_path = tmp_path / "presets.json"
    snap = quick_synthesis.method_snapshot(gui)
    quick_synthesis.save_preset("My HBTU NMM", snap, preset_path)

    gui.batch_hbtu_eq.set("9")
    gui.batch_nmm_eq.set("9")
    gui.default_base.set("DIPEA")
    assert quick_synthesis.apply_named_preset(gui, "My HBTU NMM", preset_path)
    assert gui.batch_hbtu_eq.get() == "2"
    assert gui.batch_nmm_eq.get() == "4"
    assert gui.default_base.get() == "NMM"

    assert quick_synthesis.delete_preset("My HBTU NMM", preset_path)
    assert quick_synthesis.load_presets(preset_path) == {}


def test_summary_does_not_count_acetyl_prefix_as_cys():
    gui = _method_gui()
    gui.pm_sequence = Var("Ac-EEMQRR-NH2")
    gui.pm_scale = Var("0.1")
    gui.pm_copies = Var("1")
    gui.pm_resin = Var("Rink Amide AM")
    gui.quick_expert_enabled = Var("")
    gui.cleavage_eq_override = Var("0")
    gui.cleavage_preset = Var("AUTO")
    gui.cleavage_time_h = Var("")
    text = quick_synthesis.summary(gui)
    assert "Cys detected" not in text
    assert "Met detected (1)" in text


def test_expert_manual_cleavage_override_is_explicit_in_summary():
    gui = _method_gui()
    gui.pm_sequence = Var("ACGC")
    gui.pm_scale = Var("0.1")
    gui.pm_copies = Var("1")
    gui.pm_resin = Var("Rink Amide AM")
    gui.quick_expert_enabled = Var("1")
    gui.cleavage_eq_override = Var("175")
    gui.cleavage_preset = Var("AUTO")
    gui.cleavage_time_h = Var("2.5")
    text = quick_synthesis.summary(gui)
    assert "Cys detected (2)" in text
    assert "manual cleavage equivalent override active (175 eq)" in text
    assert "cleavage time = 2.5 h" in text


def test_prepare_today_uses_sequence_defaults_and_independent_hbtu_nmm(tmp_path: Path):
    gui = SimpleNamespace(
        pm_items=[{
            "project": "P1", "peptide": "pep", "sequence": "AAAA",
            "copies": "1", "scale": "0.1", "resin": "Rink Amide AM",
            "loading": "0.8", "chemistry": "DIC/HOBt",
        }],
        batch_default_scale=Var("0.1"), batch_solution_conc=Var("0.4"),
        batch_coupling_eq=Var("2"), batch_actual_round_ml=Var("0.5"),
        batch_actual_extra_ml=Var("0"), batch_default_resin=Var("Rink Amide AM"),
        batch_default_loading=Var("0.8"), batch_hbtu_eq=Var("2"),
        batch_hbtu_conc=Var("0.4"), batch_nmm_eq=Var("4"),
        batch_nmm_conc=Var("0.8"), default_coupling_solution_solvent=Var("DMF"),
    )
    text = quick_synthesis.prepare_today_text(gui)
    assert "HBTU" in text and "2 mL (0.4 M / 2 eq)" in text
    assert "NMM" in text and "2 mL (0.8 M / 4 eq)" in text
    assert "DIC" not in text and "HOBt" not in text

    created = quick_synthesis.export_prepare_today(gui, tmp_path)
    names = {path.name for path in created}
    assert "PREP_AA_STOCK.csv" in names
    assert "PREP_COUPLING_REAGENTS.csv" in names
    assert "PREP_BASE_DEPROTECTION.csv" in names
    assert "PREP_README.txt" in names


def test_startup_baseline_restore_does_not_touch_project_fields():
    gui = _method_gui()
    gui.pm_sequence = Var("PEPTIDE")
    baseline = quick_synthesis.capture_baseline(gui)
    gui.batch_hbtu_eq.set("7")
    gui.batch_nmm_eq.set("8")
    quick_synthesis.reset_to_baseline(gui)
    assert gui.batch_hbtu_eq.get() == baseline["hbtu_eq"]
    assert gui.batch_nmm_eq.get() == baseline["nmm_eq"]
    assert gui.pm_sequence.get() == "PEPTIDE"
