from __future__ import annotations
import json
from pathlib import Path
import pandas as pd

from peptiforg_core.protonation_sensitivity import protonation_sensitivity_report
from peptiforg_core.evidence_provenance import evidence_record, dependency_audit
from peptiforg_core.interface_quality import interface_quality_evidence
from peptiforg_core.hotspot_design_transfer import build_hotspot_chemistry_profile
from spps_v4_gui.aggregation_evidence_v5 import literature_aggregation_evidence
from spps_v4_gui.decision_support_v5 import sequence_difficulty_map, stage_risk_advisor


def test_protonation_report_is_review_flag_not_pka_or_probability():
    rep=protonation_sensitivity_report('Ac-EHKK-NH2')
    text=json.dumps(rep).lower()
    assert rep['status']=='review_recommended'
    assert rep['histidine_present'] is True
    assert 'pka' in text and 'does not infer' in text
    assert 'probability' in text
    assert 'pka_value' not in rep


def test_spps_aggregation_evidence_is_limited_and_never_auto_applied():
    rep=literature_aggregation_evidence('SVITST-NH2')
    assert rep['status']=='available'
    assert rep['composition_fraction_S_V_I_T'] > 0.5
    assert rep['automatic_plan_change_allowed'] is False
    text=json.dumps(rep).lower()
    assert 'probability' in text and 'no aggregation probability' in text
    diff=sequence_difficulty_map('SVITST-NH2')
    assert diff['literature_aggregation_evidence']['automatic_plan_change_allowed'] is False
    risk=stage_risk_advisor(sequence='SVITST-NH2', resin='Rink Amide')
    assert risk['literature_aggregation_evidence']['status']=='available'
    assert risk['apply_allowed'] is False


def test_evidence_dependency_audit_does_not_promote_same_source_to_independent():
    rows=[
        evidence_record(name='guided',role='selection_driving',kind='calculated',source_id='same',status='available'),
        evidence_record(name='challenge',role='independent',kind='calculated',source_id='same',status='available'),
    ]
    audit=dependency_audit(rows)
    assert audit['shared_source_ids']==['same']
    assert 'not counted as independent validation' in audit['policy']


def _atom(atom,resn,chain,resi,x,y,z,element):
    return {'atom':atom,'resn':resn,'chain':chain,'resi':str(resi),'x':x,'y':y,'z':z,'element':element,'aa':'K' if resn=='LYS' else 'D'}


def test_interface_quality_reports_separate_descriptors_without_fake_shape_score():
    target=pd.DataFrame([
        _atom('NZ','LYS','A',1,0,0,0,'N'), _atom('CA','LYS','A',1,-1.3,0,0,'C'),
    ])
    peptide=pd.DataFrame([
        _atom('OD1','ASP','B',1,3.0,0,0,'O'), _atom('CA','ASP','B',1,4.3,0,0,'C'),
    ])
    rep=interface_quality_evidence(target,peptide,sphere_points=32)
    assert rep['status']=='available'
    assert rep['approx_interface_area_half_delta_SASA_A2'] >= 0
    assert rep['shape_complementarity']['status']=='not_computed'
    low=json.dumps(rep).lower()
    assert 'affinity' in low and 'binding free energy' in low


def test_hotspot_beta_edge_opportunity_is_report_only():
    rows=[{'sequence':'V','hotspot_score':2,'record_name':'target','region_start':10,'region_end':10,
           'secondary_structure':'E','beta_edge_candidate':'True','beta_edge_evidence':'DSSP_E'}]
    rep=build_hotspot_chemistry_profile(rows)
    opp=rep['structure_opportunities']
    assert opp['beta_edge_candidate_count']==1
    assert opp['selection_active'] is False
    assert 'not a binding-site' in opp['claim_guard']


