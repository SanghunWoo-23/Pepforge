import hashlib
import json
import pytest
from peptiforg_core.v6_target_handoff import prepare_handoff

PDB = ('ATOM      1  N   ALA A   1      11.104  13.207   2.100  1.00 20.00           N\n'
       'ATOM      2  CA  ALA A   1      12.104  13.207   2.100  1.00 20.00           C\n'
       'ATOM      3  C   ALA A   1      13.104  13.207   2.100  1.00 20.00           C\n'
       'ATOM      4  O   ALA A   1      14.104  13.207   2.100  1.00 20.00           O\nTER\nEND\n')

def project(tmp_path):
    (tmp_path/'structures').mkdir()
    files=[]
    for name, data in [('target.fasta','>P12345\nAC\n'),('structures/1ABC.pdb',PDB)]:
        p=tmp_path/name;p.write_text(data)
        content=data.encode()
        files.append({'path':name,'sha256':hashlib.sha256(content).hexdigest(),'bytes':len(content)})
    (tmp_path/'import_manifest.json').write_text(json.dumps({'schema':'pepforge.v6.online_target_import.v1','uniprot_accession':'P12345','files':files,'errors':[]}))
    return tmp_path

def test_handoff_provenance_and_manual_gate(tmp_path):
    root=project(tmp_path)
    record=prepare_handoff(root,'structures/1ABC.pdb','A',root/'handoff.json',reviewer='scientist')
    assert record['status']=='review_required'
    assert record['automatic_docking_authorized'] is False
    assert record['chain_observations']['observed_residues']==1
    assert record['structure_sha256']==hashlib.sha256(PDB.encode()).hexdigest()

def test_reject_wrong_chain(tmp_path):
    root=project(tmp_path)
    with pytest.raises(ValueError,match='chain'):
        prepare_handoff(root,'structures/1ABC.pdb','B',root/'handoff.json')

def test_reject_tamper(tmp_path):
    root=project(tmp_path)
    (root/'structures/1ABC.pdb').write_text('tampered')
    with pytest.raises(ValueError,match='integrity'):
        prepare_handoff(root,'structures/1ABC.pdb','A',root/'handoff.json')

def test_reject_traversal(tmp_path):
    root=project(tmp_path)
    with pytest.raises(ValueError,match='safe relative'):
        prepare_handoff(root,'../outside.pdb','A',root/'handoff.json')

def test_reject_import_error(tmp_path):
    root=project(tmp_path)
    p=root/'import_manifest.json';data=json.loads(p.read_text());data['errors']=[{'pdb_id':'2XYZ','error':'down'}];p.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='Import errors'):
        prepare_handoff(root,'structures/1ABC.pdb','A',root/'handoff.json')
