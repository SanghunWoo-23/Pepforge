import json
import pytest
from peptiforg_core.v6_abfe_release_gate import audit_result
from peptiforg_core.v6_openfe_result_runner import OpenFERunError

def sample(tmp_path,estimate=-4,uncertainty=.4):
 p=tmp_path/'result.json'
 p.write_text(json.dumps({'estimate':{'magnitude':estimate,'unit':'kcal/mol'},'uncertainty':{'magnitude':uncertainty,'unit':'kcal/mol'},'protocol_result':{'n_protocol_dag_results':3}}))
 return p

def test_valid_result_never_certified(tmp_path):
 r=audit_result(sample(tmp_path))
 assert r['status']=='REVIEW_REQUIRED' and not r['scientific_accuracy_certified']

def test_reject_nan(tmp_path):
 with pytest.raises(OpenFERunError):audit_result(sample(tmp_path,estimate=float('nan')))

def test_reject_negative_uncertainty(tmp_path):
 with pytest.raises(OpenFERunError):audit_result(sample(tmp_path,uncertainty=-1))

def test_missing_repeats_flagged(tmp_path):
 p=sample(tmp_path)
 d=json.loads(p.read_text());d['protocol_result'].pop('n_protocol_dag_results');d['protocol_result']['units_present']=True;p.write_text(json.dumps(d))
 assert any('repeat' in x.lower() for x in audit_result(p)['review_findings'])
