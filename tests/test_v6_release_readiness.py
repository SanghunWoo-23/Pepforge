import json
from peptiforg_core.v6_release_readiness import collect_readiness, main

def test_never_claims_unverified_science():
    r=collect_readiness()
    for key in ('gaff_openff_modified_complex_md','arbitrary_sequence_structure_prediction_without_model',
                'pymol_arbitrary_length_sequence_tokens','windows_exe_installed_test'):
        assert r['capabilities'][key]['ready'] is False

def test_device_and_dependency_schemas():
    r=collect_readiness()
    assert r['devices']['cpu']=='available'
    assert isinstance(r['devices']['openmm_platforms'],list)
    assert isinstance(r['dependencies']['rdkit'],bool)

def test_cli_report(tmp_path):
    path=tmp_path/'ready.json'
    assert main(['--output',str(path)])==0
    assert json.loads(path.read_text(encoding='utf-8'))['schema']=='pepforge.v6.runtime_readiness.v1'
