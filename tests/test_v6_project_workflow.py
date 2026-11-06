import json
import pytest
from peptiforg_core.v6_target_handoff import prepare_handoff
from peptiforg_core.v6_project_workflow import generate_project_workflow, verify_project_workflow
from test_v6_target_handoff import project

def test_workflow_handoff_and_provenance(tmp_path):
    root = project(tmp_path)
    prepare_handoff(root,'structures/1ABC.pdb','A',root/'handoff.json')
    result = generate_project_workflow(root,root/'handoff.json',root/'workflow')
    assert result['selected_chain_sequence_length'] == 1
    assert 'A\n' in (root/'workflow'/'selected_chain.fasta').read_text()
    assert result['automatic_docking_authorized'] is False
    assert all(step['status']=='not_executed' for step in result['pipeline'].values())
    assert verify_project_workflow(root/'workflow'/'workflow_manifest.json')['verified']

def test_workflow_detects_tampered_input(tmp_path):
    root=project(tmp_path)
    prepare_handoff(root,'structures/1ABC.pdb','A',root/'handoff.json')
    generate_project_workflow(root,root/'handoff.json',root/'workflow')
    (root/'target.fasta').write_text('>changed\nZZ\n')
    assert not verify_project_workflow(root/'workflow'/'workflow_manifest.json')['verified']
    with pytest.raises(ValueError,match='SHA-256'):
        generate_project_workflow(root,root/'handoff.json',root/'new_workflow')

def test_workflow_rejects_permission_forgery(tmp_path):
    root=project(tmp_path)
    prepare_handoff(root,'structures/1ABC.pdb','A',root/'handoff.json')
    handoff=json.loads((root/'handoff.json').read_text())
    handoff['automatic_docking_authorized']=True
    (root/'handoff.json').write_text(json.dumps(handoff))
    with pytest.raises(ValueError,match='permission'):
        generate_project_workflow(root,root/'handoff.json',root/'workflow')


def test_workflow_rejects_forged_execution(tmp_path):
    root=project(tmp_path)
    prepare_handoff(root,'structures/1ABC.pdb','A',root/'handoff.json')
    generate_project_workflow(root,root/'handoff.json',root/'workflow')
    manifest=root/'workflow'/'workflow_manifest.json'
    data=json.loads(manifest.read_text())
    data['pipeline']['docking']['status']='completed'
    data['automatic_docking_authorized']=True
    manifest.write_text(json.dumps(data))
    audit=verify_project_workflow(manifest)
    assert not audit['verified']
    assert not audit['stage_contract_verified']
    assert audit['automatic_docking_authorized'] is False


def test_workflow_rejects_missing_input_entry(tmp_path):
    root=project(tmp_path)
    prepare_handoff(root,'structures/1ABC.pdb','A',root/'handoff.json')
    generate_project_workflow(root,root/'handoff.json',root/'workflow')
    manifest=root/'workflow'/'workflow_manifest.json'
    data=json.loads(manifest.read_text())
    del data['inputs']['coordinate_file']
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='workflow inputs'):
        verify_project_workflow(manifest)
