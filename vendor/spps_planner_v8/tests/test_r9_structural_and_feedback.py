from pathlib import Path
import json, zipfile
import pandas as pd
from suite_gui import data_system, experimental_data, run_package

def _item(): return {'project':'P','peptide':'Pep','sequence':'ACDE','selected_plan_rows':[],'selected_material_rows':[],'selected_total_rows':[],'selected_checklist_rows':[],'selected_cleavage_rows':[]}

def test_recommendation_trace_is_separate_from_training_records(tmp_path):
    db=tmp_path/'x.sqlite'; experimental_data.initialize(db)
    before=len(experimental_data.list_records('loading',db,statuses=['verified']))
    tr=experimental_data.add_recommendation_trace({'work_item_id':'w','run_id':'r','recommendation_type':'Loading','evidence_source':'bounded','confidence':'HIGH','evidence_count':4,'recommended_condition':{'aa_eq':2},'apply_allowed':True},db)
    experimental_data.resolve_recommendation_trace(tr['trace_id'],'Applied as recommended',actual_condition={'aa_eq':2},db_path=db)
    assert len(experimental_data.list_records('loading',db,statuses=['verified']))==before
    assert experimental_data.list_recommendation_traces(db,run_id='r')[0]['operator_decision']=='Applied as recommended'

def test_analytical_domain_does_not_infer_neutral_mass_from_mz(tmp_path):
    item=_item(); data_system.ensure_hierarchy(item)
    rec=data_system.upsert_analytical(item,{'analytical_type':'LC-MS','observed_mz':'500.2','charge':'2','adduct':'[M+2H]2+'},reason='record')
    assert rec.get('observed_mz')==500.2 and rec.get('observed_assigned_mass') is None
    assert data_system.list_analytical(item)[0]['analytical_result_id']==rec['analytical_result_id']

def test_repeat_does_not_copy_analytical_and_comparison_is_descriptive():
    item=_item(); first=data_system.ensure_hierarchy(item); data_system.upsert_analytical(item,{'analytical_type':'MALDI','observed_mz':1000},reason='record')
    data_system.start_active_run(item,{'resin':'Rink','scale_mmol':0.2}); data_system.finish_active_run(item)
    repeat=data_system.repeat_active_run(item); assert repeat.get('analytical_records',[])==[]
    out=data_system.matched_repeat_observation(item,repeat['run_id']); assert out['available'] and out['causal_claim_allowed'] is False

def test_run_package_has_analytical_and_recommendation_sheets(tmp_path):
    target=run_package.build_package({'run':{'run_id':'r'},'linked_records':{'analytical':[{'analytical_type':'LC-MS'}],'recommendation_traces':[{'recommendation_type':'Loading'}]}},tmp_path/'run.zip')
    with zipfile.ZipFile(target) as z:
        z.extract('RESULTS.xlsx',tmp_path)
    xls=pd.ExcelFile(tmp_path/'RESULTS.xlsx'); assert set(['Final outcomes','Loading','Cleavage','Analytical','Recommendation trace']).issubset(xls.sheet_names)

def test_release_ui_has_no_delayed_reassert():
    root=Path(__file__).resolve().parents[1]; text=(root/'suite_gui/modules/release_ui.py').read_text(encoding='utf-8')
    tail=text.split('def apply_post_build',1)[1]; assert 'after(100' not in tail and 'after(400' not in tail and 'after(1000' not in tail and 'after_idle' not in tail

def test_canonical_recommendation_does_not_import_versioned_v5_backend():
    root=Path(__file__).resolve().parents[1]
    for name in ('loading.py','cleavage.py','coupling.py'):
        text=(root/'suite_gui/recommendation'/name).read_text(encoding='utf-8'); assert 'ml_advisor_v5 as _backend' not in text and 'condition_optimizer_v5 as _backend' not in text
