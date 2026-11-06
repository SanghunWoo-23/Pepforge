import csv
import pytest
from peptiforg_core.v6_ranker_validation import evaluate_ranker

FIELDS=['candidate_id','family_id','split','label','prediction','ood']

def run(tmp_path,rows,**kwargs):
    p=tmp_path/'input.csv'
    with p.open('w',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=FIELDS);writer.writeheader();writer.writerows(rows)
    return evaluate_ranker(p,tmp_path/'result.json',**kwargs)

def data():
    return [dict(candidate_id=str(i),family_id='f'+str(i//2),split='test',label=str(i%2),prediction=str(0.1 if i%2==0 else 0.9),ood=str(int(i%3==0))) for i in range(24)]

def test_perfect_ranker(tmp_path):
    result=run(tmp_path,data())
    assert result['test_metrics']['auroc']==1.0
    assert abs(result['test_metrics']['brier']-0.01)<1e-9
    assert result['safeguards']['minimum_test_families_met']

def test_family_leakage(tmp_path):
    rows=data();rows[0]['split']='train'
    with pytest.raises(ValueError,match='leakage'):run(tmp_path,rows)

def test_duplicate_candidate(tmp_path):
    rows=data();rows[1]['candidate_id']=rows[0]['candidate_id']
    with pytest.raises(ValueError,match='duplicate'):run(tmp_path,rows)

def test_bad_prediction(tmp_path):
    rows=data();rows[0]['prediction']='nan'
    with pytest.raises(ValueError,match='finite'):run(tmp_path,rows)

def test_small_sample_exploratory(tmp_path):
    result=run(tmp_path,data()[:4],strict=False)
    assert not result['safeguards']['minimum_test_rows_met']

def test_small_sample_strict(tmp_path):
    with pytest.raises(ValueError,match='safeguards'):run(tmp_path,data()[:4])

def test_single_class_undefined_auc(tmp_path):
    rows=data()
    for r in rows:r['label']='1'
    result=run(tmp_path,rows,strict=False)
    assert result['test_metrics']['auroc'] is None
