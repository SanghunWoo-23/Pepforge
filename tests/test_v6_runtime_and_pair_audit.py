from tools.v6_runtime_capability_probe import probe
from tools.v6_benchmark_pair_audit import audit
import pytest


def make_csv(path, rows):
    path.write_text('case_id,target_id,split,success\n'+''.join(','.join(map(str,r))+'\n' for r in rows),encoding='utf-8')


def test_probe_no_scientific_claim():
    p=probe(check_openmm=False,check_torch=False)
    assert p['scientific_validation']=='NOT_PERFORMED'
    assert not p['ready_for_validated_production_md']


def test_pair_success_and_deltas(tmp_path):
    a,b=tmp_path/'a.csv',tmp_path/'b.csv'
    make_csv(a,[('c1','t1','test',0),('c2','t2','test',1)])
    make_csv(b,[('c1','t1','test',1),('c2','t2','test',1)])
    r=audit(a,b)
    assert r['splits']['test']['delta_success_rate']==0.5
    assert r['splits']['test']['improved']==1


def test_pair_reject_missing(tmp_path):
    a,b=tmp_path/'a.csv',tmp_path/'b.csv'
    make_csv(a,[('c1','t1','test',0)])
    make_csv(b,[('c2','t2','test',1)])
    with pytest.raises(ValueError,match='Unpaired'):
        audit(a,b)


def test_pair_reject_split_leakage(tmp_path):
    a,b=tmp_path/'a.csv',tmp_path/'b.csv'
    rows=[('c1','t1','train',0),('c2','t1','test',1)]
    make_csv(a,rows);make_csv(b,rows)
    with pytest.raises(ValueError,match='span multiple splits'):
        audit(a,b)


def test_pair_reject_duplicate(tmp_path):
    a,b=tmp_path/'a.csv',tmp_path/'b.csv'
    rows=[('c1','t1','test',0),('c1','t1','test',1)]
    make_csv(a,rows);make_csv(b,rows)
    with pytest.raises(ValueError,match='Duplicate'):
        audit(a,b)