def test_launcher_panel_contract_and_ui_compliance_static():
    root=Path(__file__).resolve().parents[1]
    launcher=(root/'main_launcher.py').read_text(encoding='utf-8')
    assert 'LAUNCHER_SIDEBAR_WIDTH' in launcher and 'LAUNCHER_CONTEXT_WIDTH' in launcher
    assert 'selected_tool_name' in launcher
    assert 'grid_propagate(False)' in launcher
    workflow=(root/'peptiforg_core/workflow_gui.py').read_text(encoding='utf-8')
    external=(root/'suite_gui/external_tools_guide.py').read_text(encoding='utf-8')
    for src in (workflow,external):
        assert 'apply_pepforge_theme' in src and 'fit_window' in src and 'set_pepforge_icon' in src


def test_fast_open_uses_lazy_heavy_backends():
    root=Path(__file__).resolve().parents[1]
    structure=(root/'suite_gui/pymol_structure_builder_gui.py').read_text(encoding='utf-8')
    top='\n'.join(structure.splitlines()[:70])
    assert 'from peptiforg_core.trajectory_analyzer import analyze_trajectories' not in top
    assert 'from peptiforg_core.structure_consensus import compare_structures' not in top
    assert 'structure_file_backend_ready' in structure and 'structure_consensus_backend_ready' in structure
    assert 'text="Analyze Trajectory"' not in structure
    hotspot=(root/'suite_gui/hotspot_gui.py').read_text(encoding='utf-8')
    assert 'from sequence_hotspot_finder.engine import analyze_input, load_config' not in '\n'.join(hotspot.splitlines()[:35])
    assert 'hotspot_backend_ready' in hotspot
    assert 'structure_generation_backend_load_start' in structure
    assert 'structure_generation_backend_ready' in structure


def test_pde_beta_edge_metadata_is_report_only_and_desktop_colab_parity():
    root=Path(__file__).resolve().parents[1]
    desktop=(root/'apps/peptide_design_engine/Python/peptide_engine.py').read_text(encoding='utf-8')
    assert 'target_beta_edge_evidence_selection_active": False' in desktop
    assert (root/'apps/peptide_design_engine/Python/peptide_engine.py').read_bytes()==(root/'apps/peptide_design_engine/Colab/Ultimate_Peptide_Final_Engine.py').read_bytes()


def test_spps_aggregation_literature_domain_keeps_d_aa_out_of_canonical_model():
    rep = literature_aggregation_evidence('dS-V-Q-L-NH2')
    assert rep['modified_or_unresolved_core_count'] >= 1
    assert rep['canonical_residue_count'] == 3
    assert all(row['residue'] != 'S' for row in rep['AFPS_primary_associated_positions'])
    assert {row['residue'] for row in rep['AFPS_secondary_associated_positions']} == {'Q', 'L'}
    assert rep['literature_resin_side_5_to_15_window_count'] >= 0
    text = json.dumps(rep).lower()
    assert 'silently converted' in text
    assert 'canonical-l peptide study' in text


def test_dependency_audit_requires_independent_role_to_be_dependency_free_and_source_distinct():
    rows = [
        evidence_record(name='selection', role='selection_driving', kind='heuristic', source_id='selection_source', status='available'),
        evidence_record(name='dependent external-looking metric', role='independent', kind='calculated', source_id='metric_source', status='available', depends_on=['selection_source']),
        evidence_record(name='orthogonal record', role='independent', kind='measured', source_id='orthogonal_source', status='available'),
    ]
    audit = dependency_audit(rows)
    assert audit['dependency_limited_independent_source_ids'] == ['metric_source']
    assert audit['orthogonal_independent_source_ids'] == ['orthogonal_source']
    assert audit['orthogonal_independent_source_count'] == 1


def test_interface_quality_hotspot_coverage_is_optional_geometric_descriptor_only():
    target = pd.DataFrame([
        _atom('NZ','LYS','A',1,0,0,0,'N'), _atom('CA','LYS','A',1,-1.3,0,0,'C'),
        _atom('CA','LYS','A',2,20,0,0,'C'),
    ])
    peptide = pd.DataFrame([
        _atom('OD1','ASP','B',1,3.0,0,0,'O'), _atom('CA','ASP','B',1,4.3,0,0,'C'),
    ])
    rep = interface_quality_evidence(target, peptide, sphere_points=32, target_hotspot_residues=['A:1LYS','A:2LYS'])
    cov = rep['hotspot_coverage']
    assert cov['status'] == 'available'
    assert cov['input_hotspot_count'] == 2
    assert cov['interface_hotspot_count'] == 1
    assert cov['coverage_fraction'] == 0.5
    assert 'not hotspot validation' in cov['claim_guard'].lower()


