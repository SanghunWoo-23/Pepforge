import hashlib
import json
import pytest
from peptiforg_core.v6_target_readiness import inspect_target_project

PDB = ("ATOM      1  N   ALA A   1      11.104  13.207   2.100  1.00 20.00           N\n"
       "ATOM      2  CA  ALA A   1      12.104  13.207   2.100  1.00 20.00           C\n"
       "ATOM      3  C   ALA A   1      13.104  13.207   2.100  1.00 20.00           C\n"
       "ATOM      4  O   ALA A   1      14.104  13.207   2.100  1.00 20.00           O\nTER\nEND\n")

def project(tmp_path):
    (tmp_path/'structures').mkdir()
    files=[]
    for name, data in [('target.fasta','>X\nAC\n'),('structures/1ABC.pdb',PDB)]:
        p=tmp_path/name;p.write_text(data)
        files.append({'path':name,'sha256':hashlib.sha256(data.encode()).hexdigest(),'bytes':len(data.encode())})
    manifest={'schema':'pepforge.v6.online_target_import.v1','uniprot_accession':'P12345','files':files,'errors':[]}
    (tmp_path/'import_manifest.json').write_text(json.dumps(manifest))
    return tmp_path

def test_valid_structure_and_alignment(tmp_path):
    p=project(tmp_path)
    result=inspect_target_project(p,output_json=p/'readiness.json')
    chain=result['structures'][0]['chains'][0]
    assert chain['chain_id']=='A' and chain['reference_coverage']==0.5
    assert chain['aligned_identity']==1.0
    assert chain['backbone_incomplete_residues']==0
    assert result['ready_for_automatic_docking'] is False
    assert (p/'readiness.json').exists()

def test_tamper_detected(tmp_path):
    p=project(tmp_path)
    (p/'structures/1ABC.pdb').write_text('altered')
    result=inspect_target_project(p)
    assert result['structures'][0]['sha256_verified'] is False
    assert not result['structures'][0]['chains']

def test_manifest_path_escape(tmp_path):
    p=project(tmp_path)
    manifest=json.loads((p/'import_manifest.json').read_text())
    manifest['files'][0]['path']='../outside'
    (p/'import_manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='Unsafe'):
        inspect_target_project(p)

def test_missing_manifest(tmp_path):
    with pytest.raises(FileNotFoundError):
        inspect_target_project(tmp_path)
