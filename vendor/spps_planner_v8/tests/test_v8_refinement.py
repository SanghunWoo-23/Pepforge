from datetime import datetime, timezone
import json
import pytest
from suite_gui.v8_decision_support import validate_experiment_record, export_experiment_record, verify_experiment_record

def evidence():
    return dict(sequence='Ac-ADG-NH2',batch_id='B-001',recorded_at='2026-10-14T09:00:00+09:00',outcome='Pass',analytical_method='HPLC',operator='Operator',data_reference='labbook:1')

def test_verified_record_roundtrip_and_tampering(tmp_path):
    dest=tmp_path/'evidence.json'
    export_experiment_record(evidence(),dest)
    row=json.loads(dest.read_text(encoding='utf-8'))
    assert verify_experiment_record(row)
    row['outcome']='Fail'
    assert not verify_experiment_record(row)

def test_review_cannot_predate_record():
    row=evidence()
    row.update(reviewer='QA',reviewed_at='2026-10-14T08:59:59+09:00')
    with pytest.raises(ValueError, match='must not precede'):
        validate_experiment_record(row)

def test_input_limits():
    row=evidence();row['observations']='x'*10001
    with pytest.raises(ValueError):validate_experiment_record(row)
    row=evidence();row['sequence']='A'*4097
    with pytest.raises(ValueError):validate_experiment_record(row)

def test_verification_rejects_invalid_object():
    assert not verify_experiment_record({})
    assert not verify_experiment_record({'record_sha256':'bad'})
