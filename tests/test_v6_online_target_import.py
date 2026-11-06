import hashlib
import json
import pytest
from peptiforg_core import v6_online_target_import as m

def sample():
    return {'accession':'P12345','sequence':'ACDEFGHIK','protein_name':'Test','organism':'Example', 'pdb_cross_references':['1ABC','2XYZ']}

def test_offline_no_structure(tmp_path):
    p=tmp_path/'raw.json'; p.write_text(json.dumps({'primaryAccession':'P12345','sequence':{'value':'ACDEFGHIK'},'uniProtKBCrossReferences':[{'database':'PDB','id':'1ABC'}]}))
    res=m.import_uniprot_target('P12345',tmp_path/'out',offline_json=p,download_structures=False)
    assert len(res['files'])==2
    for x in res['files']:
        assert hashlib.sha256((tmp_path/'out'/x['path']).read_bytes()).hexdigest()==x['sha256']

def test_download_mock(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'get_uniprot_entry',lambda *a,**kw:sample())
    monkeypatch.setattr(m,'_structure_bytes',lambda *a,**kw:b'data_test\n')
    res=m.import_uniprot_target('P12345',tmp_path,pdb_limit=1)
    assert (tmp_path/'structures/1ABC.cif').exists()
    assert len(res['files'])==3

def test_download_failure_is_recorded(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'get_uniprot_entry',lambda *a,**kw:sample())
    def fail(*a,**kw): raise OSError('offline')
    monkeypatch.setattr(m,'_structure_bytes',fail)
    res=m.import_uniprot_target('P12345',tmp_path,pdb_limit=1)
    assert len(res['errors'])==1 and len(res['files'])==2

def test_invalid_accession(tmp_path):
    with pytest.raises(ValueError): m.import_uniprot_target('../bad',tmp_path)

def test_limit(tmp_path):
    with pytest.raises(ValueError): m.import_uniprot_target('P12345',tmp_path,pdb_limit=21)
