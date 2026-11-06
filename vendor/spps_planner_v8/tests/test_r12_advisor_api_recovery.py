from __future__ import annotations
import csv
import os
from pathlib import Path
from types import SimpleNamespace
import pytest


def _reset():
    from suite_gui import experimental_data, experimental_workflow
    experimental_data._INITIALIZED_DB_PATHS.clear()
    experimental_workflow._SEEDED_DB_PATHS.clear()


def test_public_advisor_facades_exist_and_cleavage_fallback_works(tmp_path):
    from suite_gui.recommendation import loading, cleavage, coupling
    assert callable(loading.advise) and callable(loading.recommend)
    assert callable(cleavage.advise) and callable(cleavage.recommend)
    assert callable(coupling.advise)
    result=cleavage.advise(db_path=tmp_path/'empty.sqlite', product='demo', sequence='Ac-AAAAAA-NH2', resin='Rink Amide AM', scale_mmol=0.2, include_parsed=True)
    rec=result.get('recommended_condition') or {}
    assert rec.get('apply_allowed') is True
    assert float(rec.get('cleavage_eq')) == 30.0


def test_loading_no_history_uses_explicit_chemistry_default_not_fake_prediction(tmp_path):
    from suite_gui.recommendation import loading
    result=loading.advise(db_path=tmp_path/'empty.sqlite', resin='2-CTC', amino_acid='Fmoc-Gly-OH', target_loading_mmol_g=0.7, include_parsed=True)
    rec=result.get('target_recommendation') or {}
    assert rec.get('recommendation_kind') == 'CHEMISTRY DEFAULT'
    assert rec.get('aa_eq') == 2.0 and rec.get('base_eq') == 4.0
    assert rec.get('predicted_loading_mmol_g') is None
    assert 'not a prediction' in str(rec.get('basis')).lower()


def test_repeated_observed_condition_beats_interpolation_when_target_is_inside_measured_range(tmp_path):
    from suite_gui import experimental_data
    from suite_gui.recommendation import loading
    db=tmp_path/'exp.sqlite'
    for value in (0.654,0.669,0.727):
        experimental_data.add_record('loading', {'resin_type':'Trityl/2-CTC resin','amino_acid_raw':'Fmoc-Arg(Pbf)-OH','aa_eq':2,'base':'DIEA','base_eq':4,'loading_rate_mmol_g':value}, db, status='parsed')
    for value in (0.292,0.307):
        experimental_data.add_record('loading', {'resin_type':'Trityl/2-CTC resin','amino_acid_raw':'Fmoc-Arg(Pbf)-OH','aa_eq':0.35,'base':'DIEA','base_eq':2,'loading_rate_mmol_g':value}, db, status='parsed')
    result=loading.advise(db_path=db,resin='Trityl/2-CTC resin',amino_acid='Fmoc-Arg(Pbf)-OH',base_eq=4,target_loading_mmol_g=0.68,include_parsed=True)
    rec=result.get('target_recommendation') or {}
    assert rec.get('recommendation_kind') == 'OBSERVED REPEATED CONDITION'
    assert rec.get('apply_allowed') is True and float(rec.get('aa_eq')) == 2.0
    assert float(rec.get('expected_low_mmol_g')) <= 0.68 <= float(rec.get('expected_high_mmol_g'))


def test_loading_seed_revision_is_additive_not_duplicate(tmp_path):
    from suite_gui import experimental_data
    db=tmp_path/'exp.sqlite'
    fields=['status','date','resin_type','amino_acid_raw','amino_acid_normalized','aa_eq','base','base_eq','loading_rate_mmol_g','raw_note']
    p=tmp_path/'loading_history_seed.csv'
    def write(values):
        with p.open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
            for i,v in enumerate(values):
                w.writerow({'status':'parsed','date':f'2030-01-0{i+1}','resin_type':'2-CTC','amino_acid_raw':'Fmoc-Gly-OH','amino_acid_normalized':'Fmoc-Gly-OH','aa_eq':2,'base':'DIEA','base_eq':4,'loading_rate_mmol_g':v,'raw_note':'seed revision test'})
    write([0.5]); assert experimental_data.import_loading_csv(p,db)['inserted']==1
    write([0.5,0.6]); assert experimental_data.import_loading_csv(p,db)['inserted']==1
    assert len(experimental_data.list_records('loading',db))==2


@pytest.mark.skipif(not os.environ.get('DISPLAY'), reason='Tk GUI test requires DISPLAY')
def test_real_recommendations_window_loading_and_cleavage_buttons_do_not_raise_advise_attribute_error(monkeypatch,tmp_path):
    monkeypatch.setenv('HOME',str(tmp_path/'home')); monkeypatch.setenv('LOCALAPPDATA',str(tmp_path/'local')); monkeypatch.setenv('APPDATA',str(tmp_path/'appdata'))
    from suite_gui.classic_2094_tk_gui import SPPSGui
    from suite_gui.modules import experimental_data_panel as panel
    errors=[]
    monkeypatch.setattr(panel.messagebox,'showerror',lambda title,msg,**kw: errors.append((title,str(msg))))
    monkeypatch.setattr(SPPSGui,'_state_file_path',lambda self: tmp_path/'state.json',raising=False)
    gui=SPPSGui()
    try:
        gui.withdraw()
        win=panel.ExperimentalDataWindow(gui); win.withdraw(); gui.update()
        win.load_resin.set('2-CTC'); win.load_aa.set('Fmoc-Arg(Pbf)-OH'); win.load_target.set('0.68'); win.load_base_eq.set('4')
        win.run_loading_advisor()
        win.clv_sequence.set('Ac-EEMQRR-NH2'); win.clv_resin.set('Rink Amide AM'); win.clv_scale.set('0.2')
        win.run_cleavage_advisor(); gui.update()
        assert not [e for e in errors if "has no attribute 'advise'" in e[1]]
        assert 'Target loading' in win.load_result.get('1.0','end')
        # R16: operator shorthand for a data-supported special residue is normalized
        # to one explicit loaded-building-block identity; recognition itself is not
        # presented as experimental support.
        win.load_aa.set('Cit'); win.load_target.set('0.68'); win.run_loading_advisor(); gui.update()
        loading_text=win.load_result.get('1.0','end')
        assert 'Fmoc-Cit-OH' in loading_text
        assert 'recognition alone is not experimental support' in loading_text
        assert win.clv_result.get('1.0','end').strip()
        win.destroy()
    finally:
        gui.destroy()
