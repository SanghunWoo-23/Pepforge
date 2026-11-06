from pathlib import Path

from suite_gui import experimental_data
from suite_gui.decision_support_v5 import stage_risk_advisor
from suite_gui.natural_language_issue_v5 import parse_issue_note


def test_korean_english_mixed_note_is_structured():
    parsed=parse_issue_note('18번 Val coupling 후 Kaiser 양성이라 한 번 더 coupling했고 이후 음성이었다.')
    assert parsed['stage']=='Coupling'
    assert parsed['issue_type']=='Abnormal Kaiser / chloranil'
    assert parsed['action_taken']=='Repeat coupling'
    assert parsed['resolution']=='Resolved'
    assert parsed['position']==18
    assert parsed['residue']=='V'
    assert parsed['detected_language']=='mixed'
    assert parsed['parse_status']=='auto_verified'
    assert parsed['confidence'] >= 0.75


def test_english_note_is_structured_without_language_setting():
    parsed=parse_issue_note('Kaiser was positive after Val coupling, so I repeated the coupling and it was fine.')
    assert parsed['issue_type']=='Abnormal Kaiser / chloranil'
    assert parsed['action_taken']=='Repeat coupling'
    assert parsed['resolution']=='Resolved'
    assert parsed['detected_language']=='en'
    assert parsed['parse_status']=='auto_verified'


def test_ambiguous_note_is_kept_out_of_ml():
    parsed=parse_issue_note('뭔가 이상했다')
    assert parsed['issue_type']=='Other'
    assert parsed['parse_status']=='needs_review'
    assert parsed['confidence'] < 0.75


def test_parser_metadata_roundtrip_and_only_verified_issue_enters_risk(tmp_path: Path):
    db=tmp_path/'nl.sqlite'
    experimental_data.initialize(db)
    good=parse_issue_note('Cleavage 후 ether를 넣었는데 침전이 잘 안 됐다.')
    experimental_data.add_issue({
        'stage':good['stage'],'product':'P1','sequence':'ACDE','issue_type':good['issue_type'],
        'severity':good['severity'],'observation':'Cleavage 후 ether를 넣었는데 침전이 잘 안 됐다.',
        'action_taken':good['action_taken'],'resolution':good['resolution'],
        'parse_confidence':good['confidence'],'parse_status':good['parse_status'],
        'parser_version':good['parser_version'],'detected_language':good['detected_language'],
    },db,status='verified')
    bad=parse_issue_note('뭔가 이상했다')
    experimental_data.add_issue({
        'stage':bad['stage'],'product':'P1','sequence':'ACDE','issue_type':bad['issue_type'],
        'severity':bad['severity'],'observation':'뭔가 이상했다','parse_confidence':bad['confidence'],
        'parse_status':bad['parse_status'],'parser_version':bad['parser_version'],'detected_language':bad['detected_language'],
    },db,status='incomplete')
    rows=experimental_data.list_records('issue',db)
    assert len(rows)==2
    assert any(r['parse_status']=='auto_verified' for r in rows)
    risk=stage_risk_advisor(sequence='ACDE',product='P1',resin='Rink Amide',db_path=db)
    assert len(risk['issues'])==1
    assert risk['issues'][0]['issue_type']=='Precipitation failure / partial precipitation'


def test_english_resin_clumping_preset_resolves_cleanly():
    parsed=parse_issue_note('The resin clumped during coupling. I added a little more DMF and manually dispersed it; the resin returned to normal.')
    assert parsed['stage']=='Coupling'
    assert parsed['issue_type']=='Aggregation / resin clumping'
    assert parsed['action_taken']=='Manual intervention'
    assert parsed['resolution']=='Resolved'
    assert parsed['detected_language']=='en'
