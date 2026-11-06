from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TEXT=(ROOT/'suite_gui/modules/experimental_data_panel.py').read_text(encoding='utf-8')


def test_top_level_navigation_is_compact():
    for label in ['text="Records"','text="Risk & Evidence"','text="Recommended Conditions"','text="Data Health"']:
        assert label in TEXT
    assert 'self.records_notebook' in TEXT
    assert 'self.recommend_notebook' in TEXT


def test_issue_flow_is_natural_language_first_and_details_are_optional():
    assert 'What happened?' in TEXT
    assert 'Kaiser test was positive after Val coupling' in TEXT
    assert 'The resin clumped during coupling.' in TEXT
    assert 'Write one sentence' in TEXT
    assert 'Review details (optional)' in TEXT
    assert 'parse_issue_note' in TEXT
    assert 'Save & Add Another' in TEXT
    assert 'Needs Review (excluded from ML)' in TEXT
    assert 'status="verified" if parsed.get("parse_status") in {"auto_verified","human_reviewed"} else "incomplete"' in TEXT
