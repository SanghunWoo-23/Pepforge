import json
from datetime import datetime, timezone
import pytest
from suite_gui.v8_decision_support import decision_report, validate_experiment_record, export_experiment_record


def test_decisions_are_explainable_non_prescriptive():
    report = decision_report("Ac-ADGWWWWWW-NH2")
    assert report["review_actions"]
    assert report["chemistry_plan_modified"] is False
    for action in report["review_actions"]:
        assert action["source_class"] == "Rule-based"
        assert action["apply_automatically"] is False
        assert action["selected_coupling_cycles"] is None
        assert action["recommended_loading"] is None
        assert action["recommended_cleavage_time"] is None


def valid():
    return dict(sequence="Ac-ADG-NH2",batch_id="B-001",recorded_at="2026-10-14T00:00:00+00:00",outcome="Pass",analytical_method="HPLC",operator="Researcher",data_reference="labbook://B-001")


def test_evidence_is_unreviewed_by_default_and_deterministic():
    a=validate_experiment_record(valid());b=validate_experiment_record(valid())
    assert a == b
    assert a["evidence_status"] == "Unreviewed"
    assert not a["auto_promoted"]
    assert len(a["record_sha256"]) == 64


def test_requires_review_metadata_and_real_reference():
    row=valid();row.update(reviewer="Reviewer",reviewed_at="2026-10-14T02:00:00+00:00")
    assert validate_experiment_record(row)["evidence_status"]=="Reviewed"
    del row["data_reference"]
    with pytest.raises(ValueError):validate_experiment_record(row)


def test_refuses_missing_bad_fields_and_naive_dates():
    for delta in ({"sequence":""},{"outcome":"unknown"},{"recorded_at":"2026-10-14T09:00:00"},{"batch_id":""}):
        row=valid();row.update(delta)
        with pytest.raises(ValueError):validate_experiment_record(row)


def test_export_refuses_overwrite(tmp_path):
    destination=tmp_path/'record.json'
    export_experiment_record(valid(),destination)
    loaded=json.loads(destination.read_text(encoding='utf-8'))
    assert loaded["source_class"]=="Experimental"
    with pytest.raises(FileExistsError):export_experiment_record(valid(),destination)