def test_fast_open_structure_package_facade_does_not_eagerly_import_rdkit_static():
    root = Path(__file__).resolve().parents[1]
    facade = (root/'pepforge_structure_tool/__init__.py').read_text(encoding='utf-8')
    assert '__getattr__' in facade
    assert 'from .pepforge_core import' not in facade
    structure = (root/'suite_gui/pymol_structure_builder_gui.py').read_text(encoding='utf-8')
    import ast
    tree = ast.parse(structure)
    top_imports = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            top_imports.append(node.module or '')
        elif isinstance(node, ast.Import):
            top_imports.extend(alias.name for alias in node.names)
    assert 'peptiforg_core.pymol_structure_builder' not in top_imports
    assert 'peptiforg_core.low_spec_validation_bridge' not in top_imports
    assert '_structure_api()' in structure


def test_pde_and_spps_use_common_startup_visibility_instrumentation():
    root = Path(__file__).resolve().parents[1]
    pde = (root/'apps/peptide_design_engine/Python/desktop_gui.py').read_text(encoding='utf-8')
    spps = (root/'suite_gui/spps_tk_gui.py').read_text(encoding='utf-8')
    assert 'apply_pepforge_theme, fit_window, BACKGROUND' in pde
    assert 'StartupTrace' in pde and 'mark_window_visible(self, self._startup_trace)' in pde
    assert 'StartupTrace' in spps and 'mark_window_visible(self, self._startup_trace)' in spps


def test_blind_candidate_review_hides_identity_without_changing_evidence_axes():
    from peptiforg_core.candidate_evidence_matrix import build_blind_review_matrix
    summary = {
        'candidate_id':'PF-CAND-123', 'sequence':'AAAA',
        'design_intent':{'mode':'STRUCTURE_GUIDED','preferred_structure':'ALPHA_HELIX'},
        'structure':{'status':'available','requested_family_match_count':3},
        'stage_status':{'SPPS':'not_available','Docking':'not_available','Trajectory':'not_available','Experimental':'not_available'},
        'evidence_role_counts':{'selection_driving':2,'contradictory':1},
        'evidence_dependency_audit':{'orthogonal_independent_source_count':0},
    }
    payload = build_blind_review_matrix([summary], hide_sequence=True)
    row = payload['rows'][0]
    assert row['candidate_id'] == 'hidden_for_blind_review'
    assert row['sequence'] == 'hidden_for_blind_review'
    assert row['psb_requested_family_valid'] == 3
    assert payload['reveal_mapping'][0]['candidate_id'] == 'PF-CAND-123'
    assert 'no aggregate winner score' in payload['policy'].lower()


def test_integrated_spps_legacy_views_use_responsive_window_sizing_not_fixed_geometry():
    root=Path(__file__).resolve().parents[1]
    classic=(root/'spps_v4_gui/classic_base.py').read_text(encoding='utf-8')
    modern=(root/'spps_v4_gui/modern_tk_gui.py').read_text(encoding='utf-8')
    assert 'ui_system.fit_window(self' in classic
    assert 'ui_system.fit_window(self' in modern
    assert "self.geometry('1920x1080')" not in classic
    assert 'self.geometry("1360x820")' not in modern


