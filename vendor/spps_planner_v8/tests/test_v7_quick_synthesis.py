from types import SimpleNamespace

from suite_gui import chemistry_workflow, quick_synthesis
from suite_gui import batch_workflow

class Var:
    def __init__(self,v): self.v=str(v)
    def get(self): return self.v
    def set(self,v): self.v=str(v)


def test_hbtu_nmm_preset_uses_nmm_as_base_not_solvent():
    gui=SimpleNamespace(
        pm_chemistry=Var(""), default_reagent=Var(""), default_reagent_eq=Var(""), default_reagent_count=Var(""),
        default_catalyst=Var(""), default_catalyst_eq=Var(""), default_catalyst_count=Var(""),
        default_base=Var(""), default_base_eq=Var(""), default_base_count=Var(""),
        default_coupling_solution_solvent=Var("DCM"), coupling_eq=Var(""), batch_hbtu_eq=Var(""), batch_hbtu_conc=Var(""),
        batch_nmm_eq=Var(""), batch_nmm_conc=Var(""), schedule_autosave=lambda:None,
    )
    chemistry_workflow.apply_hbtu_nmm(gui)
    assert gui.pm_chemistry.get()=="HBTU/NMM"
    assert gui.default_base.get()=="NMM"
    assert gui.default_coupling_solution_solvent.get()=="DMF"
    assert gui.batch_nmm_conc.get()=="0.8"


def test_quick_comparison_reports_independent_hbtu_and_nmm():
    gui=SimpleNamespace(
        pm_sequence=Var("AAAA"), pm_scale=Var("0.1"), pm_copies=Var("1"),
        batch_coupling_eq=Var("2"), batch_solution_conc=Var("0.4"),
        batch_hbtu_eq=Var("2"), batch_hbtu_conc=Var("0.4"),
        batch_nmm_eq=Var("4"), batch_nmm_conc=Var("0.8"),
        _quick_baseline={"aa_eq":2,"aa_conc":0.4,"hbtu_eq":2,"hbtu_conc":0.4,"nmm_eq":4,"nmm_conc":0.8},
    )
    text=quick_synthesis.comparison(gui)
    assert "HBTU" in text and "NMM" in text
    assert "2.00 mL" in text
