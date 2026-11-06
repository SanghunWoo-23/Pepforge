from pathlib import Path

from suite_gui import experimental_data
from suite_gui.decision_support_v5 import stage_risk_advisor


def test_issue_record_roundtrip_and_case_insensitive_sequence(tmp_path: Path):
    db=tmp_path/"issue.sqlite"
    experimental_data.initialize(db)
    row=experimental_data.add_issue({
        "stage":"Coupling","product":"Issue-Pep","sequence":"Ac-EEMQRR-NH2","scale_mmol":0.2,
        "position":4,"residue":"Q","issue_type":"Incomplete coupling","severity":"High",
        "observation":"Kaiser positive after first coupling","action_taken":"Repeat coupling","resolution":"Resolved",
    },db,status="verified")
    assert row["issue_type"]=="Incomplete coupling"
    rows=experimental_data.list_records("issue",db,statuses=["verified"])
    assert len(rows)==1
    risk=stage_risk_advisor(sequence="ac-eemqrr-nh2",product="issue-pep",resin="Rink Amide",db_path=db)
    coupling=next(x for x in risk["stages"] if x["stage"]=="Coupling")
    assert coupling["evidence_count"] >= 1
    assert any("historical synthesis issue" in r.lower() for r in coupling["reasons"])
    assert len(risk["issues"])==1


def test_issue_does_not_modify_conditions(tmp_path: Path):
    db=tmp_path/"issue.sqlite"
    experimental_data.initialize(db)
    experimental_data.add_issue({
        "stage":"Cleavage","product":"X","sequence":"ACDE","issue_type":"Precipitation failure / partial precipitation",
        "severity":"Medium","observation":"partial precipitation","action_taken":"Additional wash","resolution":"Improved",
    },db,status="verified")
    risk=stage_risk_advisor(sequence="acde",product="x",resin="Rink Amide",db_path=db)
    assert risk["apply_allowed"] is False
    assert all(stage["apply_allowed"] is False for stage in risk["stages"])


def test_issue_keeps_automatic_planner_snapshot_for_future_review(tmp_path: Path):
    import json
    db=tmp_path/'issue.sqlite'; experimental_data.initialize(db)
    snapshot={'loading':{'aa_eq':'0.4'},'coupling':{'aa_eq':'2'},'cleavage':{'cleavage_eq':30}}
    row=experimental_data.add_issue({
        'stage':'Coupling','product':'P','sequence':'AAAA','issue_type':'Incomplete coupling',
        'observation':'Kaiser positive','planner_snapshot_json':json.dumps(snapshot),
    },db,status='verified')
    assert json.loads(row['planner_snapshot_json'])==snapshot
