import csv
import pytest
from peptiforg_core.v6_probability_calibration import calibrate_predictions


def dataset(tmp_path, leak=False):
    p=tmp_path/'scores.csv'
    with p.open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['candidate_id','family_id','split','label','prediction','ood'])
        for i in range(30):w.writerow([f'v{i}',f'v{i//5}','validation',i%2,.15 if i%2==0 else .85,0])
        for i in range(20):w.writerow([f't{i}','v0' if leak and i==0 else f't{i//5}','test',i%2,.25 if i%2==0 else .75,0])
    return p


def test_calibration_and_held_out(tmp_path):
    p=dataset(tmp_path)
    result=calibrate_predictions(p,tmp_path/'report.json',tmp_path/'test.csv')
    assert result['trained_on']=='validation only'
    assert result['test_rows']==20
    with (tmp_path/'test.csv').open() as f:assert len(list(csv.DictReader(f)))==20


def test_split_leakage_rejected(tmp_path):
    p=dataset(tmp_path,True)
    with pytest.raises(ValueError,match='leakage'):
        calibrate_predictions(p,tmp_path/'report.json',tmp_path/'test.csv')


def test_no_overwrite(tmp_path):
    p=dataset(tmp_path)
    with pytest.raises(ValueError,match='overwrite'):
        calibrate_predictions(p,p,tmp_path/'test.csv')
