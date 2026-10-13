from pathlib import Path
import csv, json

from peptiforg_core.public_peptide_benchmark_v1 import PUBLIC_57_CASES, PublicBenchmarkCase, write_public_registry, sync_public_case
from peptiforg_core.native_docking_v1 import NativeDockingConfig
from peptiforg_core.native_docking_tuning_v1 import tune_native_docking


def _pdb_line(serial, atom, resn, chain, resi, x,y,z, elem):
    return f"ATOM  {serial:5d} {atom:>4s} {resn:>3s} {chain:1s}{resi:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00 20.00          {elem:>2s}"


def test_public_registry_has_57_cases(tmp_path):
    assert len(PUBLIC_57_CASES) == 57
    out=tmp_path/'registry.csv'; write_public_registry(out)
    rows=list(csv.DictReader(out.open(encoding='utf-8-sig')))
    assert len(rows)==57
    assert {'train','holdout'} <= {r['split'] for r in rows}
    assert any(r['bound_pdb']=='1SSH' for r in rows)


def test_sync_preexisting_public_case_normalizes_chains(tmp_path):
    case=PublicBenchmarkCase(2,'TST1','R','L','TST2','U')
    raw=tmp_path/'TST1'/'raw'; raw.mkdir(parents=True)
    lines=[
        _pdb_line(1,'N','ALA','R',1,0,0,0,'N'), _pdb_line(2,'CA','ALA','R',1,1,0,0,'C'), _pdb_line(3,'C','ALA','R',1,2,0,0,'C'),
        _pdb_line(4,'N','GLY','L',1,0,4,0,'N'), _pdb_line(5,'CA','GLY','L',1,1,4,0,'C'), _pdb_line(6,'C','GLY','L',1,2,4,0,'C'),
        _pdb_line(7,'N','ALA','L',2,3,4,0,'N'), _pdb_line(8,'CA','ALA','L',2,4,4,0,'C'), _pdb_line(9,'C','ALA','L',2,5,4,0,'C'), 'END']
    (raw/'TST1.pdb').write_text('\n'.join(lines)+'\n')
    payload=sync_public_case(case,tmp_path,include_unbound=False,include_uniprot=False)
    assert payload['observed_peptide_length']==2
    ref=Path(payload['reference_pdb']).read_text()
    assert ' A   1' in ref and ' P   1' in ref
    assert payload['normalized_chains']=={'receptor':'A','peptide':'P'}


def test_native_docking_config_exposes_tunable_weights():
    cfg=NativeDockingConfig(clash_penalty=31.0,smooth_contact_weight=0.11,interaction_score_scale=1.4)
    assert cfg.clash_penalty==31.0 and cfg.smooth_contact_weight==0.11 and cfg.interaction_score_scale==1.4


def test_tuner_requires_real_prepared_train_targets(tmp_path):
    reg=tmp_path/'r.csv'
    reg.write_text('target_id,split\n1ABC,train\n',encoding='utf-8')
    try:
        tune_native_docking(reg,tmp_path/'prepared',tmp_path/'out')
    except ValueError as exc:
        assert 'prepared train targets' in str(exc)
    else:
        raise AssertionError('tuner should refuse absent benchmark structures')
