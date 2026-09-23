from __future__ import annotations
from pathlib import Path
from types import SimpleNamespace
import sqlite3

from spps_v4_gui import experimental_data, experimental_workflow, model_registry_v5


def _gui(db: Path):
    item={'peptide':'RunPep','sequence':'ACDE','scale':'0.2','resin':'2-CTC','loading':'0.35','loading_aa_eq':'0.4','loading_diea_eq':'2','loading_time_h':'4'}
    return SimpleNamespace(pm_items=[item], _v2097_active_index=0, experimental_db_path=db)


def test_fast_open_db_initialization_persists_lookup_backfill(tmp_path):
    db=tmp_path/'experimental.db'
    experimental_data._INITIALIZED_DB_PATHS.discard(str(db.resolve()))
    assert Path(experimental_data.initialize(db)) == db
    with sqlite3.connect(db) as con:
        value=con.execute("SELECT meta_value FROM experimental_meta WHERE meta_key='lookup_backfill_version'").fetchone()
    assert value and int(value[0]) == experimental_data._LOOKUP_BACKFILL_VERSION
    assert str(db.resolve()) in experimental_data._INITIALIZED_DB_PATHS
    assert experimental_data.initialize(db) == db
    assert experimental_data.list_records('loading', db) == []


def test_fast_open_records_share_project_manager_run_and_work_item(tmp_path):
    db=tmp_path/'exp.sqlite'; experimental_data.initialize(db); gui=_gui(db)
    loading=experimental_workflow.add_loading_record(gui, {'resin_type':'2-CTC','amino_acid_raw':'Fmoc-Glu(OtBu)-OH','aa_eq':0.4,'base_eq':2,'loading_time_h':4,'loading_rate_mmol_g':0.34}, status='verified')
    cleavage=experimental_workflow.add_cleavage_record(gui, {'product':'RunPep','sequence':'ACDE','scale_mmol':0.2,'cleavage_eq':100,'cleavage_time_h':3}, status='verified')
    outcome=experimental_workflow.add_outcome_record(gui, {'stage':'cleavage','product':'RunPep','sequence':'ACDE','result':'Success','success_flag':1}, status='verified')
    issue=experimental_workflow.add_issue_record(gui, {'stage':'Coupling','product':'RunPep','sequence':'ACDE','issue_type':'Incomplete coupling','observation':'Kaiser positive','parse_status':'human_reviewed'}, status='verified')
    assert len({x['run_id'] for x in [loading,cleavage,outcome,issue]}) == 1
    assert len({x['work_item_id'] for x in [loading,cleavage,outcome,issue]}) == 1


def test_fast_open_rebuild_notice_after_five_verified_results(tmp_path, monkeypatch):
    db=tmp_path/'exp.sqlite'; experimental_data.initialize(db)
    monkeypatch.setattr(model_registry_v5, 'loading_model_info', lambda: {'built':True,'active_model_id':'old','built_at':'2000-01-01T00:00:00+00:00'})
    for i in range(5):
        experimental_data.add_record('loading', {'resin_type':'2-CTC','amino_acid_raw':'Fmoc-Ile-OH','aa_eq':0.2+i*0.1,'base_eq':2,'loading_time_h':4,'loading_rate_mmol_g':0.2+i*0.02}, db, status='verified')
    status=model_registry_v5.loading_rebuild_status(db)
    assert status['active_model'] is True and status['new_verified_count']==5 and status['rebuild_ready'] is True and status['threshold']==5


def test_fast_open_ui_features_present_but_batch_lot_still_not_exposed():
    root=Path(__file__).resolve().parents[1]
    panel=(root/'spps_v4_gui/modules/experimental_data_panel.py').read_text(encoding='utf-8')
    ui=(root/'spps_v4_gui/ui_system.py').read_text(encoding='utf-8')
    main=(root/'spps_v4_gui/modern_tk_gui.py').read_text(encoding='utf-8')
    assert 'Save Measured' in panel and 'quick_measured_loading' in panel
    assert 'new measured results available for model rebuild' in panel
    assert 'def fit_window_to_content' in ui
    assert 'Batch Manager' not in main or 'unexposed' in main.lower()
