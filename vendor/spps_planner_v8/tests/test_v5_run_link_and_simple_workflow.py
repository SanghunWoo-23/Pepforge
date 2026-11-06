from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from suite_gui import experimental_data, experimental_workflow, model_registry_v5


def _gui(db: Path):
    item={
        'peptide':'RunPep','sequence':'ACDE','scale':'0.2','resin':'2-CTC','loading':'0.35',
        'loading_aa_eq':'0.4','loading_diea_eq':'2','loading_time_h':'4',
    }
    return SimpleNamespace(pm_items=[item], _v2097_active_index=0, experimental_db_path=db)


def test_result_issue_cleavage_and_outcome_share_active_run_id(tmp_path: Path):
    db=tmp_path/'exp.sqlite'; experimental_data.initialize(db)
    gui=_gui(db)
    loading=experimental_workflow.add_loading_record(gui, {
        'resin_type':'2-CTC','amino_acid_raw':'Fmoc-Glu(OtBu)-OH','aa_eq':0.4,'base_eq':2,
        'loading_time_h':4,'loading_rate_mmol_g':0.34,
    }, status='verified')
    cleavage=experimental_workflow.add_cleavage_record(gui, {
        'product':'RunPep','sequence':'ACDE','scale_mmol':0.2,'cleavage_eq':100,'cleavage_time_h':3,
    }, status='verified')
    outcome=experimental_workflow.add_outcome_record(gui, {
        'stage':'cleavage','product':'RunPep','sequence':'ACDE','result':'Success','success_flag':1,
    }, status='verified')
    issue=experimental_workflow.add_issue_record(gui, {
        'stage':'Coupling','product':'RunPep','sequence':'ACDE','issue_type':'Incomplete coupling',
        'observation':'Kaiser positive','parse_status':'human_reviewed',
    }, status='verified')
    run_ids={loading['run_id'],cleavage['run_id'],outcome['run_id'],issue['run_id']}
    work_ids={loading['work_item_id'],cleavage['work_item_id'],outcome['work_item_id'],issue['work_item_id']}
    assert len(run_ids)==1 and next(iter(run_ids))
    assert len(work_ids)==1 and next(iter(work_ids))


def test_loading_rebuild_notice_becomes_ready_after_five_new_verified_results(tmp_path: Path, monkeypatch):
    db=tmp_path/'exp.sqlite'; experimental_data.initialize(db)
    monkeypatch.setattr(model_registry_v5, 'loading_model_info', lambda: {
        'built':True,'active_model_id':'old','built_at':'2000-01-01T00:00:00+00:00'
    })
    for i in range(5):
        experimental_data.add_record('loading', {
            'resin_type':'2-CTC','amino_acid_raw':'Fmoc-Ile-OH','aa_eq':0.2+i*0.1,
            'base_eq':2,'loading_time_h':4,'loading_rate_mmol_g':0.2+i*0.02,
        }, db, status='verified')
    status=model_registry_v5.loading_rebuild_status(db)
    assert status['active_model'] is True
    assert status['new_verified_count']==5
    assert status['rebuild_ready'] is True
    assert status['threshold']==5


def test_simple_ui_has_inline_measured_loading_and_content_fit_helper():
    root=Path(__file__).resolve().parents[1]
    panel=(root/'suite_gui/modules/experimental_data_panel.py').read_text(encoding='utf-8')
    ui=(root/'suite_gui/ui_system.py').read_text(encoding='utf-8')
    assert 'Save Measured' in panel
    assert 'quick_measured_loading' in panel
    assert 'new measured results available for model rebuild' in panel
    assert 'fit_window_to_content' in panel
    assert 'def fit_window_to_content' in ui
