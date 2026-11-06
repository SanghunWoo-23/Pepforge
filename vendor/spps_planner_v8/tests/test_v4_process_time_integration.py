from __future__ import annotations

from types import SimpleNamespace

from spps_planner.engine import PlanInput, generate_cleavage_cocktail, generate_step_reagent_plan
from suite_gui import peptide_item_state


class Var:
    def __init__(self, value=''):
        self.value = value
    def get(self):
        return self.value
    def set(self, value):
        self.value = value


def test_loading_time_is_first_class_but_does_not_change_stoichiometry():
    base = PlanInput(sequence='AEK', resin='2-CTC', scale_mmol=0.2, resin_loading_mmol_g=0.8,
                     apply_resin_loading=True, loading_aa_eq=2, loading_diea_eq=4)
    timed = PlanInput(sequence='AEK', resin='2-CTC', scale_mmol=0.2, resin_loading_mmol_g=0.8,
                      apply_resin_loading=True, loading_aa_eq=2, loading_diea_eq=4, loading_time_h=4)
    a = generate_step_reagent_plan(base).iloc[0]
    b = generate_step_reagent_plan(timed).iloc[0]
    assert a['planned_reagent_mmol'] == b['planned_reagent_mmol']
    assert 'time=4 h' in str(b['note'])
    assert 'time=' not in str(a['note'])


def test_cleavage_time_is_first_class_but_does_not_change_cocktail_amounts():
    base = PlanInput(sequence='AEK', resin='Amide', scale_mmol=0.2,
                     cleavage_preset='DEFAULT_TFA_TIS_WATER')
    timed = PlanInput(sequence='AEK', resin='Amide', scale_mmol=0.2,
                      cleavage_preset='DEFAULT_TFA_TIS_WATER', cleavage_time_h=3)
    a = generate_cleavage_cocktail(base)
    b = generate_cleavage_cocktail(timed)
    assert a['volume_mL'].tolist() == b['volume_mL'].tolist()
    tfa_note = str(b.loc[b['component'].eq('TFA'), 'note'].iloc[0])
    assert 'Cleavage time=3 h' in tfa_note
    assert 'Cleavage time=' not in str(a.loc[a['component'].eq('TFA'), 'note'].iloc[0])


def test_restore_remains_backward_compatible_when_legacy_gui_has_no_time_vars():
    class Adapter:
        @staticmethod
        def _write_rows(*args, **kwargs):
            return None
        @staticmethod
        def _clear_tree(*args, **kwargs):
            return None
        @staticmethod
        def _refresh_list_label(*args, **kwargs):
            return None

    class ListBox:
        def selection_clear(self, *args): pass
        def selection_set(self, *args): pass
        def activate(self, *args): pass

    gui = SimpleNamespace(
        pm_items=[{'project':'P','sequence':'AEK'}],
        pm_project=Var(), pm_peptide=Var(), pm_sequence=Var(), pm_scale=Var(), pm_resin=Var(),
        pm_loading=Var(), pm_lot=Var(), pm_chemistry=Var(), pm_copies=Var(), loading_aa_eq=Var(),
        loading_diea_eq=Var(), cleavage_preset=Var(), cleavage_eq_override=Var(),
        cleavage_components_text=Var(), apply_loading_calc=Var(False), pm_list=ListBox(),
        pm_selected_plan_tree=None, pm_selected_material_tree=None, pm_selected_total_tree=None,
        progress_tree=None, pm_cleavage_tree=None,
    )
    peptide_item_state.restore_item(
        gui, 0, Adapter, lambda obj, name, value: getattr(obj, name).set(value),
        lambda *args: None, {}, plan_columns=[], plan_widths={}, material_columns=[], material_widths={},
        total_columns=[], total_widths={}, check_columns=[], check_widths={}
    )
    assert gui.pm_sequence.get() == 'AEK'
