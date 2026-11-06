from __future__ import annotations
from pathlib import Path
from types import SimpleNamespace

from suite_gui import data_system, experimental_data, experimental_workflow


def _item():
    return {"project":"P","peptide":"Pep","sequence":"ACDE","scale":"0.2","resin":"Rink Amide","loading":"0.8","selected_plan_rows":[],"selected_material_rows":[],"selected_total_rows":[],"selected_checklist_rows":[],"selected_cleavage_rows":[]}


def _gui(item, db):
    return SimpleNamespace(pm_items=[item], _v2097_active_index=0, experimental_db_path=db)


def test_matched_repeat_reports_real_yield_and_purity_delta(tmp_path: Path):
    item=_item(); first=data_system.ensure_hierarchy(item)
    data_system.start_active_run(item,{"sequence":"ACDE","resin":"Rink Amide","scale_mmol":0.2,"loading_target_mmol_g":0.8,"loading_aa_eq":2})
    data_system.finish_active_run(item)
    first_id=first["run_id"]
    repeat=data_system.repeat_active_run(item)
    repeat["planner_snapshot_v6"]={"sequence":"ACDE","resin":"Rink Amide","scale_mmol":0.2,"loading_target_mmol_g":0.8,"loading_aa_eq":3}
    db=tmp_path/'exp.sqlite'; gui=_gui(item,db)
    experimental_data.initialize(db)
    experimental_data.add_outcome({"stage":"cleavage","product":"Pep","sequence":"ACDE","run_id":first_id,"work_item_id":item.get('work_item_id',''),"yield_percent":50,"purity_percent":80,"result":"Completed"},db)
    experimental_data.add_outcome({"stage":"cleavage","product":"Pep","sequence":"ACDE","run_id":repeat['run_id'],"work_item_id":item.get('work_item_id',''),"yield_percent":62,"purity_percent":91,"result":"Completed"},db)
    out=experimental_workflow.matched_repeat_observation(gui,repeat['run_id'])
    assert out['available'] is True
    assert out['outcome_deltas']['yield_percentage_points']==12
    assert out['outcome_deltas']['purity_percentage_points']==11
    assert out['changed_variables']['loading_aa_eq']=={'parent':2,'repeat':3}
    assert out['causal_claim_allowed'] is False


def test_recommendation_result_links_preserve_operator_decision(tmp_path: Path):
    db=tmp_path/'x.sqlite'; experimental_data.initialize(db)
    tr=experimental_data.add_recommendation_trace({'work_item_id':'w','run_id':'r','recommendation_type':'Loading','operator_decision':'Applied as recommended','actual_condition':{'aa_eq':2},'recommended_condition':{'aa_eq':2},'apply_allowed':True},db)
    linked=experimental_data.link_recommendation_results(tr['trace_id'],['result-1','result-1','result-2'],db)
    assert linked['operator_decision']=='Applied as recommended'
    assert linked['actual_condition']=={'aa_eq':2}
    assert linked['final_result_links']==['result-1','result-2']


def test_frozen_run_theoretical_mass_comes_from_frozen_snapshot(tmp_path: Path):
    item=_item(); run=data_system.ensure_hierarchy(item)
    data_system.start_active_run(item,{"sequence":"ACDE","resin":"Rink Amide","scale_mmol":0.2,"loading_target_mmol_g":0.8})
    gui=_gui(item,tmp_path/'x.sqlite')
    mass=experimental_workflow.frozen_run_theoretical_mass(gui)
    assert mass['run_id']==run['run_id']
    assert mass['source']=='frozen Run Planner snapshot'
    assert float(mass['product_mw']) > 0
    assert float(mass['mh']) > float(mass['product_mw'])


def test_analytical_completeness_is_descriptive_not_auto_pass(tmp_path: Path):
    item=_item(); run=data_system.ensure_hierarchy(item)
    data_system.start_active_run(item,{"sequence":"ACDE","resin":"Rink Amide","scale_mmol":0.2,"loading_target_mmol_g":0.8})
    gui=_gui(item,tmp_path/'x.sqlite'); experimental_data.initialize(gui.experimental_db_path)
    incomplete=experimental_workflow.analytical_completeness(gui)
    assert incomplete['complete'] is False and len(incomplete['unresolved'])==3
    data_system.upsert_hplc(item,{'sample_name':'Final','purity_percent':90},reason='record')
    data_system.upsert_analytical(item,{'analytical_type':'LC-MS','observed_mz':500},reason='record')
    experimental_data.add_outcome({'stage':'cleavage','product':'Pep','sequence':'ACDE','run_id':run['run_id'],'yield_percent':60,'result':'Completed'},gui.experimental_db_path)
    complete=experimental_workflow.analytical_completeness(gui)
    assert complete['complete'] is True
    assert 'no automatic scientific pass/fail' in complete['note']
