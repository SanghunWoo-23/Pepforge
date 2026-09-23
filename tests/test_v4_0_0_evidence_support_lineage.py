from __future__ import annotations
import json
from pathlib import Path

from peptiforg_core.modified_peptide_support import build_support_matrix, export_support_matrix
from peptiforg_core.docking_lineage import lineage_record, export_lineage
from peptiforg_core.candidate_evidence_matrix import build_candidate_evidence_matrix, export_candidate_evidence_matrix
from peptiforg_core.simulation_protocol import build_simulation_protocol
from peptiforg_core.hotspot_design_transfer import build_hotspot_chemistry_profile, export_hotspot_chemistry_profile


def test_modified_support_does_not_silently_claim_canonical_for_aib_or_d_residue(tmp_path):
    payload=build_support_matrix('Ac-dK-Aib-R-NH2')
    text=json.dumps(payload)
    assert 'Aib' in text and 'dK' in text
    rows={r['token']:r for r in payload['tokens']}
    for token in ['Aib','dK']:
        if token in rows:
            assert rows[token]['PDE'] != 'supported_canonical_evidence'
    paths=export_support_matrix('Ac-dK-Aib-R-NH2', tmp_path)
    assert Path(paths['support_json']).exists() and Path(paths['support_csv']).exists()


def test_v4_docking_lineage_prepares_pymol_review_but_does_not_claim_execution(tmp_path):
    rec=lineage_record('PF-CAND-001', 'ACDE', conformer_rank=3, pose_rank=2, pose_path='pose_02.pdb')
    assert rec['psb_structure_id'].endswith('/PSB-R03') and rec['pose_id'].endswith('/DOCK-P02')
    paths=export_lineage([rec], tmp_path)
    pml=Path(paths['pymol_review_pml']).read_text(encoding='utf-8')
    assert 'pose_02.pdb' in pml
    payload=json.loads(Path(paths['lineage_json']).read_text(encoding='utf-8'))
    assert 'actual docking engine' in payload['claim_guard'].lower() or 'actual docking' in payload['claim_guard'].lower()


def test_candidate_evidence_matrix_keeps_axes_separate(tmp_path):
    summary={'candidate_id':'PF-CAND-001','sequence':'ACDE','design_intent':{'mode':'BALANCED','preferred_structure':'ALPHA_HELIX','conformational_strategy':'ADAPTIVE'},'structure':{'status':'available','requested_family_match_count':3},'spps':{'status':'available'},'stage_status':{'PDE':'available','PSB':'available','SPPS':'available','Docking':'not_available','Trajectory':'not_available','Experimental':'not_available'},'provenance':{'PDE':'heuristic','PSB':'calculated','SPPS':'planning'}}
    rows=build_candidate_evidence_matrix([summary])
    assert rows[0]['comparison_policy']=='separate_evidence_axes_no_aggregate_affinity_score'
    assert 'score' not in {k.lower() for k in rows[0]}
    paths=export_candidate_evidence_matrix([summary], tmp_path)
    assert Path(paths['json']).exists() and Path(paths['csv']).exists()


def test_conformational_strategy_changes_start_state_plan_without_claiming_md_execution():
    pre=build_simulation_protocol('ACDEFG', preferred_structure='ALPHA_HELIX', conformational_strategy='PREORGANIZED')
    flex=build_simulation_protocol('ACDEFG', preferred_structure='ALPHA_HELIX', conformational_strategy='FLEXIBLE')
    assert pre['start_state_plan'][0]['state']=='requested_structure_psb'
    assert flex['start_state_plan'][0]['state']=='best_clash_free_psb'
    assert 'Protocol planning only' in pre['claim_guard']


def test_hotspot_profile_is_sequence_chemistry_evidence_not_3d_contact(tmp_path):
    rows=[{'sequence':'DDEF','hotspot_score':2.0,'region_start':1,'region_end':4},{'sequence':'WYKR','hotspot_score':1.0,'region_start':9,'region_end':12}]
    payload=build_hotspot_chemistry_profile(rows)
    assert payload['status']=='available' and payload['chemistry_fractions']['acidic']>0
    assert 'not a 3D contact map' in payload['claim_guard']
    paths=export_hotspot_chemistry_profile(rows, tmp_path)
    assert Path(paths['profile_json']).exists() and Path(paths['profile_csv']).exists()


