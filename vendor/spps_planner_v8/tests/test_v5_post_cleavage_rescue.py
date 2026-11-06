from types import SimpleNamespace

from suite_gui.modules.cleavage_panel import post_cleavage_rescue_summary


class V:
    def __init__(self, value): self.value=str(value)
    def get(self): return self.value
    def set(self, value): self.value=str(value)


def _gui(rescue='NH4I Reduction', conc='0.2'):
    return SimpleNamespace(
        post_cleavage_rescue=V(rescue), nh4i_eq=V('2'), nh4i_concentration_m=V(conc), nh4i_time_h=V('1'),
        pm_scale=V('0.2'),
    )


def test_nh4i_rescue_is_separate_and_calculates_operator_protocol():
    info=post_cleavage_rescue_summary(_gui())
    assert info['enabled'] is True and info['valid'] is True
    assert info['nh4i_eq']==2.0
    assert info['concentration_m']==0.2
    assert info['time_h']==1.0
    assert abs(info['nh4i_mmol']-0.4)<1e-9
    assert abs(info['nh4i_mass_mg']-57.976)<1e-6
    assert abs(info['final_solution_ml']-2.0)<1e-9
    assert info['solvent']=='TFA / DW'


def test_nh4i_above_point_two_molar_is_invalid():
    info=post_cleavage_rescue_summary(_gui(conc='0.3'))
    assert info['enabled'] is True
    assert info['valid'] is False
    assert '0.2 M' in info['warning']


def test_default_rescue_is_none():
    info=post_cleavage_rescue_summary(_gui(rescue='None'))
    assert info['enabled'] is False
    assert info['rescue']=='None'
