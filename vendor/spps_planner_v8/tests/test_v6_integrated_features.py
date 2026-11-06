from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from suite_gui import data_system, experimental_data, experimental_workflow, risk_engine
from suite_gui.v6_features import (
    analytics_snapshot, compare_scenarios, evidence_trace, execution_summary, record_quality_issues,
)


def _gui(db: Path):
    item={
        'peptide':'V6Pep','sequence':'QDIVVVFWMCN','scale':'0.2','resin':'2-CTC','loading':'0.35',
        'loading_aa_eq':'0.4','loading_diea_eq':'2','loading_time_h':'4','cleavage_time_h':'3',
        'selected_plan_rows':[{'No':'1','Unit name':'Loading','Repeat':'1'},{'No':'2','Unit name':'Coupling','Repeat':'1'}],
    }
    return SimpleNamespace(pm_items=[item], _v2097_active_index=0, experimental_db_path=db)


def test_v6_evidence_trace_and_no_extrapolation_label():
    trace=evidence_trace({'target_recommendation':{'recommendation_kind':'BOUNDED TARGET INTERPOLATION','evidence_count':7,'verified_evidence_count':6,'confidence':'HIGH','apply_allowed':True,'observed_aa_eq_min':0.2,'observed_aa_eq_max':0.8}})
    assert trace['source']=='Bounded interpolation'
    assert trace['confidence']=='HIGH' and trace['evidence_count']==7
    blocked=evidence_trace({'target_recommendation':{'recommendation_kind':'TARGET OUTSIDE OBSERVED RANGE','apply_allowed':False,'basis':'extrapolation disabled'}})
    assert blocked['source']=='Insufficient evidence' and blocked['apply_allowed'] is False
    assert 'extrapolation' in blocked['blocked_reason']


def test_v6_ab_compare_does_not_invent_cost():
    result=compare_scenarios({'coupling_eq':2,'coupling_repeats':1,'coupling_time_min':30,'cleavage_eq':50,'cleavage_time_h':3,'scale_mmol':0.2,'aa_steps':10}, {'coupling_eq':3,'coupling_repeats':2,'coupling_time_min':40,'cleavage_eq':60,'cleavage_time_h':3,'scale_mmol':0.2,'aa_steps':10})
    assert result['scenario_a']['estimated_cost'] is None
    assert result['scenario_b']['relative_reagent_burden'] > result['scenario_a']['relative_reagent_burden']
    assert result['delta_b_minus_a']['estimated_process_time_min'] > 0


def test_v6_risk_map_additions_are_warning_only():
    report=risk_engine.evaluate_rules({'sequence':'QDIVVVFWMCN','selected_plan_rows':[],'runs':[]})
    ids={row['rule_id'] for row in report['findings']}
    assert 'SEQ-NTERM-QE' in ids
    assert 'SEQ-DEAMIDATION-REVIEW' in ids
    assert 'SEQ-BETA-AGGREGATION-REVIEW' in ids
    assert 'no change is applied automatically' in report['disclaimer']


def test_v6_run_start_result_snapshot_and_lifecycle(tmp_path: Path):
    db=tmp_path/'v6.sqlite'; experimental_data.initialize(db)
    gui=_gui(db)
    started=experimental_workflow.start_experiment(gui)
    assert started['status']=='In Progress' and started['run_id']
    saved=experimental_workflow.add_outcome_record(gui, {'stage':'cleavage','product':'V6Pep','sequence':'QDIVVVFWMCN','result':'Success','success_flag':1,'yield_percent':88,'purity_percent':97,'record_state':'completed'}, status='verified')
    snapshot=json.loads(saved['planner_snapshot_json'])
    assert snapshot['sequence']=='QDIVVVFWMCN'
    assert saved['run_id']==started['run_id'] and saved['work_item_id']
    assert saved['record_state']=='completed'
    finished=experimental_workflow.finish_experiment(gui)
    assert finished['status']=='Completed' and finished['completed_at']


def test_v6_quality_and_analytics_small_sample_labels():
    outcomes=[{'record_id':'o1','sequence':'ACDE','stage':'cleavage','yield_percent':105,'purity_percent':97,'success_flag':1,'run_id':'r1','record_state':'verified'}]
    findings=record_quality_issues(outcome_rows=outcomes)
    assert any(row['code']=='PERCENT_RANGE' for row in findings)
    dash=analytics_snapshot(outcome_rows=outcomes)
    row=dash['yield_by_stage'][0]
    assert row['n']==1 and row['trend_ready'] is False
    assert 'n < 3' in dash['small_sample_note']


def test_v6_execution_summary_resume_point():
    item={'selected_plan_rows':[{'No':'1','Unit name':'A'},{'No':'2','Unit name':'B'}], 'synthesis_execution':{'events':[{'event_type':'step_status','step_no':'1','field':'status','after':'In Progress','timestamp':'2026-01-01T00:00:00Z'},{'event_type':'step_status','step_no':'1','field':'status','after':'Completed','timestamp':'2026-01-01T00:10:00Z'}]}}
    summary=execution_summary(item)
    assert summary['progress_percent']==50.0
    assert summary['resume_step']=='2'
    assert summary['steps'][0]['started_at'] and summary['steps'][0]['ended_at']


