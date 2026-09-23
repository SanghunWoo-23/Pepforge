from types import SimpleNamespace

from spps_v4_gui.classic_base import ClassicControllerBase
from spps_v4_gui.modules import plan_workflow


class Var:
    def __init__(self, value=""):
        self.value = value
    def get(self):
        return self.value
    def set(self, value):
        self.value = value


def _fake_gui(pm_sequence="GHK", legacy_sequence=""):
    return SimpleNamespace(
        pm_sequence=Var(pm_sequence),
        seq=Var(legacy_sequence),
        resin=Var("2-CTC"),
        scale=Var("1000"),
        loading=Var("0.8"),
        pm_items=[{"sequence": ""}],
        _v229_active_index=0,
        pm_scale=Var("1000"),
        pm_resin=Var("2-CTC"),
        pm_loading=Var("0.8"),
        pm_chemistry=Var("DIC/HOBt"),
        pm_copies=Var("1"),
        coupling_eq=Var("5"),
        modifier_eq=Var("3"),
        coupling_repeats=Var("1"),
        modifier_repeats=Var("1"),
        default_reagent=Var("DIC"),
        default_reagent_eq=Var("5"),
        default_reagent_count=Var("1"),
        default_catalyst=Var("HOBt"),
        default_catalyst_eq=Var("5"),
        default_catalyst_count=Var("1"),
        default_base=Var(""),
        default_base_eq=Var("0"),
        default_base_count=Var("0"),
        default_coupling_solution_solvent=Var("DMF"),
        default_solvent1=Var("DMF"),
        default_solvent1_count=Var("6"),
        default_solvent2=Var("DCM"),
        default_solvent2_count=Var("3"),
        default_depro=Var("Piperidine"),
        default_depro_ratio=Var("20% in DMF"),
        default_depro_count=Var("2"),
        default_loading_dissolve_solvent=Var("90% DCM / 10% DMF"),
        solvent_volume_mode=Var("resin_factor"),
        amide_ml_per_mmol=Var("10"),
        ctc_ml_per_mmol=Var("5"),
        solvent_molarity_m=Var("0.2"),
        loading_aa_eq=Var("2"),
        loading_diea_eq=Var("4"),
        loading_time_h=Var(""),
        cleavage_reserve_mL=Var("0"),
        short_peptide_coupling_eq=Var("2"),
        cleavage_eq_override=Var("0"),
        cleavage_preset=Var("AUTO"),
        cleavage_components_text=Var(""),
        cleavage_time_h=Var(""),
        apply_loading_calc=Var(True),
        reagent_eq_follows_coupling_eq=Var(True),
        final_meoh_count=Var("0"),
    )


def test_visible_pm_sequence_repairs_blank_legacy_sequence_and_item():
    gui = _fake_gui("GHK", "")
    assert plan_workflow._visible_sequence(gui) == "GHK"
    assert gui.seq.get() == "GHK"
    assert gui.pm_items[0]["sequence"] == "GHK"


def test_build_plan_input_uses_visible_sequence_even_when_legacy_is_blank():
    gui = _fake_gui("GHK", "")
    inp = plan_workflow._build_plan_input(gui, {})
    assert inp.sequence == "GHK"
    from spps_planner.engine import generate_step_reagent_plan
    frame = generate_step_reagent_plan(inp)
    assert not frame.empty


def test_classic_input_prefers_visible_project_manager_sequence():
    gui = _fake_gui("GHK", "")
    inp = ClassicControllerBase._input(gui)
    assert inp.sequence == "GHK"
    assert gui.seq.get() == "GHK"


def test_intentionally_blank_visible_editor_does_not_resurrect_stale_sequence():
    gui = _fake_gui("", "OLD")
    gui.pm_items[0]["sequence"] = "OLD"
    assert plan_workflow._visible_sequence(gui) == ""
    assert gui.pm_sequence.get() == ""
    assert gui.seq.get() == "OLD"
