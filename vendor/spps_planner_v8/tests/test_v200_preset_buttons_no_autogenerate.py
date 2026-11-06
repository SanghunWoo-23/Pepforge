from types import SimpleNamespace

from suite_gui import chemistry_workflow


class Var:
    def __init__(self, value=''):
        self.value = value
    def set(self, value):
        self.value = value
    def get(self):
        return self.value


def _fake_gui():
    calls = {'autosave': 0}
    gui = SimpleNamespace(
        pm_chemistry=Var(''),
        default_reagent=Var(''),
        default_catalyst=Var(''),
        default_base=Var(''),
        default_coupling_solution_solvent=Var(''),
        coupling_eq=Var(''),
        default_reagent_eq=Var(''),
        default_reagent_count=Var(''),
        default_catalyst_eq=Var(''),
        default_catalyst_count=Var(''),
        default_base_eq=Var(''),
        default_base_count=Var(''),
        batch_hbtu_eq=Var(''),
        batch_hbtu_conc=Var(''),
        batch_nmm_eq=Var(''),
        batch_nmm_conc=Var(''),
        schedule_autosave=lambda: calls.__setitem__('autosave', calls['autosave'] + 1),
    )
    return gui, calls


def test_dic_hobt_button_updates_chemistry_without_generating_plan(monkeypatch):
    gui, calls = _fake_gui()
    chemistry_workflow.apply_dic_hobt(gui)

    assert gui.pm_chemistry.get() == 'DIC/HOBt'
    assert gui.default_reagent.get() == 'DIC'
    assert gui.default_catalyst.get() == 'HOBt'
    assert gui.default_coupling_solution_solvent.get() == 'DMF'
    assert calls['autosave'] == 1


def test_hbtu_nmm_button_updates_chemistry_without_generating_plan(monkeypatch):
    gui, calls = _fake_gui()
    chemistry_workflow.apply_hbtu_nmm(gui)

    assert gui.pm_chemistry.get() == 'HBTU/NMM'
    assert gui.default_reagent.get() == 'HBTU'
    assert gui.default_base.get() == 'NMM'
    assert gui.default_coupling_solution_solvent.get() == 'DMF'
    assert gui.batch_hbtu_eq.get() == '10'
    assert gui.batch_hbtu_conc.get() == '0.4'
    assert gui.batch_nmm_eq.get() == '5'
    assert gui.batch_nmm_conc.get() == '0.8'
    assert calls['autosave'] == 1