def test_v6_data_health_has_lifecycle_and_quality(tmp_path: Path):
    db=tmp_path/'health.sqlite'; experimental_data.initialize(db)
    experimental_data.add_outcome({'stage':'cleavage','sequence':'ACD','run_id':'r','work_item_id':'w','result':'Fail','success_flag':0,'yield_percent':20,'record_state':'failed_informative'},db,status='verified')
    health=experimental_data.data_health(db)
    assert health['record_state_counts']['outcome']['failed_informative']==1
    assert health['quality_findings_count'] >= 1  # failed-informative without a cause note


def test_v6_ui_surface_contains_integrated_features():
    root=Path(__file__).resolve().parents[1]
    panel=(root/'suite_gui/modules/experimental_data_panel.py').read_text(encoding='utf-8')
    work=(root/'suite_gui/work_item_window.py').read_text(encoding='utf-8')
    assert 'Compare A/B' in panel and 'Analytics' in panel and 'Sequence Risk Map' in panel
    assert 'Start Experiment' in panel and 'Failed + Informative' in panel
    assert 'Export Simple' in work and 'Export Detailed' in work and 'Resume' in work


def test_v6_gui_workflow_blocks_orphan_experimental_records(tmp_path: Path):
    db=tmp_path/'orphan.sqlite'; experimental_data.initialize(db)
    gui=SimpleNamespace(pm_items=[], _v2097_active_index=None, experimental_db_path=db)
    import pytest
    with pytest.raises(ValueError, match='prevents orphan'):
        experimental_workflow.add_outcome_record(gui, {'stage':'cleavage','sequence':'ACD','result':'Success'}, status='verified')


def test_v6_quality_detects_recorded_plan_actual_deviation():
    outcomes=[{
        'record_id':'o-dev','sequence':'ACD','stage':'coupling','run_id':'r1','record_state':'completed',
        'planner_snapshot_json':json.dumps({'sequence':'ACD','scale_mmol':0.2}),
        'actual_condition_json':json.dumps({'deviation_count':1,'deviations':[{'event_type':'plan_correction','field':'Repeat','before':1,'after':2}]})
    }]
    findings=record_quality_issues(outcome_rows=outcomes)
    assert any(row['code']=='PLAN_ACTUAL_DEVIATION_RECORDED' for row in findings)


def test_v6_analytics_tracks_repeat_history_coupling_and_sensitive_issues():
    snap=json.dumps({'selected_plan_rows':[{'Unit name':'Coupling','Repeat':'2'}]})
    outcomes=[
        {'sequence':'ACDE','stage':'final','success_flag':1,'yield_percent':80,'purity_percent':96,'planner_snapshot_json':snap,'created_at':'2026-09-01T00:00:00Z','run_id':'r1'},
        {'sequence':'ACDE','stage':'final','success_flag':0,'yield_percent':60,'purity_percent':88,'planner_snapshot_json':snap,'created_at':'2026-09-02T00:00:00Z','run_id':'r2'},
    ]
    issues=[{'stage':'cleavage','issue_type':'oxidation','observation':'Met oxidation observed','run_id':'r1'}]
    dash=analytics_snapshot(outcome_rows=outcomes, issue_rows=issues)
    assert dash['same_sequence_history'][0]['n']==2
    assert dash['outcome_by_coupling_repeats'][0]['group']=='2'
    assert dash['sensitive_issue_counts'][0]['group']=='Oxidation-related'
    assert dash['outcome_by_month'][0]['group']=='2026-09'


def test_v6_start_snapshot_is_immutable_and_repeated_start_is_idempotent(tmp_path: Path):
    db=tmp_path/'freeze.sqlite'; experimental_data.initialize(db)
    gui=_gui(db)
    first=experimental_workflow.start_experiment(gui)
    frozen_first=json.loads(json.dumps(gui.pm_items[0]['runs'][0]['planner_snapshot_v6']))
    assert frozen_first['sequence']=='QDIVVVFWMCN'
    gui.pm_items[0]['sequence']='ACDE'
    second=experimental_workflow.start_experiment(gui)
    frozen_second=gui.pm_items[0]['runs'][0]['planner_snapshot_v6']
    assert second['already_started'] is True
    assert second['started_at']==first['started_at']
    assert frozen_second==frozen_first
    assert experimental_workflow.planner_snapshot(gui)['sequence']=='QDIVVVFWMCN'
    actual=experimental_workflow.actual_condition_snapshot(gui)
    assert actual['planner_change_count'] >= 1
    assert any(row['field']=='sequence' for row in actual['planner_changes_since_start'])