def test_spps_aggregation_domain_status_distinguishes_partial_and_full_out_of_domain():
    partial = literature_aggregation_evidence('dS-V-Q-L-NH2')
    assert partial['status'] == 'partial_out_of_domain'
    assert partial['canonical_residue_count'] == 3
    assert partial['out_of_domain_core_count'] == 1
    assert partial['canonical_subset_fraction_of_core'] == 0.75
    assert partial['composition_fraction_S_V_I_T'] == round(1 / 3, 4)
    assert 'canonical-l subset' in partial['domain_interpretation'].lower()

    outside = literature_aggregation_evidence('dS-dV-dI-NH2')
    assert outside['status'] == 'out_of_domain'
    assert outside['canonical_residue_count'] == 0
    assert outside['out_of_domain_core_count'] == 3
    assert outside['composition_fraction_S_V_I_T'] is None
    assert outside['canonical_subset_fraction_of_core'] == 0.0


def test_candidate_matrix_preserves_aggregation_domain_counts_without_winner_score():
    from peptiforg_core.candidate_evidence_matrix import row_from_summary
    aggregation = literature_aggregation_evidence('dS-V-Q-L-NH2')
    row = row_from_summary({'candidate_id':'C1','sequence':'dS-V-Q-L-NH2','spps_literature_aggregation_evidence':aggregation})
    assert row['spps_aggregation_literature_status'] == 'partial_out_of_domain'
    assert row['spps_aggregation_canonical_residue_count'] == 3
    assert row['spps_aggregation_out_of_domain_core_count'] == 1
    assert row['spps_aggregation_canonical_subset_fraction'] == 0.75
    assert row['comparison_policy'] == 'separate_evidence_axes_no_aggregate_affinity_score'
    assert 'winner' not in row


def test_gui_import_surfaces_do_not_require_heavy_scientific_stack(tmp_path):
    import os
    import subprocess
    import sys
    root = Path(__file__).resolve().parents[1]
    script = (
        "import sys, sysconfig, importlib; "
        "purelib=sysconfig.get_paths().get('purelib'); platlib=sysconfig.get_paths().get('platlib'); "
        "[sys.path.append(p) for p in (purelib,platlib) if p and p not in sys.path]; "
        "mods=['main_launcher','suite_gui.hotspot_gui','apps.peptide_design_engine.Python.desktop_gui',"
        "'suite_gui.pymol_structure_builder_gui','suite_gui.spps_tk_gui','suite_gui.docking_workbench_gui',"
        "'suite_gui.external_tools_guide','peptiforg_core.workflow_gui']; "
        "[importlib.import_module(m) for m in mods]; "
        "heavy=['pandas','numpy','openpyxl','sklearn','rdkit','MDAnalysis','mdtraj']; "
        "bad=[m for m in heavy if m in sys.modules]; "
        "assert not bad, bad"
    )
    completed = subprocess.run(
        [sys.executable, '-S', '-c', script], cwd=root, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
    )
    assert completed.returncode == 0, completed.stderr

    output = tmp_path / 'external-output-must-not-exist-on-import'
    env = os.environ.copy(); env['PEPFORGE_OUTPUT_DIR'] = str(output)
    completed = subprocess.run(
        [sys.executable, '-c', 'import suite_gui.external_tools_guide'], cwd=root,
        env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    assert not output.exists()


def test_spps_recent_project_and_cterm_mapping_regressions_are_fixed():
    root = Path(__file__).resolve().parents[1]
    menu = (root/'spps_v4_gui/v3_menu.py').read_text(encoding='utf-8')
    panel = (root/'spps_v4_gui/modules/experimental_data_panel.py').read_text(encoding='utf-8')
    assert 'from spps_v4_gui import ui_system' in '\n'.join(menu.splitlines()[:12])
    assert 'AA_BOTTLE_NAME' not in panel
    assert 'AA_REAGENT_NAMES' in panel


def test_startup_window_visible_marker_is_idempotent(tmp_path):
    from peptiforg_core.startup_runtime import StartupTrace, mark_window_visible
    class FakeWindow:
        def __init__(self): self.calls = 0
        def update_idletasks(self): self.calls += 1
    trace = StartupTrace('fake', tmp_path)
    window = FakeWindow()
    mark_window_visible(window, trace)
    mark_window_visible(window, trace)
    assert [row['event'] for row in trace.events].count('first_window_visible') == 1
    assert window.calls == 1