def test_workflow_exports_hotspot_profile_and_candidate_matrix_controls():
    root=Path(__file__).resolve().parents[1]
    src=(root/'peptiforg_core/workflow_gui.py').read_text(encoding='utf-8')
    bridge=(root/'peptiforg_core/hotspot_workflow_bridge.py').read_text(encoding='utf-8')
    assert 'write_design_handoff' in src
    assert 'hotspot_chemistry_profile_json' in bridge
    assert 'Export Candidate Evidence Matrix' in src
    assert 'pymol_docking_review_pml' in src


def test_docking_workbench_exports_specific_interaction_evidence_profiles():
    root=Path(__file__).resolve().parents[1]
    src=(root/'suite_gui/docking_workbench_gui.py').read_text(encoding='utf-8')
    assert 'docking_specific_interaction_evidence' in src
    assert 'interaction_evidence_profiles' in src
    assert 'CONSERVATIVE_MANUAL' in src
    # Existing coarse screening remains for backward compatibility rather than
    # being silently reinterpreted as the new geometry-aware evidence table.
    assert 'docking_atom_contact_report' in src


def test_structure_consensus_v2_reports_contact_map_and_hotspot_local_rmsd(tmp_path):
    import pytest, numpy as np
    mdtraj=pytest.importorskip('mdtraj')
    from peptiforg_core.structure_consensus import compare_structures
    topology=mdtraj.Topology(); chain=topology.add_chain(); xyz=[]
    for i,name in enumerate(['ALA','GLY','LEU','SER','VAL']):
        res=topology.add_residue(name,chain,resSeq=i+1)
        for atom_name, element, offset in [('N',mdtraj.element.nitrogen,0.0),('CA',mdtraj.element.carbon,0.12),('C',mdtraj.element.carbon,0.24),('O',mdtraj.element.oxygen,0.32)]:
            topology.add_atom(atom_name,element,res); xyz.append([i*0.35+offset,0.0,0.0])
    base=np.asarray(xyz,dtype=np.float32)
    a=tmp_path/'a.pdb'; b=tmp_path/'b.pdb'
    mdtraj.Trajectory(base[None,:,:],topology).save_pdb(str(a))
    shifted=base.copy(); shifted[4:8,1]+=0.02
    mdtraj.Trajectory(shifted[None,:,:],topology).save_pdb(str(b))
    result=compare_structures(a,b,tmp_path/'consensus',hotspot_residue_indices=[2,3],contact_cutoff_A=8.0)
    assert result['version']=='2.0.0'
    assert 'contact_map_jaccard_fraction' in result and 'hotspot_ca_rmsd_A' in result
    assert Path(result['contact_map_csv']).exists()


def test_pde_can_consume_workflow_hotspot_chemistry_profile(tmp_path):
    import importlib.util
    root=Path(__file__).resolve().parents[1]
    profile_path=tmp_path/'hotspot_chemistry_profile_for_PDE.json'
    profile_path.write_text(json.dumps({'chemistry_fractions':{'acidic':0.5,'basic':0.0,'hydrophobic':0.25,'aromatic':0.25,'polar_hbond_capable':0.5}}),encoding='utf-8')
    engine=root/'apps/peptide_design_engine/Python/peptide_engine.py'
    spec=importlib.util.spec_from_file_location('pde_hotspot_profile_test',engine); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    mod.CONFIG['HOTSPOT_COMPLEMENTARITY_MODE']='REPORT_ONLY'
    mod.CONFIG['HOTSPOT_CHEMISTRY_PROFILE_PATH']=str(profile_path)
    mod.CONFIG['_EXTRACTED_HOTSPOTS']=[]
    rep=mod.hotspot_chemistry_complementarity_report(list('KKFW'))
    assert rep['status']=='available'
    assert rep['profile_source']=='workflow_weighted_hotspot_profile'
    assert rep['selection_active'] is False
    assert rep['score'] >= 0.0


def test_desktop_and_colab_pde_engine_parity_after_hotspot_transfer_upgrade():
    root=Path(__file__).resolve().parents[1]
    desktop=(root/'apps/peptide_design_engine/Python/peptide_engine.py').read_bytes()
    colab=(root/'apps/peptide_design_engine/Colab/Ultimate_Peptide_Final_Engine.py').read_bytes()
    assert desktop == colab
