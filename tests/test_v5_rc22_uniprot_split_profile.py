from pathlib import Path
import json

from peptiforg_core.uniprot_bridge_v1 import normalize_uniprot_accession
from peptiforg_core.public_benchmark_leakage_v1 import audit_public_benchmark_split


def _pdb(chain='A', resn='ALA', n=3):
    lines=[]
    serial=1
    for i in range(1,n+1):
        lines.append(f"ATOM  {serial:5d}  CA  {resn:>3s} {chain}{i:4d}    {i*3.0:8.3f}{0.0:8.3f}{0.0:8.3f}  1.00 20.00           C")
        serial+=1
    return '\n'.join(lines)+'\nEND\n'


def test_uniprot_accession_normalization():
    assert normalize_uniprot_accession('p43603') == 'P43603'
    assert normalize_uniprot_accession('not accession') == ''


def test_split_audit_detects_exact_sequence_leakage(tmp_path):
    reg=tmp_path/'registry.csv'
    reg.write_text('target_id,split\nT001,train\nT002,holdout\n',encoding='utf-8')
    for tid in ('T001','T002'):
        d=tmp_path/'prepared'/tid/'prepared'; d.mkdir(parents=True)
        (d/'receptor_bound_A.pdb').write_text(_pdb(),encoding='utf-8')
    out=audit_public_benchmark_split(reg,tmp_path/'prepared',tmp_path/'audit')
    assert out['status']=='FAIL'
    assert out['exact_receptor_sequence_cross_split_overlap']
    assert out['sequence_identity_threshold_independence']=='NOT_EVALUATED'


def test_public_registry_contains_source_provenance(tmp_path):
    from peptiforg_core.public_peptide_benchmark_v1 import write_public_registry
    p=Path(write_public_registry(tmp_path/'r.csv'))
    text=p.read_text(encoding='utf-8-sig')
    assert '10.1021/acs.jcim.0c00372' in text
    assert 'RCSB PDB' in text and 'UniProtKB' in text