def test_v6_finish_requires_start_and_terminal_run_cannot_restart(tmp_path: Path):
    import pytest
    db=tmp_path/'lifecycle.sqlite'; experimental_data.initialize(db)
    gui=_gui(db)
    with pytest.raises(ValueError, match='Start the active Run'):
        experimental_workflow.finish_experiment(gui)
    experimental_workflow.start_experiment(gui)
    first_finish=experimental_workflow.finish_experiment(gui)
    second_finish=experimental_workflow.finish_experiment(gui)
    assert second_finish['already_finished'] is True
    assert second_finish['completed_at']==first_finish['completed_at']
    with pytest.raises(ValueError, match='Create a new synthesis Run'):
        experimental_workflow.start_experiment(gui)


def test_v6_detailed_run_export_contains_frozen_plan_actual_context_and_linked_records(tmp_path: Path):
    db=tmp_path/'export.sqlite'; experimental_data.initialize(db)
    gui=_gui(db)
    experimental_workflow.start_experiment(gui)
    experimental_workflow.add_outcome_record(gui, {
        'stage':'final','product':'V6Pep','sequence':'QDIVVVFWMCN','result':'Success',
        'success_flag':1,'yield_percent':82,'purity_percent':96,'record_state':'completed',
    }, status='verified')
    simple=experimental_workflow.run_export_payload(gui, detailed=False)
    detailed=experimental_workflow.run_export_payload(gui, detailed=True)
    assert simple['format']=='simple' and 'planner_snapshot_frozen' not in simple
    assert detailed['format']=='detailed'
    assert detailed['planner_snapshot_frozen']['sequence']=='QDIVVVFWMCN'
    assert 'actual_condition' in detailed and 'steps' in detailed['execution']
    assert len(detailed['linked_records']['outcomes'])==1
    assert detailed['linked_records']['outcomes'][0]['purity_percent']==96.0


def test_v6_data_health_separates_post_start_planner_edits_from_actual_execution(tmp_path: Path):
    db=tmp_path/'planner_edit.sqlite'; experimental_data.initialize(db)
    gui=_gui(db)
    experimental_workflow.start_experiment(gui)
    gui.pm_items[0]['scale']='0.3'
    saved=experimental_workflow.add_outcome_record(gui, {
        'stage':'final','product':'V6Pep','sequence':'QDIVVVFWMCN','result':'Recorded',
        'record_state':'completed',
    }, status='verified')
    actual=json.loads(saved['actual_condition_json'])
    assert actual['planner_change_count'] >= 1
    findings=record_quality_issues(outcome_rows=[saved])
    assert any(row['code']=='PLANNER_CHANGED_AFTER_START' for row in findings)


def test_v6_run_ui_state_guides_operator_actions(tmp_path: Path):
    db=tmp_path/'ui_state.sqlite'; experimental_data.initialize(db)
    gui=_gui(db)
    before=experimental_workflow.run_ui_state(gui)
    assert before['can_start'] is True
    assert before['can_finish'] is False
    assert before['can_record_result'] is False
    assert before['can_create_new_run'] is True

    experimental_workflow.start_experiment(gui)
    active=experimental_workflow.run_ui_state(gui)
    assert active['status']=='In Progress'
    assert active['can_start'] is False and active['can_finish'] is True
    assert active['can_record_result'] is True and active['can_record_issue'] is True
    assert active['can_create_new_run'] is False

    experimental_workflow.finish_experiment(gui)
    done=experimental_workflow.run_ui_state(gui)
    assert done['finished'] is True
    assert done['can_start'] is False and done['can_finish'] is False
    assert done['can_create_new_run'] is True
    # Bench measurements/issues may be entered later, but remain linked to the frozen Run.
    assert done['can_record_result'] is True and done['can_record_issue'] is True


def test_v6_new_run_cannot_silently_abandon_in_progress_experiment(tmp_path: Path):
    import pytest
    db=tmp_path/'new_run_guard.sqlite'; experimental_data.initialize(db)
    gui=_gui(db)
    experimental_workflow.start_experiment(gui)
    item=gui.pm_items[0]
    with pytest.raises(ValueError, match='Finish the active experiment'):
        data_system.new_run(item, 'Repeat synthesis')
    experimental_workflow.finish_experiment(gui)
    second=data_system.new_run(item, 'Repeat synthesis')
    assert second['run_id'] != item['runs'][0]['run_id']
    assert item['active_run_id']==second['run_id']


def test_v6_issue_dialog_has_one_note_editor_and_run_aware_quick_actions():
    root=Path(__file__).resolve().parents[1]
    panel=(root/'suite_gui/modules/experimental_data_panel.py').read_text(encoding='utf-8')
    work=(root/'suite_gui/work_item_window.py').read_text(encoding='utf-8')
    assert panel.count('observation=tk.Text(note_card,height=9,wrap="word",font=("Segoe UI",11))') == 1
    assert 'run_context_var' in panel and 'Final Result' in panel
    assert 'can_record_result' in panel and 'can_record_issue' in panel
    assert 'self.new_run_button' in work and 'self.final_result_button' in work
