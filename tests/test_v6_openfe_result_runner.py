import json,hashlib
import pytest
from peptiforg_core.v6_openfe_result_runner import inspect_openfe_result,run,OpenFERunError

def test_missing_entire_cycle(tmp_path):
    p=tmp_path/'leg.json';p.write_text(json.dumps({'estimate':-4,'uncertainty':1}))
    with pytest.raises(OpenFERunError):inspect_openfe_result(p)

def test_unitless_blocked(tmp_path):
    p=tmp_path/'result.json';p.write_text(json.dumps({'estimate':-4,'uncertainty':1,'protocol_result':{'unit_results':1}}))
    with pytest.raises(OpenFERunError):inspect_openfe_result(p)

def test_real_result_preserved_unvalidated(tmp_path):
    p=tmp_path/'result.json';p.write_text(json.dumps({'estimate':{'magnitude':-4,'unit':'kilocalorie/mole'},'uncertainty':{'magnitude':0.5,'unit':'kilocalorie/mole'},'protocol_result':{'unit_results':1}}))
    result=inspect_openfe_result(p)
    assert result['status']=='COMPUTED_NOT_INDEPENDENTLY_VALIDATED'
    assert result['estimate_raw']['magnitude']==-4

def test_no_executable_does_not_make_output(tmp_path):
    p=tmp_path/'transformation.json';p.write_text('{}')
    with pytest.raises(OpenFERunError):run(p,tmp_path/'out',openfe_executable='missing-openfe-executable-39828')
    assert not (tmp_path/'out').exists()

def test_provenance_required(tmp_path,monkeypatch):
    p=tmp_path/'transformation.json';p.write_text('{}')
    monkeypatch.setattr('peptiforg_core.v6_openfe_result_runner.shutil.which',lambda _: '/usr/bin/true')
    with pytest.raises(OpenFERunError,match='manifest'):run(p,tmp_path/'out')
    assert not (tmp_path/'out').exists()

def test_provenance_tamper(tmp_path,monkeypatch):
    p=tmp_path/'transformation.json';p.write_text('{}')
    p.with_suffix('.manifest.json').write_text(json.dumps({'transformation_sha256':'bad'}))
    monkeypatch.setattr('peptiforg_core.v6_openfe_result_runner.shutil.which',lambda _: '/usr/bin/true')
    with pytest.raises(OpenFERunError,match='hash'):run(p,tmp_path/'out')
