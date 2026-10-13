from pathlib import Path
import json

from peptiforg_core.public_peptide_benchmark_v1 import PublicBenchmarkCase, sync_public_case
from peptiforg_core.v5_final_release_v1 import V5_FINAL_VERSION, _registry_summary


def _pdb_line(serial, atom, resn, chain, resi, x):
    return f"ATOM  {serial:5d} {atom:^4s} {resn:>3s} {chain:1s}{resi:4d}    {x:8.3f}{0.0:8.3f}{0.0:8.3f}  1.00 20.00           C\n"


def test_public_benchmark_offline_cache(tmp_path):
    cache=tmp_path/'cache'; cache.mkdir()
    bound=cache/'9ZZZ.pdb'
    text='HEADER TEST\n'
    serial=1
    for chain,resn,n in [('R','ALA',3),('Q','GLY',2)]:
        for i in range(1,n+1):
            text += _pdb_line(serial,'CA',resn,chain,i,float(i)); serial+=1
    bound.write_text(text+'END\n',encoding='utf-8')
    unbound=cache/'8YYY.pdb'
    text='HEADER TEST\n'
    for i in range(1,4):
        text += _pdb_line(i,'CA','ALA','U',i,float(i))
    unbound.write_text(text+'END\n',encoding='utf-8')
    case=PublicBenchmarkCase(2,'9ZZZ','R','Q','8YYY','U')
    payload=sync_public_case(case,tmp_path/'out',include_uniprot=False,local_cache=cache,allow_network=False)
    assert payload['coordinate_retrieval']['bound']=='local_cache'
    assert payload['coordinate_retrieval']['unbound']=='local_cache'
    assert Path(payload['reference_pdb']).is_file()
    assert payload['observed_peptide_length']==2


def test_final_registry_contract():
    root=Path(__file__).resolve().parents[1]
    reg=_registry_summary(root)
    assert V5_FINAL_VERSION=='5.0.0'
    assert reg['status']=='PASS'
    assert reg['count']==57
    assert reg['unique_target_ids']==57
